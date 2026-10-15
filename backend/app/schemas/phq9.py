from pydantic import BaseModel, Field
from typing import Dict, Any

class PHQ9SubmitRequest(BaseModel):
    session_id: str
    q1: int = Field(..., ge=0, le=3, description="Little interest or pleasure in doing things")
    q2: int = Field(..., ge=0, le=3, description="Feeling down, depressed, or hopeless")
    q3: int = Field(..., ge=0, le=3, description="Trouble falling or staying asleep, or sleeping too much")
    q4: int = Field(..., ge=0, le=3, description="Feeling tired or having little energy")
    q5: int = Field(..., ge=0, le=3, description="Poor appetite or overeating")
    q6: int = Field(..., ge=0, le=3, description="Feeling bad about yourself - or that you are a failure")
    q7: int = Field(..., ge=0, le=3, description="Trouble concentrating on things")
    q8: int = Field(..., ge=0, le=3, description="Moving or speaking slowly, or fidgety/restless")
    q9: int = Field(..., ge=0, le=3, description="Thoughts that you would be better off dead, or hurting yourself")

class PHQ9Response(BaseModel):
    id: str
    session_id: str
    total_score: int
    severity_category: str
    has_self_harm_risk: bool
    interpretation: str
    item_responses: Dict[str, int]
