import os
import uuid
import pytest
from fastapi.testclient import TestClient
try:
    from backend.main import app
    from backend.app.core.config import settings
except ImportError:
    from main import app
    from app.core.config import settings

client = TestClient(app)

def test_registration_roles_and_codes():
    results = {}
    uid = uuid.uuid4().hex[:6]

    # 1. User registration (no code required, active immediately)
    email_user = f"user_{uid}@example.com"
    r_user = client.post("/api/v1/auth/register", json={
        "full_name": "Standard User",
        "email": email_user,
        "password": "Password123!",
        "role": "User"
    })
    assert r_user.status_code == 200, r_user.text
    data_user = r_user.json()
    assert data_user["user"]["role"] == "User"
    assert data_user["user"]["clinician_status"] is None
    assert data_user["user"]["is_active"] is True
    results["1_user_no_code"] = "PASS"

    # 2. Clinician registration with VALID code -> Active as Clinician
    email_clin_valid = f"clin_valid_{uid}@example.com"
    r_clin_valid = client.post("/api/v1/auth/register", json={
        "full_name": "Dr. Valid Clinician",
        "email": email_clin_valid,
        "password": "Password123!",
        "role": "Clinician",
        "access_code": settings.CLINICIAN_REGISTRATION_CODE
    })
    assert r_clin_valid.status_code == 200, r_clin_valid.text
    data_clin_valid = r_clin_valid.json()
    assert data_clin_valid["user"]["role"] == "Clinician"
    assert data_clin_valid["user"]["clinician_status"] == "approved"
    results["2_clinician_valid_code"] = "PASS"

    # 3. Clinician registration with WRONG code -> 400 Invalid clinician access code
    email_clin_wrong = f"clin_wrong_{uid}@example.com"
    r_clin_wrong = client.post("/api/v1/auth/register", json={
        "full_name": "Dr. Wrong Code",
        "email": email_clin_wrong,
        "password": "Password123!",
        "role": "Clinician",
        "access_code": "WRONG_CLINICIAN_CODE"
    })
    assert r_clin_wrong.status_code == 400
    assert "Invalid clinician access code" in r_clin_wrong.json()["detail"]
    results["3_clinician_wrong_code"] = "PASS"

    # 4. Clinician registration with NO code -> Created as User with pending clinician status
    email_clin_nocode = f"clin_nocode_{uid}@example.com"
    r_clin_nocode = client.post("/api/v1/auth/register", json={
        "full_name": "Dr. No Code Pending",
        "email": email_clin_nocode,
        "password": "Password123!",
        "role": "Clinician"
    })
    assert r_clin_nocode.status_code == 200, r_clin_nocode.text
    data_clin_nocode = r_clin_nocode.json()
    assert data_clin_nocode["user"]["role"] == "User"
    assert data_clin_nocode["user"]["clinician_status"] == "pending"
    results["4_clinician_no_code_pending"] = "PASS"

    # 5. Admin registration with VALID code -> Active as Admin
    email_admin_valid = f"admin_valid_{uid}@example.com"
    r_admin_valid = client.post("/api/v1/auth/register", json={
        "full_name": "Admin Super",
        "email": email_admin_valid,
        "password": "Password123!",
        "role": "Admin",
        "access_code": settings.ADMIN_REGISTRATION_CODE
    })
    assert r_admin_valid.status_code == 200, r_admin_valid.text
    data_admin_valid = r_admin_valid.json()
    assert data_admin_valid["user"]["role"] == "Admin"
    results["5_admin_valid_code"] = "PASS"

    # 6. Admin registration with WRONG code -> 400 Invalid admin access code
    email_admin_wrong = f"admin_wrong_{uid}@example.com"
    r_admin_wrong = client.post("/api/v1/auth/register", json={
        "full_name": "Fake Admin",
        "email": email_admin_wrong,
        "password": "Password123!",
        "role": "Admin",
        "access_code": "wrong_code_xyz"
    })
    assert r_admin_wrong.status_code == 400
    assert "Invalid admin access code" in r_admin_wrong.json()["detail"]
    results["6_admin_wrong_code"] = "PASS"

    # 7. Admin registration with NO code -> 400 Invalid admin access code
    email_admin_nocode = f"admin_nocode_{uid}@example.com"
    r_admin_nocode = client.post("/api/v1/auth/register", json={
        "full_name": "No Code Admin",
        "email": email_admin_nocode,
        "password": "Password123!",
        "role": "Admin"
    })
    assert r_admin_nocode.status_code == 400
    assert "Invalid admin access code" in r_admin_nocode.json()["detail"]
    results["7_admin_no_code"] = "PASS"

    # 8. Attempt to send role "admin" (lowercase/unvalidated) without code -> 400
    email_admin_sneak = f"admin_sneak_{uid}@example.com"
    r_admin_sneak = client.post("/api/v1/auth/register", json={
        "full_name": "Sneak Admin",
        "email": email_admin_sneak,
        "password": "Password123!",
        "role": "admin"
    })
    assert r_admin_sneak.status_code == 400
    assert "Invalid admin access code" in r_admin_sneak.json()["detail"]
    results["8_admin_role_without_code_rejected"] = "PASS"

    # 9. Duplicate email registration -> 400 Email already registered
    r_dup = client.post("/api/v1/auth/register", json={
        "full_name": "Duplicate User",
        "email": email_user,
        "password": "Password123!",
        "role": "User"
    })
    assert r_dup.status_code == 400
    assert "already registered" in r_dup.json()["detail"].lower()
    results["9_duplicate_email"] = "PASS"

    print("\n--- REGISTRATION TEST RESULTS ---")
    for k, v in results.items():
        print(f"  {k}: {v}")

def test_user_history_isolation_and_deletion():
    uid = uuid.uuid4().hex[:6]

    # Register User A
    user_a_email = f"usera_{uid}@example.com"
    res_a = client.post("/api/v1/auth/register", json={
        "full_name": "User Alpha",
        "email": user_a_email,
        "password": "Password123!",
        "role": "User"
    })
    token_a = res_a.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # Register User B
    user_b_email = f"userb_{uid}@example.com"
    res_b = client.post("/api/v1/auth/register", json={
        "full_name": "User Beta",
        "email": user_b_email,
        "password": "Password123!",
        "role": "User"
    })
    token_b = res_b.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # User A creates a screening analysis
    an_res_a = client.post(
        "/analyze",
        data={
            "text": "I feel exhausted, unmotivated, and sad most days.",
            "patient_name": "User Alpha",
            "symptoms": "fatigue, low mood",
            "duration": "3 weeks"
        },
        headers=headers_a
    )
    assert an_res_a.status_code == 200, an_res_a.text

    # User A views their history -> sees 1 record
    hist_a = client.get("/history", headers=headers_a)
    assert hist_a.status_code == 200
    records_a = hist_a.json()
    assert len(records_a) >= 1
    rec_a_id = records_a[0]["id"]

    # User B views their history -> sees 0 records (CANNOT see User A's record!)
    hist_b = client.get("/history", headers=headers_b)
    assert hist_b.status_code == 200
    records_b = hist_b.json()
    user_b_matching = [r for r in records_b if r["id"] == rec_a_id]
    assert len(user_b_matching) == 0, "Security Violation: User B can see User A's records!"

    # User B attempts to DELETE User A's record -> 403 Forbidden
    del_forbidden = client.delete(f"/history/{rec_a_id}", headers=headers_b)
    assert del_forbidden.status_code == 403, "Security Violation: User B was able to delete User A's record!"

    # User A deletes their own record -> 200 OK
    del_ok = client.delete(f"/history/{rec_a_id}", headers=headers_a)
    assert del_ok.status_code == 200

    # User A adds another analysis then uses "Delete all my data"
    client.post(
        "/analyze",
        data={
            "text": "Everything feels overwhelming and grey.",
            "patient_name": "User Alpha"
        },
        headers=headers_a
    )
    hist_a_recheck = client.get("/history", headers=headers_a).json()
    assert len(hist_a_recheck) >= 1

    del_all = client.delete("/history/all", headers=headers_a)
    assert del_all.status_code == 200
    hist_a_empty = client.get("/history", headers=headers_a).json()
    assert len(hist_a_empty) == 0, "Delete all data did not remove user records!"

    print("User history isolation and deletion test PASSED successfully!")

if __name__ == "__main__":
    test_registration_roles_and_codes()
    test_user_history_isolation_and_deletion()
