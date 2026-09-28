import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
ANNOTATED_DIR = UPLOAD_DIR / "annotated"
ANNOTATED_DIR.mkdir(parents=True, exist_ok=True)
MODEL_DIR = BASE_DIR / "models_weights"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Pit Track API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    DATABASE_URL: str = f"sqlite:///{BASE_DIR}/pit_track.db"
    
    # AI Detection Settings
    YOLO_MODEL_PATH: str = str(MODEL_DIR / "pothole_yolo.pt")
    DEFAULT_CONFIDENCE_THRESHOLD: float = 0.35
    DEFAULT_IOU_THRESHOLD: float = 0.45
    USE_CV_FALLBACK_IF_NO_WEIGHTS: bool = True
    
    # Spatial Tracking Settings
    GEO_DUPLICATION_RADIUS_METERS: float = 7.0  # detections within 7m are clustered as the same pit
    
    # Severity Thresholds (defects / area ratio)
    SEVERITY_LOW_MAX_AREA: float = 0.02
    SEVERITY_MED_MAX_AREA: float = 0.08
    SEVERITY_HIGH_MAX_AREA: float = 0.18

    # Webhook Alert Settings
    ALERT_WEBHOOK_URL: Optional[str] = None
    ENABLE_ALERT_WEBHOOKS: bool = True

    model_config = SettingsConfigDict(case_sensitive=True, env_file=".env", extra="ignore")

settings = Settings()
