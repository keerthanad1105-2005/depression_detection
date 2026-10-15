from sqlalchemy import Column, Integer, String, Float, Text
from app.db.base import Base

class HistoryRecord(Base):
    __tablename__ = "history"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    username = Column(String(255), nullable=True)
    analysis_type = Column(String(100), nullable=True)
    score = Column(Float, nullable=True)
    level = Column(String(50), nullable=True)
    date = Column(String(100), nullable=True)
    dob = Column(String(50), nullable=True)
    age = Column(String(20), nullable=True)
    gender = Column(String(50), nullable=True)
    occupation = Column(String(255), nullable=True)
    symptoms = Column(Text, nullable=True)
    duration = Column(String(100), nullable=True)
    language = Column(String(50), nullable=True)
    transcript = Column(Text, nullable=True)
    is_test = Column(Integer, default=0)
    is_reviewed = Column(Integer, default=0)
    user_id = Column(String(100), nullable=True, index=True)
    user_email = Column(String(255), nullable=True, index=True)
