import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

from app.config import settings, UPLOAD_DIR, ANNOTATED_DIR
from app.database import engine, Base
from app.routers import (
    detection_router,
    pits_router,
    analytics_router,
    reports_router
)

# Initialize database schema tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="""
## AI Pit Track API 🛣️🔍
An AI-powered computer vision and geospatial tracking API for real-time road pit, defect, and pothole detection.

### Key Capabilities:
- **AI Pit & Pothole Detection**: YOLO / Adaptive Computer Vision engine detecting road depressions with confidence & severity rating.
- **Geospatial Tracking & Clustering**: Groups repeated detections within configurable GPS radius to prevent duplicates.
- **Defect Lifecycle Management**: Track repair stages from `DETECTED` to `IN_PROGRESS` and `REPAIRED`.
- **Road Health Index & GeoJSON**: Instant heatmaps, severity breakdown, and GeoJSON endpoints.
- **CSV & Audit Reporting**: Road maintenance exports for engineering and municipal teams.
- **Built-in Interactive Dashboard**: Visual map, live image inspector, and metrics at `/dashboard`.
    """,
    openapi_tags=[
        {"name": "AI Detection & Inference", "description": "Run AI vision models on road images and video streams"},
        {"name": "Road Pit Management", "description": "CRUD operations, status tracking, and pit defect lifecycle"},
        {"name": "Analytics & Spatial GeoJSON", "description": "GeoJSON points, heatmaps, and road quality index scores"},
        {"name": "Maintenance & Inspection Reports", "description": "Export reports for highway authorities and maintenance teams"},
    ]
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
api_v1_prefix = settings.API_V1_STR
app.include_router(detection_router, prefix=api_v1_prefix)
app.include_router(pits_router, prefix=api_v1_prefix)
app.include_router(analytics_router, prefix=api_v1_prefix)
app.include_router(reports_router, prefix=api_v1_prefix)

# Mount Uploads directory for static image serving
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

# Mount Dashboard frontend
STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/dashboard", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/dashboard")

@app.get("/health", tags=["Health"])
def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION
    }
