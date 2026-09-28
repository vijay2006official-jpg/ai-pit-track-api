from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict
from app.models.pit import SeverityLevel, PitStatus

class BoundingBox(BaseModel):
    x_min: float = Field(..., description="Normalized minimum X coordinate [0.0 - 1.0]")
    y_min: float = Field(..., description="Normalized minimum Y coordinate [0.0 - 1.0]")
    x_max: float = Field(..., description="Normalized maximum X coordinate [0.0 - 1.0]")
    y_max: float = Field(..., description="Normalized maximum Y coordinate [0.0 - 1.0]")
    pixel_width: Optional[int] = None
    pixel_height: Optional[int] = None

class DetectionItem(BaseModel):
    id: Optional[int] = None
    confidence: float
    severity: SeverityLevel
    bbox: BoundingBox
    estimated_area_sq_px: Optional[float] = None
    annotated_image_url: Optional[str] = None
    raw_image_url: Optional[str] = None
    detected_at: Optional[datetime] = None

class ImageDetectionResponse(BaseModel):
    success: bool = True
    total_pits_detected: int
    max_severity: SeverityLevel
    detections: List[DetectionItem]
    annotated_image_url: Optional[str] = None
    associated_pit_id: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    message: str = "Inference completed successfully"

class RoadPitBase(BaseModel):
    latitude: float
    longitude: float
    address: Optional[str] = None
    road_name: Optional[str] = None
    severity: SeverityLevel = SeverityLevel.MEDIUM
    status: PitStatus = PitStatus.DETECTED
    notes: Optional[str] = None

class RoadPitCreate(RoadPitBase):
    pass

class RoadPitUpdate(BaseModel):
    severity: Optional[SeverityLevel] = None
    status: Optional[PitStatus] = None
    address: Optional[str] = None
    road_name: Optional[str] = None
    notes: Optional[str] = None

class RoadPitResponse(RoadPitBase):
    id: int
    detection_count: int
    max_confidence: float
    estimated_area_sq_px: float
    first_detected_at: datetime
    last_detected_at: datetime
    repaired_at: Optional[datetime] = None
    latest_annotated_image: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class RoadPitDetailResponse(RoadPitResponse):
    detections: List[DetectionItem] = []

    model_config = ConfigDict(from_attributes=True)

class VideoFrameDetection(BaseModel):
    frame_index: int
    timestamp_sec: float
    pits_detected: int
    detections: List[DetectionItem]

class VideoDetectionResponse(BaseModel):
    success: bool
    total_frames_processed: int
    total_pits_found: int
    video_duration_sec: float
    processed_video_url: Optional[str] = None
    frame_results: List[VideoFrameDetection]
