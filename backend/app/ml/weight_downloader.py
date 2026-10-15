import os
import logging
from typing import Dict, Any, Optional
from app.core.config import settings

logger = logging.getLogger("mindscan.weights")

def get_model_status() -> Dict[str, Any]:
    """
    Inspects settings.MODELS_DIR and returns availability status for each modality model.
    Provides honest, clear diagnostic messages for missing model checkpoints.
    """
    models_dir = settings.MODELS_DIR
    
    # 1. Text model
    text_primary = os.path.join(models_dir, "xlm_roberta_depression")
    text_legacy = os.path.join(models_dir, "roberta_depression")
    text_available = os.path.isdir(text_primary) or os.path.isdir(text_legacy)
    text_path = text_primary if os.path.isdir(text_primary) else (text_legacy if os.path.isdir(text_legacy) else None)
    
    # 2. Voice model
    voice_path = os.path.join(models_dir, "wav2vec2_xls_r_voice")
    voice_available = os.path.isdir(voice_path)
    
    # 3. Face model
    face_path = os.path.join(models_dir, "mobilevit_face.pth")
    face_available = os.path.isfile(face_path)
    
    return {
        "text": {
            "name": "XLM-RoBERTa Depression Classifier",
            "available": text_available,
            "path": text_path,
            "status": "Model loaded and active" if text_available else "Model not available: using multilingual Indic-aware clinical lexicon zero-shot fallback."
        },
        "voice": {
            "name": "Wav2Vec2 XLS-R Acoustic Biomarkers",
            "available": voice_available,
            "path": voice_path if voice_available else None,
            "status": "Model loaded and active" if voice_available else "Model not available: acoustic observations extracted without trained classification weights."
        },
        "face": {
            "name": "MobileViT Facial Emotion Model",
            "available": face_available,
            "path": face_path if face_available else None,
            "status": "Model loaded and active" if face_available else "Model not available: using Haar-cascade visual affect heuristic."
        },
        "summary": {
            "models_dir": models_dir,
            "hf_repo_id": settings.HF_MODEL_REPO_ID,
            "all_available": text_available and voice_available and face_available
        }
    }


def download_weights_if_configured():
    """
    If HF_MODEL_REPO_ID is set in environment, downloads missing model weights from Hugging Face Hub
    into settings.MODELS_DIR and caches them locally for subsequent runs.
    """
    repo_id = settings.HF_MODEL_REPO_ID
    if not repo_id:
        logger.info("[Weights] HF_MODEL_REPO_ID not configured; using local models directory or fallback heuristics.")
        return

    os.makedirs(settings.MODELS_DIR, exist_ok=True)
    logger.info(f"[Weights] Checking Hugging Face Hub repository: {repo_id}")
    
    try:
        from huggingface_hub import snapshot_download
        logger.info(f"[Weights] Downloading/verifying weights from {repo_id} to {settings.MODELS_DIR}...")
        snapshot_download(
            repo_id=repo_id,
            local_dir=settings.MODELS_DIR,
            local_dir_use_symlinks=False,
            ignore_patterns=["*.git*", "*.md"]
        )
        logger.info("[Weights] Model weights download/verification complete.")
    except Exception as e:
        logger.warning(f"[Weights] Could not download weights from Hugging Face Hub ({repo_id}): {e}")
        logger.warning("[Weights] System will proceed using clinical heuristic fallbacks.")


def log_startup_model_status():
    """Outputs clear startup diagnostic summary of ML models."""
    status = get_model_status()
    print("=" * 70)
    print(" MindScan Machine Learning Model Status Check")
    print("=" * 70)
    for modality, info in [("Text", status["text"]), ("Voice", status["voice"]), ("Face", status["face"])]:
        state = "[AVAILABLE]" if info["available"] else "[NOT FOUND - FALLBACK ACTIVE]"
        print(f" * {modality.ljust(6)}: {state} {info['name']}")
        print(f"          -> {info['status']}")
    print("=" * 70)
