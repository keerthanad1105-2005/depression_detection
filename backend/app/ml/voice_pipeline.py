import os
import torch
import librosa
from typing import Dict, Any, Tuple, Optional
from transformers import Wav2Vec2Processor, Wav2Vec2ForSequenceClassification
from app.core.config import settings
from app.ml.acoustic_features import extract_acoustic_features

import subprocess
import shutil

def convert_audio_to_16k_mono_wav(input_path: str, output_path: str) -> Tuple[bool, Optional[str]]:
    """
    Converts any audio file (WebM, OGG, MP3, WAV, M4A) to 16 kHz mono 16-bit PCM WAV using FFmpeg.
    """
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        return False, "FFmpeg is not installed or not in PATH. Please install FFmpeg on Windows using: 'winget install Gyan.FFmpeg'"
    
    cmd = [
        ffmpeg_bin, "-y", "-i", input_path,
        "-ar", "16000", "-ac", "1",
        "-c:a", "pcm_s16le", output_path
    ]
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if proc.returncode != 0:
            err = proc.stderr.decode("utf-8", errors="ignore")
            return False, f"FFmpeg audio conversion error: {err[:200]}"
        return True, None
    except Exception as e:
        return False, f"Could not execute FFmpeg: {str(e)}"

class VoicePipeline:
    """
    Multilingual Vocal Biomarker and Acoustic Pipeline.
    Acoustic Model: facebook/wav2vec2-xls-r-300m (Multilingual 128-language pre-trained XLS-R foundation).
    Note: Requires retraining on task-specific multilingual depression/emotion speech datasets.
    Biomarkers (Speech Rate, Pause Ratio, Pitch Variability, Energy RMS) remain purely language-independent.
    """
    ACOUSTIC_MODEL_ID = "facebook/wav2vec2-xls-r-300m"

    def __init__(self):
        self.device = torch.device("cpu")
        # Multilingual XLS-R checkpoint only (no English-only wav2vec2-base fallback)
        self.model_path = os.path.join(settings.MODELS_DIR, "wav2vec2_xls_r_voice")
        self.processor = None
        self.model = None
        self.labels = [
            "neutral", "calm", "happy", "sad",
            "angry", "fearful", "disgust", "surprised"
        ]
        self._load_model()
        
    def _load_model(self):
        try:
            if os.path.exists(self.model_path):
                print(f"[VoicePipeline] Loading multilingual XLS-R model from {self.model_path}")
                self.processor = Wav2Vec2Processor.from_pretrained(self.model_path)
                self.model = Wav2Vec2ForSequenceClassification.from_pretrained(self.model_path)
                self.model.to(self.device)
                self.model.eval()
                print("[VoicePipeline] XLS-R acoustic model successfully initialized.")
            else:
                print(f"[VoicePipeline] Model checkpoint not found at {self.model_path}.")
                print(f"[VoicePipeline] Multilingual foundation target: {self.ACOUSTIC_MODEL_ID}.")
                print("[VoicePipeline] Model status: 'Voice model not trained yet'.")
        except Exception as e:
            print(f"[VoicePipeline] Error loading model: {e}")

    def analyze(
        self,
        audio_path: str
    ) -> Tuple[Dict[str, Any], Optional[str]]:
        """
        Language-independent audio-only acoustic biomarker and vocal affect analysis.
        Uses voiced-segment timing, pause duration & frequency, pitch variability,
        and RMS energy, evaluated with the multilingual XLS-R foundation model.
        """
        # 1. Extract acoustic features & validate quality (min 20s, silence trimming, RMS check, noise check)
        acoustic_features, error_msg = extract_acoustic_features(audio_path)
        if error_msg:
            return {}, error_msg
            
        speech_rate = acoustic_features.get("speech_rate_syl_per_sec", 3.0)
        pause_ratio = acoustic_features.get("pause_length_ratio", 0.25)
        pause_freq = acoustic_features.get("pause_frequency_per_min", 0.0)
        pitch_std = acoustic_features.get("pitch_variability_f0_std", 25.0)
        energy_mean = acoustic_features.get("energy_rms_mean", 0.05)

        detected_emotion = "unclassified"
        is_model_trained = (self.model is not None and self.processor is not None)

        # 2. Multilingual XLS-R-300M inference
        if is_model_trained:
            try:
                import soundfile as sf
                speech, sr = sf.read(audio_path)
                if speech.ndim > 1:
                    speech = np.mean(speech, axis=1)
                speech = speech.astype(np.float32)
                inputs = self.processor(speech, sampling_rate=16000, return_tensors="pt")
                with torch.no_grad():
                    logits = self.model(**inputs).logits
                    probs = torch.softmax(logits, dim=1)[0]
                    pred_idx = torch.argmax(probs).item()
                    detected_emotion = self.labels[pred_idx] if pred_idx < len(self.labels) else "neutral"
                    
                if detected_emotion in ["sad", "fearful"]:
                    emotion_dep_prob = float(probs[pred_idx].item()) * 0.90
                elif detected_emotion in ["angry", "disgust"]:
                    emotion_dep_prob = 0.65
                elif detected_emotion in ["calm", "neutral"]:
                    emotion_dep_prob = 0.35
                elif detected_emotion in ["happy", "surprised"]:
                    emotion_dep_prob = 0.15
                else:
                    emotion_dep_prob = 0.25
            except Exception as e:
                print(f"[VoicePipeline] XLS-R inference error: {e}")
                detected_emotion = "neutral"
                emotion_dep_prob = 0.25

            # Acoustic biomarker clinical score
            acoustic_score = 0.0
            if pitch_std < 18.0:
                acoustic_score += 0.30
            elif pitch_std < 25.0:
                acoustic_score += 0.15
                
            if pause_ratio > 0.35:
                acoustic_score += 0.35
            elif pause_ratio > 0.25:
                acoustic_score += 0.20
                
            if speech_rate < 2.8:
                acoustic_score += 0.25
                
            if energy_mean < 0.02:
                acoustic_score += 0.10

            fused_voice_prob = min(max(0.60 * emotion_dep_prob + 0.40 * acoustic_score, 0.05), 0.95)
            voice_score_pct = round(float(fused_voice_prob * 100), 2)
            model_status = "trained"

            if fused_voice_prob < 0.25:
                risk_band = "Minimal"
            elif fused_voice_prob < 0.50:
                risk_band = "Mild"
            elif fused_voice_prob < 0.70:
                risk_band = "Moderate"
            elif fused_voice_prob < 0.85:
                risk_band = "Moderately Severe"
            else:
                risk_band = "Severe"
        else:
            # Model not trained yet - never fake results!
            fused_voice_prob = None
            voice_score_pct = None
            model_status = "Voice model not trained yet"
            risk_band = "Voice model not trained yet"
            detected_emotion = "unclassified"

        result = {
            "depression_probability": round(float(fused_voice_prob), 4) if fused_voice_prob is not None else None,
            "voice_score": voice_score_pct,
            "risk_band": risk_band,
            "detected_emotion": detected_emotion,
            "model_status": model_status,
            "model_name": self.ACOUSTIC_MODEL_ID,
            "speech_rate": round(float(speech_rate), 2),
            "pause_length": f"{round(pause_ratio * 100, 1)}%",
            "pause_frequency": f"{pause_freq} / min",
            "pitch_variability": f"{round(pitch_std, 1)} Hz ({round(float(acoustic_features.get('pitch_variability_semitones', 2.0)), 1)} st)",
            "pitch_variability_hz": round(float(pitch_std), 1),
            "pitch_variability_semitones": round(float(acoustic_features.get("pitch_variability_semitones", 2.0)), 1),
            "energy": round(float(energy_mean), 4),
            "acoustic_features": acoustic_features
        }
        return result, None

voice_pipeline = VoicePipeline()
