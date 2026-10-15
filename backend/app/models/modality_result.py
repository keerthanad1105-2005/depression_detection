import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, Boolean, DateTime, ForeignKey, Text
from app.db.base import Base

class ModalityResult(Base):
    __tablename__ = "modality_results"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("screening_sessions.id"), nullable=False)
    modality_type = Column(String(20), nullable=False)  # text, voice, face
    
    skipped = Column(Boolean, default=False)
    depression_probability = Column(Float, nullable=True)  # 0.0 to 1.0
    primary_emotion = Column(String(50), nullable=True)
    confidence_score = Column(Float, nullable=True)  # 0.0 to 1.0
    
    # Detailed features (e.g., highlighted words for text, acoustic features for voice, expressions for face)
    details_json = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
