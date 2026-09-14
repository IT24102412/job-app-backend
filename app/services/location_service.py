import math

from sqlalchemy.orm import Session

from app.models import RegionalCenter


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Straight-line distance between two GPS points, in kilometers."""
    R = 6371  # Earth's radius in km

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def find_nearest_regional_center(latitude: float, longitude: float, db: Session) -> RegionalCenter | None:
    centers = db.query(RegionalCenter).all()
    if not centers:
        return None

    nearest = min(
        centers,
        key=lambda center: haversine_distance_km(latitude, longitude, center.latitude, center.longitude),
    )
    return nearest