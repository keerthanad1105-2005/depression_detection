import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, Boolean, DateTime, ForeignKey, Text
from app.db.base import Base

class FusionResult(Base):
    __tablename__ = "fusion_results"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("screening_sessions.id"), unique=True, nullable=False)
    
    fused_score = Column(Float, nullable=False)  # 0.0 to 1.0
    risk_band = Column(String(50), nullable=False)  # Minimal, Mild, Moderate, Moderately Severe, Severe
    confidence_level = Column(Float, nullable=False)  # 0.0 to 1.0 (e.g. 0.85 = 85%)
    
    modalities_used = Column(String(100), nullable=False)  # e.g. "text,voice,face"
    phq9_discordance_flag = Column(Boolean, default=False)
    concordance_notes = Column(Text, nullable=True)
    recommendations = Column(Text, nullable=True)
    
    pdf_report_path = Column(String(500), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
