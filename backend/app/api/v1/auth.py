import uuid
import re
import time
import json
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.db.session import get_db
from app.models.user import User
from app.models.audit_log import AuditLog
from app.core.config import settings
from app.core.security import (
    hash_password, verify_password, create_access_token, create_refresh_token,
    decode_token, check_password_strength
)
from app.schemas.auth import (
    UserRegister, UserLogin, GoogleLogin, PasswordResetRequest, PasswordResetConfirm,
    TokenResponse, UserResponse
)
from app.api.deps import require_auth_user

router = APIRouter(prefix="/auth", tags=["Authentication"])

# =====================================================================
# In-Memory Rate Limiter for Login & Admin Registration Attempts
# =====================================================================
LOGIN_ATTEMPTS = {}
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_SECONDS = 300  # 5 minutes

ADMIN_REGISTER_ATTEMPTS = {}
MAX_ADMIN_REG_ATTEMPTS = 5
ADMIN_LOCKOUT_SECONDS = 900  # 15 minutes

def check_login_rate_limit(key: str):
    now = time.time()
    record = LOGIN_ATTEMPTS.get(key)
    if record:
        if record.get("locked_until", 0) > now:
            remaining = int(record["locked_until"] - now)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many failed login attempts. Please try again in {remaining} seconds."
            )
        if now - record.get("last_attempt", 0) > 600:
            LOGIN_ATTEMPTS.pop(key, None)

def record_failed_login(key: str):
    now = time.time()
    record = LOGIN_ATTEMPTS.setdefault(key, {"count": 0, "locked_until": 0, "last_attempt": now})
    record["count"] += 1
    record["last_attempt"] = now
    if record["count"] >= MAX_FAILED_ATTEMPTS:
        record["locked_until"] = now + LOCKOUT_DURATION_SECONDS

def clear_failed_login(key: str):
    LOGIN_ATTEMPTS.pop(key, None)

def check_admin_register_rate_limit(key: str):
    now = time.time()
    record = ADMIN_REGISTER_ATTEMPTS.get(key)
    if record:
        if record.get("locked_until", 0) > now:
            remaining = int(record["locked_until"] - now)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many failed admin registration attempts. Please try again in {remaining} seconds."
            )
        if now - record.get("last_attempt", 0) > 1800:
            ADMIN_REGISTER_ATTEMPTS.pop(key, None)

def record_failed_admin_register(key: str):
    now = time.time()
    record = ADMIN_REGISTER_ATTEMPTS.setdefault(key, {"count": 0, "locked_until": 0, "last_attempt": now})
    record["count"] += 1
    record["last_attempt"] = now
    if record["count"] >= MAX_ADMIN_REG_ATTEMPTS:
        record["locked_until"] = now + ADMIN_LOCKOUT_SECONDS

def clear_admin_register_rate_limit(key: str):
    ADMIN_REGISTER_ATTEMPTS.pop(key, None)

# =====================================================================
# Auth Endpoints
# =====================================================================

@router.get("/check-email")
def check_email_availability(email: str = Query(...), db: Session = Depends(get_db)):
    """Check if an email is already registered."""
    clean_email = email.strip().lower()
    exists = db.query(User).filter(User.email == clean_email).first() is not None
    return {"email": clean_email, "available": not exists}

@router.post("/register", response_model=TokenResponse)
def register_user(payload: UserRegister, request: Request, db: Session = Depends(get_db)):
    import secrets

    # 1. Full name validation: 2-100 characters
    clean_name = payload.full_name.strip()
    if len(clean_name) < 2 or len(clean_name) > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Full name must be between 2 and 100 characters."
        )

    # 2. Check unique email (Email IS the username)
    clean_email = payload.email.strip().lower()
    existing_email = db.query(User).filter(User.email == clean_email).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered. Please log in."
        )

    # 3. Password minimum 8 characters
    if len(payload.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long."
        )

    # 4. Strict Server-Side Role Assignment & Access Code Validation
    client_ip = request.client.host if request.client else "unknown"
    admin_rate_key = f"admin_reg:{client_ip}"

    raw_role = (payload.role or "User").strip().lower()
    provided_code = (payload.access_code or "").strip()

    assigned_role = "User"
    clinician_status = None
    audit_action = "register"
    audit_details = {
        "email": clean_email,
        "full_name": clean_name,
        "ip": client_ip,
        "requested_role": payload.role
    }

    if raw_role == "admin":
        expected_admin_code = (settings.ADMIN_REGISTRATION_CODE or "").strip()
        # If ADMIN_REGISTRATION_CODE is empty in .env, disable admin registration completely
        if not expected_admin_code:
            audit = AuditLog(
                user_id="anonymous",
                action="admin_register_failed",
                resource="auth",
                details_json=json.dumps({
                    **audit_details,
                    "reason": "Admin registration is disabled (ADMIN_REGISTRATION_CODE not configured)"
                })
            )
            db.add(audit)
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin registration is currently disabled."
            )

        # Rate-limit admin registration attempts
        check_admin_register_rate_limit(admin_rate_key)

        # Constant-time comparison
        if not provided_code or not secrets.compare_digest(provided_code, expected_admin_code):
            record_failed_admin_register(admin_rate_key)
            audit = AuditLog(
                user_id="anonymous",
                action="admin_register_failed",
                resource="auth",
                details_json=json.dumps({
                    **audit_details,
                    "reason": "Invalid admin access code" if provided_code else "Missing admin access code"
                })
            )
            db.add(audit)
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid admin access code"
            )

        clear_admin_register_rate_limit(admin_rate_key)
        assigned_role = "Admin"
        audit_action = "admin_register_success"

    elif raw_role == "clinician":
        expected_clinician_code = (settings.CLINICIAN_REGISTRATION_CODE or "").strip()
        if provided_code:
            # Code was provided: validate against CLINICIAN_REGISTRATION_CODE
            if expected_clinician_code and secrets.compare_digest(provided_code, expected_clinician_code):
                assigned_role = "Clinician"
                clinician_status = "approved"
                audit_action = "register_clinician_code_success"
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid clinician access code"
                )
        else:
            # Without a code, account is created as User and pending clinician request goes to admin
            assigned_role = "User"
            clinician_status = "pending"
            audit_action = "register_clinician_request"

    else:
        # Default strictly to User, ignore any unvalidated client role or flag
        assigned_role = "User"
        clinician_status = None
        audit_action = "register"

    # The email IS the username
    user = User(
        id=str(uuid.uuid4()),
        username=clean_email,
        email=clean_email,
        password_hash=hash_password(payload.password),
        full_name=clean_name,
        role=assigned_role,
        clinician_status=clinician_status,
        is_active=True,
        email_verified=True
    )
    db.add(user)

    audit_details["assigned_role"] = assigned_role
    audit_details["clinician_status"] = clinician_status
    audit = AuditLog(
        user_id=user.id,
        action=audit_action,
        resource="auth",
        details_json=json.dumps(audit_details)
    )
    db.add(audit)
    db.commit()
    db.refresh(user)

    access_token = create_access_token({
        "sub": user.id,
        "role": user.role,
        "email": user.email,
        "username": user.username,
        "full_name": user.full_name
    })
    refresh_token = create_refresh_token({"sub": user.id})

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": user
    }

@router.post("/login", response_model=TokenResponse)
def login_user(payload: UserLogin, request: Request, db: Session = Depends(get_db)):
    # Extract identifier: can be username or email
    raw_ident = payload.username_or_email or payload.email or payload.username or ""
    identifier = raw_ident.strip().lower()
    if not identifier:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please provide your username or email."
        )

    client_ip = request.client.host if request.client else "unknown"
    rate_limit_key = f"{client_ip}:{identifier}"
    check_login_rate_limit(rate_limit_key)

    # Find user by either email or username
    user = db.query(User).filter(
        or_(
            User.email == identifier,
            User.username == identifier
        )
    ).first()

    if not user or not verify_password(payload.password, user.password_hash):
        record_failed_login(rate_limit_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username/email or password."
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been deactivated. Please contact support."
        )

    clear_failed_login(rate_limit_key)

    audit = AuditLog(user_id=user.id, action="login", resource="auth")
    db.add(audit)
    db.commit()

    access_token = create_access_token({"sub": user.id, "role": user.role, "email": user.email, "username": user.username})
    refresh_token = create_refresh_token({"sub": user.id})

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": user
    }

@router.get("/google/config")
def get_google_config():
    """
    Returns public Google OAuth configuration (Client ID and Redirect URI).
    """
    return {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI
    }

@router.post("/google", response_model=TokenResponse)
def google_auth(payload: GoogleLogin, db: Session = Depends(get_db)):
    """
    Sign in with Google OAuth 2.0.
    A first-time Google user is automatically registered; a returning user signs in directly.
    Saves and displays the user's real name and email from their Google account.
    """
    email_clean = payload.email.strip().lower()
    user = db.query(User).filter(User.email == email_clean).first()

    # Determine real display name from Google profile or email structure
    raw_name = (payload.full_name or "").strip()
    if not raw_name or raw_name.lower() in ("google user", "google test user"):
        # Format name from email (e.g. dev.patel@gmail.com -> Dev Patel)
        prefix = email_clean.split("@")[0].replace(".", " ").replace("_", " ")
        resolved_name = " ".join([word.capitalize() for word in prefix.split() if not word.isdigit()]) or "User"
    else:
        resolved_name = raw_name

    if not user:
        user = User(
            id=str(uuid.uuid4()),
            username=email_clean,
            email=email_clean,
            password_hash=hash_password(str(uuid.uuid4())),
            full_name=resolved_name,
            role="User",
            clinician_status=None,
            is_active=True,
            email_verified=True
        )
        db.add(user)
        audit = AuditLog(
            user_id=user.id,
            action="google_register",
            resource="auth",
            details_json=json.dumps({"email": email_clean, "full_name": resolved_name})
        )
        db.add(audit)
    else:
        # Always update name if user previously had generic "Google User" or if real name provided
        if user.full_name in ("Google User", "Google Test User", "", None) or (raw_name and raw_name.lower() not in ("google user", "google test user")):
            user.full_name = resolved_name
        audit = AuditLog(
            user_id=user.id,
            action="google_login",
            resource="auth",
            details_json=json.dumps({"email": email_clean, "full_name": user.full_name})
        )
        db.add(audit)

    db.commit()
    db.refresh(user)

    access_token = create_access_token({"sub": user.id, "role": user.role, "email": user.email, "username": user.username, "full_name": user.full_name})
    refresh_token = create_refresh_token({"sub": user.id})

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": user
    }

@router.post("/logout")
def logout_endpoint(current_user: User = Depends(require_auth_user), db: Session = Depends(get_db)):
    """
    Log out the user, auditing the action.
    Client-side clears stored tokens and redirects to /login.
    """
    audit = AuditLog(user_id=current_user.id, action="logout", resource="auth")
    db.add(audit)
    db.commit()
    return {"message": "Logged out successfully."}

@router.post("/refresh")
def refresh_token_endpoint(refresh_token: str, db: Session = Depends(get_db)):
    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token."
        )
    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive."
        )

    new_access_token = create_access_token({"sub": user.id, "role": user.role, "email": user.email, "username": user.username})
    return {"access_token": new_access_token, "token_type": "bearer"}

@router.post("/password/check-strength")
def check_strength_endpoint(password: str):
    return check_password_strength(password)

@router.post("/forgot-password")
def forgot_password(payload: PasswordResetRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    reset_token = None
    if user:
        reset_token = create_access_token(
            {"sub": user.id, "purpose": "password_reset"},
            expires_delta=timedelta(hours=1)
        )
    return {
        "message": "If an account exists with this email, password reset instructions have been generated.",
        "simulated_reset_token": reset_token
    }

@router.post("/reset-password")
def reset_password(payload: PasswordResetConfirm, db: Session = Depends(get_db)):
    token_payload = decode_token(payload.token)
    if not token_payload or token_payload.get("purpose") != "password_reset":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token."
        )
    user_id = token_payload.get("sub")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    strength = check_password_strength(payload.new_password)
    if not strength["is_acceptable"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Weak password: {', '.join(strength['feedback'])}"
        )

    user.password_hash = hash_password(payload.new_password)
    audit = AuditLog(user_id=user.id, action="reset_password", resource="auth")
    db.add(audit)
    db.commit()
    return {"message": "Password updated successfully. You can now log in."}

@router.get("/me")
def get_current_user_profile(user: User = Depends(require_auth_user)):
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

