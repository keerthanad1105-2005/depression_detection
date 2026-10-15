import os
from typing import List, Union, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WORKSPACE_DIR = os.path.dirname(BASE_DIR)

class Settings(BaseSettings):
    PROJECT_NAME: str = "MindScan: Multimodal Depression Screening Support"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    
    # Security & JWT
    SECRET_KEY: str = "mindscan-super-secret-key-production-change-me-32bytes-long!"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    SECURE_COOKIES: bool = False
    
    # Registration Access Codes
    ADMIN_REGISTRATION_CODE: str = ""
    CLINICIAN_REGISTRATION_CODE: str = ""
    
    # Database
    DATABASE_PATH: str = os.path.join(BASE_DIR, "mindscan.db")
    DATABASE_URL: str = f"sqlite:///{os.path.join(BASE_DIR, 'mindscan.db')}"
    
    # Frontend URL & CORS
    FRONTEND_URL: str = "http://localhost:3000"
    CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8000",
        "http://localhost:8000"
    ]
    
    # Google OAuth 2.0 Credentials
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:3000/login.html"
    
    # Model Weights Configuration & Storage
    BASE_DIR: str = BASE_DIR
    WORKSPACE_DIR: str = WORKSPACE_DIR
    UPLOAD_DIR: str = os.path.join(BASE_DIR, "uploads")
    REPORT_DIR: str = os.path.join(BASE_DIR, "reports")
    MODELS_DIR: str = os.path.join(BASE_DIR, "models")
    HF_MODEL_REPO_ID: Optional[str] = None
    DOWNLOAD_MODELS_ON_STARTUP: bool = False
    
    # Concurrency & Logging
    WEB_CONCURRENCY: int = 1
    LOG_LEVEL: str = "INFO"
    
    # Safety Helplines
    TELE_MANAS_HELPLINE: str = "14416"
    KIRAN_HELPLINE: str = "1800-599-0019"
    VANDREVALA_HELPLINE: str = "+91 9999 666 555"

    model_config = SettingsConfigDict(
        env_file=(os.path.join(BASE_DIR, ".env"), ".env"),
        extra="allow",
        case_sensitive=False
    )

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: Optional[str]) -> str:
        if not v:
            return f"sqlite:///{os.path.join(BASE_DIR, 'mindscan.db')}"
        # Normalize postgres:// scheme (Render / Railway / Supabase use postgres://, SQLAlchemy requires postgresql://)
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql://", 1)
        return v

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @field_validator("MODELS_DIR", mode="before")
    @classmethod
    def resolve_models_dir(cls, v: Optional[str]) -> str:
        if v and os.path.isdir(v):
            return v
        # Check standard locations
        workspace_models = os.path.join(WORKSPACE_DIR, "depression_detection", "training", "models")
        if os.path.isdir(workspace_models):
            return workspace_models
        local_models = os.path.join(BASE_DIR, "models")
        return v or local_models

settings = Settings()

# Ensure runtime directories exist
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.REPORT_DIR, exist_ok=True)
os.makedirs(settings.MODELS_DIR, exist_ok=True)
