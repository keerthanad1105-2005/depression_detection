
# MindScan — Multimodal Depression Detection System

An enterprise-grade, clinical-grade multimodal screening platform utilizing text sentiment, facial affect geometry, and **language-independent acoustic speech analysis** to assess depression risk indicators.

---

## 🌟 Architecture Overview

MindScan integrates three primary diagnostic modalities through late multimodal fusion:

1. **Text Analysis:**
   - Evaluates linguistic sentiment, cognitive distress patterns, and psychiatric markers using `xlm-roberta-base`.
   - Incorporates multilingual lexicons covering 100+ languages (English, Hindi, Kannada, Tamil, etc.).

2. **Facial Affect Analysis:**
   - Evaluates facial expression geometry, eye-contact deviations, and affective flatness using MobileViT / AffectNet.
   - Operates universally across all demographics without language dependence.

3. **Language-Independent Voice Analysis:**
   - **Pure Audio-Only Pipeline:** Operates directly on raw audio waveforms without speech-to-text, transcriptions, or translations.
   - **Physics-Based Acoustic Biomarkers:**
     - **Speech Rate (syllables/second):** Derived from voiced-segment timing via acoustic onset envelopes (not words).
     - **Pause Length Ratio (%):** Ratio of silent intervals to total duration.
     - **Pause Frequency (/min):** Frequency of silence boundaries exceeding 250ms per minute.
     - **Pitch Variability ($f_0$ std):** Fundamental frequency dispersion measured via probabilistic YIN tracking.
     - **Vocal Energy (RMS):** Root-mean-square amplitude across voiced segments.
   - **Multilingual Foundation Model:** Configured for `facebook/wav2vec2-xls-r-300m` (pretrained across 128 languages).
   - **Clinical Honesty Guarantee:** If the fine-tuned XLS-R weights are not present, MindScan states `"Voice model not trained yet"` instead of generating synthetic or unverified scores.
   - **Zero-Retention Guarantee:** Audio recordings are stored in memory and deleted immediately after processing unless the user explicitly checks the opt-in checkbox.

> **Important Clinical Notice:**  
> *Voice analysis is language-independent across all spoken languages, but may have lower accuracy than English-only models trained specifically on English speech.*

---

## 🛠️ Tech Stack

- **Backend:** FastAPI, PyTorch, Librosa, SciPy, SoundFile, OpenCV, ReportLab, SQLite, Uvicorn
- **Frontend:** Vanilla HTML5, CSS3 (Glassmorphism design tokens), Vanilla JavaScript (No frameworks)
- **Speech Processing:** FFmpeg (16 kHz mono conversion), Librosa acoustic feature extraction (No Whisper / STT dependencies)

---

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.10+
- FFmpeg installed and accessible in system PATH

### 2. Backend Setup
```bash
cd backend
python -m venv venv
venv\Scripts\activate   # On Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### 3. Frontend Setup
```bash
cd frontend
python -m http.server 3000
```
Open `http://localhost:

/login.html` in your browser.

---

## 🔒 Privacy & Compliance

- **Zero Audio Retention by Default:** Audio files are purged from disk immediately upon analysis completion.
- **No Speech Transcription:** Audio is analyzed purely as a physical acoustic vibration signal. No words, transcripts, or conversations are stored or logged.
- **HIPAA / GDPR Ready:** Role-based access control (User, Clinician, Admin) with complete audit logging.
