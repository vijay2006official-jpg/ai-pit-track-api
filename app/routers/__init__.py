from app.routers.detection import router as detection_router
from app.routers.pits import router as pits_router
from app.routers.analytics import router as analytics_router
from app.routers.reports import router as reports_router

__all__ = [
    "detection_router",
    "pits_router",
    "analytics_router",
    "reports_router"
]
