from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from app.models.pit import SeverityLevel, PitStatus

class GeoJSONGeometry(BaseModel):
    type: str = "Point"
    coordinates: List[float]  # [longitude, latitude]

class GeoJSONProperties(BaseModel):
    id: int
    severity: SeverityLevel
    status: PitStatus
    detection_count: int
    max_confidence: float
    address: Optional[str] = None
    road_name: Optional[str] = None
    last_detected_at: str

class GeoJSONFeature(BaseModel):
    type: str = "Feature"
    geometry: GeoJSONGeometry
    properties: GeoJSONProperties

class GeoJSONFeatureCollection(BaseModel):
    type: str = "FeatureCollection"
    features: List[GeoJSONFeature]

class RoadQualitySummary(BaseModel):
    total_pits_recorded: int
    active_pits: int
    repaired_pits: int
    in_progress_pits: int
    severity_breakdown: Dict[str, int]
    status_breakdown: Dict[str, int]
    road_health_index_score: float  # 0 to 100 (100 is pristine road)
    average_confidence: float
    total_inspections: int
