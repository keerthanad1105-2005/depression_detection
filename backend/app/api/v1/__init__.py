from fastapi import APIRouter
from app.api.v1.auth import router as auth_router
from app.api.v1.screening import router as screening_router
from app.api.v1.reports import router as reports_router
from app.api.v1.history import router as history_router
from app.api.v1.clinician import router as clinician_router
from app.api.v1.admin import router as admin_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(screening_router)
api_router.include_router(reports_router)
api_router.include_router(history_router)
api_router.include_router(clinician_router)
api_router.include_router(admin_router)
