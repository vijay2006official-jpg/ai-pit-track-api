import os
import shutil
import uuid
import time
import base64
import numpy as np
import cv2
from datetime import datetime, timezone
from typing import Optional
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import UPLOAD_DIR, ANNOTATED_DIR, settings
from app.models.pit import RoadPit, PitDetection, PitStatus, SeverityLevel
from app.schemas.pit import ImageDetectionResponse, VideoDetectionResponse
from app.services.ai_detector import ai_detector
from app.services.geo_tracker import GeoTrackerService

router = APIRouter(prefix="/detect", tags=["AI Detection & Inference"])

@router.post("/image", response_model=ImageDetectionResponse, summary="Detect road pits & potholes in an image")
async def detect_road_pit_image(
    file: UploadFile = File(..., description="Road/Dashcam image (JPEG/PNG)"),
    latitude: Optional[float] = Form(None, description="GPS Latitude"),
    longitude: Optional[float] = Form(None, description="GPS Longitude"),
    speed_kmh: Optional[float] = Form(None, description="Vehicle speed in km/h"),
    device_id: Optional[str] = Form(None, description="Dashcam / Mobile Device identifier"),
    confidence_threshold: Optional[float] = Form(settings.DEFAULT_CONFIDENCE_THRESHOLD, description="Confidence threshold (0.0 - 1.0)"),
    db: Session = Depends(get_db)
):
    """
    Accepts an image, runs AI computer vision / YOLO detection, computes severity,
    performs spatial tracking/deduplication if GPS is provided, and persists the results.
    """
    # Validate file extension or content-type
    ext = Path(file.filename).suffix.lower() if file.filename else ""
    valid_exts = [".jpg", ".jpeg", ".png", ".webp", ".bmp", ".jfif", ".tif", ".tiff"]
    is_image_type = file.content_type and file.content_type.startswith("image/")
    
    if ext not in valid_exts and not is_image_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{ext}'. Please upload an image (.jpg, .jpeg, .png, .webp)."
        )

    clean_ext = ext if ext in valid_exts else ".jpg"
    safe_name = "".join(c for c in (file.filename or "upload") if c.isalnum() or c in "._-")
    raw_filename = f"raw_{uuid.uuid4().hex[:12]}_{safe_name}{clean_ext if not safe_name.endswith(clean_ext) else ''}"
    raw_path = UPLOAD_DIR / raw_filename

    file.file.seek(0)
    with open(raw_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        # Run AI detection
        detections, annotated_path, max_severity = ai_detector.detect_on_image(
            raw_path,
            confidence_threshold=confidence_threshold or settings.DEFAULT_CONFIDENCE_THRESHOLD
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI Detection failed: {str(e)}"
        )

    # Relative paths for web access
    annotated_url = f"/uploads/annotated/{annotated_path.name}"
    raw_url = f"/uploads/{raw_filename}"

    associated_pit_id = None

    if detections:
        # If GPS coordinates are provided, cluster or create a RoadPit
        if latitude is not None and longitude is not None:
            existing_pit = GeoTrackerService.find_nearest_pit(db, latitude, longitude)
            
            total_est_area = sum(d.estimated_area_sq_px or 0 for d in detections)
            max_conf = max(d.confidence for d in detections)

            now = datetime.now(timezone.utc)
            if existing_pit:
                # Update existing tracked pit
                existing_pit.detection_count += 1
                existing_pit.last_detected_at = now
                if max_conf > existing_pit.max_confidence:
                    existing_pit.max_confidence = max_conf
                if total_est_area > existing_pit.estimated_area_sq_px:
                    existing_pit.estimated_area_sq_px = total_est_area
                # Escalate severity if detected higher
                severity_rank = {SeverityLevel.LOW: 1, SeverityLevel.MEDIUM: 2, SeverityLevel.HIGH: 3, SeverityLevel.CRITICAL: 4}
                if severity_rank[max_severity] > severity_rank[existing_pit.severity]:
                    existing_pit.severity = max_severity

                associated_pit_id = existing_pit.id
                db_pit = existing_pit
            else:
                # Create new RoadPit record
                road_name, address = GeoTrackerService.estimate_road_address(latitude, longitude)
                db_pit = RoadPit(
                    latitude=latitude,
                    longitude=longitude,
                    road_name=road_name,
                    address=address,
                    severity=max_severity,
                    status=PitStatus.DETECTED,
                    detection_count=1,
                    max_confidence=max_conf,
                    estimated_area_sq_px=total_est_area,
                    first_detected_at=now,
                    last_detected_at=now
                )
                db.add(db_pit)
                db.flush()
                associated_pit_id = db_pit.id

            # Save individual detection items in DB
            for det in detections:
                pit_detection = PitDetection(
                    road_pit_id=associated_pit_id,
                    confidence=det.confidence,
                    severity=det.severity,
                    bbox_x_min=det.bbox.x_min,
                    bbox_y_min=det.bbox.y_min,
                    bbox_x_max=det.bbox.x_max,
                    bbox_y_max=det.bbox.y_max,
                    raw_image_path=raw_url,
                    annotated_image_path=annotated_url,
                    latitude=latitude,
                    longitude=longitude,
                    speed_kmh=speed_kmh,
                    device_id=device_id,
                    detected_at=now
                )
                db.add(pit_detection)

            db.commit()

            # Dispatch Emergency Webhook Alert if defect is critical/high
            if max_severity in [SeverityLevel.CRITICAL, SeverityLevel.HIGH]:
                from app.services.webhook_service import WebhookService
                WebhookService.dispatch_alert_background(
                    pit_id=associated_pit_id,
                    severity=max_severity.value,
                    road_name=getattr(db_pit, "road_name", "Unknown Route"),
                    latitude=latitude,
                    longitude=longitude,
                    confidence=max_conf
                )

    return ImageDetectionResponse(
        success=True,
        total_pits_detected=len(detections),
        max_severity=max_severity if detections else SeverityLevel.LOW,
        detections=detections,
        annotated_image_url=annotated_url if detections else raw_url,
        associated_pit_id=associated_pit_id,
        latitude=latitude,
        longitude=longitude,
        message=f"Detected {len(detections)} road pit(s)/defect(s)" if detections else "No road pits detected in this frame."
    )


@router.post("/video", response_model=VideoDetectionResponse, summary="Analyze road video / dashcam footage")
async def detect_road_pit_video(
    file: UploadFile = File(..., description="Dashcam / Road Video (.mp4, .avi, .mov)"),
    sample_fps: int = Form(2, description="Frames per second to sample for detection"),
    confidence_threshold: float = Form(settings.DEFAULT_CONFIDENCE_THRESHOLD, description="Confidence threshold")
):
    """
    Analyzes uploaded video footage frame-by-frame and identifies road defects across timestamps.
    """
    ext = Path(file.filename).suffix.lower()
    if ext not in [".mp4", ".avi", ".mov", ".mkv"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported video format '{ext}'. Allowed: .mp4, .avi, .mov, .mkv"
        )

    temp_video_path = UPLOAD_DIR / f"video_{uuid.uuid4().hex[:12]}_{file.filename}"
    with open(temp_video_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        results = ai_detector.detect_on_video(
            temp_video_path,
            sample_fps=sample_fps,
            conf_threshold=confidence_threshold
        )
        return VideoDetectionResponse(
            success=True,
            total_frames_processed=results["total_frames_processed"],
            total_pits_found=results["total_pits_found"],
            video_duration_sec=results["video_duration_sec"],
            frame_results=results["frame_results"]
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Video processing failed: {str(e)}"
        )


@router.websocket("/ws/stream")
async def websocket_dashcam_stream(websocket: WebSocket, db: Session = Depends(get_db)):
    """
    Real-Time WebSocket Video Streaming Endpoint.
    Accepts continuous video frame packets (base64) with telemetry, runs sub-20ms inference,
    and streams back bounding boxes and severity metrics in real-time.
    """
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            start_time = time.time()

            base64_str = data.get("image", "")
            if "," in base64_str:
                base64_str = base64_str.split(",", 1)[1]

            img_bytes = base64.b64decode(base64_str)
            nparr = np.frombuffer(img_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if frame is None:
                await websocket.send_json({"error": "Failed to decode frame image"})
                continue

            conf_thresh = float(data.get("confidence_threshold", settings.DEFAULT_CONFIDENCE_THRESHOLD))
            detections, max_severity = ai_detector.detect_on_frame(frame, confidence_threshold=conf_thresh)

            lat = data.get("latitude")
            lon = data.get("longitude")
            associated_pit_id = None

            if detections and lat is not None and lon is not None:
                existing_pit = GeoTrackerService.find_nearest_pit(db, float(lat), float(lon))
                now = datetime.now(timezone.utc)
                if existing_pit:
                    existing_pit.detection_count += 1
                    existing_pit.last_detected_at = now
                    associated_pit_id = existing_pit.id
                else:
                    road_name, address = GeoTrackerService.estimate_road_address(float(lat), float(lon))
                    db_pit = RoadPit(
                        latitude=float(lat),
                        longitude=float(lon),
                        road_name=road_name,
                        address=address,
                        severity=max_severity,
                        status=PitStatus.DETECTED,
                        detection_count=1,
                        max_confidence=max(d.confidence for d in detections),
                        first_detected_at=now,
                        last_detected_at=now
                    )
                    db.add(db_pit)
                    db.flush()
                    associated_pit_id = db_pit.id

                db.commit()

            latency_ms = round((time.time() - start_time) * 1000, 1)

            await websocket.send_json({
                "success": True,
                "latency_ms": latency_ms,
                "fps": round(1000.0 / max(latency_ms, 1.0), 1),
                "total_pits_detected": len(detections),
                "max_severity": max_severity.value if detections else "NONE",
                "associated_pit_id": associated_pit_id,
                "detections": [
                    {
                        "id": d.id,
                        "confidence": d.confidence,
                        "severity": d.severity.value,
                        "bbox": {
                            "x_min": d.bbox.x_min,
                            "y_min": d.bbox.y_min,
                            "x_max": d.bbox.x_max,
                            "y_max": d.bbox.y_max
                        }
                    }
                    for d in detections
                ]
            })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"error": str(e)})
            await websocket.close()
        except Exception:
            pass
