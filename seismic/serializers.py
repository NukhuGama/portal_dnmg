"""Transform provider-specific earthquake payloads into portal GeoJSON."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.utils import timezone

from .classification import RECENT_EVENT_HOURS, risk_for_magnitude
from .geography import distance_from_timor_leste


class USGSEarthquakeSerializer:
    """Normalize one USGS GeoJSON feature to the app's provider-neutral shape."""

    RECENT_EVENT_WINDOW = timedelta(hours=RECENT_EVENT_HOURS)

    @staticmethod
    def normalize_feature(feature):
        properties = feature.get("properties") or {}
        coordinates = (feature.get("geometry") or {}).get("coordinates") or [None, None, None]
        longitude, latitude = coordinates[0], coordinates[1]
        if latitude is None or longitude is None:
            return None
        magnitude = float(properties.get("mag") or 0)
        event_time = datetime.fromtimestamp((properties.get("time") or 0) / 1000, tz=ZoneInfo("UTC")).astimezone(ZoneInfo("Asia/Dili"))
        event_age = timezone.now() - event_time
        is_recent = timedelta(0) <= event_age <= USGSEarthquakeSerializer.RECENT_EVENT_WINDOW
        risk = risk_for_magnitude(magnitude)
        depth = coordinates[2] if len(coordinates) > 2 else None
        return {
            "type": "Feature",
            "id": feature.get("id"),
            "geometry": {"type": "Point", "coordinates": [longitude, latitude, depth]},
            "properties": {
                "id": feature.get("id"), "magnitude": magnitude,
                "magnitude_type": properties.get("magType") or "-",
                "place": properties.get("place") or "Location not specified",
                "latitude": round(float(latitude), 5), "longitude": round(float(longitude), 5),
                "depth_km": round(float(depth), 1) if depth is not None else None,
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
