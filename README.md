# 🛣️ AI Pit Track API

[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg?style=flat&logo=FastAPI&logoColor=white)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![OpenCV](https://img.shields.io/badge/OpenCV-Computer%20Vision-5C3EE8.svg?logo=opencv&logoColor=white)](https://opencv.org)
[![PyTorch](https://img.shields.io/badge/PyTorch-Ultralytics%20YOLO-EE4C2C.svg?logo=pytorch&logoColor=white)](https://ultralytics.com)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

An **AI-powered computer vision & geospatial tracking REST API** engineered to detect road pits, potholes, surface depressions, and structural defects from dashcams, drones, and inspection cameras in real-time.

---

## 🌟 Key Features

- 🧠 **Dual-Engine AI Vision**:
  - **YOLO Deep Learning Support**: Integrates directly with custom YOLO weights (`.pt` / ONNX).
  - **Adaptive Computer Vision Pipeline**: Multi-scale CLAHE, Otsu asphalt depression segmentation, and morphological Black-Hat filtering for instant, zero-setup road defect localization.
- 📐 **Dynamic Severity Rating**: Automatically grades detected defects into `LOW`, `MEDIUM`, `HIGH`, or `CRITICAL` based on surface area ratio and depression depth.
- 📍 **Geospatial Tracking & Deduplication**:
  - Automatically calculates Haversine distances to cluster repeated detections of the same pothole within a configurable GPS radius (e.g. 7 meters).
  - Maintains inspection count, maximum confidence, and historical detection snapshots.
- 🔄 **Defect Lifecycle Management**: Full workflow support (`DETECTED` ➔ `VERIFIED` ➔ `IN_PROGRESS` ➔ `REPAIRED` ➔ `CLOSED`).
- 🗺️ **GeoJSON & Heatmap Support**: Native GeoJSON feature collections for direct rendering in Mapbox, Leaflet, and GIS tools.
- 📊 **Road Health Index & Analytics**: Network-wide pavement condition scoring and statistical defect breakdowns.
- 📋 **Maintenance Export**: Instant CSV/Excel audit reports for municipal public works and highway authorities.
- 💻 **Modern Web Dashboard**: Built-in responsive UI with an interactive Leaflet map, image dropzone, live test pothole synthesizer, and defect tables at `/dashboard`.

---

## 📁 Project Architecture

```
AI pit track API/
├── app/
│   ├── __init__.py
│   ├── main.py                     # FastAPI application & route mounting
│   ├── config.py                   # App configuration & environment settings
│   ├── database.py                 # SQLAlchemy 2.0 connection & session maker
│   ├── models/
│   │   ├── __init__.py
│   │   └── pit.py                  # RoadPit, PitDetection, and Status Enums
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── pit.py                  # Pydantic v2 schemas for detection & pits
│   │   └── analytics.py            # GeoJSON and Road Health Index schemas
│   ├── services/
│   │   ├── __init__.py
│   │   ├── ai_detector.py          # YOLO & Computer Vision road defect engine
│   │   ├── geo_tracker.py          # Haversine distance & spatial clustering
│   │   └── report_generator.py     # CSV audit report exporter
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── detection.py            # Image & Video AI inference endpoints
│   │   ├── pits.py                 # Pit lifecycle & CRUD endpoints
│   │   ├── analytics.py            # Road Health Index & GeoJSON endpoints
│   │   └── reports.py              # Export endpoints
│   └── static/
│       ├── index.html              # Interactive Dashboard UI
│       ├── style.css               # Modern UI styling
│       └── app.js                  # Frontend Leaflet & inference scripts
├── tests/
│   ├── test_api.py                 # Automated API test suite
│   └── test_detector.py            # AI vision engine tests
├── uploads/                        # Stored raw & annotated defect images
├── requirements.txt                # Python dependencies
├── pytest.ini                      # Test runner configuration
├── run.py                          # Server launcher script
└── README.md                       # Documentation
```

---

## 🚀 Quickstart

### 1. Installation

Clone or open the repository, then install the dependencies:

```bash
pip install -r requirements.txt
```

### 2. Start the API Server

```bash
python run.py
```
*Or using Uvicorn directly:*
```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

The server will be live at:
- **Interactive UI Dashboard**: [http://127.0.0.1:8000/dashboard](http://127.0.0.1:8000/dashboard)
- **Interactive Swagger Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc Documentation**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

## 📡 API Reference

### 1. AI Detection & Inference

#### `POST /api/v1/detect/image`
Upload an image frame with optional GPS metadata. Returns detected bounding boxes, severity ratings, annotated image URL, and the assigned/clustered Pit ID.

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/detect/image" \
  -F "file=@road_dashcam.jpg" \
  -F "latitude=37.7749" \
  -F "longitude=-122.4194" \
  -F "speed_kmh=45.0"
```

**Response:**
```json
{
  "success": true,
  "total_pits_detected": 1,
  "max_severity": "HIGH",
  "detections": [
    {
      "id": 1,
      "confidence": 0.89,
      "severity": "HIGH",
      "bbox": {
        "x_min": 0.38,
        "y_min": 0.55,
        "x_max": 0.62,
        "y_max": 0.78,
        "pixel_width": 154,
        "pixel_height": 110
      },
      "estimated_area_sq_px": 16940.0
    }
  ],
  "annotated_image_url": "/uploads/annotated/annotated_98a12bc_road_dashcam.jpg",
  "associated_pit_id": 4,
  "latitude": 37.7749,
  "longitude": -122.4194,
  "message": "Detected 1 road pit(s)/defect(s)"
}
```

#### `POST /api/v1/detect/video`
Upload dashcam video footage to track defects frame-by-frame across timestamps.

#### `WS /api/v1/detect/ws/stream`
Real-Time WebSocket Video Streaming Endpoint. Accepts continuous frames (Base64) with GPS telemetry packets, executes sub-20ms in-memory defect inference, and streams bounding boxes and severity metrics live.

**Example Payload:**
```json
{
  "image": "data:image/jpeg;base64,...",
  "latitude": 37.7749,
  "longitude": -122.4194
}
```

**Realtime Output:**
```json
{
  "success": true,
  "latency_ms": 14.2,
  "fps": 70.4,
  "total_pits_detected": 1,
  "max_severity": "HIGH",
  "associated_pit_id": 4,
  "detections": [...]
}
```

---

### 2. Road Pit Management & Lifecycle

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/pits` | List tracked pits (filter by `severity`, `status`, `min_confidence`) |
| `POST` | `/api/v1/pits` | Manually register a road pit entity |
| `GET` | `/api/v1/pits/{pit_id}` | Get pit details & all historical detection snapshots |
| `PATCH` | `/api/v1/pits/{pit_id}` | Update status (`IN_PROGRESS`, `REPAIRED`, etc.) |
| `DELETE` | `/api/v1/pits/{pit_id}` | Delete a road pit record |

**Update Pit Status Example:**
```bash
curl -X PATCH "http://127.0.0.1:8000/api/v1/pits/4" \
  -H "Content-Type: application/json" \
  -d '{"status": "REPAIRED", "notes": "Asphalt patch applied by Crew #3"}'
```

---

### 3. Spatial Analytics & GeoJSON

#### `GET /api/v1/analytics/summary`
Returns pavement quality score (0 to 100), active defect count, and severity distributions.

#### `GET /api/v1/analytics/geojson`
Returns a standard GeoJSON `FeatureCollection` ready for direct display on Leaflet, Mapbox, Google Maps, or ArcGIS.

---

### 4. Maintenance Audit Reports

#### `GET /api/v1/reports/export/csv`
Downloads a formatted `.csv` maintenance audit report with GPS coordinates, defect severity, confidence scores, and repair timestamps.

---

## 🧪 Running Automated Tests

Run the complete test suite with `pytest`:

```bash
python -m pytest -v
```

---

## ⚙️ Configuration (.env)

Customize parameters via environment variables or `.env` file:

```ini
PROJECT_NAME="AI Pit Track API"
DATABASE_URL="sqlite:///./pit_track.db"
GEO_DUPLICATION_RADIUS_METERS=7.0
DEFAULT_CONFIDENCE_THRESHOLD=0.35
```

---

## 📄 License
This project is licensed under the MIT License.
