from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.pit import RoadPit, PitDetection, SeverityLevel, PitStatus
from app.schemas.pit import (
    RoadPitResponse,
    RoadPitDetailResponse,
    RoadPitCreate,
    RoadPitUpdate,
    DetectionItem,
    BoundingBox
)
from app.services.geo_tracker import GeoTrackerService

router = APIRouter(prefix="/pits", tags=["Road Pit Management"])

@router.get("", response_model=List[RoadPitResponse], summary="List tracked road pits")
def list_pits(
    severity: Optional[SeverityLevel] = Query(None, description="Filter by severity"),
    status: Optional[PitStatus] = Query(None, description="Filter by status"),
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0, description="Minimum detection confidence"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    query = db.query(RoadPit)

    if severity:
        query = query.filter(RoadPit.severity == severity)
    if status:
        query = query.filter(RoadPit.status == status)
    if min_confidence:
        query = query.filter(RoadPit.max_confidence >= min_confidence)

    pits = query.order_by(RoadPit.last_detected_at.desc()).offset(skip).limit(limit).all()

    # Attach latest annotated image if available
    response = []
    for pit in pits:
        latest_det = db.query(PitDetection).filter(PitDetection.road_pit_id == pit.id).order_by(PitDetection.detected_at.desc()).first()
        pit_data = RoadPitResponse.model_validate(pit)
        if latest_det:
            pit_data.latest_annotated_image = latest_det.annotated_image_path
        response.append(pit_data)

    return response

@router.post("", response_model=RoadPitResponse, status_code=status.HTTP_201_CREATED, summary="Manually register a road pit")
def create_pit(
    pit_in: RoadPitCreate,
    db: Session = Depends(get_db)
):
    road_name, address = GeoTrackerService.estimate_road_address(pit_in.latitude, pit_in.longitude)
    now = datetime.now(timezone.utc)
    db_pit = RoadPit(
        latitude=pit_in.latitude,
        longitude=pit_in.longitude,
        address=pit_in.address or address,
        road_name=pit_in.road_name or road_name,
        severity=pit_in.severity,
        status=pit_in.status,
        notes=pit_in.notes,
        detection_count=1,
        max_confidence=1.0,
        first_detected_at=now,
        last_detected_at=now
    )
    db.add(db_pit)
    db.commit()
    db.refresh(db_pit)
    return RoadPitResponse.model_validate(db_pit)

@router.get("/{pit_id}", response_model=RoadPitDetailResponse, summary="Get details and history of a specific road pit")
def get_pit(pit_id: int, db: Session = Depends(get_db)):
    pit = db.query(RoadPit).filter(RoadPit.id == pit_id).first()
    if not pit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Road pit with ID {pit_id} not found")

    detections = db.query(PitDetection).filter(PitDetection.road_pit_id == pit.id).order_by(PitDetection.detected_at.desc()).all()
    
    detection_items = [
        DetectionItem(
            id=d.id,
            confidence=d.confidence,
            severity=d.severity,
            bbox=BoundingBox(
                x_min=d.bbox_x_min,
                y_min=d.bbox_y_min,
                x_max=d.bbox_x_max,
                y_max=d.bbox_y_max
            ),
            annotated_image_url=d.annotated_image_path,
            raw_image_url=d.raw_image_path,
            detected_at=d.detected_at
        )
        for d in detections
    ]

    latest_annotated = detection_items[0].annotated_image_url if detection_items else None
    
    return RoadPitDetailResponse(
        id=pit.id,
        latitude=pit.latitude,
        longitude=pit.longitude,
        address=pit.address,
        road_name=pit.road_name,
        severity=pit.severity,
        status=pit.status,
        notes=pit.notes,
        detection_count=pit.detection_count,
        max_confidence=pit.max_confidence,
        estimated_area_sq_px=pit.estimated_area_sq_px,
        first_detected_at=pit.first_detected_at,
        last_detected_at=pit.last_detected_at,
        repaired_at=pit.repaired_at,
        latest_annotated_image=latest_annotated,
        detections=detection_items
    )

@router.patch("/{pit_id}", response_model=RoadPitResponse, summary="Update status or severity of a road pit")
def update_pit(
    pit_id: int,
    pit_update: RoadPitUpdate,
    db: Session = Depends(get_db)
):
    pit = db.query(RoadPit).filter(RoadPit.id == pit_id).first()
    if not pit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Road pit with ID {pit_id} not found")

    if pit_update.severity is not None:
        pit.severity = pit_update.severity
    if pit_update.status is not None:
        pit.status = pit_update.status
        if pit_update.status == PitStatus.REPAIRED and not pit.repaired_at:
            pit.repaired_at = datetime.now(timezone.utc)
    if pit_update.address is not None:
        pit.address = pit_update.address
    if pit_update.road_name is not None:
        pit.road_name = pit_update.road_name
    if pit_update.notes is not None:
        pit.notes = pit_update.notes

    db.commit()
    db.refresh(pit)
    return RoadPitResponse.model_validate(pit)

@router.delete("/{pit_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a road pit record")
def delete_pit(pit_id: int, db: Session = Depends(get_db)):
    pit = db.query(RoadPit).filter(RoadPit.id == pit_id).first()
    if not pit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Road pit with ID {pit_id} not found")

    db.delete(pit)
    db.commit()
    return None
