from typing import Dict, Any, List, Optional
from app.core.config import settings

def perform_multimodal_late_fusion(
    text_res: Optional[Dict[str, Any]] = None,
    voice_res: Optional[Dict[str, Any]] = None,
    face_res: Optional[Dict[str, Any]] = None,
    phq9_score: Optional[int] = None,
    has_self_harm_risk: bool = False
) -> Dict[str, Any]:
    """
    Performs calibrated late fusion across active modalities and PHQ-9.
    Gracefully handles skipped modalities with dynamic weight re-normalization
    and confidence degradation.
    Works seamlessly whether voice is present or skipped/untrained.
    """
    # Nominal weights learned on validation splits
    base_weights = {
        "text": 0.40,
        "voice": 0.30,
        "face": 0.30
    }
    
    active_modalities = {}
    skipped_modalities = []
    
    if text_res and not text_res.get("skipped", False) and text_res.get("depression_probability") is not None:
        active_modalities["text"] = float(text_res["depression_probability"])
    else:
        skipped_modalities.append("text")
        
    if voice_res and not voice_res.get("skipped", False) and voice_res.get("depression_probability") is not None:
        active_modalities["voice"] = float(voice_res["depression_probability"])
    else:
        skipped_modalities.append("voice")
        
    if face_res and not face_res.get("skipped", False) and face_res.get("depression_probability") is not None:
        active_modalities["face"] = float(face_res["depression_probability"])
    else:
        skipped_modalities.append("face")
        
    # Re-normalize weights for active modalities
    if active_modalities:
        total_active_nominal_weight = sum(base_weights[m] for m in active_modalities)
        normalized_weights = {
            m: base_weights[m] / total_active_nominal_weight
            for m in active_modalities
        }
        
        # Calculate weighted AI score
        ai_fused_score = sum(
            active_modalities[m] * normalized_weights[m]
            for m in active_modalities
        )
        
        # Confidence calculation (penalized if modalities skipped)
        coverage_ratio = len(active_modalities) / 3.0
        confidence_level = round(0.55 + 0.38 * coverage_ratio, 2)
    else:
        # If all 3 skipped, rely solely on PHQ-9 if available
        ai_fused_score = (phq9_score / 27.0) if phq9_score is not None else 0.20
        confidence_level = 0.50

    # Integrate PHQ-9 clinical self-report into final fused score
    if phq9_score is not None:
        phq9_norm = phq9_score / 27.0
        # AI models (65%) + PHQ-9 (35%)
        final_fused_score = 0.65 * ai_fused_score + 0.35 * phq9_norm
    else:
        final_fused_score = ai_fused_score
        
    final_fused_score = min(max(final_fused_score, 0.0), 1.0)

    # Risk Band Categorization
    if final_fused_score < 0.20:
        risk_band = "Minimal"
    elif final_fused_score < 0.45:
        risk_band = "Mild"
    elif final_fused_score < 0.70:
        risk_band = "Moderate"
    elif final_fused_score < 0.85:
        risk_band = "Moderately Severe"
    else:
        risk_band = "Severe"

    # AI vs PHQ-9 Clinical Concordance Analysis
    discordance_flag = False
    concordance_notes = "AI multimodal assessment and PHQ-9 self-report demonstrate clinical alignment."
    
    if phq9_score is not None and active_modalities:
        phq9_norm = phq9_score / 27.0
        diff = abs(ai_fused_score - phq9_norm)
        
        if diff >= 0.30:
            discordance_flag = True
            if ai_fused_score > phq9_norm:
                concordance_notes = (
                    "Noticeable disagreement: Objective AI acoustic/linguistic markers indicate higher distress "
                    "than subjective PHQ-9 responses. Consider exploring masked depression, social desirability bias, "
                    "or emotional minimization."
                )
            else:
                concordance_notes = (
                    "Noticeable disagreement: Patient reports significant subjective symptoms on PHQ-9, but vocal "
                    "and facial markers show moderate expressivity. Consider situational anxiety, somatization, or "
                    "acute stress reaction."
                )

    # Recommendations formulated for clinical decision support
    recommendations = []
    if risk_band in ["Moderately Severe", "Severe"] or has_self_harm_risk:
        recommendations.append("Immediate clinical psychiatric evaluation and safety assessment strongly recommended.")
        recommendations.append("Connect with licensed mental health professional or crisis support hotline without delay.")
        recommendations.append("Establish supportive contact with a trusted family member or designated emergency contact.")
    elif risk_band == "Moderate":
        recommendations.append("Comprehensive clinical interview by a psychologist or psychiatrist is indicated.")
        recommendations.append("Consider evidence-based psychotherapy (Cognitive Behavioral Therapy / Interpersonal Therapy).")
        recommendations.append("Implement sleep hygiene protocols and monitored physical activity.")
    elif risk_band == "Mild":
        recommendations.append("Structured psychoeducation and lifestyle self-care strategies (exercise, regular sleep).")
        recommendations.append("Follow-up screening within 2 to 4 weeks to monitor symptom trajectory.")
    else:
        recommendations.append("Encourage maintenance of existing social connections and wellness routines.")
        recommendations.append("Routine periodic self-assessment if subjective stress changes.")

    # Emergency Helpline Panel (India & Global)
    helplines = [
        {
            "name": "Tele-MANAS (Govt of India)",
            "number": "14416 / 1800-891-4416",
            "available": "24/7 Toll-Free, Multi-lingual",
            "description": "National Tele Mental Health Programme of India for free counseling and crisis care."
        },
        {
            "name": "Kiran Mental Health Helpline",
            "number": "1800-599-0019",
            "available": "24/7 Toll-Free",
            "description": "Department of Empowerment of Persons with Disabilities mental health rehabilitation line."
        },
        {
            "name": "Vandrevala Foundation",
            "number": "+91 9999 666 555",
            "available": "24/7 Free Helpline",
            "description": "Professional psychological counseling and immediate emotional support."
        }
    ]

    return {
        "fused_score": round(float(final_fused_score), 4),
        "risk_band": risk_band,
        "confidence_level": confidence_level,
        "modalities_used": list(active_modalities.keys()),
        "skipped_modalities": skipped_modalities,
        "phq9_score": phq9_score,
        "phq9_discordance_flag": discordance_flag,
        "concordance_notes": concordance_notes,
        "has_self_harm_risk": has_self_harm_risk,
        "recommendations": recommendations,
        "helpline_panel": helplines,
        "disclaimer": (
            "MindScan is a screening-support tool designed for informational and clinical triage guidance only. "
            "It does NOT constitute a definitive medical diagnosis. Clinical judgment of a licensed healthcare provider "
            "must always take precedence."
        )
    }
