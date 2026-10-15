from pydantic import BaseModel
from typing import Optional, Dict, Any

class DraftSaveRequest(BaseModel):
    user_id: Optional[str] = None
    step: str  # patient_info, phq9, text, voice, face
    draft_data: Dict[str, Any]
    opt_in_store_audio: bool = False
    opt_in_store_face: bool = False

class DraftResponse(BaseModel):
    has_draft: bool
    step: Optional[str] = None
    draft_data: Optional[Dict[str, Any]] = None
    updated_at: Optional[str] = None
