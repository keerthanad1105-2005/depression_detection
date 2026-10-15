import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from app.db.base import Base

class ClinicalNote(Base):
    __tablename__ = "clinical_notes"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("screening_sessions.id"), nullable=False)
    clinician_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    
    note_content = Column(Text, nullable=False)
    triage_priority = Column(String(50), default="Medium")  # Low, Medium, High, Urgent
    
    created_at = Column(DateTime, default=datetime.utcnow)
