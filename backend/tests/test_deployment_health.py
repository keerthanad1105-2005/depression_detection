import pytest
from fastapi.testclient import TestClient
try:
    from backend.main import app
    from backend.app.core.config import settings
except ImportError:
    from main import app
    from app.core.config import settings

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("healthy", "degraded")
    assert "models" in data
    assert "database" in data
    assert data["database"] == "connected"
    assert "ffmpeg" in data
    assert "version" in data
    assert "environment" in data

    # Modality status honest reporting check
    models = data["models"]
    assert "text" in models
    assert "voice" in models
    assert "face" in models
    assert "available" in models["text"]
    assert "status" in models["text"]
    assert "available" in models["voice"]
    assert "status" in models["voice"]
    assert "available" in models["face"]
    assert "status" in models["face"]


def test_security_headers():
    response = client.get("/health")
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "SAMEORIGIN"
    assert response.headers.get("X-XSS-Protection") == "1; mode=block"
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"


def test_cors_preflight():
    response = client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type"
        }
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert response.headers.get("access-control-allow-credentials") == "true"
