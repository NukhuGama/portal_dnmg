"""Geographic reference data and calculations used by seismic features."""

import math
from zoneinfo import ZoneInfo


TIMOR_LESTE = {"latitude": -8.8742, "longitude": 125.7275, "radius_km": 550}
TIMOR_LESTE_TZ = ZoneInfo("Asia/Dili")


def distance_from_timor_leste(latitude, longitude):
    """Return the great-circle distance to the Timor-Leste reference point in km."""
    radius_km = 6371.0088
    lat1, lon1 = math.radians(TIMOR_LESTE["latitude"]), math.radians(TIMOR_LESTE["longitude"])
    lat2, lon2 = math.radians(latitude), math.radians(longitude)
    delta_lat, delta_lon = lat2 - lat1, lon2 - lon1
    a = math.sin(delta_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
    return round(radius_km * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))
