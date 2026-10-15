import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from app.db.base import Base

class PHQ9Assessment(Base):
    __tablename__ = "phq9_assessments"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("screening_sessions.id"), unique=True, nullable=False)
    
    q1_interest = Column(Integer, nullable=False)
    q2_depressed = Column(Integer, nullable=False)
    q3_sleep = Column(Integer, nullable=False)
    q4_tired = Column(Integer, nullable=False)
    q5_appetite = Column(Integer, nullable=False)
    q6_failure = Column(Integer, nullable=False)
    q7_concentrating = Column(Integer, nullable=False)
    q8_slow_restless = Column(Integer, nullable=False)
    q9_self_harm = Column(Integer, nullable=False)
    
    total_score = Column(Integer, nullable=False)  # 0 to 27
    severity_category = Column(String(50), nullable=False)  # Minimal, Mild, Moderate, Moderately Severe, Severe
    
    created_at = Column(DateTime, default=datetime.utcnow)
