import csv
import io
import json
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session
from typing import Optional, List
from app.db.session import get_db
from app.models.session import ScreeningSession
from app.models.patient import Patient
from app.models.fusion_result import FusionResult
from app.models.phq9 import PHQ9Assessment
from app.api.v1.screening import calculate_age

router = APIRouter(prefix="/history", tags=["Screening History"])

@router.get("/")
def list_history(
    search: Optional[str] = Query(None),
    risk_band: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    query = db.query(ScreeningSession, Patient, FusionResult).\
        join(Patient, ScreeningSession.patient_id == Patient.id).\
        outerjoin(FusionResult, ScreeningSession.id == FusionResult.session_id)

    if search:
        query = query.filter(Patient.full_name.ilike(f"%{search}%"))
        
    if risk_band and risk_band != "All":
        query = query.filter(FusionResult.risk_band == risk_band)

    total_count = query.count()
    results = query.order_by(ScreeningSession.created_at.desc()).\
        offset((page - 1) * limit).limit(limit).all()

    items = []
    for session, patient, fusion in results:
        items.append({
            "session_id": session.id,
            "patient_name": patient.full_name,
            "patient_dob": patient.date_of_birth.isoformat() if (patient and patient.date_of_birth) else None,
            "patient_age": calculate_age(patient.date_of_birth) if (patient and patient.date_of_birth) else getattr(patient, "age", None),
            "patient_gender": patient.gender,
            "status": session.status,
            "risk_band": fusion.risk_band if fusion else "Incomplete",
            "fused_score": fusion.fused_score if fusion else None,
            "confidence_level": fusion.confidence_level if fusion else None,
            "modalities_used": fusion.modalities_used.split(",") if fusion else [],
            "has_self_harm_risk": session.has_self_harm_risk,
            "created_at": session.created_at.isoformat()
        })

    return {
        "items": items,
        "total": total_count,
        "page": page,
        "limit": limit,
        "total_pages": (total_count + limit - 1) // limit if total_count > 0 else 1
    }

@router.get("/{session_id}")
def get_session_details(session_id: str, db: Session = Depends(get_db)):
    session = db.query(ScreeningSession).filter(ScreeningSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
        
    patient = db.query(Patient).filter(Patient.id == session.patient_id).first()
    fusion = db.query(FusionResult).filter(FusionResult.session_id == session_id).first()
    phq = db.query(PHQ9Assessment).filter(PHQ9Assessment.session_id == session_id).first()

    return {
        "session_id": session.id,
        "patient": {
            "id": patient.id if patient else None,
            "full_name": patient.full_name if patient else "Anonymous",
            "dob": patient.date_of_birth.isoformat() if (patient and patient.date_of_birth) else None,
            "age": calculate_age(patient.date_of_birth) if (patient and patient.date_of_birth) else getattr(patient, "age", None),
            "gender": patient.gender if patient else "N/A",
            "occupation": patient.occupation if patient else "N/A"
        },
        "symptoms": json.loads(session.symptoms_json) if session.symptoms_json else [],
        "symptom_duration": session.symptom_duration_text,
        "has_self_harm_risk": session.has_self_harm_risk,
        "fused_score": fusion.fused_score if fusion else None,
        "risk_band": fusion.risk_band if fusion else "Incomplete",
        "confidence_level": fusion.confidence_level if fusion else None,
        "modalities_used": fusion.modalities_used.split(",") if fusion else [],
        "phq9_score": phq.total_score if phq else None,
        "phq9_severity": phq.severity_category if phq else None,
        "concordance_notes": fusion.concordance_notes if fusion else None,
        "recommendations": fusion.recommendations.split("\n") if (fusion and fusion.recommendations) else [],
        "created_at": session.created_at.isoformat()
    }

@router.delete("/{session_id}")
def delete_session(session_id: str, db: Session = Depends(get_db)):
    session = db.query(ScreeningSession).filter(ScreeningSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
        
    # Cascade delete records
    db.query(FusionResult).filter(FusionResult.session_id == session_id).delete()
    db.query(PHQ9Assessment).filter(PHQ9Assessment.session_id == session_id).delete()
    db.delete(session)
    db.commit()
    return {"message": "Screening session and all associated data permanently deleted."}

@router.get("/export/csv")
def export_history_csv(db: Session = Depends(get_db)):
    results = db.query(ScreeningSession, Patient, FusionResult).\
        join(Patient, ScreeningSession.patient_id == Patient.id).\
        outerjoin(FusionResult, ScreeningSession.id == FusionResult.session_id).\
        order_by(ScreeningSession.created_at.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Session ID", "Patient Name", "Age", "Gender", "Occupation",
        "Risk Band", "Fused Score", "Confidence", "Self-Harm Risk", "Date"
    ])

    for session, patient, fusion in results:
        writer.writerow([
            session.id,
            patient.full_name,
            calculate_age(patient.date_of_birth),
            patient.gender,
            patient.occupation or "N/A",
            fusion.risk_band if fusion else "Incomplete",
            fusion.fused_score if fusion else "",
            f"{int(fusion.confidence_level * 100)}%" if (fusion and fusion.confidence_level) else "",
            "YES" if session.has_self_harm_risk else "No",
            session.created_at.strftime("%Y-%m-%d %H:%M")
        ])

    csv_data = output.getvalue()
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=mindscan_screenings_export.csv"}
    )
