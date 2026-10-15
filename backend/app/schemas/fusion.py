from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

class ModalityScoreSummary(BaseModel):
    modality: str
    probability: float
    risk_band: str
    confidence: float
    summary: str
    skipped: bool = False

class HelplineResource(BaseModel):
    name: str
    number: str
    available: str
    description: str

class FusedResultsResponse(BaseModel):
    session_id: str
    fused_score: float
    risk_band: str  # Minimal, Mild, Moderate, Moderately Severe, Severe
    confidence_level: float
    modalities_used: List[str]
    skipped_modalities: List[str]
    
    # Clinical comparison
    phq9_score: Optional[int] = None
    phq9_severity: Optional[str] = None
    phq9_discordance_flag: bool = False
    concordance_notes: str
    
    # Per-modality summaries
    modality_breakdown: List[ModalityScoreSummary]
    
    # Recommendations & safety
    recommendations: List[str]
    has_self_harm_risk: bool = False
    helpline_panel: List[HelplineResource]
    disclaimer: str
    pdf_report_url: str
    created_at: datetime
