import io
import csv
from typing import List
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.pit import RoadPit

class ReportGeneratorService:
    @staticmethod
    def generate_csv_report(pits: List[RoadPit]) -> str:
        """
        Generates a CSV audit export for road maintenance departments.
        """
        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow([
            "Pit ID",
            "Latitude",
            "Longitude",
            "Road Name",
            "Address",
            "Severity Level",
            "Current Status",
            "Detection Count",
            "Max Confidence (%)",
            "Est. Area (px)",
            "First Detected",
            "Last Detected",
            "Repaired At",
            "Notes"
        ])

        for p in pits:
            writer.writerow([
                p.id,
                p.latitude,
                p.longitude,
                p.road_name or "",
                p.address or "",
                p.severity.value,
                p.status.value,
                p.detection_count,
                f"{p.max_confidence * 100:.1f}%",
                f"{p.estimated_area_sq_px:.1f}",
                p.first_detected_at.strftime("%Y-%m-%d %H:%M:%S") if p.first_detected_at else "",
                p.last_detected_at.strftime("%Y-%m-%d %H:%M:%S") if p.last_detected_at else "",
                p.repaired_at.strftime("%Y-%m-%d %H:%M:%S") if p.repaired_at else "N/A",
                p.notes or ""
            ])

        return output.getvalue()
