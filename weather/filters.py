"""Small request-value filters shared by public weather views."""

from .models import WeatherStation


PUBLIC_MAP_STATION_FILTERS = frozenset({
    'ALL',
    'AWS',
    WeatherStation.StationType.AWOS,
    'MARINE',
    WeatherStation.StationType.TIDE_GAUGE,
    WeatherStation.StationType.BUOY,
})


def normalize_public_station_filter(value):
    """Return a supported map filter, falling back safely to ``ALL``."""
    normalized_value = (value or 'ALL').strip().upper()
    if normalized_value in PUBLIC_MAP_STATION_FILTERS:
        return normalized_value
    return 'ALL'
