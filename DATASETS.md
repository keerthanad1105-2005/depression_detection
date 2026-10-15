# MindScan Multimodal & Multilingual Datasets Registry

> **Clinical AI Honesty Notice:**
> The MindScan screening platform uses state-of-the-art multilingual foundation models:
> - **Acoustic Foundation & Affect:** `facebook/wav2vec2-xls-r-300m` (128 languages)
> - **Language-Independent Acoustic Biomarkers:** Pure DSP signal analysis (Librosa & SciPy)
> - **Text Foundation:** `xlm-roberta-base` (100 languages)
>
> **Notice on Voice Analysis:**
> *Voice analysis is language-independent across all spoken languages, but may have lower accuracy than English-only models trained specifically on English speech.*
> MindScan processes vocal features purely from audio acoustics—no speech-to-text, transcripts, or translations are generated, displayed, or stored.
> Foundation models provide cross-lingual acoustic representations. However, domain-specific clinical depression classification requires fine-tuning on annotated emotional and clinical speech datasets. **MindScan never fabricates or fakes model states: if the acoustic checkpoint is not yet fine-tuned, the system displays "Voice model not trained yet" rather than an unverified score.**

---

## 1. Speech & Audio Datasets

### A. Multilingual & Cross-Lingual Acoustic Sources

| Dataset Name | Languages Supported | Acoustic Properties & Biomarker Relevance | Status / License |
| :--- | :--- | :--- | :--- |
| **Mozilla Common Voice (Indic & Global Subsets)** | Hindi (50+ hrs), Tamil (100+ hrs), Kannada (15+ hrs), Telugu, Bengali, Marathi, Gujarati, Punjabi, Malayalam + global | Diverse crowd-sourced speech corpus with varied acoustics, noise levels, speaker demographics, and ages. Used for cross-lingual acoustic feature extraction and fine-tuning `facebook/wav2vec2-xls-r-300m`. | Open (CC-0) |
| **IITKGP-SEMSC (Simulated Emotion Speech Corpus)** | Hindi | Created by IIT Kharagpur. Audio recordings of native speakers portraying primary affective states (sadness, anger, happiness, neutral). Used for Indic acoustic depression biomarker calibration. | Academic Research Request |
| **IISc MILE Indic Speech Corpus** | Kannada, Tamil, Hindi | High-quality 16 kHz studio-recorded speech from Karnataka and Tamil Nadu speakers. Useful for prosodic pitch range ($f_0$) and speech rate calibration on Dravidian and Indo-Aryan phonology. | Research License |

### B. English-Only Speech Datasets

| Dataset Name | Languages | Acoustic Properties | Status |
| :--- | :--- | :--- | :--- |
| **RAVDESS (Ryerson Audio-Visual Database)** | **English ONLY** | 1,440 studio audio files from 24 professional North American actors portraying 8 emotion states (neutral, calm, happy, sad, angry, fearful, disgust, surprised). | Active in repo (`datasets/RAVDESS/`) |
| **CREMA-D (Crowd-sourced Emotional Multimodal Actors)** | **English ONLY** | 7,442 clips from 91 actors of diverse ethnicities, speaking 12 sentences in English with 6 emotion categories. | Open (Academic) |
| **DAIC-WOZ Audio Recordings** | **English ONLY** | High-fidelity audio recordings of clinical interviews with depressed patients. Standard benchmark for acoustic psychomotor slowing and pause latency analysis. | Restricted (USC ICT) |

---

## 2. Language-Independent Acoustic Biomarkers

MindScan extracts core acoustic biomarkers using digital signal processing (Librosa & SciPy) entirely from audio physics, without requiring speech recognition or vocabulary dependencies:

1. **Speech Rate (syllables/second):** Measured from voiced-segment timing and spectral onset envelope peaks (NOT word counts).
2. **Pause Length Ratio (%):** Measured by silence duration relative to total speech duration (RMS $< 0.005$).
3. **Pause Frequency (/min):** Number of silent intervals exceeding 250ms per minute of active speech.
4. **Pitch Variability ($f_0$ standard deviation):** Measured using the probabilistic YIN pitch tracking algorithm (`librosa.yin`).
5. **Vocal Energy (RMS Amplitude):** Measured by root-mean-square amplitude across voiced frames.

> **Crucial Clinical Principle:** These biomarkers measure physics-based physiological manifestations of psychomotor retardation (glottal tension, reduced subglottal pressure, respiratory flattening) and are **fundamentally language-independent**. Whether a speaker speaks English, Hindi, Kannada, or any other language, prolonged acoustic pauses, flat pitch variability, and reduced vocal energy reflect neuro-motor depressive slowing.

---

## 3. Text Datasets

### A. Multilingual & Cross-Lingual Text Sources

| Dataset Name | Languages Supported | Description & Mental Health Application | Status / License |
| :--- | :--- | :--- | :--- |
| **GoEmotions (Multilingual / Translated)** | English, Hindi, Tamil, Telugu, Bengali, Marathi + 10 global | 58,000 Reddit comments annotated for 27 distinct emotion categories (grief, sadness, optimism, anxiety, relief). Cross-lingual translated splits enable fine-tuning `xlm-roberta-base` on non-English affective texts. | Open (Apache 2.0) |
| **XNLI (Cross-lingual Natural Language Inference)** | 15 languages: English, Hindi, Urdu, Arabic, French, Spanish, Russian, etc. | 7,500 human-translated sentence pairs evaluated for cross-lingual affective alignment and sentiment hypothesis transfer. | Open (CC BY-NC 4.0) |
| **Hindi Mental Health & Sentiment Corpus** | Hindi (Devanagari script) | Academic social-media mental health dataset compiled by IIIT-Hyderabad / IIT-Patna, annotated for depression markers, distress, and suicidality. | Academic Research Use |
| **Multilingual Emotion Lexicon (NRC Emotion / EmoLex)** | 105+ languages including Hindi, Kannada, Tamil, Telugu, Bengali, Marathi, Gujarati, Punjabi, Urdu | Word-level affective association matrix for 8 basic emotions and positive/negative polarity. | Research & Non-commercial |

### B. English-Only Text Sources

| Dataset Name | Languages | Notes & Constraints | Status |
| :--- | :--- | :--- | :--- |
| **Reddit Cleaned Depression Dataset** | **English ONLY** | 7,731 cleaned posts from `r/depression` and control subreddits (`is_depression` binary label). Used to evaluate baseline RoBERTa / XLM-RoBERTa performance on English clinical narratives. | Active in repo (`datasets/reddit/`) |
| **DAIC-WOZ Transcripts (Distress Analysis Interview)** | **English ONLY** | Transcripts of semi-structured clinical interviews conducted by an animated virtual interviewer (Ellie) with veterans and psychiatric patients. Annotated with PHQ-8 ground-truth depression scores. | Restricted Academic (USC ICT) |

---

## 4. Retraining Steps for Acoustic Model

```bash
# Ensure Common Voice Indic and/or RAVDESS audio is organized in datasets/
python depression_detection/training/train_wav2vec2_voice.py
```
This loads `facebook/wav2vec2-xls-r-300m`, maps audio to 16 kHz mono tensors, and trains an 8-class emotional classification head. Trained weights are saved to `training/models/wav2vec2_xls_r_voice/`.

---

## 5. Model Architecture Summary

| Component | Target Model | Current Deployment Mode | Multilingual Support |
| :--- | :--- | :--- | :--- |
| **Acoustic Biomarkers** | Librosa DSP (Onsets, RMS, YIN) | Pure audio physics extraction | **Language-Independent (Any Language)** |
| **Vocal Affect** | `facebook/wav2vec2-xls-r-300m` | Multilingual foundation (Untrained checkpoint displays explicit status) | **128 languages (post fine-tuning)** |
| **Text Classifier** | `xlm-roberta-base` | Multilingual Indic Lexicon + Transformer | **100 languages (Devanagari, Dravidian, Latin)** |
| **Facial Affect** | MobileViT / AffectNet | Visual facial expression analysis | **Universal (Face geometry)** |
| **Multimodal Fusion** | Stacking + Clinical Prior | Robust Late Fusion | **Active across all modalities** |
