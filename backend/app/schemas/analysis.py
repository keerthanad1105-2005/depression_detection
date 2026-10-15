from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class KeywordSaliency(BaseModel):
    word: str
    weight: float
    sentiment: str  # negative, neutral, positive

class TextAnalysisResponse(BaseModel):
    session_id: str
    modality: str = "text"
    depression_probability: float
    risk_band: str
    confidence_score: float
    word_count: int
    top_saliency_tokens: List[KeywordSaliency]
    summary_sentence: str

class VoiceAcousticFeatures(BaseModel):
    speech_rate_syl_per_sec: float
    pause_length_ratio: float
    pitch_variability_f0_std: float
    energy_rms_mean: float

class VoiceAnalysisResponse(BaseModel):
    session_id: str
    modality: str = "voice"
    depression_probability: float
    risk_band: str
    confidence_score: float
    detected_emotion: str
    acoustic_features: VoiceAcousticFeatures
    summary_sentence: str

class FaceAnalysisResponse(BaseModel):
    session_id: str
    modality: str = "face"
    depression_probability: float
    risk_band: str
    confidence_score: float
    primary_emotion: str
    emotion_probabilities: Dict[str, float]
    predicted_gender: str
    gender_confidence: float
    faces_detected: int
    summary_sentence: str
