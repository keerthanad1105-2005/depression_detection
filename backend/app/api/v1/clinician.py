import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from app.db.session import get_db
from app.models.user import User
from app.models.patient import Patient
from app.models.session import ScreeningSession
from app.models.fusion_result import FusionResult
from app.models.clinical_note import ClinicalNote
from app.api.deps import require_role, require_clinician
from app.api.v1.screening import calculate_age

router = APIRouter(prefix="/clinician", tags=["Clinician Portal"], dependencies=[Depends(require_clinician)])

class NoteCreate(BaseModel):
    session_id: str
    note_content: str
    triage_priority: Optional[str] = "Medium"  # Low, Medium, High, Urgent

@router.get("/patients")
def get_clinician_patient_queue(
    search: Optional[str] = None,
    sort_by_risk: bool = True,
    db: Session = Depends(get_db),
    # Optional role checking (allows demo mode or authenticated clinician)
):
    """
    Returns patient registry with latest screening session and risk level.
    Sorted by clinical triage priority (Severe / High Risk first).
    """
    patients = db.query(Patient).all()
    queue = []

    # Risk ranking order for sorting
    risk_weights = {
        "Severe": 5,
        "Moderately Severe": 4,
        "Moderate": 3,
        "Mild": 2,
        "Minimal": 1,
        "Incomplete": 0
    }

    for p in patients:
        latest_session = db.query(ScreeningSession).\
            filter(ScreeningSession.patient_id == p.id).\
            order_by(ScreeningSession.created_at.desc()).first()

        fusion = None
        notes_count = 0
        if latest_session:
            fusion = db.query(FusionResult).filter(FusionResult.session_id == latest_session.id).first()
            notes_count = db.query(ClinicalNote).filter(ClinicalNote.session_id == latest_session.id).count()

        risk = fusion.risk_band if fusion else "Incomplete"
        queue.append({
            "patient_id": p.id,
            "patient_name": p.full_name,
            "dob": p.date_of_birth.isoformat() if p.date_of_birth else None,
            "age": calculate_age(p.date_of_birth) if p.date_of_birth else getattr(p, "age", None),
            "gender": p.gender,
            "occupation": p.occupation or "N/A",
            "latest_session_id": latest_session.id if latest_session else None,
            "latest_session_date": latest_session.created_at.strftime("%d %b %Y") if latest_session else "None",
            "risk_band": risk,
            "fused_score": fusion.fused_score if fusion else 0.0,
            "has_self_harm_risk": latest_session.has_self_harm_risk if latest_session else False,
            "notes_count": notes_count,
            "risk_rank": risk_weights.get(risk, 0) + (10 if (latest_session and latest_session.has_self_harm_risk) else 0)
        })

    if search:
        queue = [item for item in queue if search.lower() in item["patient_name"].lower()]

    if sort_by_risk:
        queue = sorted(queue, key=lambda x: x["risk_rank"], reverse=True)

    return {"patients": queue, "total": len(queue)}

@router.post("/notes")
def create_clinical_note(
    payload: NoteCreate,
    db: Session = Depends(get_db)
):
    session = db.query(ScreeningSession).filter(ScreeningSession.id == payload.session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Screening session not found.")

    note = ClinicalNote(
        id=str(uuid.uuid4()),
        session_id=payload.session_id,
        clinician_id=session.user_id or "system-clinician",
        note_content=payload.note_content,
        triage_priority=payload.triage_priority or "Medium"
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return {"message": "Clinical note saved successfully.", "note_id": note.id}

@router.get("/notes/{session_id}")
def get_session_notes(session_id: str, db: Session = Depends(get_db)):
    notes = db.query(ClinicalNote).filter(ClinicalNote.session_id == session_id).order_by(ClinicalNote.created_at.desc()).all()
    return [{
        "id": n.id,
        "note_content": n.note_content,
        "triage_priority": n.triage_priority,
        "created_at": n.created_at.strftime("%d %b %Y, %H:%M")
    } for n in notes]
