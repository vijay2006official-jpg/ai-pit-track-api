import numpy as np
import cv2
from pathlib import Path
from app.services.ai_detector import ai_detector
from app.models.pit import SeverityLevel

def test_detector_finds_pothole_depression(tmp_path):
    # Generate test image with pothole
    h, w = 480, 640
    img = np.full((h, w, 3), 90, dtype=np.uint8)
    
    # Draw dark depression
    cv2.ellipse(img, (320, 300), (90, 45), 0, 0, 360, (15, 15, 15), -1)
    
    test_img_path = tmp_path / "test_pothole.jpg"
    cv2.imwrite(str(test_img_path), img)

    detections, annotated_path, highest_severity = ai_detector.detect_on_image(test_img_path)

    assert len(detections) >= 1
    assert annotated_path.exists()
    assert highest_severity in [SeverityLevel.LOW, SeverityLevel.MEDIUM, SeverityLevel.HIGH, SeverityLevel.CRITICAL]
    assert 0.0 <= detections[0].bbox.x_min <= 1.0
    assert 0.0 <= detections[0].bbox.y_max <= 1.0
