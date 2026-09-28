import io
import numpy as np
import cv2
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import Base, engine

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

def create_synthetic_pothole_image():
    # 640x480 asphalt image with a dark depression
    img = np.full((480, 640, 3), 70, dtype=np.uint8)
    # Add road defect
    cv2.ellipse(img, (320, 320), (80, 40), 0, 0, 360, (20, 20, 20), -1)
    _, encoded = cv2.imencode(".jpg", img)
    return io.BytesIO(encoded.tobytes())

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_detect_image_endpoint():
    img_bytes = create_synthetic_pothole_image()
    response = client.post(
        "/api/v1/detect/image",
        files={"file": ("test_road.jpg", img_bytes, "image/jpeg")},
        data={"latitude": 37.7749, "longitude": -122.4194}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["total_pits_detected"] >= 1
    assert data["associated_pit_id"] is not None
    assert "annotated_image_url" in data

def test_spatial_clustering_deduplication():
    # Detect same pit at same coordinate twice
    img1 = create_synthetic_pothole_image()
    res1 = client.post(
        "/api/v1/detect/image",
        files={"file": ("test_road1.jpg", img1, "image/jpeg")},
        data={"latitude": 37.77490, "longitude": -122.41940}
    )
    pit_id_1 = res1.json()["associated_pit_id"]

    img2 = create_synthetic_pothole_image()
    # 2 meters away
    res2 = client.post(
        "/api/v1/detect/image",
        files={"file": ("test_road2.jpg", img2, "image/jpeg")},
        data={"latitude": 37.77491, "longitude": -122.41941}
    )
    pit_id_2 = res2.json()["associated_pit_id"]

    # Should cluster to same pit entity
    assert pit_id_1 == pit_id_2

    # Verify detection count incremented
    pit_res = client.get(f"/api/v1/pits/{pit_id_1}")
    assert pit_res.status_code == 200
    assert pit_res.json()["detection_count"] >= 2

def test_pit_lifecycle_and_update():
    # Register manually
    create_res = client.post(
        "/api/v1/pits",
        json={
            "latitude": 40.7128,
            "longitude": -74.0060,
            "severity": "HIGH",
            "notes": "Main Street deep pothole"
        }
    )
    assert create_res.status_code == 201
    pit_id = create_res.json()["id"]

    # Update to REPAIRED
    patch_res = client.patch(
        f"/api/v1/pits/{pit_id}",
        json={"status": "REPAIRED"}
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["status"] == "REPAIRED"
    assert patch_res.json()["repaired_at"] is not None

def test_analytics_and_geojson():
    # Insert test pit
    client.post(
        "/api/v1/pits",
        json={
            "latitude": 51.5074,
            "longitude": -0.1278,
            "severity": "CRITICAL"
        }
    )

    # Check summary
    summary_res = client.get("/api/v1/analytics/summary")
    assert summary_res.status_code == 200
    summary = summary_res.json()
    assert summary["total_pits_recorded"] >= 1
    assert "road_health_index_score" in summary

    # Check GeoJSON
    geojson_res = client.get("/api/v1/analytics/geojson")
    assert geojson_res.status_code == 200
    geojson = geojson_res.json()
    assert geojson["type"] == "FeatureCollection"
    assert len(geojson["features"]) >= 1

def test_csv_report_export():
    client.post(
        "/api/v1/pits",
        json={
            "latitude": 34.0522,
            "longitude": -118.2437,
            "severity": "MEDIUM"
        }
    )
    report_res = client.get("/api/v1/reports/export/csv")
    assert report_res.status_code == 200
    assert "text/csv" in report_res.headers["content-type"]
    assert "Pit ID,Latitude,Longitude" in report_res.text

def test_websocket_stream():
    import base64
    img_bytes = create_synthetic_pothole_image().getvalue()
    b64_str = base64.b64encode(img_bytes).decode("utf-8")

    with client.websocket_connect("/api/v1/detect/ws/stream") as websocket:
        websocket.send_json({
            "image": b64_str,
            "latitude": 37.7749,
            "longitude": -122.4194
        })
        data = websocket.receive_json()
        assert data["success"] is True
        assert "latency_ms" in data
        assert "fps" in data
        assert data["total_pits_detected"] >= 1

def test_work_order_generation():
    create_res = client.post(
        "/api/v1/pits",
        json={
            "latitude": 37.7749,
            "longitude": -122.4194,
            "severity": "CRITICAL",
            "road_name": "Main Interstate 80"
        }
    )
    pit_id = create_res.json()["id"]

    # HTML Work Order
    html_res = client.get(f"/api/v1/reports/work-order/{pit_id}")
    assert html_res.status_code == 200
    assert "DEPARTMENT OF PUBLIC WORKS" in html_res.text
    assert f"WO-{pit_id:05d}" in html_res.text

    # JSON Work Order
    json_res = client.get(f"/api/v1/reports/work-order/{pit_id}/json")
    assert json_res.status_code == 200
    data = json_res.json()
    assert "material_and_dispatch_estimates" in data
    assert data["material_and_dispatch_estimates"]["cold_mix_asphalt_kg"] > 0

def test_webhook_alert_endpoint():
    res = client.post("/api/v1/analytics/webhooks/test", params={"webhook_url": "https://httpbin.org/post"})
    assert res.status_code == 200
    assert "success" in res.json()


