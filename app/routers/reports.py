from fastapi import APIRouter, Depends, Response, HTTPException, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.pit import RoadPit, PitDetection
from app.services.report_generator import ReportGeneratorService
from app.services.work_order_service import WorkOrderService

router = APIRouter(prefix="/reports", tags=["Maintenance & Inspection Reports"])

@router.get("/export/csv", summary="Export road maintenance audit report as CSV")
def export_csv_report(db: Session = Depends(get_db)):
    pits = db.query(RoadPit).order_by(RoadPit.last_detected_at.desc()).all()
    csv_content = ReportGeneratorService.generate_csv_report(pits)

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=road_pits_audit_report.csv"}
    )

@router.get("/work-order/{pit_id}", response_class=HTMLResponse, summary="Generate printable PDF/HTML repair work order")
def get_printable_work_order(pit_id: int, db: Session = Depends(get_db)):
    pit = db.query(RoadPit).filter(RoadPit.id == pit_id).first()
    if not pit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Road pit with ID {pit_id} not found")

    latest_det = db.query(PitDetection).filter(PitDetection.road_pit_id == pit.id).order_by(PitDetection.detected_at.desc()).first()
    latest_img = latest_det.annotated_image_path if latest_det else None

    html_content = WorkOrderService.generate_printable_html_work_order(pit, latest_image_url=latest_img)
    return HTMLResponse(content=html_content)

@router.get("/work-order/{pit_id}/json", summary="Get repair material and cost estimates in JSON")
def get_work_order_estimates_json(pit_id: int, db: Session = Depends(get_db)):
    pit = db.query(RoadPit).filter(RoadPit.id == pit_id).first()
    if not pit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Road pit with ID {pit_id} not found")

    estimates = WorkOrderService.calculate_repair_material_estimate(pit.severity, pit.estimated_area_sq_px)
    return {
        "pit_id": pit.id,
        "road_name": pit.road_name,
        "severity": pit.severity.value,
        "status": pit.status.value,
        "coordinates": {"latitude": pit.latitude, "longitude": pit.longitude},
        "material_and_dispatch_estimates": estimates
    }
