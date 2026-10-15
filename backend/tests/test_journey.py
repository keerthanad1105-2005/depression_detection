import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
import uuid

def test_auth_and_rbac(client: TestClient):
    # 1. Register new user using Email as the username (no separate username field)
    unique_suffix = uuid.uuid4().hex[:6]
    test_user_payload = {
        "email": f"journey_user_{unique_suffix}@example.com",
        "password": "Password123!",
        "full_name": "Journey Test User",
        "role": "User"
    }
    reg_resp = client.post("/api/v1/auth/register", json=test_user_payload)
    assert reg_resp.status_code in (200, 201)
    reg_data = reg_resp.json()
    assert "access_token" in reg_data or "id" in reg_data or "email" in reg_data

    # 2. Login with email and password
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": test_user_payload["email"], "password": "Password123!"}
    )
    assert login_resp.status_code == 200
    token_data = login_resp.json()
    user_token = token_data["access_token"]
    assert user_token is not None

    # 3. Login with wrong password shows clear error
    bad_login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": test_user_payload["email"], "password": "WrongPassword!"}
    )
    assert bad_login_resp.status_code in (400, 401)
    assert "Incorrect" in bad_login_resp.json()["detail"] or "Invalid" in bad_login_resp.json()["detail"] or "credentials" in bad_login_resp.json()["detail"].lower()

    # 4. User role access to forbidden Admin endpoint returns 403
    forbidden_resp = client.get(
        "/api/v1/admin/dashboard-stats",
        headers={"Authorization": f"Bearer {user_token}"}
    )
    assert forbidden_resp.status_code == 403

def test_email_registration_and_clinician_approval(client: TestClient):
    # 1. Live Email Availability Check
    unique_suffix = uuid.uuid4().hex[:6]
    test_email = f"clinician_cand_{unique_suffix}@example.com"
    
    check_resp = client.get(f"/api/v1/auth/check-email?email={test_email}")
    assert check_resp.status_code == 200
    assert check_resp.json()["available"] is True

    # 2. Register with Clinician role -> Created as User with pending clinician_status
    reg_resp = client.post("/api/v1/auth/register", json={
        "full_name": "Dr. Candidate",
        "email": test_email,
        "password": "Password123!",
        "role": "Clinician"
    })
    assert reg_resp.status_code == 200
    reg_data = reg_resp.json()
    created_user = reg_data["user"]
    assert created_user["role"] == "User"  # Never auto-granted!
    assert created_user["clinician_status"] == "pending"

    # 3. Duplicate Email Check fails
    dup_resp = client.post("/api/v1/auth/register", json={
        "full_name": "Dr. Candidate Duplicate",
        "email": test_email,
        "password": "Password123!",
        "role": "Clinician"
    })
    assert dup_resp.status_code == 400
    assert "already registered" in dup_resp.json()["detail"].lower()

    # 4. Attempt to send "Admin" role without code -> Rejected with 400
    admin_attempt_email = f"sneak_admin_{unique_suffix}@example.com"
    sneak_resp = client.post("/api/v1/auth/register", json={
        "full_name": "Sneaky User",
        "email": admin_attempt_email,
        "password": "Password123!",
        "role": "Admin"
    })
    assert sneak_resp.status_code == 400
    assert "Invalid admin access code" in sneak_resp.json()["detail"]

    # 4b. Arbitrary untrusted role string -> Ignored by server, defaults strictly to User
    untrusted_email = f"untrusted_{unique_suffix}@example.com"
    untrusted_resp = client.post("/api/v1/auth/register", json={
        "full_name": "Untrusted Role User",
        "email": untrusted_email,
        "password": "Password123!",
        "role": "SuperManager"
    })
    assert untrusted_resp.status_code == 200
    assert untrusted_resp.json()["user"]["role"] == "User"

    # 5. Admin approves the pending clinician request
    admin_login_resp = client.post("/api/v1/auth/login", json={
        "email": "admin@mindscan.health",
        "password": "Admin@12345"
    })
    assert admin_login_resp.status_code == 200
    admin_token = admin_login_resp.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    approve_resp = client.post(
        f"/api/v1/admin/users/{created_user['id']}/approve-clinician",
        headers=admin_headers
    )
    assert approve_resp.status_code == 200
    assert approve_resp.json()["new_role"] == "Clinician"

    # 6. Verify user list includes approved clinician
    users_resp = client.get("/api/v1/admin/users", headers=admin_headers)
    assert users_resp.status_code == 200
    user_records = users_resp.json()
    matched = [u for u in user_records if u["id"] == created_user["id"]]
    assert len(matched) == 1
    assert matched[0]["role"] == "Clinician"
    assert matched[0]["clinician_status"] == "approved"

def test_analysis_draft_autosave_and_privacy(client: TestClient):
    # Register and login a draft test user
    unique_suffix = uuid.uuid4().hex[:6]
    email = f"draft_user_{unique_suffix}@example.com"
    reg_resp = client.post("/api/v1/auth/register", json={
        "email": email,
        "password": "Password123!",
        "full_name": "Draft User",
        "role": "User"
    })
    assert reg_resp.status_code in (200, 201)

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"}
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Save draft step: patient info + PHQ9 with privacy check
    draft_payload = {
        "step": "phq9",
        "draft_data": {
            "patientName": "Draft Patient",
            "patientDOB": "1995-05-15",
            "patientAge": "29",
            "patientSymptoms": "Fatigue, low mood",
            "phq9Score": 14,
            "phq9Answers": [1, 2, 1, 2, 1, 2, 2, 2, 1],
            "audio_base64": "data:audio/wav;base64,RAW_AUDIO_STREAM_DATA",
            "photo_base64": "data:image/jpeg;base64,RAW_PHOTO_DATA"
        },
        "opt_in_save_media": False
    }

    save_resp = client.post("/api/v1/screening/draft", json=draft_payload, headers=headers)
    assert save_resp.status_code == 200
    save_data = save_resp.json()
    assert save_data["status"] == "saved"
    assert save_data["step"] == "phq9"

    # Retrieve draft and verify raw audio/photo was stripped per privacy policy
    get_resp = client.get("/api/v1/screening/draft", headers=headers)
    assert get_resp.status_code == 200
    get_data = get_resp.json()
    assert get_data["exists"] is True
    assert get_data["step"] == "phq9"
    retrieved_draft = get_data["draft_data"]
    assert retrieved_draft["patientName"] == "Draft Patient"
    assert "audio_base64" not in retrieved_draft
    assert "photo_base64" not in retrieved_draft

    # Discard draft
    del_resp = client.delete("/api/v1/screening/draft", headers=headers)
    assert del_resp.status_code == 200

    # Verify deleted
    get_after_del = client.get("/api/v1/screening/draft", headers=headers)
    assert get_after_del.status_code == 200
    assert get_after_del.json()["exists"] is False

def test_dob_future_validation(client: TestClient):
    # Future DOB must return 400 Bad Request
    future_date = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")
    resp = client.post(
        "/analyze",
        data={
            "text": "Feeling low today",
            "dob": future_date,
            "name": "Time Traveler"
        }
    )
    assert resp.status_code == 400
    assert "future" in resp.json()["detail"].lower()

def test_multimodal_modality_skipping_confidence(client: TestClient):
    # Text only (face and voice skipped) -> Result appears with lower confidence
    resp = client.post(
        "/analyze",
        data={
            "text": "I feel sad, exhausted, and cannot sleep at night.",
            "name": "Partial Assessment",
            "dob": "1990-01-01",
            "symptoms": "Sadness, insomnia"
        }
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "final_score" in data
    assert "level" in data
    assert data["confidence"] < 0.8  # Lower confidence due to skipped modalities
    assert "Face" in data["skipped_modalities"]
    assert "Voice" in data["skipped_modalities"]
    assert "Text" in data["modalities_used"]

def test_admin_dashboard_population_symptoms_and_redirects(client: TestClient):
    # 1. Admin dashboard stats includes top reported symptoms
    resp = client.get("/admin-dashboard")
    assert resp.status_code == 200
    admin_data = resp.json()
    assert "most_reported_symptoms" in admin_data
    assert isinstance(admin_data["most_reported_symptoms"], list)

    # 2. Redirects for retired statistics URLs
    stat_resp = client.get("/statistics", follow_redirects=False)
    assert stat_resp.status_code in (301, 302, 307)
    assert stat_resp.headers["location"] == "/"

    analytics_resp = client.get("/analytics", follow_redirects=False)
    assert analytics_resp.status_code in (301, 302, 307)
    assert analytics_resp.headers["location"] == "/"
