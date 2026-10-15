from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Dict, Any
from datetime import datetime

class UserRegister(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8)
    role: Optional[str] = "User"  # "User", "Clinician", or "Admin"
    access_code: Optional[str] = None  # Admin/Clinician registration code
    username: Optional[str] = None  # Legacy/compatibility fallback

class UserLogin(BaseModel):
    email: Optional[str] = None
    password: str
    username_or_email: Optional[str] = None
    username: Optional[str] = None

class GoogleLogin(BaseModel):
    email: EmailStr
    full_name: str
    google_id: Optional[str] = None
    username: Optional[str] = None
    role: Optional[str] = "User"

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8)

class UserResponse(BaseModel):
    id: str
    username: Optional[str] = None
    email: str
    full_name: str
    role: str
    clinician_status: Optional[str] = None
    is_active: bool
    email_verified: bool
    created_at: datetime

    class Config:
        from_attributes = True

class TokenRefreshRequest(BaseModel):
    refresh_token: Optional[str] = None

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse

