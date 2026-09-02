"""Transform provider-specific earthquake payloads into portal GeoJSON."""

import math
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.utils import timezone

from .classification import RECENT_EVENT_HOURS, risk_for_magnitude
from .geography import TIMOR_LESTE_TZ, distance_from_timor_leste


class USGSEarthquakeSerializer:
    """Normalize one USGS GeoJSON feature to the app's provider-neutral shape."""

    RECENT_EVENT_WINDOW = timedelta(hours=RECENT_EVENT_HOURS)

    @staticmethod
    def normalize_feature(feature):
        """Return a safe, provider-neutral event or ``None`` for bad input.

        USGS is an external provider. A malformed or partially populated feature
        must not turn an otherwise usable response into a 500 error.
        """
        if not isinstance(feature, dict):
            return None

        properties = feature.get("properties") or {}
        geometry = feature.get("geometry") or {}
        coordinates = geometry.get("coordinates") or []
        if not isinstance(properties, dict) or not isinstance(coordinates, (list, tuple)) or len(coordinates) < 2:
            return None

        try:
            longitude, latitude = float(coordinates[0]), float(coordinates[1])
            magnitude = float(properties["mag"])
            event_timestamp = float(properties["time"]) / 1000
        except (KeyError, TypeError, ValueError, OverflowError):
            return None

        if not all(math.isfinite(value) for value in (longitude, latitude, magnitude)):
            return None

        try:
            event_time = datetime.fromtimestamp(event_timestamp, tz=ZoneInfo("UTC")).astimezone(TIMOR_LESTE_TZ)
        except (OverflowError, OSError, ValueError):
            return None

        event_age = timezone.now() - event_time
        is_recent = timedelta(0) <= event_age <= USGSEarthquakeSerializer.RECENT_EVENT_WINDOW
        risk = risk_for_magnitude(magnitude)
        try:
            depth = float(coordinates[2]) if len(coordinates) > 2 and coordinates[2] is not None else None
        except (TypeError, ValueError, OverflowError):
            depth = None
        return {
            "type": "Feature",
            "id": feature.get("id"),
            "geometry": {"type": "Point", "coordinates": [longitude, latitude, depth]},
            "properties": {
                "id": feature.get("id"), "magnitude": magnitude,
                "magnitude_type": properties.get("magType") or "-",
                "place": properties.get("place") or "Location not specified",
                "latitude": round(latitude, 5), "longitude": round(longitude, 5),
                "depth_km": round(depth, 1) if depth is not None else None,
                "time": event_time.isoformat(), "time_display": event_time.strftime("%d %b %Y, %H:%M GMT+9"),
                "is_recent": is_recent,
                "distance_km": distance_from_timor_leste(latitude, longitude),
                "risk": risk["label"], "risk_code": risk["code"], "risk_range": risk["range"], "color": risk["color"],
                "tsunami": bool(properties.get("tsunami")), "felt": properties.get("felt"),
                "status": properties.get("status"), "alert": properties.get("alert"),
                "significance": properties.get("sig"), "event_type": properties.get("type") or "earthquake",
                "updated": properties.get("updated"), "usgs_url": properties.get("url"), "detail_url": properties.get("detail"),
            },
        }
