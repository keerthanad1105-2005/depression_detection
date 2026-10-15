"""
MindScan FastAPI Application Entrypoint Shim
Enables running the application via both:
    uvicorn app.main:app --reload --port 8000
and
    uvicorn main:app --reload --port 8000
"""
from main import app

__all__ = ["app"]
