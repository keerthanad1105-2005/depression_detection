import os
import time
import uuid
import shutil
import logging
from collections import defaultdict
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, Request, Depends, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import engine, SessionLocal, get_db
from app.db.base import Base
import app.models  # Ensure all models are registered
from app.models.user import User
from app.models.history import HistoryRecord
from app.api.v1 import api_router
from app.api.deps import get_current_user
from app.ml.weight_downloader import (
    download_weights_if_configured,
    log_startup_model_status,
    get_model_status,
)

# Structured Logging Setup
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("mindscan.backend")

# Initialize tables (creates any new tables if not already present)
Base.metadata.create_all(bind=engine)

# Configure documentation endpoints based on DEBUG / ENVIRONMENT
docs_enabled = settings.DEBUG or settings.ENVIRONMENT != "production"

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="MindScan: Multimodal Clinical Screening Support Platform (Text, Voice, Face & PHQ-9 Fusion)",
    version="1.0.0",
    docs_url="/docs" if docs_enabled else None,
    redoc_url="/redoc" if docs_enabled else None
)

# -----------------------------------------------------------------------------
# Production Security Headers Middleware
# -----------------------------------------------------------------------------
@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if settings.ENVIRONMENT == "production" or settings.SECURE_COOKIES:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

# -----------------------------------------------------------------------------
# Structured Request Logging Middleware
# -----------------------------------------------------------------------------
@app.middleware("http")
async def request_logger_middleware(request: Request, call_next):
    start_time = time.time()
    client_ip = request.client.host if request.client else "unknown"
    response = await call_next(request)
    duration_ms = round((time.time() - start_time) * 1000, 2)
    logger.info(f"{client_ip} - \"{request.method} {request.url.path}\" {response.status_code} ({duration_ms}ms)")
    return response

# -----------------------------------------------------------------------------
# IP Rate Limiting Middleware (Sliding Window per IP)
# -----------------------------------------------------------------------------
RATE_LIMIT_WINDOW = 60.0  # seconds
MAX_REQUESTS_PER_MINUTE = 120
_ip_request_timestamps = defaultdict(list)

@app.middleware("http")
async def rate_limiting_middleware(request: Request, call_next):
    path = request.url.path
    # Exempt health checks and documentation assets from rate limiting
    if path in ("/health", "/api/v1/health", "/docs", "/redoc", "/openapi.json") or path.startswith("/static"):
        return await call_next(request)

    client_ip = request.client.host if request.client else "127.0.0.1"
    now = time.time()
    cutoff = now - RATE_LIMIT_WINDOW

    timestamps = [t for t in _ip_request_timestamps[client_ip] if t > cutoff]
    if len(timestamps) >= MAX_REQUESTS_PER_MINUTE:
        logger.warning(f"Rate limit exceeded for IP: {client_ip} on {path}")
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests. Rate limit of 120 requests/minute exceeded. Please slow down."},
            headers={"Retry-After": "60"}
        )
    timestamps.append(now)
    _ip_request_timestamps[client_ip] = timestamps
    return await call_next(request)

# -----------------------------------------------------------------------------
# Production CORS Setup
# -----------------------------------------------------------------------------
default_origins = [
    "https://mindscan-frontend.onrender.com",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:8000",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:8000"
]

cors_origins_set = set(default_origins)
if isinstance(settings.CORS_ORIGINS, list):
    for o in settings.CORS_ORIGINS:
        if o and o != "*":
            cors_origins_set.add(o.rstrip("/"))
elif isinstance(settings.CORS_ORIGINS, str):
    for o in settings.CORS_ORIGINS.split(","):
        o_clean = o.strip()
        if o_clean and o_clean != "*":
            cors_origins_set.add(o_clean.rstrip("/"))

if settings.FRONTEND_URL:
    cors_origins_set.add(settings.FRONTEND_URL.rstrip("/"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(cors_origins_set),
    allow_origin_regex=r"^https:\/\/.*\.onrender\.com$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# -----------------------------------------------------------------------------
# Health Check Endpoints
# -----------------------------------------------------------------------------
@app.get("/health")
@app.get("/api/v1/health")
def health_check():
    db_ok = True
    db_message = "connected"
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        db_ok = False
        db_message = f"unhealthy: {str(e)}"

    ffmpeg_available = shutil.which("ffmpeg") is not None
    model_status = get_model_status()
    overall_status = "healthy" if db_ok else "degraded"

    return JSONResponse(
        status_code=200 if db_ok else 503,
        content={
            "status": overall_status,
            "environment": settings.ENVIRONMENT,
            "version": "1.0.0",
            "timestamp": datetime.utcnow().isoformat(),
            "database": db_message,
            "ffmpeg": "available" if ffmpeg_available else "missing",
            "models": model_status
        }
    )

# Include API Router
app.include_router(api_router, prefix=settings.API_V1_STR)

# -----------------------------------------------------------------------------
# Startup Checks & Initialization
# -----------------------------------------------------------------------------
@app.on_event("startup")
def startup_checks():
    # 1. Check FFmpeg installation
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        logger.info(f"[Startup] FFmpeg verified in PATH: {ffmpeg_path}")
    else:
        logger.warning("[Startup] WARNING: FFmpeg was not found in PATH! Audio conversion requires FFmpeg.")

    # 2. Check and seed default demo accounts
    db = SessionLocal()
    try:
        users_to_seed = [
            ("admin@mindscan.health", "admin", "Admin@12345", "System Administrator", "Admin"),
            ("dr.sharma@mindscan.health", "dr_sharma", "Clinician@12345", "Dr. A. Sharma (Psychiatrist)", "Clinician"),
            ("user@mindscan.health", "jane_doe", "User@12345", "Jane Doe", "User")
        ]
        for email, uname, pwd, name, role in users_to_seed:
            existing = db.query(User).filter(User.email == email).first()
            if not existing:
                u = User(
                    email=email,
                    username=uname,
                    password_hash=hash_password(pwd),
                    full_name=name,
                    role=role,
                    is_active=True,
                    email_verified=True
                )
                db.add(u)
            elif not existing.username:
                existing.username = uname
        db.commit()
        logger.info("[Startup] Verified default demo accounts initialized.")
    except Exception as e:
        logger.error(f"[Startup] Error seeding demo accounts: {e}")
    finally:
        db.close()

    # 3. Model weights check & download
    try:
        download_weights_if_configured()
        log_startup_model_status()
    except Exception as e:
        logger.error(f"[Startup] Error in model weights initialization: {e}")


import sqlite3
import cv2
import numpy as np
from datetime import datetime
from typing import Optional
from fastapi import UploadFile, File, Form, HTTPException
from app.ml.text_pipeline import text_pipeline
from app.ml.voice_pipeline import voice_pipeline, convert_audio_to_16k_mono_wav
from app.ml.face_pipeline import face_pipeline

DEPRESSION_DB_PATH = os.path.join(settings.WORKSPACE_DIR, "depression_detection", "backend", "depression.db")
if not os.path.exists(DEPRESSION_DB_PATH):
    DEPRESSION_DB_PATH = os.path.join(settings.BASE_DIR, "depression.db")

def get_depression_db():
    conn = sqlite3.connect(DEPRESSION_DB_PATH, check_same_thread=False)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS history(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        analysis_type TEXT,
        score REAL,
        level TEXT,
        date TEXT,
        dob TEXT,
        age TEXT,
        gender TEXT,
        occupation TEXT,
        symptoms TEXT,
        duration TEXT,
        language TEXT,
        transcript TEXT
    )
    """)
    # Automatic migration: ensure newly added columns exist in older database files
    cols = [c[1] for c in conn.execute("PRAGMA table_info(history)").fetchall()]
    migration_columns = [
        ("dob", "TEXT"),
        ("age", "TEXT"),
        ("gender", "TEXT"),
        ("occupation", "TEXT"),
        ("symptoms", "TEXT"),
        ("duration", "TEXT"),
        ("language", "TEXT"),
        ("transcript", "TEXT"),
        ("is_test", "INTEGER DEFAULT 0"),
        ("is_reviewed", "INTEGER DEFAULT 0"),
        ("user_id", "TEXT"),
        ("user_email", "TEXT")
    ]
    for col, ctype in migration_columns:
        if col not in cols:
            try:
                conn.execute(f"ALTER TABLE history ADD COLUMN {col} {ctype}")
            except Exception as e:
                print(f"[DB Migration] Add column {col}: {e}")
    conn.commit()
    return conn

# =====================================================================
# Compatibility Endpoints (for Frontend Dashboard & History)
# =====================================================================

@app.get("/admin-dashboard")
def legacy_admin_dashboard(include_test_data: bool = False):
    from app.api.v1.admin import get_admin_dashboard_stats
    db = SessionLocal()
    try:
        return get_admin_dashboard_stats(include_test_data=include_test_data, db=db)
    finally:
        db.close()

@app.get("/history")
def legacy_get_history(current_user: Optional[User] = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user:
        raise HTTPException(
            status_code=401,
            detail="Authentication required to access history records."
        )

    # 1. Primary: SQLAlchemy HistoryRecord query (PostgreSQL & SQLite)
    try:
        query = db.query(HistoryRecord)
        if current_user.role == "User":
            user_id_str = str(current_user.id)
            user_email = current_user.email
            full_name = current_user.full_name or ""
            query = query.filter(
                (HistoryRecord.user_id == user_id_str) |
                (HistoryRecord.user_email == user_email) |
                ((HistoryRecord.user_id == None) & ((HistoryRecord.username == user_email) | (HistoryRecord.username == full_name)))
            )
        records = query.order_by(HistoryRecord.id.desc()).all()
        if records or not settings.DATABASE_URL.startswith("sqlite"):
            return [
                {
                    "id": r.id,
                    "username": r.username,
                    "analysis_type": r.analysis_type,
                    "score": r.score,
                    "level": r.level,
                    "date": r.date,
                    "dob": r.dob,
                    "age": r.age,
                    "gender": r.gender,
                    "occupation": r.occupation,
                    "symptoms": r.symptoms,
                    "duration": r.duration,
                    "user_id": r.user_id,
                    "user_email": r.user_email
                }
                for r in records
            ]
    except Exception as e:
        logger.warning(f"[History] HistoryRecord query fallback: {e}")

    # 2. Local fallback to sqlite connection
    conn = get_depression_db()
    cursor = conn.cursor()
    if current_user.role == "User":
        cursor.execute("""
            SELECT id, username, analysis_type, score, level, date, dob, age, gender, occupation, symptoms, duration, user_id, user_email
            FROM history
            WHERE user_id = ? OR user_email = ? OR (user_id IS NULL AND (username = ? OR username = ?))
            ORDER BY id DESC
        """, (str(current_user.id), current_user.email, current_user.email, current_user.full_name or ""))
    else:
        cursor.execute("""
            SELECT id, username, analysis_type, score, level, date, dob, age, gender, occupation, symptoms, duration, user_id, user_email
            FROM history
            ORDER BY id DESC
        """)

    rows = cursor.fetchall()
    return [
        {
            "id": row[0],
            "username": row[1],
            "analysis_type": row[2],
            "score": row[3],
            "level": row[4],
            "date": row[5],
            "dob": row[6] if len(row) > 6 and row[6] else None,
            "age": row[7] if len(row) > 7 and row[7] else None,
            "gender": row[8] if len(row) > 8 and row[8] else None,
            "occupation": row[9] if len(row) > 9 and row[9] else None,
            "symptoms": row[10] if len(row) > 10 and row[10] else None,
            "duration": row[11] if len(row) > 11 and row[11] else None,
            "user_id": row[12] if len(row) > 12 and row[12] else None,
            "user_email": row[13] if len(row) > 13 and row[13] else None
        }
        for row in rows
    ]

@app.delete("/history/all")
@app.delete("/history-all")
def legacy_delete_all_user_history(current_user: Optional[User] = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
        
    deleted_count = 0
    try:
        query = db.query(HistoryRecord)
        if current_user.role == "User":
            query = query.filter(
                (HistoryRecord.user_id == str(current_user.id)) |
                (HistoryRecord.user_email == current_user.email) |
                ((HistoryRecord.user_id == None) & ((HistoryRecord.username == current_user.email) | (HistoryRecord.username == (current_user.full_name or ""))))
            )
        else:
            query = query.filter(
                (HistoryRecord.user_id == str(current_user.id)) |
                (HistoryRecord.user_email == current_user.email)
            )
        deleted_count = query.delete(synchronize_session=False)
        db.commit()
    except Exception as e:
        logger.warning(f"[History] HistoryRecord deletion warning: {e}")

    # Also clean up local SQLite if active
    if settings.DATABASE_URL.startswith("sqlite"):
        try:
            conn = get_depression_db()
            cursor = conn.cursor()
            if current_user.role == "User":
                cursor.execute(
                    """DELETE FROM history 
                       WHERE user_id = ? OR user_email = ? OR (user_id IS NULL AND (username = ? OR username = ?))""",
                    (str(current_user.id), current_user.email, current_user.email, current_user.full_name or "")
                )
            else:
                cursor.execute(
                    "DELETE FROM history WHERE user_id = ? OR user_email = ?",
                    (str(current_user.id), current_user.email)
                )
            deleted_count = max(deleted_count, cursor.rowcount)
            conn.commit()
        except Exception:
            pass

    return {"message": "All your screening history records have been deleted permanently.", "deleted_count": deleted_count}

@app.delete("/history/{history_id}")
def legacy_delete_history(history_id: int, current_user: Optional[User] = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")

    found = False
    # Check SQLAlchemy HistoryRecord
    try:
        rec = db.query(HistoryRecord).filter(HistoryRecord.id == history_id).first()
        if rec:
            found = True
            if current_user.role == "User":
                is_owner = (
                    (rec.user_id and rec.user_id == str(current_user.id)) or
                    (rec.user_email and rec.user_email.lower() == current_user.email.lower()) or
                    (rec.username and (
                        rec.username.lower() == current_user.email.lower() or
                        rec.username.lower() == (current_user.full_name or "").lower()
                    ))
                )
                if not is_owner:
                    raise HTTPException(status_code=403, detail="You can only delete your own screening records.")
            db.delete(rec)
            db.commit()
            return {"message": "History deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"[History] Delete check warning: {e}")

    # Fallback SQLite check
    conn = get_depression_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, user_id, user_email, username FROM history WHERE id=?", (history_id,))
    row = cursor.fetchone()
    if not row and not found:
        raise HTTPException(status_code=404, detail="History record not found")

    if row and current_user.role == "User":
        rec_user_id, rec_user_email, rec_username = row[1], row[2], row[3]
        is_owner = (
            (rec_user_id and rec_user_id == str(current_user.id)) or
            (rec_user_email and rec_user_email.lower() == current_user.email.lower()) or
            (rec_username and (
                rec_username.lower() == current_user.email.lower() or
                rec_username.lower() == (current_user.full_name or "").lower()
            ))
        )
        if not is_owner:
            raise HTTPException(status_code=403, detail="You can only delete your own screening records.")

    if row:
        cursor.execute("DELETE FROM history WHERE id=?", (history_id,))
        conn.commit()
    return {"message": "History deleted successfully"}

@app.post("/check-face")
async def check_face_image(image: UploadFile = File(...)):
    """
    Validates portrait image (rejects no-face and multi-face),
    and predicts gender to pre-fill demographic form.
    """
    ext = (os.path.splitext(image.filename)[1] or ".jpg").lower()
    if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid image format. Please capture a live photo or upload JPG/PNG."
        )
    contents = await image.read()
    nparr = np.frombuffer(contents, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(status_code=400, detail="Could not decode image file. Please provide a valid JPG or PNG photo.")

    face_res, err = face_pipeline.analyze(img)
    if err:
        raise HTTPException(status_code=400, detail=err)

    return {
        "success": True,
        "faces_detected": face_res.get("faces_detected", 1),
        "primary_emotion": face_res.get("primary_emotion", "neutral"),
        "predicted_gender": face_res.get("predicted_gender", "Female"),
        "gender_confidence": face_res.get("gender_confidence", 0.8),
        "summary": face_res.get("summary_sentence", "")
    }

@app.post("/analyze-voice")
async def standalone_analyze_voice(
    audio: UploadFile = File(...),
    store_audio_opt_in: bool = Form(False)
):
    """
    Language-independent audio-only vocal biomarker and acoustic analysis:
    1. Converts audio to 16 kHz mono WAV via FFmpeg.
    2. Enforces minimum 20s, silence/noise quality checks.
    3. Extracts language-independent acoustic biomarkers: speech rate (voiced timing),
       pause length & frequency, pitch variability, RMS energy.
    4. Evaluates vocal affect with multilingual facebook/wav2vec2-xls-r-300m foundation model.
    5. Deletes raw audio after analysis unless user explicitly ticks the consent box.
    """
    upload_dir = settings.UPLOAD_DIR
    os.makedirs(upload_dir, exist_ok=True)
    session_tag = uuid.uuid4().hex[:8]
    ext = os.path.splitext(audio.filename or "")[1] or ".webm"
    raw_path = os.path.join(upload_dir, f"voice_raw_{session_tag}{ext}")
    wav_path = os.path.join(upload_dir, f"voice_16k_{session_tag}.wav")

    with open(raw_path, "wb") as f:
        f.write(await audio.read())

    try:
        ok, conv_err = convert_audio_to_16k_mono_wav(raw_path, wav_path)
        if not ok:
            raise HTTPException(status_code=400, detail=conv_err)

        voice_res, voice_err = voice_pipeline.analyze(wav_path)
        if voice_err:
            raise HTTPException(status_code=400, detail=voice_err)

        return {
            "success": True,
            **voice_res
        }
    finally:
        # Zero-retention enforcement: Purge audio files unless user explicitly opted in
        if not store_audio_opt_in:
            if os.path.exists(raw_path):
                try:
                    os.remove(raw_path)
                except Exception:
                    pass
            if os.path.exists(wav_path):
                try:
                    os.remove(wav_path)
                except Exception:
                    pass

@app.post("/analyze")
async def legacy_analyze(
    text: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    audio: Optional[UploadFile] = File(None),
    phq9_score: Optional[float] = Form(None),
    phq9_answers: Optional[str] = Form(None),
    patient_name: Optional[str] = Form(None),
    dob: Optional[str] = Form(None),
    age: Optional[str] = Form(None),
    gender: Optional[str] = Form(None),
    occupation: Optional[str] = Form(None),
    symptoms: Optional[str] = Form(None),
    duration: Optional[str] = Form(None),
    store_audio_opt_in: bool = Form(False),
    current_user: Optional[User] = Depends(get_current_user)
):
    upload_dir = settings.UPLOAD_DIR
    os.makedirs(upload_dir, exist_ok=True)
    session_tag = uuid.uuid4().hex[:8]
    
    image_path = None
    raw_audio_path = None
    wav_audio_path = None

    has_text = bool(text and text.strip())
    has_image = bool(image and image.filename and len(image.filename.strip()) > 0)
    has_audio = bool(audio and audio.filename and len(audio.filename.strip()) > 0)
    has_phq9 = phq9_score is not None

    if not (has_text or has_image or has_audio or has_phq9):
        raise HTTPException(
            status_code=400,
            detail="Please provide at least one assessment modality (Text, Voice, Face) or PHQ-9 answers."
        )

    # DOB future validation
    if dob:
        try:
            dob_date = datetime.strptime(dob, "%Y-%m-%d").date()
            if dob_date > datetime.now().date():
                raise HTTPException(status_code=400, detail="Date of birth cannot be in the future.")
        except ValueError:
            pass

    if has_image:
        image_path = os.path.join(upload_dir, f"temp_{session_tag}_{image.filename}")
        with open(image_path, "wb") as f:
            f.write(await image.read())

    if has_audio:
        audio_ext = os.path.splitext(audio.filename or "")[1] or ".webm"
        raw_audio_path = os.path.join(upload_dir, f"raw_{session_tag}{audio_ext}")
        wav_audio_path = os.path.join(upload_dir, f"conv_16k_{session_tag}.wav")
        with open(raw_audio_path, "wb") as f:
            f.write(await audio.read())

    modalities_used = []
    skipped_modalities = []
    scores_to_average = []
    scored_modalities = []
    modality_statuses = {
        "Text": "Skipped",
        "Voice": "Skipped",
        "Face": "Skipped",
        "PHQ-9": "Skipped"
    }

    text_res = {}
    text_score = None
    if has_text:
        text_clean = text.strip()
        text_res = text_pipeline.analyze(text_clean)
        text_score = text_res.get("depression_probability", text_res.get("score", 0.5))
        modalities_used.append("Text")
        scored_modalities.append("Text")
        scores_to_average.append(text_score)
        modality_statuses["Text"] = "Used"
    else:
        skipped_modalities.append("Text")

    face_res = {}
    face_score = None
    face_emotion = "neutral"
    predicted_gender = gender or "Female"
    gender_conf = 0.8
    if has_image and image_path:
        img = cv2.imread(image_path)
        if img is None:
            raise HTTPException(status_code=400, detail="Could not decode image file. Please provide a valid JPG or PNG photo.")
        face_res, err = face_pipeline.analyze(img)
        if err:
            raise HTTPException(status_code=400, detail=err)
        face_score = face_res.get("depression_probability", 0.5)
        face_emotion = face_res.get("primary_emotion", "neutral")
        predicted_gender = face_res.get("predicted_gender", gender or "Female")
        gender_conf = face_res.get("gender_confidence", 0.8)
        modalities_used.append("Face")
        scored_modalities.append("Face")
        scores_to_average.append(face_score)
        modality_statuses["Face"] = "Used"
    else:
        skipped_modalities.append("Face")

    voice_res = {}
    voice_prob = None
    voice_emotion = "unclassified"
    if has_audio and raw_audio_path and wav_audio_path:
        ok, conv_err = convert_audio_to_16k_mono_wav(raw_audio_path, wav_audio_path)
        if not ok:
            raise HTTPException(status_code=400, detail=conv_err)
        voice_res, voice_err = voice_pipeline.analyze(wav_audio_path)
        if voice_err:
            raise HTTPException(status_code=400, detail=voice_err)
        voice_prob = voice_res.get("depression_probability")
        voice_emotion = voice_res.get("detected_emotion", "unclassified")
        modalities_used.append("Voice")
        if voice_prob is not None:
            scores_to_average.append(voice_prob)
            scored_modalities.append("Voice")
            modality_statuses["Voice"] = "Used"
        else:
            # Voice model not trained yet: features only, does not contribute to score
            modality_statuses["Voice"] = "Features only"
    else:
        skipped_modalities.append("Voice")

    if has_phq9 and phq9_score is not None:
        phq9_norm = float(phq9_score) / 27.0
        scores_to_average.append(phq9_norm)
        modalities_used.append("PHQ-9")
        scored_modalities.append("PHQ-9")
        modality_statuses["PHQ-9"] = "Used"

    # Honest Confidence: calculated ONLY from modalities that returned a real score
    scored_count = len(scores_to_average)
    has_features_only_voice = (modality_statuses.get("Voice") == "Features only")
    
    if scored_count >= 3 and not has_features_only_voice:
        confidence_level = "High Confidence"
        confidence_score = 0.88
        assessment_mode = "Full multimodal assessment"
    elif scored_count == 2 or (scored_count >= 2 and has_features_only_voice):
        confidence_level = "Moderate Confidence"
        confidence_score = 0.70
        if has_features_only_voice:
            assessment_mode = "Multimodal assessment with Voice features (observations only, not scored)"
        else:
            assessment_mode = "Partial assessment (some modalities skipped)"
    elif scored_count == 1:
        confidence_level = "Lower Confidence (Single Scored Modality)"
        confidence_score = 0.52
        assessment_mode = "Single scored modality assessment"
    else:
        confidence_level = "Low Confidence"
        confidence_score = 0.35
        assessment_mode = "Screening with insufficient scored data"

    if scores_to_average:
        avg_score = sum(scores_to_average) / float(len(scores_to_average))
    else:
        avg_score = 0.50

    final_score = round(avg_score * 100.0, 2)

    if final_score < 35:
        level = "Low Depression"
    elif final_score < 70:
        level = "Moderate Depression"
    else:
        level = "High Depression"

    resolved_name = (patient_name or "").strip()
    if not resolved_name and current_user:
        resolved_name = (current_user.full_name or current_user.email or "").strip()
    if not resolved_name:
        resolved_name = "Anonymous Patient"

    user_id = str(current_user.id) if current_user else None
    user_email = current_user.email if current_user else None
    analysis_type = " + ".join(modalities_used) if modalities_used else "Single Modality"

    saved_hist_id = None
    try:
        # 1. Primary persistence using SQLAlchemy HistoryRecord (PostgreSQL & SQLite)
        db_sql = SessionLocal()
        try:
            hist_entry = HistoryRecord(
                username=resolved_name,
                analysis_type=analysis_type,
                score=final_score,
                level=level,
                date=datetime.now().strftime("%d-%m-%Y %H:%M"),
                dob=dob,
                age=age,
                gender=gender or predicted_gender,
                occupation=occupation,
                symptoms=symptoms,
                duration=duration,
                user_id=user_id,
                user_email=user_email
            )
            db_sql.add(hist_entry)

            # Delete user's active draft upon successful analysis completion
            from app.models.analysis_draft import AnalysisDraft
            db_sql.query(AnalysisDraft).filter(
                (AnalysisDraft.user_id == resolved_name) | (AnalysisDraft.user_id == "anonymous")
            ).delete()
            db_sql.commit()
            db_sql.refresh(hist_entry)
            saved_hist_id = hist_entry.id
        except Exception as e:
            logger.error(f"[History Save] HistoryRecord save error: {e}")
            db_sql.rollback()
        finally:
            db_sql.close()

        # 2. Local fallback SQLite persistence if in SQLite mode
        if settings.DATABASE_URL.startswith("sqlite"):
            try:
                conn = get_depression_db()
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO history
                    (username, analysis_type, score, level, date, dob, age, gender, occupation, symptoms, duration, user_id, user_email)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        resolved_name,
                        analysis_type,
                        final_score,
                        level,
                        datetime.now().strftime("%d-%m-%Y %H:%M"),
                        dob,
                        age,
                        gender or predicted_gender,
                        occupation,
                        symptoms,
                        duration,
                        user_id,
                        user_email
                    )
                )
                conn.commit()
                if not saved_hist_id and cursor.lastrowid:
                    saved_hist_id = cursor.lastrowid
            except Exception:
                pass

        return {
            "id": saved_hist_id,
            "text_score": round(text_score * 100.0, 2) if text_score is not None else None,
            "face_emotion": face_emotion,
            "voice_emotion": voice_emotion,
            "voice_score": voice_res.get("voice_score"),
            "model_status": voice_res.get("model_status", "Voice model not trained yet"),
            "risk_band": level,
            "voice_risk_band": voice_res.get("risk_band", "Voice model not trained yet"),
            "speech_rate": voice_res.get("speech_rate"),
            "pause_length": voice_res.get("pause_length"),
            "pause_frequency": voice_res.get("pause_frequency"),
            "pitch_variability": voice_res.get("pitch_variability"),
            "pitch_variability_hz": voice_res.get("pitch_variability_hz"),
            "pitch_variability_semitones": voice_res.get("pitch_variability_semitones"),
            "energy": voice_res.get("energy"),
            "predicted_gender": predicted_gender,
            "gender_confidence": gender_conf,
            "final_score": final_score,
            "level": level,
            "patient_name": resolved_name,
            "dob": dob,
            "age": age,
            "duration": duration,
            "symptoms": symptoms,
            "modalities_used": modalities_used,
            "scored_modalities": scored_modalities,
            "skipped_modalities": skipped_modalities,
            "modality_statuses": modality_statuses,
            "assessment_mode": assessment_mode,
            "voice_features_label": "Voice features (observations only, not part of the score)",
            "confidence_level": confidence_level,
            "confidence_score": confidence_score,
            "confidence": confidence_score,
            "top_saliency_tokens": text_res.get("top_saliency_tokens", [])
        }

    finally:
        if image_path and os.path.exists(image_path):
            try:
                os.remove(image_path)
            except Exception:
                pass
        # Zero-retention enforcement: Purge audio files unless user explicitly opted in
        if not store_audio_opt_in:
            if raw_audio_path and os.path.exists(raw_audio_path):
                try:
                    os.remove(raw_audio_path)
                except Exception:
                    pass
            if wav_audio_path and os.path.exists(wav_audio_path):
                try:
                    os.remove(wav_audio_path)
                except Exception:
                    pass

# =====================================================================
# Analysis Autosave & Draft Endpoints
# =====================================================================
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas.draft import DraftSaveRequest

@app.post("/screening/draft")
def legacy_save_draft(payload: DraftSaveRequest, db: Session = Depends(get_db)):
    from app.api.v1.screening import save_screening_draft
    return save_screening_draft(payload=payload, current_user=None, db=db)

@app.get("/screening/draft")
def legacy_get_draft(user_id: Optional[str] = None, db: Session = Depends(get_db)):
    from app.api.v1.screening import get_screening_draft
    return get_screening_draft(user_id=user_id, current_user=None, db=db)

@app.delete("/screening/draft")
def legacy_delete_draft(user_id: Optional[str] = None, db: Session = Depends(get_db)):
    from app.api.v1.screening import delete_screening_draft
    return delete_screening_draft(user_id=user_id, current_user=None, db=db)

# =====================================================================
# Redirection for Retired Statistics Endpoints
# =====================================================================
from fastapi.responses import RedirectResponse

@app.get("/statistics")
@app.get("/analytics")
@app.get("/statisticsSection")
def redirect_statistics_to_home():
    """Redirects retired standalone statistics routes directly to Home."""
    return RedirectResponse(url="/", status_code=302)

@app.get("/login")
def login_page_redirect():
    return RedirectResponse(url="/login.html")

@app.get("/register")
def register_page_redirect():
    return RedirectResponse(url="/register.html")

@app.get("/api/health")
def health_check():
    return {
        "name": settings.PROJECT_NAME,
        "status": "online",
        "version": "1.0.0",
        "documentation": "/docs"
    }

from fastapi import Depends
from app.api.deps import require_admin, require_clinician, require_auth_user

@app.get("/auth/me")
def root_auth_me(user: User = Depends(require_auth_user)):
    return {
        "id": user.id,
        "name": user.full_name,
        "full_name": user.full_name,
        "email": user.email,
        "role": user.role,
        "username": user.username or user.email.split("@")[0],
        "is_active": user.is_active,
        "email_verified": user.email_verified,
        "created_at": user.created_at.isoformat() if user.created_at else None
    }

@app.get("/admin")
@app.get("/admin/{path:path}")
def admin_root_block(user: User = Depends(require_admin)):
    return {"message": "Admin access verified", "user": user.email, "role": user.role}

@app.get("/clinician")
@app.get("/clinician/{path:path}")
def clinician_root_block(user: User = Depends(require_clinician)):
    return {"message": "Clinician access verified", "user": user.email, "role": user.role}

# =====================================================================
# Mount Frontend Static Directory at Root (Fast, Concurrent Async)
# =====================================================================
frontend_dir = os.path.join(settings.WORKSPACE_DIR, "frontend")
if os.path.isdir(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)


