import enum
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, Float, String, DateTime, Enum, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database import Base

def utc_now():
    return datetime.now(timezone.utc)

class SeverityLevel(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class PitStatus(str, enum.Enum):
    DETECTED = "DETECTED"
    VERIFIED = "VERIFIED"
    IN_PROGRESS = "IN_PROGRESS"
    REPAIRED = "REPAIRED"
    FALSE_POSITIVE = "FALSE_POSITIVE"

class RoadPit(Base):
    """
    Aggregated Tracked Pit/Pothole on a road.
    Multiple detections at close GPS locations update this pit entity.
    """
    __tablename__ = "road_pits"

    id = Column(Integer, primary_key=True, index=True)
    latitude = Column(Float, nullable=False, index=True)
    longitude = Column(Float, nullable=False, index=True)
    address = Column(String(255), nullable=True)
    road_name = Column(String(255), nullable=True)
    
    severity = Column(Enum(SeverityLevel), default=SeverityLevel.MEDIUM, index=True)
    status = Column(Enum(PitStatus), default=PitStatus.DETECTED, index=True)
    
    detection_count = Column(Integer, default=1)
    max_confidence = Column(Float, default=0.0)
    estimated_area_sq_px = Column(Float, default=0.0)
    
    first_detected_at = Column(DateTime, default=utc_now)
    last_detected_at = Column(DateTime, default=utc_now, onupdate=utc_now)
    repaired_at = Column(DateTime, nullable=True)
    
    notes = Column(Text, nullable=True)
    
    # Relationship with individual inspection detections
    detections = relationship("PitDetection", back_populates="road_pit", cascade="all, delete-orphan")


class PitDetection(Base):
    """
    Single snapshot/detection of a pothole from an image/video frame.
    """
    __tablename__ = "pit_detections"

    id = Column(Integer, primary_key=True, index=True)
    road_pit_id = Column(Integer, ForeignKey("road_pits.id", ondelete="CASCADE"), nullable=True)
    
    confidence = Column(Float, nullable=False)
    severity = Column(Enum(SeverityLevel), default=SeverityLevel.MEDIUM)
    
    # Bounding Box normalized [x_min, y_min, x_max, y_max]
    bbox_x_min = Column(Float, nullable=False)
    bbox_y_min = Column(Float, nullable=False)
    bbox_x_max = Column(Float, nullable=False)
    bbox_y_max = Column(Float, nullable=False)
    
    # Image Paths
    raw_image_path = Column(String(500), nullable=True)
    annotated_image_path = Column(String(500), nullable=True)
    
    # Telemetry
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    speed_kmh = Column(Float, nullable=True)
    device_id = Column(String(100), nullable=True)
    
    detected_at = Column(DateTime, default=utc_now)
    
    road_pit = relationship("RoadPit", back_populates="detections")
