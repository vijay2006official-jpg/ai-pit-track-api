from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models.pit import RoadPit, PitDetection, SeverityLevel, PitStatus
from app.schemas.analytics import (
    RoadQualitySummary,
    GeoJSONFeatureCollection,
    GeoJSONFeature,
    GeoJSONGeometry,
    GeoJSONProperties
)

router = APIRouter(prefix="/analytics", tags=["Analytics & Spatial GeoJSON"])

@router.get("/summary", response_model=RoadQualitySummary, summary="Get road network health statistics & defect breakdown")
def get_analytics_summary(db: Session = Depends(get_db)):
    total_pits = db.query(RoadPit).count()
    active_pits = db.query(RoadPit).filter(RoadPit.status.in_([PitStatus.DETECTED, PitStatus.VERIFIED])).count()
    repaired_pits = db.query(RoadPit).filter(RoadPit.status == PitStatus.REPAIRED).count()
    in_progress_pits = db.query(RoadPit).filter(RoadPit.status == PitStatus.IN_PROGRESS).count()
    total_detections = db.query(PitDetection).count()

    # Severity distribution
    severities = [SeverityLevel.LOW, SeverityLevel.MEDIUM, SeverityLevel.HIGH, SeverityLevel.CRITICAL]
    severity_breakdown = {}
    for sev in severities:
        cnt = db.query(RoadPit).filter(RoadPit.severity == sev).count()
        severity_breakdown[sev.value] = cnt

    # Status distribution
    statuses = [PitStatus.DETECTED, PitStatus.VERIFIED, PitStatus.IN_PROGRESS, PitStatus.REPAIRED, PitStatus.FALSE_POSITIVE]
    status_breakdown = {}
    for st in statuses:
        cnt = db.query(RoadPit).filter(RoadPit.status == st).count()
        status_breakdown[st.value] = cnt

    # Avg confidence
    avg_conf = db.query(func.avg(RoadPit.max_confidence)).scalar() or 0.0

    # Calculate Road Health Index Score (0 to 100)
    # Penalty based on active pits weighted by severity
    critical_cnt = severity_breakdown.get(SeverityLevel.CRITICAL.value, 0)
    high_cnt = severity_breakdown.get(SeverityLevel.HIGH.value, 0)
    med_cnt = severity_breakdown.get(SeverityLevel.MEDIUM.value, 0)
    low_cnt = severity_breakdown.get(SeverityLevel.LOW.value, 0)

    penalty = (critical_cnt * 15.0) + (high_cnt * 8.0) + (med_cnt * 3.0) + (low_cnt * 1.0)
    health_score = max(0.0, min(100.0, 100.0 - penalty))

    return RoadQualitySummary(
        total_pits_recorded=total_pits,
        active_pits=active_pits,
        repaired_pits=repaired_pits,
        in_progress_pits=in_progress_pits,
        severity_breakdown=severity_breakdown,
        status_breakdown=status_breakdown,
        road_health_index_score=round(health_score, 1),
        average_confidence=round(float(avg_conf), 3),
        total_inspections=total_detections
    )

@router.get("/geojson", response_model=GeoJSONFeatureCollection, summary="Get all road pits as GeoJSON for maps & heatmaps")
def get_geojson_features(db: Session = Depends(get_db)):
    pits = db.query(RoadPit).all()

    features = []
    for p in pits:
        feature = GeoJSONFeature(
            type="Feature",
            geometry=GeoJSONGeometry(
                type="Point",
                coordinates=[p.longitude, p.latitude]
            ),
            properties=GeoJSONProperties(
                id=p.id,
                severity=p.severity,
                status=p.status,
                detection_count=p.detection_count,
                max_confidence=p.max_confidence,
                address=p.address,
                road_name=p.road_name,
                last_detected_at=p.last_detected_at.isoformat() if p.last_detected_at else ""
            )
        )
        features.append(feature)

    return GeoJSONFeatureCollection(
        type="FeatureCollection",
        features=features
    )

@router.post("/webhooks/test", summary="Test webhook hazard notification delivery")
async def test_webhook_alert(
    webhook_url: str = "https://httpbin.org/post"
):
    from app.services.webhook_service import WebhookService
    success = await WebhookService.send_alert_async(
        pit_id=999,
        severity="CRITICAL",
        road_name="Test Highway 101",
        latitude=37.7749,
        longitude=-122.4194,
        confidence=0.95,
        webhook_url=webhook_url
    )
    return {
        "success": success,
        "tested_url": webhook_url,
        "message": "Webhook test alert sent successfully" if success else "Webhook test failed (check URL or network)"
    }
