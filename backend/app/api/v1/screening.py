import os
import json
import uuid
import shutil
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Optional, List
from app.db.session import get_db
from app.core.config import settings
from app.models.user import User
from app.models.patient import Patient
from app.models.session import ScreeningSession
from app.models.phq9 import PHQ9Assessment
from app.models.modality_result import ModalityResult
from app.models.fusion_result import FusionResult
from app.models.audit_log import AuditLog
from app.models.analysis_draft import AnalysisDraft
from app.schemas.patient import SessionInitRequest
from app.schemas.phq9 import PHQ9SubmitRequest
from app.schemas.draft import DraftSaveRequest
from app.api.deps import get_current_user
from app.ml.text_pipeline import text_pipeline
from app.ml.voice_pipeline import voice_pipeline
from app.ml.face_pipeline import face_pipeline
from app.ml.fusion_engine import perform_multimodal_late_fusion
from app.services.pdf_service import generate_screening_pdf_report

router = APIRouter(prefix="/screening", tags=["Screening Stepper Flow"])

def calculate_age(dob: Optional[date]) -> Optional[int]:
    if not dob:
        return None
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

def calculate_duration_str(onset_date: Optional[date]) -> str:
    if not onset_date:
        return "Not specified"
    days = (date.today() - onset_date).days
    if days < 0:
        return "Just started"
    if days < 7:
        return f"{days} day{'s' if days != 1 else ''}"
    weeks = days // 7
    rem_days = days % 7
    if weeks < 4:
        return f"{weeks} week{'s' if weeks != 1 else ''}" + (f", {rem_days} day{'s' if rem_days != 1 else ''}" if rem_days > 0 else "")
    months = days // 30
    rem_weeks = (days % 30) // 7
    return f"{months} month{'s' if months != 1 else ''}" + (f", {rem_weeks} week{'s' if rem_weeks != 1 else ''}" if rem_weeks > 0 else "")

@router.post("/draft")
def save_screening_draft(
    payload: DraftSaveRequest,
    current_user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Autosaves draft after each completed step (patient info, PHQ-9, text, voice, face).
    Raw audio and photos are NEVER saved in a draft unless the user opted in.
    """
    user_key = (current_user.id if current_user else None) or payload.user_id or "anonymous"
    clean_data = dict(payload.draft_data)
    
    # Enforce privacy constraint: strip raw media unless explicitly opted in
    if not payload.opt_in_store_audio:
        for k in ["audio_blob", "audio_base64", "audio_path", "voice_blob", "voice_base64", "voice_path"]:
            clean_data.pop(k, None)
    if not payload.opt_in_store_face:
        for k in ["face_blob", "face_base64", "photo_blob", "photo_base64", "image_base64", "photo_path", "image_path"]:
            clean_data.pop(k, None)

    draft = db.query(AnalysisDraft).filter(AnalysisDraft.user_id == user_key).first()
    if draft:
        draft.step = payload.step
        draft.draft_data = json.dumps(clean_data)
        draft.has_audio = bool(payload.opt_in_store_audio and ("audio_path" in clean_data or "audio_base64" in clean_data))
        draft.has_photo = bool(payload.opt_in_store_face and ("photo_path" in clean_data or "face_base64" in clean_data))
        draft.updated_at = datetime.utcnow()
    else:
        draft = AnalysisDraft(
            id=str(uuid.uuid4()),
            user_id=user_key,
            step=payload.step,
            draft_data=json.dumps(clean_data),
            has_audio=bool(payload.opt_in_store_audio and ("audio_path" in clean_data or "audio_base64" in clean_data)),
            has_photo=bool(payload.opt_in_store_face and ("photo_path" in clean_data or "face_base64" in clean_data)),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(draft)
    db.commit()
    return {
        "success": True,
        "status": "saved",
        "step": draft.step,
        "updated_at": draft.updated_at.isoformat()
    }

@router.get("/draft")
def get_screening_draft(
    user_id: Optional[str] = None,
    current_user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieves the user's active draft if one exists.
    """
    user_key = (current_user.id if current_user else None) or user_id or "anonymous"
    draft = db.query(AnalysisDraft).filter(AnalysisDraft.user_id == user_key).first()
    if not draft:
        return {"has_draft": False, "exists": False}
    try:
        data = json.loads(draft.draft_data)
    except Exception:
        data = {}
    return {
        "has_draft": True,
        "exists": True,
        "step": draft.step,
        "draft_data": data,
        "updated_at": draft.updated_at.isoformat()
    }

@router.delete("/draft")
def delete_screening_draft(
    user_id: Optional[str] = None,
    current_user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Deletes the draft after analysis completion or on explicit Start Over.
    """
    user_key = (current_user.id if current_user else None) or user_id or "anonymous"
    db.query(AnalysisDraft).filter(AnalysisDraft.user_id == user_key).delete()
    db.commit()
    return {"success": True, "message": "Draft deleted."}

@router.post("/init")
def initialize_screening_session(
    payload: SessionInitRequest,
    current_user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Initializes a screening session. Calculates age automatically.
    Calculates symptom duration automatically.
    Flags immediate safety alert if 'thoughts of self-harm' is selected.
    """
    # 1. Resolve Patient
    patient = None
    if payload.patient:
        if payload.patient.date_of_birth > date.today():
            raise HTTPException(status_code=400, detail="Date of birth cannot be in the future.")
        patient = Patient(
            id=str(uuid.uuid4()),
            user_id=current_user.id if current_user else None,
            full_name=payload.patient.full_name,
            date_of_birth=payload.patient.date_of_birth,
            gender=payload.patient.gender,
            occupation=payload.patient.occupation,
            emergency_contact_name=payload.patient.emergency_contact_name,
            emergency_contact_phone=payload.patient.emergency_contact_phone
        )
        db.add(patient)
        db.commit()
        db.refresh(patient)
    elif payload.patient_id:
        patient = db.query(Patient).filter(Patient.id == payload.patient_id).first()
        if not patient:
            raise HTTPException(status_code=404, detail="Patient profile not found.")

    if not patient:
        # Default anonymous patient placeholder
        patient = Patient(
            id=str(uuid.uuid4()),
            user_id=current_user.id if current_user else None,
            full_name="Guest Patient",
            date_of_birth=date(1995, 1, 1),
            gender="Prefer not to say"
        )
        db.add(patient)
        db.commit()
        db.refresh(patient)

    # 2. Check for self-harm symptom
    has_self_harm = any(
        "harm" in s.lower() or "suicid" in s.lower() for s in payload.symptoms
    )
    duration_text = calculate_duration_str(payload.symptoms_onset_date)
    age = calculate_age(patient.date_of_birth)

    session = ScreeningSession(
        id=str(uuid.uuid4()),
        patient_id=patient.id,
        user_id=current_user.id if current_user else None,
        status="in_progress",
        consent_given=payload.consent_given,
        consent_timestamp=datetime.utcnow() if payload.consent_given else None,
        store_media_opt_in=payload.store_media_opt_in,
        symptoms_json=json.dumps(payload.symptoms),
        symptoms_onset_date=payload.symptoms_onset_date,
        symptom_duration_text=duration_text,
        has_self_harm_risk=has_self_harm
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    return {
        "session_id": session.id,
        "patient": {
            "id": patient.id,
            "full_name": patient.full_name,
            "date_of_birth": patient.date_of_birth.isoformat(),
            "age": age,
            "gender": patient.gender,
            "occupation": patient.occupation
        },
        "symptoms": payload.symptoms,
        "symptom_duration": duration_text,
        "has_self_harm_risk": has_self_harm,
        "consent_recorded": session.consent_given
    }

@router.post("/phq9")
def submit_phq9_assessment(payload: PHQ9SubmitRequest, db: Session = Depends(get_db)):
    session = db.query(ScreeningSession).filter(ScreeningSession.id == payload.session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Screening session not found.")

    total = sum([
        payload.q1, payload.q2, payload.q3, payload.q4,
        payload.q5, payload.q6, payload.q7, payload.q8, payload.q9
    ])

    if total <= 4:
        severity = "Minimal"
        interp = "Minimal or no depressive symptoms reported."
    elif total <= 9:
        severity = "Mild"
        interp = "Mild depressive symptoms. Active monitoring recommended."
    elif total <= 14:
        severity = "Moderate"
        interp = "Moderate depressive symptoms. Clinical evaluation advised."
    elif total <= 19:
        severity = "Moderately Severe"
        interp = "Moderately severe symptoms. Active clinical treatment strongly warranted."
    else:
        severity = "Severe"
        interp = "Severe symptoms. Immediate clinical and psychiatric intervention needed."

    has_self_harm = payload.q9 > 0
    if has_self_harm:
        session.has_self_harm_risk = True
        db.commit()

    # Create or update PHQ9 assessment
    phq = db.query(PHQ9Assessment).filter(PHQ9Assessment.session_id == payload.session_id).first()
    if not phq:
        phq = PHQ9Assessment(
            id=str(uuid.uuid4()),
            session_id=payload.session_id,
            q1_interest=payload.q1,
            q2_depressed=payload.q2,
            q3_sleep=payload.q3,
            q4_tired=payload.q4,
            q5_appetite=payload.q5,
            q6_failure=payload.q6,
            q7_concentrating=payload.q7,
            q8_slow_restless=payload.q8,
            q9_self_harm=payload.q9,
            total_score=total,
            severity_category=severity
        )
        db.add(phq)
    else:
        phq.q1_interest = payload.q1
        phq.q2_depressed = payload.q2
        phq.q3_sleep = payload.q3
        phq.q4_tired = payload.q4
        phq.q5_appetite = payload.q5
        phq.q6_failure = payload.q6
        phq.q7_concentrating = payload.q7
        phq.q8_slow_restless = payload.q8
        phq.q9_self_harm = payload.q9
        phq.total_score = total
        phq.severity_category = severity

    db.commit()
    db.refresh(phq)

    return {
        "id": phq.id,
        "session_id": payload.session_id,
        "total_score": total,
        "severity_category": severity,
        "has_self_harm_risk": has_self_harm,
        "interpretation": interp
    }

@router.post("/analyze-text")
def analyze_text_step(
    session_id: str = Form(...),
    text: str = Form(...),
    db: Session = Depends(get_db)
):
    session = db.query(ScreeningSession).filter(ScreeningSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    if len(text.strip()) < 10:
        raise HTTPException(status_code=400, detail="Please enter at least a few sentences (minimum 15 words) describing your recent days.")

    result = text_pipeline.analyze(text)

    # Save Modality Result
    mod_res = db.query(ModalityResult).filter(
        ModalityResult.session_id == session_id,
        ModalityResult.modality_type == "text"
    ).first()
    
    if not mod_res:
        mod_res = ModalityResult(
            id=str(uuid.uuid4()),
            session_id=session_id,
            modality_type="text",
            skipped=False,
            depression_probability=result["depression_probability"],
            confidence_score=result["confidence_score"],
            details_json=json.dumps(result)
        )
        db.add(mod_res)
    else:
        mod_res.skipped = False
        mod_res.depression_probability = result["depression_probability"]
        mod_res.confidence_score = result["confidence_score"]
        mod_res.details_json = json.dumps(result)

    db.commit()
    return {"session_id": session_id, **result}

@router.post("/analyze-voice")
async def analyze_voice_step(
    session_id: str = Form(...),
    audio: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    session = db.query(ScreeningSession).filter(ScreeningSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    # Save to disk temporarily
    ext = os.path.splitext(audio.filename or "")[1] or ".webm"
    temp_raw = os.path.join(settings.UPLOAD_DIR, f"voice_raw_{session_id}_{uuid.uuid4().hex[:6]}{ext}")
    temp_16k = os.path.join(settings.UPLOAD_DIR, f"voice_16k_{session_id}_{uuid.uuid4().hex[:6]}.wav")

    with open(temp_raw, "wb") as f:
        f.write(await audio.read())

    try:
        from app.ml.voice_pipeline import convert_audio_to_16k_mono_wav
        ok, conv_err = convert_audio_to_16k_mono_wav(temp_raw, temp_16k)
        if not ok:
            raise HTTPException(status_code=400, detail=conv_err)

        result, error_msg = voice_pipeline.analyze(temp_16k)
        if error_msg:
            raise HTTPException(status_code=400, detail=error_msg)

        # Save Modality Result
        mod_res = db.query(ModalityResult).filter(
            ModalityResult.session_id == session_id,
            ModalityResult.modality_type == "voice"
        ).first()

        if not mod_res:
            mod_res = ModalityResult(
                id=str(uuid.uuid4()),
                session_id=session_id,
                modality_type="voice",
                skipped=False,
                depression_probability=result.get("depression_probability"),
                primary_emotion=result.get("detected_emotion"),
                confidence_score=0.85 if result.get("depression_probability") is not None else 0.50,
                details_json=json.dumps(result)
            )
            db.add(mod_res)
        else:
            mod_res.skipped = False
            mod_res.depression_probability = result.get("depression_probability")
            mod_res.primary_emotion = result.get("detected_emotion")
            mod_res.confidence_score = 0.85 if result.get("depression_probability") is not None else 0.50
            mod_res.details_json = json.dumps(result)

        db.commit()
        return {"session_id": session_id, **result}
    finally:
        # Zero-retention enforcement: Purge raw audio file unless opt-in is active
        if not session.store_media_opt_in:
            for p in [temp_raw, temp_16k]:
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except Exception:
                        pass

@router.post("/analyze-face")
async def analyze_face_step(
    session_id: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    session = db.query(ScreeningSession).filter(ScreeningSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    ext = (os.path.splitext(file.filename)[1] or ".jpg").lower()
    temp_filename = f"face_{session_id}_{uuid.uuid4().hex[:6]}{ext}"
    temp_path = os.path.join(settings.UPLOAD_DIR, temp_filename)

    with open(temp_path, "wb") as f:
        f.write(await file.read())

    try:
        if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid image format. Please capture a live photo or upload an image (JPG or PNG)."
            )
        result, error_msg = face_pipeline.analyze_image(temp_path)


        if error_msg:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)


        # Save Modality Result
        mod_res = db.query(ModalityResult).filter(
            ModalityResult.session_id == session_id,
            ModalityResult.modality_type == "face"
        ).first()

        if not mod_res:
            mod_res = ModalityResult(
                id=str(uuid.uuid4()),
                session_id=session_id,
                modality_type="face",
                skipped=False,
                depression_probability=result["depression_probability"],
                primary_emotion=result.get("primary_emotion"),
                confidence_score=result["confidence_score"],
                details_json=json.dumps(result)
            )
            db.add(mod_res)
        else:
            mod_res.skipped = False
            mod_res.depression_probability = result["depression_probability"]
            mod_res.primary_emotion = result.get("primary_emotion")
            mod_res.confidence_score = result["confidence_score"]
            mod_res.details_json = json.dumps(result)

        db.commit()
        return {"session_id": session_id, **result}
    finally:
        # Zero-retention enforcement: Purge raw face imagery unless opt-in
        if not session.store_media_opt_in and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass

@router.post("/skip-modality")
def skip_modality_step(
    session_id: str = Form(...),
    modality: str = Form(...),  # text, voice, face
    db: Session = Depends(get_db)
):
    session = db.query(ScreeningSession).filter(ScreeningSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    mod_res = db.query(ModalityResult).filter(
        ModalityResult.session_id == session_id,
        ModalityResult.modality_type == modality
    ).first()

    if not mod_res:
        mod_res = ModalityResult(
            id=str(uuid.uuid4()),
            session_id=session_id,
            modality_type=modality,
            skipped=True
        )
        db.add(mod_res)
    else:
        mod_res.skipped = True
        mod_res.depression_probability = None

    db.commit()
    return {"session_id": session_id, "modality": modality, "skipped": True}

@router.post("/fuse")
def fuse_screening_results(
    session_id: str = Form(...),
    db: Session = Depends(get_db)
):
    session = db.query(ScreeningSession).filter(ScreeningSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    patient = db.query(Patient).filter(Patient.id == session.patient_id).first()
    phq = db.query(PHQ9Assessment).filter(PHQ9Assessment.session_id == session_id).first()
    
    # Retrieve modality results
    text_row = db.query(ModalityResult).filter(ModalityResult.session_id == session_id, ModalityResult.modality_type == "text").first()
    voice_row = db.query(ModalityResult).filter(ModalityResult.session_id == session_id, ModalityResult.modality_type == "voice").first()
    face_row = db.query(ModalityResult).filter(ModalityResult.session_id == session_id, ModalityResult.modality_type == "face").first()

    text_res = json.loads(text_row.details_json) if (text_row and not text_row.skipped and text_row.details_json) else None
    voice_res = json.loads(voice_row.details_json) if (voice_row and not voice_row.skipped and voice_row.details_json) else None
    face_res = json.loads(face_row.details_json) if (face_row and not face_row.skipped and face_row.details_json) else None

    # Perform Multimodal Late Fusion
    fused_output = perform_multimodal_late_fusion(
        text_res=text_res,
        voice_res=voice_res,
        face_res=face_res,
        phq9_score=phq.total_score if phq else None,
        has_self_harm_risk=session.has_self_harm_risk
    )

    # Format modality summaries
    modality_breakdown = []
    for mod_name, res, row in [("text", text_res, text_row), ("voice", voice_res, voice_row), ("face", face_res, face_row)]:
        if not row or row.skipped:
            modality_breakdown.append({
                "modality": mod_name,
                "probability": None,
                "risk_band": "Skipped",
                "confidence": 0.0,
                "summary": f"{mod_name.capitalize()} evaluation skipped by user.",
                "skipped": True,
                "status": "Skipped"
            })
        elif mod_name == "voice" and (row.depression_probability is None or (voice_res and voice_res.get("model_status") != "trained")):
            speech_rate = voice_res.get("speech_rate", "N/A") if voice_res else "N/A"
            pause_len = voice_res.get("pause_length", "N/A") if voice_res else "N/A"
            pitch_var = voice_res.get("pitch_variability", "N/A") if voice_res else "N/A"
            rms_val = voice_res.get("energy", "N/A") if voice_res else "N/A"
            modality_breakdown.append({
                "modality": mod_name,
                "probability": None,
                "risk_band": "Voice model not trained yet",
                "confidence": 0.0,
                "summary": f"Voice features (observations only, not part of the score): Rate={speech_rate} syl/s, Pause={pause_len}, Pitch std={pitch_var}, Energy={rms_val}",
                "skipped": False,
                "status": "Features only"
            })
        else:
            modality_breakdown.append({
                "modality": mod_name,
                "probability": row.depression_probability or 0.0,
                "risk_band": res.get("risk_band", "Minimal") if res else "Minimal",
                "confidence": row.confidence_score or 0.8,
                "summary": res.get("summary_sentence", "Completed.") if res else "Completed.",
                "skipped": False,
                "status": "Used"
            })

    # Prepare payload for PDF report generation
    symptoms = json.loads(session.symptoms_json) if session.symptoms_json else []
    report_data = {
        "session_id": session_id,
        "patient": {
            "full_name": patient.full_name if patient else "Anonymous",
            "age": calculate_age(patient.date_of_birth) if patient else None,
            "gender": patient.gender if patient else "N/A",
            "occupation": patient.occupation if patient else "N/A"
        },
        "symptoms": symptoms,
        "symptom_duration": session.symptom_duration_text or "N/A",
        "has_self_harm_risk": session.has_self_harm_risk,
        "fused_score": fused_output["fused_score"],
        "risk_band": fused_output["risk_band"],
        "confidence_level": fused_output["confidence_level"],
        "modalities_used": fused_output["modalities_used"],
        "phq9_score": phq.total_score if phq else None,
        "concordance_notes": fused_output["concordance_notes"],
        "recommendations": fused_output["recommendations"],
        "modality_breakdown": modality_breakdown,
        "speech_rate": voice_res.get("speech_rate") if voice_res else None,
        "pause_length": voice_res.get("pause_length") if voice_res else None,
        "pitch_variability": voice_res.get("pitch_variability") if voice_res else None
    }

    # Generate PDF report
    pdf_path = generate_screening_pdf_report(report_data)

    # Save Fusion Result in DB
    fusion_rec = db.query(FusionResult).filter(FusionResult.session_id == session_id).first()
    if not fusion_rec:
        fusion_rec = FusionResult(
            id=str(uuid.uuid4()),
            session_id=session_id,
            fused_score=fused_output["fused_score"],
            risk_band=fused_output["risk_band"],
            confidence_level=fused_output["confidence_level"],
            modalities_used=",".join(fused_output["modalities_used"]),
            phq9_discordance_flag=fused_output["phq9_discordance_flag"],
            concordance_notes=fused_output["concordance_notes"],
            recommendations="\n".join(fused_output["recommendations"]),
            pdf_report_path=pdf_path
        )
        db.add(fusion_rec)
    else:
        fusion_rec.fused_score = fused_output["fused_score"]
        fusion_rec.risk_band = fused_output["risk_band"]
        fusion_rec.confidence_level = fused_output["confidence_level"]
        fusion_rec.modalities_used = ",".join(fused_output["modalities_used"])
        fusion_rec.phq9_discordance_flag = fused_output["phq9_discordance_flag"]
        fusion_rec.concordance_notes = fused_output["concordance_notes"]
        fusion_rec.recommendations = "\n".join(fused_output["recommendations"])
        fusion_rec.pdf_report_path = pdf_path

    session.status = "completed"
    # Delete drafts after the analysis is completed
    user_key = (current_user.id if current_user else None) or "anonymous"
    db.query(AnalysisDraft).filter(AnalysisDraft.user_id == user_key).delete()
    db.commit()

    return {
        "session_id": session_id,
        "fused_score": fused_output["fused_score"],
        "risk_band": fused_output["risk_band"],
        "confidence_level": fused_output["confidence_level"],
        "modalities_used": fused_output["modalities_used"],
        "skipped_modalities": fused_output["skipped_modalities"],
        "phq9_score": phq.total_score if phq else None,
        "phq9_severity": phq.severity_category if phq else None,
        "phq9_discordance_flag": fused_output["phq9_discordance_flag"],
        "concordance_notes": fused_output["concordance_notes"],
        "modality_breakdown": modality_breakdown,
        "recommendations": fused_output["recommendations"],
        "has_self_harm_risk": session.has_self_harm_risk,
        "helpline_panel": fused_output["helpline_panel"],
        "detected_language": fused_output.get("detected_language", "en"),
        "language_name": fused_output.get("language_name", "English"),
        "is_non_english": fused_output.get("is_non_english", False),
        "accuracy_note": fused_output.get("accuracy_note"),
        "transcript": fused_output.get("transcript"),
        "disclaimer": fused_output["disclaimer"],
        "pdf_report_url": f"/api/v1/reports/{session_id}/download",
        "created_at": session.created_at.isoformat()
    }
