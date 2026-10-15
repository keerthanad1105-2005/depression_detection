import uuid
from datetime import datetime, date
from sqlalchemy import Column, String, Boolean, Date, DateTime, ForeignKey, Text, Integer
from app.db.base import Base

class ScreeningSession(Base):
    __tablename__ = "screening_sessions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = Column(String(36), ForeignKey("patients.id"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    status = Column(String(50), default="in_progress")  # in_progress, completed, cancelled
    
    # Consent
    consent_given = Column(Boolean, default=False)
    consent_timestamp = Column(DateTime, nullable=True)
    store_media_opt_in = Column(Boolean, default=False)
    
    # Symptoms & Duration
    symptoms_json = Column(Text, nullable=True)  # List of symptoms stored as JSON string
    symptoms_onset_date = Column(Date, nullable=True)
    symptom_duration_text = Column(String(100), nullable=True)  # e.g. "3 weeks, 2 days"
    has_self_harm_risk = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
