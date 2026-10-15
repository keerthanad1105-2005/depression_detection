import os
import json
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.session import ScreeningSession
from app.models.patient import Patient
from app.models.phq9 import PHQ9Assessment
from app.models.modality_result import ModalityResult
from app.models.fusion_result import FusionResult
from app.services.pdf_service import generate_screening_pdf_report
from app.api.v1.screening import calculate_age

router = APIRouter(prefix="/reports", tags=["Clinical PDF Reports"])

@router.get("/{session_id}/download")
def download_pdf_report(session_id: str, db: Session = Depends(get_db)):
    session = db.query(ScreeningSession).filter(ScreeningSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Screening session not found.")

    fusion = db.query(FusionResult).filter(FusionResult.session_id == session_id).first()
    
    # Check if report already exists on disk
    if fusion and fusion.pdf_report_path and os.path.exists(fusion.pdf_report_path):
        return FileResponse(
            fusion.pdf_report_path,
            media_type="application/pdf",
            filename=f"MindScan_Report_{session_id[:8]}.pdf"
        )

    # Re-generate if missing
    patient = db.query(Patient).filter(Patient.id == session.patient_id).first()
    phq = db.query(PHQ9Assessment).filter(PHQ9Assessment.session_id == session_id).first()
    mod_results = db.query(ModalityResult).filter(ModalityResult.session_id == session_id).all()

    breakdown = []
    for m in mod_results:
        details = json.loads(m.details_json) if m.details_json else {}
        is_untrained_voice = (m.modality_type == "voice" and (m.depression_probability is None or details.get("model_status") != "trained"))
        if is_untrained_voice:
            breakdown.append({
                "modality": m.modality_type,
                "probability": None,
                "risk_band": "Voice model not trained yet",
                "confidence": 0.0,
                "summary": f"Voice features (observations only, not part of the score): Rate={details.get('speech_rate', 'N/A')} syl/s, Pause={details.get('pause_length', 'N/A')}, Pitch std={details.get('pitch_variability', 'N/A')}",
                "skipped": False,
                "status": "Features only"
            })
        else:
            breakdown.append({
                "modality": m.modality_type,
                "probability": m.depression_probability or 0.0,
                "risk_band": details.get("risk_band", "Minimal") if not m.skipped else "Skipped",
                "confidence": m.confidence_score or 0.8,
                "summary": details.get("summary_sentence", "Completed.") if not m.skipped else "Skipped by user.",
                "skipped": m.skipped,
                "status": "Used" if not m.skipped else "Skipped"
            })

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
        "fused_score": fusion.fused_score if fusion else 0.20,
        "risk_band": fusion.risk_band if fusion else "Minimal",
        "confidence_level": fusion.confidence_level if fusion else 0.80,
        "modalities_used": fusion.modalities_used.split(",") if fusion else ["text"],
        "phq9_score": phq.total_score if phq else None,
        "concordance_notes": fusion.concordance_notes if fusion else "Clinical assessment completed.",
        "recommendations": fusion.recommendations.split("\n") if (fusion and fusion.recommendations) else ["Consult clinician."],
        "modality_breakdown": breakdown
    }

    pdf_path = generate_screening_pdf_report(report_data)
    if fusion:
        fusion.pdf_report_path = pdf_path
        db.commit()

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=f"MindScan_Report_{session_id[:8]}.pdf"
    )

@router.get("/{session_id}/view")
def view_pdf_inline(session_id: str, db: Session = Depends(get_db)):
    session = db.query(ScreeningSession).filter(ScreeningSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Screening session not found.")
    fusion = db.query(FusionResult).filter(FusionResult.session_id == session_id).first()
    if not fusion or not fusion.pdf_report_path or not os.path.exists(fusion.pdf_report_path):
        return download_pdf_report(session_id, db)
    return FileResponse(
        fusion.pdf_report_path,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename=MindScan_Report_{session_id[:8]}.pdf"}
    )
