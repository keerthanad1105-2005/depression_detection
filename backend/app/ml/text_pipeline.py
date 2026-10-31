"""
MindScan Multilingual Text Pipeline.
Foundation Architecture: xlm-roberta-base (100-language cross-lingual language model).
Accepts typed text and voice transcripts in English, Hindi, Kannada, Tamil, Telugu,
Malayalam, Bengali, Marathi, Gujarati, Punjabi, Urdu, and other scripts.
Extracts influential/saliency keywords in any native Unicode script.
Includes language detection and honesty confidence discounting for non-English inputs.
"""

import os
import re
import torch
from typing import Dict, Any, List, Optional, Tuple
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from app.core.config import settings

# Unicode script ranges for automatic language/script identification
SCRIPT_PATTERNS = [
    (re.compile(r"[\u0900-\u097F]"), "hi", "Hindi (Devanagari)"),
    (re.compile(r"[\u0C80-\u0CFF]"), "kn", "Kannada"),
    (re.compile(r"[\u0B80-\u0BFF]"), "ta", "Tamil"),
    (re.compile(r"[\u0C00-\u0C7F]"), "te", "Telugu"),
    (re.compile(r"[\u0D00-\u0D7F]"), "ml", "Malayalam"),
    (re.compile(r"[\u0980-\u09FF]"), "bn", "Bengali"),
    (re.compile(r"[\u0A80-\u0AFF]"), "gu", "Gujarati"),
    (re.compile(r"[\u0A00-\u0A7F]"), "pa", "Punjabi (Gurmukhi)"),
    (re.compile(r"[\u0600-\u06FF]"), "ur", "Urdu (Perso-Arabic)"),
    (re.compile(r"[a-zA-Z]"), "en", "English (Latin)"),
]

def detect_text_language(text: str) -> Tuple[str, str]:
    """
    Detects language code and human-readable name from text based on script analysis.
    Defaults to ('en', 'English') if undetermined.
    """
    for regex, code, name in SCRIPT_PATTERNS:
        if regex.search(text):
            return code, name
    return "en", "English"


# Multilingual clinical affective lexicon (Depression & Positive markers)
MULTILINGUAL_DEP_LEXICON: Dict[str, float] = {
    # English
    "depressed": 0.95, "sad": 0.85, "hopeless": 0.92, "empty": 0.88,
    "worthless": 0.94, "suicide": 0.98, "kill": 0.90, "harm": 0.92,
    "tired": 0.70, "exhausted": 0.80, "cry": 0.78, "crying": 0.80,
    "alone": 0.75, "lonely": 0.82, "anxious": 0.76, "pain": 0.79,
    "hate": 0.74, "darkness": 0.82, "guilt": 0.80, "failure": 0.84,
    "sleep": 0.65, "insomnia": 0.78, "numb": 0.85, "die": 0.95,
    "useless": 0.88, "burden": 0.90, "pointless": 0.89, "distress": 0.84,

    # Hindi / Devanagari (उदासी, दर्द, अकेला, निराशा, बेकार, कमजोरी, आदि)
    "उदास": 0.88, "उदासी": 0.92, "दुख": 0.85, "दुखी": 0.86, "दर्द": 0.80,
    "अकेला": 0.82, "अकेलापन": 0.86, "निराश": 0.88, "निराशा": 0.90,
    "थकान": 0.72, "थका": 0.70, "रोना": 0.78, "रो": 0.75, "मौत": 0.92,
    "मरना": 0.94, "आत्महत्या": 0.98, "चिंता": 0.76, "बेचैनी": 0.78,
    "खालीपन": 0.88, "व्यर्थ": 0.85, "बोझ": 0.86, "हार": 0.82,
    "बेकार": 0.84, "कमजोरी": 0.75, "परेशान": 0.80, "परेशानी": 0.82,
    "तनाव": 0.76, "तकलीफ": 0.82, "नींद": 0.68,

    # Kannada (ಖಿನ್ನತೆ, ದುಃಖ, ನೋವು, ಒಂಟಿತನ, ಬೇಸರ, ಇತ್ಯಾದಿ)
    "ಖಿನ್ನತೆ": 0.94, "ದುಃಖ": 0.86, "ನೋವು": 0.82, "ಒಂಟಿ": 0.80,
    "ಒಂಟಿತನ": 0.88, "ಆಯಾಸ": 0.74, "ಸಾವು": 0.92, "ಸಾಯಲು": 0.95,
    "ಆತ್ಮಹತ್ಯೆ": 0.98, "ಚಿಂತೆ": 0.76, "ಅಳು": 0.78, "ಬೇಸರ": 0.82,
    "ಭಯ": 0.75, "ನಿರಾಶೆ": 0.90, "ಶೂನ್ಯ": 0.86, "ನಿದ್ರೆ": 0.68, "ಕಷ್ಟ": 0.80,

    # Tamil (மனச்சோர்வு, துன்பம், தனிமை, துக்கம், முதலியன)
    "மனச்சோர்வு": 0.95, "துன்பம்": 0.86, "துக்கம்": 0.86, "வலி": 0.82, "தனிமை": 0.88,
    "சோர்வு": 0.75, "சோர்வாக": 0.76, "இறப்பு": 0.92, "தற்கொலை": 0.98, "கவலை": 0.78,
    "அழுகை": 0.80, "ஏமாற்றம்": 0.84, "வெறுமை": 0.88, "தூக்கமின்மை": 0.78,

    # Telugu (విచారం, బాధ, ఒంటరితనం, మొదలైనవి)
    "విచారం": 0.88, "బాధ": 0.85, "ఒంటరితనం": 0.88, "అలసట": 0.72,
    "చావు": 0.92, "ఆత్మహత్య": 0.98, "ఆందోళన": 0.78, "ఏడుపు": 0.80,
    "నిరాశ": 0.90,

    # Malayalam (വിഷാദം, സങ്കടം, ഏകാന്തത)
    "വിഷാദം": 0.95, "സങ്കടം": 0.86, "വേദന": 0.82, "ഏകാന്തത": 0.88,
    "ക്ഷീണം": 0.74, "മരണം": 0.92, "ആത്മഹത്യ": 0.98,

    # Bengali (বিষণ্ণতা, কষ্ট, একাকীত্ব)
    "বিষণ্ণতা": 0.94, "কষ্ট": 0.85, "একাকীত্ব": 0.88, "ক্লান্তি": 0.74,
    "মৃত্যু": 0.92, "আত্মহত্যা": 0.98, "উদ্বেগ": 0.78, "হতাশা": 0.90,

    # Marathi (उदासीनता, दुःख, एकटेपणा)
    "उदासीनता": 0.92, "दुःख": 0.86, "एकटेपणा": 0.88, "थकवा": 0.72,
    "मृत्यू": 0.92, "काळजी": 0.76, "निराशा": 0.90,

    # Gujarati (ઉદાસી, દુઃખ, એકલતા)
    "ઉદાસી": 0.90, "દુઃખ": 0.86, "એકલતા": 0.88, "થાક": 0.72,
    "આત્મહત્યા": 0.98, "ચિંતા": 0.78,

    # Punjabi (ਉਦਾਸੀ, ਦੁੱਖ, ਇਕੱਲਾਪਣ)
    "ਉਦਾਸੀ": 0.90, "ਦੁੱਖ": 0.86, "ਦਰਦ": 0.82, "ਇਕੱਲਾਪਣ": 0.88,

    # Urdu (اداسی, غم, تنہائی, خودکشی)
    "اداسی": 0.90, "غم": 0.86, "درد": 0.82, "تنہائی": 0.88,
    "خودکشی": 0.98, "پریشانی": 0.78, "موت": 0.92,
}

MULTILINGUAL_POS_LEXICON: Dict[str, float] = {
    # English
    "happy": -0.80, "joy": -0.85, "great": -0.70, "good": -0.60,
    "excited": -0.85, "grateful": -0.80, "hopeful": -0.85, "love": -0.75,
    "peace": -0.70, "relaxed": -0.70, "optimistic": -0.80, "laugh": -0.75,
    # Hindi
    "खुश": -0.82, "खुशी": -0.85, "आनंद": -0.80, "अच्छा": -0.65,
    "आशा": -0.80, "शांति": -0.75, "हंसना": -0.70,
    # Kannada
    "ಖುಷಿ": -0.82, "ಸಂತೋಷ": -0.85, "ಆನಂದ": -0.80, "ಶಾಂತಿ": -0.75,
    # Tamil
    "மகிழ்ச்சி": -0.85, "சந்தோஷம்": -0.82, "அமைதி": -0.75,
    # Telugu
    "సంతోషం": -0.85, "ఆనందం": -0.82, "శాంతి": -0.75,
    # Malayalam
    "സന്തോഷം": -0.85, "ആനന്ദം": -0.82,
    # Bengali
    "আনন্দ": -0.85, "সুখ": -0.82, "শান্তি": -0.75,
    # Marathi / Gujarati / Urdu
    "आनंद": -0.82, "સંતોષ": -0.80, "خوشی": -0.85, "اطمینان": -0.75,
}


class TextPipeline:
    """
    Multilingual Text Affect and Depression Classifier.
    Target Foundation Model: xlm-roberta-base
    Provides native script tokenization, cross-lingual affective saliency,
    and confidence discounting for non-English evaluations.
    """
    FOUNDATION_MODEL = "xlm-roberta-base"

    def __init__(self):
        self.device = torch.device("cpu")
        self.model_path = os.path.join(settings.MODELS_DIR, "xlm_roberta_depression")
        # Legacy fallback if trained roberta model exists
        if not os.path.exists(self.model_path):
            legacy_path = os.path.join(settings.MODELS_DIR, "roberta_depression")
            if os.path.exists(legacy_path):
                self.model_path = legacy_path

        self.tokenizer = None
        self.model = None
        self._load_model()

    def _load_model(self):
        try:
            if os.path.exists(self.model_path):
                print(f"[TextPipeline] Loading fine-tuned model from {self.model_path}")
                self.tokenizer = AutoTokenizer.from_pretrained(self.model_path)
                self.model = AutoModelForSequenceClassification.from_pretrained(self.model_path)
                self.model.to(self.device)
                self.model.eval()
                print("[TextPipeline] Fine-tuned multilingual model successfully initialized.")
            else:
                print(f"[TextPipeline] Model path not found: {self.model_path}.")
                print(f"[TextPipeline] Multilingual foundation target: {self.FOUNDATION_MODEL}.")
                print("[TextPipeline] Using multilingual Indic-aware clinical lexicon for zero-shot affective evaluation.")
        except Exception as e:
            print(f"[TextPipeline] Error loading model: {e}")

    def analyze(self, text: str, forced_language: Optional[str] = None) -> Dict[str, Any]:
        text_clean = text.strip()
        
        # Unicode-safe word tokenization that preserves Indic (Devanagari, Tamil, Kannada, etc.), Latin, and Perso-Arabic scripts
        words = [w.strip() for w in re.split(r'[\s\d\.,!?;:\"\'\(\)\[\]{}—–\-_/\\।|]+', text_clean) if w.strip()]
        word_count = len(words)

        # Detect language / script
        detected_lang_code, detected_lang_name = detect_text_language(text_clean)
        if forced_language and forced_language != "auto":
            detected_lang_code = forced_language

        is_non_english = (detected_lang_code != "en")

        saliency_tokens = []
        for word in words:
            w_lower = word.lower()
            matched = False
            # 1. Exact match
            if w_lower in MULTILINGUAL_DEP_LEXICON:
                saliency_tokens.append({
                    "word": word,
                    "weight": MULTILINGUAL_DEP_LEXICON[w_lower],
                    "sentiment": "negative"
                })
                matched = True
            elif w_lower in MULTILINGUAL_POS_LEXICON:
                saliency_tokens.append({
                    "word": word,
                    "weight": abs(MULTILINGUAL_POS_LEXICON[w_lower]),
                    "sentiment": "positive"
                })
                matched = True

            # 2. Substring / Root match for inflected Indic words
            if not matched and len(word) >= 3:
                for lex_key, weight in MULTILINGUAL_DEP_LEXICON.items():
                    if len(lex_key) >= 3 and (lex_key in w_lower or w_lower in lex_key):
                        saliency_tokens.append({
                            "word": word,
                            "weight": weight,
                            "sentiment": "negative"
                        })
                        matched = True
                        break
                if not matched:
                    for lex_key, weight in MULTILINGUAL_POS_LEXICON.items():
                        if len(lex_key) >= 3 and (lex_key in w_lower or w_lower in lex_key):
                            saliency_tokens.append({
                                "word": word,
                                "weight": abs(weight),
                                "sentiment": "positive"
                            })
                            break

        # Deduplicate & rank top influential words (preserved in original native script)
        seen = set()
        unique_tokens = []
        for item in sorted(saliency_tokens, key=lambda x: x["weight"], reverse=True):
            if item["word"].lower() not in seen:
                seen.add(item["word"].lower())
                unique_tokens.append(item)
        top_tokens = unique_tokens[:8]

        # ML model inference if fine-tuned weights exist
        if self.model and self.tokenizer:
            try:
                inputs = self.tokenizer(
                    text_clean,
                    return_tensors="pt",
                    truncation=True,
                    padding=True,
                    max_length=128
                ).to(self.device)

                with torch.no_grad():
                    outputs = self.model(**inputs)
                    probs = torch.softmax(outputs.logits, dim=1)
                    ml_prob = float(probs[0][1].item())

                # For non-English inputs, blend model probability with native script clinical affect score
                if is_non_english:
                    heuristic_prob = self._heuristic_prob(words)
                    depression_prob = 0.35 * ml_prob + 0.65 * heuristic_prob
                else:
                    depression_prob = ml_prob
            except Exception as e:
                print(f"[TextPipeline] Inference error: {e}")
                depression_prob = self._heuristic_prob(words)
        else:
            depression_prob = self._heuristic_prob(words)

        # Risk band categorization
        if depression_prob < 0.25:
            risk_band = "Minimal"
            summary = "Text exhibits balanced affective tone with minimal depressive linguistic markers."
        elif depression_prob < 0.50:
            risk_band = "Mild"
            summary = "Text contains occasional cognitive vulnerability and subtle depressive phrasing."
        elif depression_prob < 0.70:
            risk_band = "Moderate"
            summary = "Noticeable frequency of dysphoric themes, negative self-referential words, and distress."
        elif depression_prob < 0.85:
            risk_band = "Moderately Severe"
            summary = "High prevalence of hopelessness, worthlessness, and pervasive depressive vocabulary."
        else:
            risk_band = "Severe"
            summary = "Extremely high density of acute despair and severe depressive linguistic patterns."

        # Calibrate confidence: For non-English input, lower confidence and add mandatory honesty note
        base_confidence = 0.88 if self.model else 0.80
        accuracy_note = None
        if is_non_english:
            base_confidence = round(base_confidence * 0.80, 2)
            accuracy_note = "Accuracy may be lower for this language."

        return {
            "depression_probability": round(depression_prob, 4),
            "risk_band": risk_band,
            "confidence_score": base_confidence,
            "word_count": word_count,
            "top_saliency_tokens": top_tokens,
            "summary_sentence": summary,
            "detected_language": detected_lang_code,
            "language_name": detected_lang_name,
            "is_non_english": is_non_english,
            "accuracy_note": accuracy_note,
            "model_name": self.FOUNDATION_MODEL
        }

    def _heuristic_prob(self, words: List[str]) -> float:
        if not words:
            return 0.10
        dep_score = 0.0
        pos_score = 0.0
        for w in words:
            w_lower = w.lower().strip(".,!?;:\"'()[]{}")
            if not w_lower:
                continue
            found_dep = MULTILINGUAL_DEP_LEXICON.get(w_lower)
            if found_dep is None and len(w_lower) >= 4:
                for k, v in MULTILINGUAL_DEP_LEXICON.items():
                    if len(k) >= 4 and (k == w_lower or k in w_lower):
                        found_dep = abs(v)
                        break
            if found_dep is not None:
                dep_score += abs(found_dep)

            found_pos = MULTILINGUAL_POS_LEXICON.get(w_lower)
            if found_pos is None and len(w_lower) >= 4:
                for k, v in MULTILINGUAL_POS_LEXICON.items():
                    if len(k) >= 4 and (k == w_lower or k in w_lower):
                        found_pos = abs(v)
                        break
            if found_pos is not None:
                pos_score += abs(found_pos)

        # Baseline offset: -2.2 gives sigmoid(-2.2) ≈ 0.10 (Minimal depression baseline)
        raw = -2.2 + (dep_score * 1.5) - (pos_score * 1.5)
        prob = 1.0 / (1.0 + torch.exp(-torch.tensor(raw)).item())
        return min(max(prob, 0.05), 0.95)


text_pipeline = TextPipeline()
