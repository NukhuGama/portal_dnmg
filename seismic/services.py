"""Reusable seismic data-source service layer."""

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.core.cache import cache
from .geography import TIMOR_LESTE, TIMOR_LESTE_TZ


logger = logging.getLogger(__name__)


USGS_QUERY_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"


class EarthquakeServiceError(Exception):
    """A provider could not supply usable earthquake data."""


class EarthquakeDataSource(ABC):
    """Contract for USGS and future local or regional seismic providers."""

    source_name = "Unknown source"

    @abstractmethod
    def fetch_features(self, scope, start_date, end_date):
        """Return provider-native GeoJSON-style features."""


class USGSEarthquakeDataSource(EarthquakeDataSource):
    source_name = "USGS Earthquake Hazards Program"

    def fetch_features(self, scope, start_date, end_date):
        start = datetime.combine(start_date, time.min, tzinfo=TIMOR_LESTE_TZ).astimezone(ZoneInfo("UTC"))
        end = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=TIMOR_LESTE_TZ).astimezone(ZoneInfo("UTC"))
        params = {
            "format": "geojson", "starttime": start.strftime("%Y-%m-%dT%H:%M:%S"),
            "endtime": end.strftime("%Y-%m-%dT%H:%M:%S"), "minmagnitude": "2.5", "orderby": "time", "limit": "1000",
        }
        if scope == "timor-leste":
            params.update({
                "latitude": str(TIMOR_LESTE["latitude"]), "longitude": str(TIMOR_LESTE["longitude"]),
                "maxradiuskm": str(TIMOR_LESTE["radius_km"]),
            })
        url = f"{USGS_QUERY_URL}?{urllib.parse.urlencode(params)}"
        request = urllib.request.Request(url, headers={"User-Agent": "DNMG-Portal/1.0"})
        try:
            with urllib.request.urlopen(request, timeout=12) as response:
                return json.loads(response.read().decode("utf-8")).get("features", [])
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            logger.warning("USGS earthquake request failed: %s", exc)
            raise EarthquakeServiceError("USGS earthquake data is temporarily unavailable.") from exc


class USGSEarthquakeService:
    """Cached USGS adapter returning the portal's provider-neutral GeoJSON."""

    cache_seconds = 300

    @classmethod
    def fetch(cls, scope, start_date, end_date):
        cache_key = f"seismic:usgs:{scope}:{start_date.isoformat()}:{end_date.isoformat()}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        # Import here to keep the provider contract independent of serializers.
        from .serializers import USGSEarthquakeSerializer

        raw_features = USGSEarthquakeDataSource().fetch_features(scope, start_date, end_date)
        if not isinstance(raw_features, list):
            logger.error("USGS earthquake response did not contain a feature list")
            raise EarthquakeServiceError("USGS earthquake data is temporarily unavailable.")
        features = [normalized for feature in raw_features if (normalized := USGSEarthquakeSerializer.normalize_feature(feature))]
        result = {
            "type": "FeatureCollection", "features": features,
            "metadata": {
                "count": len(features), "scope": scope, "start_date": start_date.isoformat(), "end_date": end_date.isoformat(),
                "source": USGSEarthquakeDataSource.source_name,
                "source_url": "https://earthquake.usgs.gov/earthquakes/search/", "timor_leste": TIMOR_LESTE,
            },
        }
        cache.set(cache_key, result, cls.cache_seconds)
        return result
