from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import date, datetime

class PatientCreate(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    date_of_birth: date
    gender: str = Field(..., description="Male, Female, Other, Prefer not to say")
    occupation: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None

    @validator("date_of_birth")
    def validate_dob_not_future(cls, v):
        if v > date.today():
            raise ValueError("Date of birth cannot be in the future")
        return v

class PatientResponse(BaseModel):
    id: str
    user_id: Optional[str]
    full_name: str
    date_of_birth: date
    age: int
    gender: str
    occupation: Optional[str]
    emergency_contact_name: Optional[str]
    emergency_contact_phone: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True

class SessionInitRequest(BaseModel):
    patient_id: Optional[str] = None
    patient: Optional[PatientCreate] = None
    consent_given: bool = True
    store_media_opt_in: bool = False
    symptoms: List[str] = []
    symptoms_onset_date: Optional[date] = None
