import numpy as np
import librosa
from typing import Dict, Any, Tuple, Optional

def extract_acoustic_features(audio_path: str, target_sr: int = 16000) -> Tuple[Dict[str, float], Optional[str]]:
    """
    Loads audio file, validates minimum length & noise, and computes:
    - speech_rate_syl_per_sec (syllables / voiced sec)
    - pause_length_ratio (unvoiced/pause time / total duration)
    - pitch_variability_f0_std (F0 pitch standard deviation in Hz)
    - energy_rms_mean (average RMS energy)
    """
    try:
        y, sr = librosa.load(audio_path, sr=target_sr, mono=True)
    except Exception as e:
        return {}, f"Could not decode audio file: {str(e)}"
        
    # Trim leading and trailing silence
    try:
        y_trimmed, _ = librosa.effects.trim(y, top_db=25)
    except Exception:
        y_trimmed = y

    duration = librosa.get_duration(y=y_trimmed, sr=sr)
    if duration < 20.0:
        return {}, f"Audio recording is too short ({duration:.1f}s). Minimum required duration is 20 seconds (recommended 30-60 seconds). Please speak for at least 20 seconds."
        
    rms = librosa.feature.rms(y=y_trimmed)[0]
    mean_rms = float(np.mean(rms))
    if mean_rms < 0.001:
        return {}, "Audio is too quiet or near silent. Please check your microphone volume, speak closer to the mic, and re-record."
        
    # Non-silent intervals check to reject mostly silent recordings
    intervals = librosa.effects.split(y_trimmed, top_db=25)
    if len(intervals) == 0:
        return {}, "Audio contains no detectable speech. Please re-record and speak clearly."
    voiced_duration = sum((end - start) for start, end in intervals) / sr
    if voiced_duration < 8.0 or (voiced_duration / max(duration, 0.1)) < 0.25:
        return {}, "Audio is mostly silent or contains too little speech. Please provide at least 20 seconds of continuous speech."

    # Check for excessive static or clipping noise
    if mean_rms > 0.45:
        return {}, "Audio contains excessive background noise or distortion. Please move to a quiet environment, lower your input gain, and re-record."

    total_pause_duration = max(0.0, duration - voiced_duration)
    pause_ratio = min(max(total_pause_duration / max(duration, 0.1), 0.0), 1.0)
    pause_count = max(0, len(intervals) - 1)
    pause_freq_per_min = round(pause_count / max(duration / 60.0, 0.2), 1)
    
    # Syllables estimation via onset envelope peaks (timing-based, language-independent)
    onset_env = librosa.onset.onset_strength(y=y_trimmed, sr=sr)
    peaks = librosa.util.peak_pick(onset_env, pre_max=3, post_max=3, pre_avg=3, post_avg=5, delta=0.5, wait=10)
    syllable_count = max(len(peaks), 1)
    speech_rate = syllable_count / max(voiced_duration, 0.5)
    
    # Pitch (F0) estimation using pyin with speech range (75-400 Hz)
    try:
        import scipy.signal
        f0, voiced_flag, voiced_probs = librosa.pyin(
            y_trimmed,
            fmin=75.0,
            fmax=400.0,
            sr=sr
        )
        # Strictly ignore unvoiced frames and NaNs within speech range
        voiced_mask = (voiced_flag == True) & (~np.isnan(f0)) & (f0 >= 75.0) & (f0 <= 400.0)
        f0_voiced = f0[voiced_mask]
        
        if len(f0_voiced) > 5:
            # Apply 5-point median filter to eliminate transient octave-jump artifacts
            f0_smooth = scipy.signal.medfilt(f0_voiced, kernel_size=5)
            med_f0 = float(np.median(f0_smooth))
            if med_f0 > 0:
                # Exclude octave jumps beyond 0.55x to 1.8x of median speech pitch
                f0_filtered = f0_smooth[(f0_smooth >= med_f0 * 0.55) & (f0_smooth <= med_f0 * 1.8)]
            else:
                f0_filtered = f0_smooth
            if len(f0_filtered) < 5:
                f0_filtered = f0_smooth

            pitch_std = float(np.std(f0_filtered))
            # Standard deviation in semitones relative to 100 Hz reference
            semitones = 12.0 * np.log2(f0_filtered / 100.0)
            pitch_std_st = float(np.std(semitones))
        else:
            pitch_std = 20.0
            pitch_std_st = 2.0
    except Exception:
        pitch_std = 22.0
        pitch_std_st = 2.2

    features = {
        "speech_rate_syl_per_sec": round(float(speech_rate), 2),
        "pause_length_ratio": round(float(pause_ratio), 3),
        "pause_frequency_per_min": pause_freq_per_min,
        "pitch_variability_f0_std": round(float(pitch_std), 1),
        "pitch_variability_semitones": round(float(pitch_std_st), 2),
        "energy_rms_mean": round(float(mean_rms), 4)
    }
    
    return features, None
