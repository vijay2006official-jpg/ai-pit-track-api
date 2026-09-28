import math
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from app.models.pit import RoadPit, SeverityLevel, PitStatus
from app.config import settings

def haversine_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great-circle distance between two GPS points on Earth in meters.
    """
    R = 6371000.0  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c

class GeoTrackerService:
    @staticmethod
    def find_nearest_pit(
        db: Session,
        latitude: float,
        longitude: float,
        radius_meters: float = settings.GEO_DUPLICATION_RADIUS_METERS
    ) -> Optional[RoadPit]:
        """
        Finds if an existing tracked pit exists within `radius_meters`.
        Uses an approximate bounding box query first for fast indexing, then haversine distance.
        """
        # 1 deg latitude is approx 111,000 meters
        lat_delta = radius_meters / 111000.0
        # 1 deg longitude delta varies with latitude
        cos_lat = math.cos(math.radians(latitude))
        lon_delta = radius_meters / (111000.0 * max(cos_lat, 0.0001))

        candidates = db.query(RoadPit).filter(
            RoadPit.latitude.between(latitude - lat_delta, latitude + lat_delta),
            RoadPit.longitude.between(longitude - lon_delta, longitude + lon_delta),
            RoadPit.status != PitStatus.FALSE_POSITIVE
        ).all()

        nearest_pit = None
        min_dist = float("inf")

        for pit in candidates:
            dist = haversine_distance_meters(latitude, longitude, pit.latitude, pit.longitude)
            if dist <= radius_meters and dist < min_dist:
                min_dist = dist
                nearest_pit = pit

        return nearest_pit

    @staticmethod
    def estimate_road_address(latitude: float, longitude: float) -> Tuple[str, str]:
        """
        Provides a friendly location name / road segment identifier.
        """
        # Format a standard road coordinate tag or placeholder
        road_name = f"Route Segment #{int(abs(latitude * 100))}-{int(abs(longitude * 100))}"
        address = f"Lat: {latitude:.5f}, Lon: {longitude:.5f}"
        return road_name, address
