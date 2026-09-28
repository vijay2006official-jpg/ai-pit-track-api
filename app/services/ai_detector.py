import os
import uuid
from typing import List, Tuple, Optional, Dict, Any
from pathlib import Path
import numpy as np
import cv2

from app.config import settings, ANNOTATED_DIR, UPLOAD_DIR
from app.models.pit import SeverityLevel
from app.schemas.pit import BoundingBox, DetectionItem


class AIDetectorService:
    def __init__(self):
        self.yolo_model = None
        self._load_yolo_if_available()

    def _load_yolo_if_available(self):
        """Loads custom YOLO weights if present on disk."""
        if os.path.exists(settings.YOLO_MODEL_PATH):
            try:
                from ultralytics import YOLO
                self.yolo_model = YOLO(settings.YOLO_MODEL_PATH)
                print(f"[AIDetector] Loaded YOLO weights from {settings.YOLO_MODEL_PATH}")
            except Exception as e:
                print(f"[AIDetector] Custom YOLO load warning: {e}")
                self.yolo_model = None

    def calculate_severity(self, bbox_area_ratio: float, depression_intensity: float) -> SeverityLevel:
        """
        Calculates road defect severity based on frame area ratio and depression depth.
        """
        score = (bbox_area_ratio * 0.6) + (depression_intensity * 0.4)

        if score < settings.SEVERITY_LOW_MAX_AREA:
            return SeverityLevel.LOW
        elif score < settings.SEVERITY_MED_MAX_AREA:
            return SeverityLevel.MEDIUM
        elif score < settings.SEVERITY_HIGH_MAX_AREA:
            return SeverityLevel.HIGH
        else:
            return SeverityLevel.CRITICAL

    def detect_pits_cv_engine(
        self,
        image_np: np.ndarray,
        conf_threshold: float = 0.30
    ) -> List[Dict[str, Any]]:
        """
        Multi-Stage Road Pit & Pothole Vision Engine.
        Combines:
        1. Dark asphalt depression segmentation (Otsu & Adaptive Thresholding)
        2. Black-Hat morphological filtering for localized dips & cracks
        3. Contour geometric filtering & contrast verification
        """
        h, w = image_np.shape[:2]
        frame_area = float(h * w)
        gray = cv2.cvtColor(image_np, cv2.COLOR_BGR2GRAY)

        # 1. CLAHE Contrast Enhancement
        clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        blurred = cv2.GaussianBlur(enhanced, (5, 5), 0)

        # 2. Road Region of Interest (focusing on bottom 80% where road surface is situated)
        roi_start_y = int(h * 0.20)
        roi_gray = gray[roi_start_y:h, :]
        roi_blur = blurred[roi_start_y:h, :]

        # 3. Method A: Dark depression thresholding relative to median road brightness
        median_brightness = float(np.median(roi_gray))
        dark_thresh_val = max(10.0, median_brightness * 0.75)
        _, mask_dark = cv2.threshold(roi_blur, int(dark_thresh_val), 255, cv2.THRESH_BINARY_INV)

        # 4. Method B: Morphological Black-Hat filter (extracts dark structures smaller than kernel)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31))
        blackhat = cv2.morphologyEx(roi_blur, cv2.MORPH_BLACKHAT, kernel)
        _, mask_blackhat = cv2.threshold(blackhat, 18, 255, cv2.THRESH_BINARY)

        # Combine both detection masks
        combined_mask = cv2.bitwise_or(mask_dark, mask_blackhat)

        # Clean noise with morphological open & close
        clean_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        cleaned = cv2.morphologyEx(combined_mask, cv2.MORPH_OPEN, clean_kernel)
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, clean_kernel)

        contours, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        detections = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            # Must be between 0.05% and 45% of total frame area
            if area < (frame_area * 0.0005) or area > (frame_area * 0.45):
                continue

            x, y, bw, bh = cv2.boundingRect(cnt)
            abs_y = y + roi_start_y

            aspect_ratio = float(bw) / max(bh, 1)
            # Potholes and road pits typically have aspect ratio between 0.2 and 4.5
            if aspect_ratio < 0.2 or aspect_ratio > 4.5:
                continue

            pit_roi = gray[abs_y:abs_y + bh, x:x + bw]
            if pit_roi.size == 0:
                continue

            local_mean = float(np.mean(pit_roi))
            depression_ratio = max(0.0, (median_brightness - local_mean) / (median_brightness + 1e-5))
            area_ratio = area / frame_area

            # Estimate confidence based on contrast, edge definition, and depression depth
            confidence = min(0.98, 0.45 + (depression_ratio * 0.4) + min(0.35, area_ratio * 4.0))

            if confidence >= conf_threshold:
                severity = self.calculate_severity(area_ratio, depression_ratio)
                detections.append({
                    "bbox": BoundingBox(
                        x_min=float(x) / w,
                        y_min=float(abs_y) / h,
                        x_max=float(x + bw) / w,
                        y_max=float(abs_y + bh) / h,
                        pixel_width=bw,
                        pixel_height=bh
                    ),
                    "confidence": round(float(confidence), 3),
                    "severity": severity,
                    "area_sq_px": float(area)
                })

        return self._nms_bboxes(detections)

    def _nms_bboxes(self, detections: List[Dict[str, Any]], iou_thresh: float = 0.4) -> List[Dict[str, Any]]:
        """Performs Non-Maximum Suppression on bounding boxes."""
        if not detections:
            return []

        detections = sorted(detections, key=lambda d: d["confidence"], reverse=True)
        keep = []

        while detections:
            current = detections.pop(0)
            keep.append(current)

            b1 = current["bbox"]
            remaining = []
            for d in detections:
                b2 = d["bbox"]
                ix_min = max(b1.x_min, b2.x_min)
                iy_min = max(b1.y_min, b2.y_min)
                ix_max = min(b1.x_max, b2.x_max)
                iy_max = min(b1.y_max, b2.y_max)

                iw = max(0.0, ix_max - ix_min)
                ih = max(0.0, iy_max - iy_min)
                inter = iw * ih

                area1 = (b1.x_max - b1.x_min) * (b1.y_max - b1.y_min)
                area2 = (b2.x_max - b2.x_min) * (b2.y_max - b2.y_min)
                union = area1 + area2 - inter

                iou = inter / (union + 1e-6)
                if iou < iou_thresh:
                    remaining.append(d)
            detections = remaining

        return keep

    def detect_on_image(
        self,
        image_path: Path,
        confidence_threshold: float = settings.DEFAULT_CONFIDENCE_THRESHOLD
    ) -> Tuple[List[DetectionItem], Path, SeverityLevel]:
        """
        Runs detection on an image, draws styled bounding boxes, saves annotated output.
        """
        image = cv2.imread(str(image_path))
        if image is None:
            raise ValueError(f"Unable to read image at {image_path}")

        h, w = image.shape[:2]
        raw_detections: List[Dict[str, Any]] = []

        # 1. Try YOLO if custom weights are loaded
        if self.yolo_model is not None:
            try:
                results = self.yolo_model.predict(source=str(image_path), conf=confidence_threshold, verbose=False)
                for r in results:
                    for box in r.boxes:
                        coords = box.xyxy[0].cpu().numpy()
                        conf = float(box.conf[0].cpu().numpy())
                        xmin, ymin, xmax, ymax = coords
                        bw = int(xmax - xmin)
                        bh = int(ymax - ymin)
                        area = float(bw * bh)
                        area_ratio = area / (h * w)
                        severity = self.calculate_severity(area_ratio, 0.4)

                        raw_detections.append({
                            "bbox": BoundingBox(
                                x_min=float(xmin) / w,
                                y_min=float(ymin) / h,
                                x_max=float(xmax) / w,
                                y_max=float(ymax) / h,
                                pixel_width=bw,
                                pixel_height=bh
                            ),
                            "confidence": round(conf, 3),
                            "severity": severity,
                            "area_sq_px": area
                        })
            except Exception as e:
                print(f"[AIDetector] YOLO inference failed, using CV engine: {e}")

        # 2. Fallback to adaptive Computer Vision engine
        if not raw_detections:
            raw_detections = self.detect_pits_cv_engine(image, conf_threshold=confidence_threshold)

        # 3. Create Annotated Image
        annotated_img = image.copy()
        severity_colors = {
            SeverityLevel.LOW: (0, 255, 128),       # Cyan-Green
            SeverityLevel.MEDIUM: (0, 215, 255),    # Yellow-Amber
            SeverityLevel.HIGH: (0, 128, 255),      # Orange
            SeverityLevel.CRITICAL: (0, 0, 255)     # Red
        }

        detection_items: List[DetectionItem] = []
        highest_severity = SeverityLevel.LOW

        severity_rank = {
            SeverityLevel.LOW: 1,
            SeverityLevel.MEDIUM: 2,
            SeverityLevel.HIGH: 3,
            SeverityLevel.CRITICAL: 4
        }

        for idx, item in enumerate(raw_detections):
            bbox: BoundingBox = item["bbox"]
            conf = item["confidence"]
            sev: SeverityLevel = item["severity"]

            if severity_rank[sev] > severity_rank[highest_severity]:
                highest_severity = sev

            x1 = int(bbox.x_min * w)
            y1 = int(bbox.y_min * h)
            x2 = int(bbox.x_max * w)
            y2 = int(bbox.y_max * h)

            color = severity_colors.get(sev, (0, 255, 255))

            # Main bounding box
            cv2.rectangle(annotated_img, (x1, y1), (x2, y2), color, 3)

            # High-tech corner brackets
            corner_len = max(8, min(24, int((x2 - x1) * 0.2)))
            cv2.line(annotated_img, (x1, y1), (x1 + corner_len, y1), color, 4)
            cv2.line(annotated_img, (x1, y1), (x1, y1 + corner_len), color, 4)
            cv2.line(annotated_img, (x2, y2), (x2 - corner_len, y2), color, 4)
            cv2.line(annotated_img, (x2, y2), (x2, y2 - corner_len), color, 4)

            # Label banner
            label = f"ROAD PIT #{idx+1} | {sev.value} ({conf:.0%})"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.52, 2)
            label_y1 = max(0, y1 - th - 8)
            label_y2 = y1
            cv2.rectangle(annotated_img, (x1, label_y1), (x1 + tw + 12, label_y2), color, -1)
            cv2.putText(
                annotated_img,
                label,
                (x1 + 6, y1 - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.52,
                (0, 0, 0),
                2,
                cv2.LINE_AA
            )

            detection_items.append(
                DetectionItem(
                    id=idx + 1,
                    confidence=conf,
                    severity=sev,
                    bbox=bbox,
                    estimated_area_sq_px=item["area_sq_px"]
                )
            )

        # Save annotated image
        annotated_filename = f"annotated_{uuid.uuid4().hex[:12]}_{image_path.name}"
        annotated_path = ANNOTATED_DIR / annotated_filename
        cv2.imwrite(str(annotated_path), annotated_img)

        return detection_items, annotated_path, highest_severity

    def detect_on_frame(
        self,
        frame_np: np.ndarray,
        confidence_threshold: float = settings.DEFAULT_CONFIDENCE_THRESHOLD
    ) -> Tuple[List[DetectionItem], SeverityLevel]:
        """
        Fast in-memory road pit detection for real-time video streaming & WebSockets (sub-20ms).
        """
        h, w = frame_np.shape[:2]
        raw_detections = self.detect_pits_cv_engine(frame_np, conf_threshold=confidence_threshold)

        detection_items: List[DetectionItem] = []
        highest_severity = SeverityLevel.LOW
        severity_rank = {
            SeverityLevel.LOW: 1,
            SeverityLevel.MEDIUM: 2,
            SeverityLevel.HIGH: 3,
            SeverityLevel.CRITICAL: 4
        }

        for idx, item in enumerate(raw_detections):
            bbox: BoundingBox = item["bbox"]
            conf = item["confidence"]
            sev: SeverityLevel = item["severity"]

            if severity_rank[sev] > severity_rank[highest_severity]:
                highest_severity = sev

            detection_items.append(
                DetectionItem(
                    id=idx + 1,
                    confidence=conf,
                    severity=sev,
                    bbox=bbox,
                    estimated_area_sq_px=item["area_sq_px"]
                )
            )

        return detection_items, highest_severity

    def detect_on_video(
        self,
        video_path: Path,
        sample_fps: int = 2,
        conf_threshold: float = 0.35
    ) -> Dict[str, Any]:
        """Processes video frame-by-frame and tracks defects."""
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise ValueError(f"Cannot open video file {video_path}")

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        duration = total_frames / fps

        frame_step = max(1, int(fps / sample_fps))
        frame_idx = 0
        processed_count = 0
        total_pits = 0
        frame_results = []

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % frame_step == 0:
                temp_frame_path = UPLOAD_DIR / f"temp_frame_{uuid.uuid4().hex[:8]}.jpg"
                cv2.imwrite(str(temp_frame_path), frame)

                detections, _, _ = self.detect_on_image(temp_frame_path, confidence_threshold=conf_threshold)
                if temp_frame_path.exists():
                    temp_frame_path.unlink()

                if detections:
                    total_pits += len(detections)
                    frame_results.append({
                        "frame_index": frame_idx,
                        "timestamp_sec": round(frame_idx / fps, 2),
                        "pits_detected": len(detections),
                        "detections": detections
                    })

                processed_count += 1

            frame_idx += 1

        cap.release()

        return {
            "total_frames_processed": processed_count,
            "total_pits_found": total_pits,
            "video_duration_sec": round(duration, 2),
            "frame_results": frame_results
        }


# Singleton instance
ai_detector = AIDetectorService()
