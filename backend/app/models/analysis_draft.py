import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Boolean, DateTime
from app.db.base import Base

class AnalysisDraft(Base):
    __tablename__ = "analysis_drafts"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(50), index=True, nullable=False)  # User ID or username
    step = Column(String(50), nullable=False)  # patient_info, phq9, text, voice, face
    draft_data = Column(Text, nullable=False)  # JSON payload of fields and answers
    has_audio = Column(Boolean, default=False)
    has_photo = Column(Boolean, default=False)
    audio_path = Column(String(255), nullable=True)
    photo_path = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
