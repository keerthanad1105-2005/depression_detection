"""
Deprecated Analytics Module
The standalone Statistics Dashboard has been retired.
All-users population metrics (timeline, risk distribution, symptom frequencies) have been
consolidated into the Admin Dashboard (/admin-dashboard), and personal trajectories
are served via the 'My trend' interactive chart on the user's home and results pages.
"""
from fastapi import APIRouter
from fastapi.responses import RedirectResponse

router = APIRouter(prefix="/analytics", tags=["Analytics & Trends (Deprecated)"])

@router.get("")
@router.get("/")
@router.get("/summary")
@router.get("/trends")
def deprecated_analytics_redirect():
    """Redirects deprecated statistics endpoints to Home."""
    return RedirectResponse(url="/", status_code=302)
