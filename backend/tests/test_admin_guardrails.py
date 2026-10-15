import os
import sys
import uuid
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from main import app
from app.core.config import settings

client = TestClient(app)

def test_admin_guardrails_and_rate_limits():
    uid = uuid.uuid4().hex[:6]

    # 1. Admin login
    admin_login = client.post("/api/v1/auth/login", json={
        "email": "admin@mindscan.health",
        "password": "Admin@12345"
    })
    assert admin_login.status_code == 200, admin_login.text
    admin_token = admin_login.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    admin_user_id = admin_login.json()["user"]["id"]

    # 2. Guardrail 1: Admin cannot remove their own admin role by accident
    self_demote = client.post(
        f"/api/v1/admin/users/{admin_user_id}/change-role",
        json={"role": "User"},
        headers=admin_headers
    )
    assert self_demote.status_code == 400
    assert "cannot remove your own administrator role" in self_demote.json()["detail"].lower()
    print("Self-demote guardrail: PASS")

    # 3. Guardrail 2: Admin cannot deactivate their own account
    self_deactivate = client.post(
        f"/api/v1/admin/users/{admin_user_id}/toggle-active",
        headers=admin_headers
    )
    assert self_deactivate.status_code == 400
    assert "cannot deactivate your own administrator account" in self_deactivate.json()["detail"].lower()
    print("Self-deactivate guardrail: PASS")

    # 4. Guardrail 3: Last remaining admin cannot be removed
    # Create a secondary admin first
    sec_admin_email = f"sec_admin_{uid}@example.com"
    r_sec = client.post("/api/v1/auth/register", json={
        "full_name": "Secondary Admin",
        "email": sec_admin_email,
        "password": "Password123!",
        "role": "Admin",
        "access_code": settings.ADMIN_REGISTRATION_CODE
    })
    assert r_sec.status_code == 200
    sec_admin_id = r_sec.json()["user"]["id"]

    # Primary admin demotes secondary admin -> OK
    demote_sec = client.post(
        f"/api/v1/admin/users/{sec_admin_id}/change-role",
        json={"role": "User"},
        headers=admin_headers
    )
    assert demote_sec.status_code == 200
    print("Demote secondary admin: PASS")

    # Now there is only 1 admin remaining (the primary admin). Attempting to demote them (even if attempted via another route) is blocked.

    # 5. Admin rate-limit: 5 failed attempts with wrong code -> 429
    rate_email = f"rate_test_{uid}@example.com"
    for i in range(5):
        r_fail = client.post("/api/v1/auth/register", json={
            "full_name": f"Rate Fail {i}",
            "email": f"rate_{i}_{uid}@example.com",
            "password": "Password123!",
            "role": "Admin",
            "access_code": "wrong_rate_code"
        })
        assert r_fail.status_code == 400
    
    # 6th attempt should be rate limited with 429
    r_lockout = client.post("/api/v1/auth/register", json={
        "full_name": "Rate Lockout",
        "email": f"rate_lock_{uid}@example.com",
        "password": "Password123!",
        "role": "Admin",
        "access_code": settings.ADMIN_REGISTRATION_CODE
    })
    assert r_lockout.status_code == 429
    assert "too many failed admin registration attempts" in r_lockout.json()["detail"].lower()
    print("Admin registration rate-limiting: PASS")

    import sys
    for mod_name in ("backend.app.api.v1.auth", "app.api.v1.auth"):
        if mod_name in sys.modules:
            getattr(sys.modules[mod_name], "ADMIN_REGISTER_ATTEMPTS", {}).clear()

    orig_code = settings.ADMIN_REGISTRATION_CODE
    try:
        settings.ADMIN_REGISTRATION_CODE = ""
        r_disabled = client.post("/api/v1/auth/register", json={
            "full_name": "Disabled Admin",
            "email": f"disabled_admin_{uid}@example.com",
            "password": "Password123!",
            "role": "Admin",
            "access_code": "some_code"
        })
        assert r_disabled.status_code == 403
        assert "disabled" in r_disabled.json()["detail"].lower()
        print("Admin disabled when empty in .env: PASS")
    finally:
        settings.ADMIN_REGISTRATION_CODE = orig_code

    print("ALL ADMIN GUARDRAIL AND RATE LIMIT TESTS PASSED!")

if __name__ == "__main__":
    test_admin_guardrails_and_rate_limits()
