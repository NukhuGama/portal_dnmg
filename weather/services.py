import json
import logging
import time
import urllib.request
import urllib.error
from urllib.parse import urlencode, urlparse
from datetime import timedelta, timezone as datetime_timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo
import pymysql
from django.conf import settings
from django.core.cache import cache
from django.db import OperationalError
from django.utils.dateparse import parse_datetime
from django.utils.timezone import is_aware, localtime, make_aware, now
from .models import AwosMetarReport, WeatherStation, WeatherObservation, Municipality

logger = logging.getLogger(__name__)

INITIAL_STATIONS_DATA = [
    {
        "external_id": 15401,
        "name": "Dili Tide Gauge",
        "code": "TG-DILI-15401",
        "station_type": WeatherStation.StationType.TIDE_GAUGE,
        "municipality": Municipality.DILI,
        "latitude": Decimal("-8.553200"),
        "longitude": Decimal("125.574700"),
    },
    {
        "external_id": 15402,
        "name": "Oecusse Tide Gauge",
        "code": "TG-OEC-15402",
        "station_type": WeatherStation.StationType.TIDE_GAUGE,
        "municipality": Municipality.OECUSSE,
        "latitude": Decimal("-9.186800"),
        "longitude": Decimal("124.392400"),
    },
    {
        "external_id": 15403,
        "name": "Marine Buoy Station",
        "code": "MB-DILI-15403",
        "station_type": WeatherStation.StationType.BUOY,
        "municipality": Municipality.DILI,
        "latitude": Decimal("-8.524000"),
        "longitude": Decimal("124.592000"),
    },
    {
        "external_id": 15404,
        "name": "Liquica AWS",
        "code": "15404",
        "station_type": WeatherStation.StationType.AWS,
        "municipality": Municipality.LIQUICA,
        "latitude": Decimal("-8.579800"),
        "longitude": Decimal("125.362800"),
    },
    {
        "external_id": 15433,
        "name": "Ermera AWS",
        "code": "AWS-ERM-15433",
        "station_type": WeatherStation.StationType.AWS,
        "municipality": Municipality.ERMERA,
        "latitude": Decimal("-8.716300"),
        "longitude": Decimal("125.449500"),
    },
    {
        "external_id": 15434,
        "name": "Manatuto AWS",
        "code": "AWS-MNT-15434",
        "station_type": WeatherStation.StationType.AWS,
        "municipality": Municipality.MANATUTO,
        "latitude": Decimal("-8.536900"),
        "longitude": Decimal("126.013500"),
    },
    {
        "external_id": 15435,
        "name": "Baucau AWS",
        "code": "AWS-BAU-15435",
        "station_type": WeatherStation.StationType.AWS,
        "municipality": Municipality.BAUCAU,
        "latitude": Decimal("-8.479400"),
        "longitude": Decimal("126.399600"),
    },
    {
        "external_id": 15436,
        "name": "Lospalos AWS",
        "code": "AWS-LSP-15436",
        "station_type": WeatherStation.StationType.AWS,
        "municipality": Municipality.LAUTEM,
        "latitude": Decimal("-8.494100"),
        "longitude": Decimal("126.990400"),
    },
    {
        "external_id": 15437,
        "name": "Viqueque AWS",
        "code": "AWS-VQQ-15437",
        "station_type": WeatherStation.StationType.AWS,
        "municipality": Municipality.VIQUEQUE,
        "latitude": Decimal("-8.881800"),
        "longitude": Decimal("126.372700"),
    },
    {
        "external_id": 15438,
        "name": "Nahareca-AWS",
        "code": "AWS-NAH-15438",
        "station_type": WeatherStation.StationType.AWS,
        "municipality": Municipality.VIQUEQUE,
        "latitude": Decimal("-8.701600"),
        "longitude": Decimal("126.480100"),
    },
    {
        "external_id": 15439,
        "name": "Seical-AWS",
        "code": "AWS-SEI-15439",
        "station_type": WeatherStation.StationType.AWS,
        "municipality": Municipality.BAUCAU,
        "latitude": Decimal("-8.507400"),
        "longitude": Decimal("126.516800"),
    },
    {
        "external_id": 15440,
        "name": "Larisula-AWS",
        "code": "AWS-LRS-15440",
        "station_type": WeatherStation.StationType.AWS,
        "municipality": Municipality.BAUCAU,
        "latitude": Decimal("-8.661400"),
        "longitude": Decimal("126.737100"),
    },
    {
        "external_id": 15441,
        "name": "Baguia-AWS",
        "code": "AWS-BAG-15441",
        "station_type": WeatherStation.StationType.AWS,
        "municipality": Municipality.BAUCAU,
        "latitude": Decimal("-8.628900"),
        "longitude": Decimal("126.655600"),
    },
    {
        "external_id": 15442,
        "name": "Quelicai-AWS",
        "code": "AWS-QLC-15442",
        "station_type": WeatherStation.StationType.AWS,
        "municipality": Municipality.BAUCAU,
        "latitude": Decimal("-8.602400"),
        "longitude": Decimal("126.559100"),
    },
    {
        "external_id": 15443,
        "name": "Nunira-AWS",
        "code": "AWS-NUN-15443",
        "station_type": WeatherStation.StationType.AWS,
        "municipality": Municipality.BAUCAU,
        "latitude": Decimal("-8.484300"),
        "longitude": Decimal("126.654100"),
    },
]

class DNMGStationSyncService:
    # A station is considered live only when its newest observation is no more
    # than five hours old.  Keep this in the shared service so public and staff
    # views cannot drift apart again.
    ONLINE_WINDOW = timedelta(hours=5)

    # station-data supplies the full telemetry set (including tide-gauge and
    # buoy parameters) when requested with a Timor-Leste 24-hour window.
    API_BASE_URL = "https://ms-obs.dnmg.gov.tl/station-data/"
    CURRENT_OBSERVATION_API_BASE_URL = "https://ms-obs.dnmg.gov.tl/station-data/"
    # The portal displays live observations. Keep normal page loads inexpensive,
    # but do not let an old API response obscure a newer timestamp/value pair.
    CACHE_TIMEOUT = 60
    # A synchronization can take longer than its one-minute API-response cache,
    # especially when an upstream station is slow. Keep the distributed Redis
    # lock long enough to prevent a second scheduler run from overlapping it.
    SYNC_LOCK_TIMEOUT = 15 * 60
    SYNC_RESULTS_CACHE_KEY = "dnmg_station_sync_results"
    SYNC_LOCK_CACHE_KEY = "dnmg_station_sync_in_progress"
    TIMOR_LESTE_TIMEZONE = ZoneInfo("Asia/Dili")
    TELEMETRY_QUANTUM = Decimal("0.01")
    WIND_SPEED_MS_TO_KMH = Decimal("3.6")
    CHART_INTERVALS_BY_STATION_ID = {
        15403: 30,
        15404: 15,
        15433: 15,
        15434: 15,
        15435: 15,
        15436: 15,
        15437: 15,
    }
    CHART_INTERVALS_BY_STATION_TYPE = {
        WeatherStation.StationType.TIDE_GAUGE: 10,
    }
    TELEMETRY_FIELDS = (
        "temperature", "humidity", "rainfall_mm", "wind_speed_kmh",
        "wind_direction", "pressure_hpa", "wave_height_m", "tide_level_mm",
        "peak_period_s", "solar_radiation", "wind_gust_kmh",
        "sea_surface_temp", "battery_voltage",
    )

    @classmethod
    def build_last_24_hours_api_url(cls, external_id, current_time=None):
        """Build a station-data request for the previous 24 hours in Asia/Dili.

        The API accepts UTC timestamps, so calculate the range in Timor-Leste
        time first and then convert both boundaries to the UTC wire format.
        """
        local_end = localtime(current_time or now(), cls.TIMOR_LESTE_TIMEZONE).replace(
            second=0,
            microsecond=0,
        )
        local_start = local_end - timedelta(hours=24)

        def utc_timestamp(value):
            return value.astimezone(datetime_timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        query = urlencode({
            "all_params": "true",
            "end_time": utc_timestamp(local_end),
            "start_time": utc_timestamp(local_start),
            "tz": cls.TIMOR_LESTE_TIMEZONE.key,
        })
        return f"{cls.API_BASE_URL}{external_id}?{query}"

    @classmethod
    def parse_decimal(cls, value):
        """Return an API telemetry value rounded to the two precision places shown in the UI."""
        if value in (None, "", "none"):
            return None
        try:
            return Decimal(str(value)).quantize(cls.TELEMETRY_QUANTUM, rounding=ROUND_HALF_UP)
        except (InvalidOperation, TypeError, ValueError):
            return None

    @classmethod
    def parse_wind_measurement_kmh(cls, value):
        """Convert an API wind-speed or wind-gust measurement from m/s to km/h."""
        if value in (None, "", "none"):
            return None
        try:
            return (Decimal(str(value)) * cls.WIND_SPEED_MS_TO_KMH).quantize(
                cls.TELEMETRY_QUANTUM,
                rounding=ROUND_HALF_UP,
            )
        except (InvalidOperation, TypeError, ValueError):
            return None

    @staticmethod
    def parse_coordinate(value):
        """Keep the API coordinate precision; coordinates are not telemetry readings."""
        if value in (None, "", "none"):
            return None
        try:
            return Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return None

    @staticmethod
    def update_station_coordinates(station, latitude, longitude):
        """Update provider-managed coordinates without overwriting DNMG entries."""
        if station.coordinate_source == WeatherStation.CoordinateSource.MANUAL:
            return
        if latitude is None or longitude is None:
            return
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            logger.warning("Ignoring out-of-range provider coordinates for station %s", station.external_id)
            return
        if station.latitude == latitude and station.longitude == longitude:
            return
        station.latitude = latitude
        station.longitude = longitude
        station.save(update_fields=['latitude', 'longitude'])

    @staticmethod
    def get_time_series_entries(payload, *keys):
        """Return telemetry entries for a field across supported API payload shapes.

        The station API has returned both top-level parameter lists and nested
        ``data`` objects. Tide gauges in particular can use human-readable
        parameter names such as ``Air Temperature`` and ``Air Pressure``.
        Normalising the names here keeps the map and dashboard independent of
        that transport detail.
        """
        if not isinstance(payload, dict):
            return []

        def normalise_key(value):
            return ''.join(char for char in str(value).lower() if char.isalnum())

        expected_keys = {normalise_key(key) for key in keys}

        def matches_parameter(parameter_name):
            normalised_name = normalise_key(parameter_name)
            if normalised_name in expected_keys:
                return True
            # Station vendors occasionally suffix a standard parameter name
            # with the sensor/height/unit. Match only unambiguous air
            # temperature and atmospheric-pressure variants.
            wants_air_temperature = 'airtemperature' in expected_keys
            wants_pressure = 'noncoordinatepressure' in expected_keys
            if wants_air_temperature and (
                'airtemp' in normalised_name
                or ('air' in normalised_name and 'temperature' in normalised_name)
            ):
                return True
            if wants_pressure and 'pressure' in normalised_name and 'water' not in normalised_name:
                return True
            return False
        containers = [payload]
        for container_key in ('data', 'series', 'time_series', 'parameters'):
            container = payload.get(container_key)
            if isinstance(container, dict):
                containers.append(container)

        entries = []
        for container in containers:
            for key, raw_entries in container.items():
                if not matches_parameter(key):
                    # A nested response can hold a flat parameter list under a
                    # generic key such as data.observations or data.records.
                    if isinstance(raw_entries, list):
                        for entry in raw_entries:
                            if not isinstance(entry, dict):
                                continue
                            parameter_name = (
                                entry.get('parameter')
                                or entry.get('parameter_name')
                                or entry.get('param')
                                or entry.get('variable')
                                or entry.get('name')
                            )
                            if parameter_name is not None and matches_parameter(parameter_name):
                                entries.append(entry)
                    continue
                if isinstance(raw_entries, dict):
                    for entries_key in ('data', 'values', 'observations', 'records', 'series'):
                        if isinstance(raw_entries.get(entries_key), list):
                            raw_entries = raw_entries[entries_key]
                            break
                    else:
                        # Some API versions return {timestamp: value} instead
                        # of an array of {start_time, value} objects.
                        timestamp_entries = [
                            {'start_time': timestamp, 'value': value}
                            for timestamp, value in raw_entries.items()
                            if isinstance(timestamp, str) and 'T' in timestamp
                        ]
                        raw_entries = timestamp_entries or [raw_entries]
                if isinstance(raw_entries, list):
                    entries.extend(entry for entry in raw_entries if isinstance(entry, dict))

        # Some current-observation responses use a single flat list where the
        # parameter name is stored on each reading rather than as a dictionary
        # key (for example: {"parameter": "Air Temperature", ...}).
        for container_key in ('data', 'series', 'time_series', 'observations', 'records'):
            flat_entries = payload.get(container_key)
            if not isinstance(flat_entries, list):
                continue
            for entry in flat_entries:
                if not isinstance(entry, dict):
                    continue
                parameter_name = (
                    entry.get('parameter')
                    or entry.get('parameter_name')
                    or entry.get('param')
                    or entry.get('variable')
                    or entry.get('name')
                )
                if parameter_name is not None and matches_parameter(parameter_name):
                    entries.append(entry)
        return entries

    @staticmethod
    def get_series_value(entry):
        """Read the value key used by either version of the station API."""
        for key in ('value', 'reading', 'measurement', 'measurement_value', 'val'):
            value = entry.get(key)
            if value not in (None, '', 'none'):
                return value
        return None

    @classmethod
    def get_series_timestamp(cls, entry):
        """Read the timestamp key used by either version of the station API."""
        for key in (
            'start_time', 'timestamp', 'timestamp_utc', 'time', 'datetime',
            'datetime_utc', 'date_time', 'observed_at', 'end_time',
        ):
            timestamp = cls.parse_api_timestamp(entry.get(key))
            if timestamp is not None:
                return timestamp
        return None

    @classmethod
    def parse_api_timestamp(cls, value):
        """Interpret API timestamps as UTC and normalize them to Timor-Leste time."""
        if not value:
            return None
        try:
            parsed = parse_datetime(value)
            if not parsed:
                return None
            if not is_aware(parsed):
                parsed = make_aware(parsed, datetime_timezone.utc)
            return localtime(parsed, cls.TIMOR_LESTE_TIMEZONE)
        except (TypeError, ValueError):
            return None

    @classmethod
    def clear_live_api_cache(cls):
        """Discard cached responses so the next sync uses the configured station-data feed."""
        cache.delete(cls.SYNC_RESULTS_CACHE_KEY)
        cache.delete(cls.SYNC_LOCK_CACHE_KEY)
        for external_id in WeatherStation.objects.exclude(external_id__isnull=True).values_list('external_id', flat=True):
            cache.delete(f"dnmg_live_obs_{external_id}")

    @classmethod
    def purge_api_observations(cls):
        """Remove non-AWOS observations created by the automatic station-data sync only."""
        cls.clear_live_api_cache()
        deleted_count, _ = WeatherObservation.objects.filter(
            recorded_by__isnull=True,
        ).exclude(station__station_type=WeatherStation.StationType.AWOS).delete()
        return deleted_count

    @staticmethod
    def store_automatic_observation(station, recorded_at, **values):
        """Create or update one provider observation, preventing repeated-sync duplicates."""
        observations = WeatherObservation.objects.filter(
            station=station,
            recorded_at=recorded_at,
            recorded_by__isnull=True,
        ).order_by('-id')
        observation = observations.first()
        if observation:
            observations.exclude(pk=observation.pk).delete()
            changed_fields = []
            for field, value in values.items():
                if getattr(observation, field) != value:
                    changed_fields.append(field)
                setattr(observation, field, value)
            if changed_fields:
                observation.save(update_fields=changed_fields)
            return observation
        return WeatherObservation.objects.create(
            station=station,
            recorded_at=recorded_at,
            **values,
        )

    @staticmethod
    def degrees_to_compass(deg):
        if deg is None:
            return ""
        try:
            val = float(deg) % 360
            dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
                    "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
            idx = int((val + 11.25) / 22.5) % 16
            return dirs[idx]
        except Exception:
            return ""

    @classmethod
    def sync_all_stations(cls, force=False):
        """Synchronize once per cache interval and prevent duplicate sync jobs."""
        cached_results = cache.get(cls.SYNC_RESULTS_CACHE_KEY)
        stations_initialized = WeatherStation.objects.filter(external_id__isnull=False).exists()
        if cached_results is not None and stations_initialized and not force:
            return cached_results

        # Redis cache.add is atomic across the web and sync containers. A
        # concurrent job can therefore serve the most recently stored result
        # rather than issuing duplicate upstream requests and DB writes.
        if not cache.add(cls.SYNC_LOCK_CACHE_KEY, True, cls.SYNC_LOCK_TIMEOUT):
            return cached_results or []

        try:
            results = cls._sync_all_stations(force=force)
            cache.set(cls.SYNC_RESULTS_CACHE_KEY, results, cls.CACHE_TIMEOUT)
            return results
        except OperationalError:
            logger.warning("Database was busy during station sync; serving existing station data.")
            return cached_results or []
        finally:
            cache.delete(cls.SYNC_LOCK_CACHE_KEY)

    @classmethod
    def _sync_all_stations(cls, force=False):
        """
        Ensures all 15 stations exist in DB and triggers API synchronization.
        Saves updated latitude/longitude from API into backend DB.
        Also cleans up any legacy duplicate Liquica entries.
        """
        # --- Cleanup: Remove legacy duplicate Liquica entries (external_id=None) ---
        # try:
        #     primary_liquica = WeatherStation.objects.filter(external_id=15404).first()
        #     # Target any station with no external_id that is named or coded as Liquica
        #     legacy_entries = WeatherStation.objects.filter(external_id__isnull=True).filter(
        #         code__in=['15404', 'AWS-LIQ-15404', 'Liquica']
        #     )
        #     for dup in legacy_entries:
        #         if primary_liquica and dup.pk != primary_liquica.pk:
        #             # Re-point any orphan observations to the canonical station
        #             dup.observations.all().update(station=primary_liquica)
        #             dup.delete()
        #             logger.info(f"Deleted duplicate Liquica station: ID={dup.id} name={dup.name!r} code={dup.code!r}")
        # except Exception as e:
        #     logger.warning(f"Liquica duplicate cleanup warning: {e}")

        # # --- Ensure canonical name/code for Liquica 15404 ---
        # try:
        #     WeatherStation.objects.filter(external_id=15404).update(
        #         name='Liquica',
        #         code='15404',
        #         latitude=Decimal('-8.579800'),
        #         longitude=Decimal('125.362800'),
        #     )
        # except Exception as e:
        #     logger.warning(f"Liquica update warning: {e}")

        results = []
        for station_meta in INITIAL_STATIONS_DATA:
            ext_id = station_meta["external_id"]
            station, created = WeatherStation.objects.get_or_create(
                external_id=ext_id,
                defaults={
                    "name": station_meta["name"],
                    "code": station_meta["code"],
                    "station_type": station_meta["station_type"],
                    "municipality": station_meta["municipality"],
                    "latitude": station_meta["latitude"],
                    "longitude": station_meta["longitude"],
                    "coordinate_source": WeatherStation.CoordinateSource.PROVIDER,
                    "status": WeatherStation.Status.ACTIVE,
                }
            )

            obs = cls.fetch_and_store_observation(station, force=force)
            if obs is None:
                status = "failed"
            elif obs.condition_text == "No Live Data":
                status = "no_live_data"
            else:
                status = "synced"
            results.append({
                "station": station.name,
                "external_id": ext_id,
                "observation_id": obs.id if obs else None,
                "status": status,
            })
        return results

    @classmethod
    def store_time_series_observation(cls, station, payload):
        """Store the latest telemetry and every available API sample from the last 24 hours."""
        def latest_series_entry(*keys):
            candidates = []
            for entry in cls.get_time_series_entries(payload, *keys):
                value = cls.get_series_value(entry)
                timestamp = cls.get_series_timestamp(entry)
                if value is not None and timestamp is not None:
                    candidates.append((timestamp, value))
            if not candidates:
                return None, None
            timestamp, value = max(candidates, key=lambda candidate: candidate[0])
            return value, timestamp

        station_data = payload.get('station', {})
        if isinstance(station_data, dict):
            latitude = cls.parse_coordinate(station_data.get('latitude'))
            longitude = cls.parse_coordinate(station_data.get('longitude'))
            cls.update_station_coordinates(station, latitude, longitude)

        air_temperature_value, air_temperature_time = latest_series_entry(
            'air_temperature', 'air temperature', 'air_temp', 'air_temperature_2m',
            'air_temperature_avg', 'air_temperature_mean', 'temperature_2m', 'temperature',
        )
        humidity_value, humidity_time = latest_series_entry('relative_humidity')
        atmospheric_pressure_value, atmospheric_pressure_time = latest_series_entry(
            'non_coordinate_pressure', 'air_pressure', 'air pressure',
            'atmospheric_pressure', 'barometric_pressure', 'station_pressure',
            'air_pressure_avg', 'air_pressure_mean', 'pressure',
        )
        wind_speed_value, wind_speed_time = latest_series_entry('wind_speed')
        wind_direction_value, wind_direction_time = latest_series_entry('wind_direction')
        wind_gust_value, wind_gust_time = latest_series_entry('maximum_wind_gust_speed')
        rainfall_value, rainfall_time = latest_series_entry('total_precipitation_or_total_water_equivalent')
        tide_value, tide_time = latest_series_entry('tide_level', 'Tide_level')
        wave_height_value, wave_height_time = latest_series_entry('significant_wave_height')
        peak_period_value, peak_period_time = latest_series_entry('peak_period')
        sea_temp_value, sea_temp_time = latest_series_entry('sea_surface_temperature')
        solar_value, solar_time = latest_series_entry('solar_radiation')
        battery_value, battery_time = latest_series_entry('battery_voltage', 'battery_status')

        # Marine buoys report water temperature and wave period rather than
        # atmospheric pressure. Store sea-surface temperature in the common
        # temperature field too, so the live map and 30-minute history show it.
        if station.station_type == WeatherStation.StationType.BUOY:
            temperature_value, temperature_time = sea_temp_value, sea_temp_time
            pressure_value, pressure_time = None, None
        else:
            temperature_value, temperature_time = air_temperature_value, air_temperature_time
            pressure_value, pressure_time = atmospheric_pressure_value, atmospheric_pressure_time

        timestamps = [
            timestamp for timestamp in (
                temperature_time, humidity_time, pressure_time, wind_speed_time,
                wind_direction_time, wind_gust_time, rainfall_time, tide_time,
                wave_height_time, peak_period_time, sea_temp_time, solar_time, battery_time,
            ) if timestamp is not None
        ]
        if not timestamps:
            logger.info("Station %s returned no usable time-series measurements.", station.external_id)
            return None

        temperature = cls.parse_decimal(temperature_value)
        rainfall = cls.parse_decimal(rainfall_value)
        tide_level = cls.parse_decimal(tide_value)
        wave_height = cls.parse_decimal(wave_height_value)
        solar_rad = cls.parse_decimal(solar_value)
        condition = "Live Monitoring"
        if station.station_type == WeatherStation.StationType.TIDE_GAUGE:
            condition = f"Tide Level: {tide_level} mm" if tide_level is not None else "Live Monitoring"
        elif station.station_type == WeatherStation.StationType.BUOY:
            condition = f"Wave Height: {wave_height} m" if wave_height is not None else "Live Monitoring"
        elif rainfall is not None and rainfall > 0:
            condition = f"Rainfall: {rainfall} mm"
        elif temperature is not None:
            condition = "Clear / Sunny" if solar_rad is not None and solar_rad > 500 else "Active Monitoring"

        # Persist every API time-series sample from the rolling 24-hour window.
        # This gives the public chart and the admin dashboard the same complete
        # observation range instead of retaining only whichever record was synced
        # most recently.
        current_time = now()
        cutoff = current_time - timedelta(hours=24)
        history_by_timestamp = {}
        temperature_keys = (
            ('sea_surface_temperature',)
            if station.station_type == WeatherStation.StationType.BUOY
            else (
                'air_temperature', 'air temperature', 'air_temp', 'air_temperature_2m',
                'air_temperature_avg', 'air_temperature_mean', 'temperature_2m', 'temperature',
            )
        )
        pressure_keys = () if station.station_type == WeatherStation.StationType.BUOY else (
            'non_coordinate_pressure', 'air_pressure', 'air pressure',
            'atmospheric_pressure', 'barometric_pressure', 'station_pressure',
            'air_pressure_avg', 'air_pressure_mean', 'pressure',
        )
        series_fields = (
            ('temperature', temperature_keys, cls.parse_decimal),
            ('humidity', ('relative_humidity',), cls.parse_decimal),
            ('pressure_hpa', pressure_keys, cls.parse_decimal),
            ('wind_speed_kmh', ('wind_speed',), cls.parse_wind_measurement_kmh),
            ('wind_direction', ('wind_direction',), cls.degrees_to_compass),
            ('wind_gust_kmh', ('maximum_wind_gust_speed',), cls.parse_wind_measurement_kmh),
            ('rainfall_mm', ('total_precipitation_or_total_water_equivalent',), cls.parse_decimal),
            ('tide_level_mm', ('tide_level', 'Tide_level'), cls.parse_decimal),
            ('wave_height_m', ('significant_wave_height',), cls.parse_decimal),
            ('peak_period_s', ('peak_period',), cls.parse_decimal),
            ('sea_surface_temp', ('sea_surface_temperature',), cls.parse_decimal),
            ('solar_radiation', ('solar_radiation',), cls.parse_decimal),
            ('battery_voltage', ('battery_voltage', 'battery_status'), cls.parse_decimal),
        )
        for field_name, keys, converter in series_fields:
            for entry in cls.get_time_series_entries(payload, *keys):
                timestamp = cls.get_series_timestamp(entry)
                value = converter(cls.get_series_value(entry))
                if timestamp is None or value is None or not cutoff <= timestamp <= current_time:
                    continue
                history_by_timestamp.setdefault(timestamp, {})[field_name] = value

        blank_telemetry = {
            'temperature': None, 'humidity': None, 'rainfall_mm': None,
            'wind_speed_kmh': None, 'wind_direction': '', 'pressure_hpa': None,
            'wave_height_m': None, 'tide_level_mm': None, 'peak_period_s': None,
            'solar_radiation': None, 'wind_gust_kmh': None,
            'sea_surface_temp': None, 'battery_voltage': None,
        }
        for timestamp, values in history_by_timestamp.items():
            telemetry = {**blank_telemetry, **values}
            cls.store_automatic_observation(
                station,
                timestamp,
                **telemetry,
                condition_text="Live Monitoring",
            )

        return cls.store_automatic_observation(
            station,
            max(timestamps),
            temperature=temperature,
            humidity=cls.parse_decimal(humidity_value),
            rainfall_mm=rainfall,
            wind_speed_kmh=cls.parse_wind_measurement_kmh(wind_speed_value),
            wind_direction=cls.degrees_to_compass(wind_direction_value),
            pressure_hpa=cls.parse_decimal(pressure_value),
            wave_height_m=wave_height,
            tide_level_mm=tide_level,
            peak_period_s=cls.parse_decimal(peak_period_value),
            solar_radiation=solar_rad,
            wind_gust_kmh=cls.parse_wind_measurement_kmh(wind_gust_value),
            sea_surface_temp=cls.parse_decimal(sea_temp_value),
            battery_voltage=cls.parse_decimal(battery_value),
            condition_text=condition,
        )

    @classmethod
    def fetch_and_store_observation(cls, station: WeatherStation, force=False):
        """
        Fetches the last 24 hours of complete station telemetry with caching.
        """
        if not station.external_id:
            return None

        cache_key = f"dnmg_live_obs_{station.external_id}"
        cached_data = cache.get(cache_key)

        data = None
        if cached_data and not force:
            data = cached_data
        else:
            # Request every available parameter for the previous 24 hours. This
            # includes air temperature, atmospheric pressure, and other values
            # that are not available from the legacy time-series endpoint.
            url = cls.build_last_24_hours_api_url(station.external_id)
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "DNMG-Portal/1.0 (+https://dnmg.gov.tl)"}
            )
            try:
                with urllib.request.urlopen(req, timeout=5) as response:
                    if response.status == 200:
                        payload = json.loads(response.read().decode('utf-8'))
                        data = payload
                        cache.set(cache_key, data, cls.CACHE_TIMEOUT)
            except Exception as e:
                logger.warning(f"Unable to fetch live API for station {station.external_id}: {e}")
                data = None

        time_series_observation = None
        if isinstance(data, dict):
            # station-data may include both a summary and timestamped parameter
            # series. Always store the series first so tide-gauge and buoy
            # telemetry remains available to charts and the live views.
            time_series_observation = cls.store_time_series_observation(station, data)

        # The unbounded endpoint remains authoritative for the newest dashboard
        # value. Any fields it does not provide are filled from the complete
        # 24-hour all_params response above.
        current_cache_key = f"dnmg_current_obs_{station.external_id}"
        current_data = None if force else cache.get(current_cache_key)
        if current_data is None:
            current_url = f"{cls.CURRENT_OBSERVATION_API_BASE_URL}{station.external_id}"
            current_request = urllib.request.Request(
                current_url,
                headers={"User-Agent": "DNMG-Portal/1.0 (+https://dnmg.gov.tl)"},
            )
            try:
                with urllib.request.urlopen(current_request, timeout=5) as response:
                    if response.status == 200:
                        current_data = json.loads(response.read().decode('utf-8'))
                        cache.set(current_cache_key, current_data, cls.CACHE_TIMEOUT)
            except Exception as error:
                logger.warning(
                    "Unable to fetch current observation for station %s: %s",
                    station.external_id,
                    error,
                )
        if isinstance(current_data, dict) and 'summary' in current_data:
            current_timestamped_observation = cls.store_time_series_observation(station, current_data)
            if current_timestamped_observation is not None:
                time_series_observation = current_timestamped_observation
            data = current_data
        elif time_series_observation is not None:
            # A usable all_params response is sufficient when a current summary
            # is temporarily unavailable.
            return time_series_observation

        def get_daily_val(daily_dict, key, which='latest'):
            if not isinstance(daily_dict, dict):
                return None
            entry = daily_dict.get(key)
            if entry is None and key == "Tide_level":
                entry = daily_dict.get("tide_level") or daily_dict.get("Tide_level")
            elif entry is None:
                entry = daily_dict.get(key.lower()) or daily_dict.get(key.capitalize())
            if isinstance(entry, dict):
                # Prefer the API's current/latest reading. Daily maximums are
                # useful summaries, but they do not necessarily match the API
                # timestamp displayed in the portal.
                for reading_key in (which, 'latest', 'current', 'last', 'value'):
                    sub = entry.get(reading_key)
                    if isinstance(sub, dict) and sub.get('value') is not None:
                        return sub['value']
                    if sub not in (None, '', {}):
                        return sub
            return None

        now_dt = now()
        # Use the API's availability.latest as recorded_at if available, else current time
        api_recorded_at = now_dt

        temperature = None
        humidity = None
        rainfall = None
        wind_speed = None
        wind_dir = ""
        pressure = None
        wave_height = None
        tide_level = None
        peak_period = None
        solar_rad = None
        wind_gust = None
        sea_temp = None
        battery_v = None
        condition = "Live Monitoring"

        if data and isinstance(data, dict):
            # The station-data endpoint returns UTC timestamps (for example, ending in Z).
            # Django stores aware values in UTC, while all UI/API display is localized to Asia/Dili.
            st_info = data.get("station", {})
            avail = st_info.get("availability", {})
            latest_ts_str = avail.get("latest") if isinstance(avail, dict) else None
            api_recorded_at = cls.parse_api_timestamp(latest_ts_str) or now_dt

            # If the API has no current data (empty data dict), stop here —
            # do NOT create a fake observation; return existing latest instead
            api_data_dict = data.get("data", {})
            api_summary = data.get("summary", {})
            api_daily = api_summary.get("daily", {})
            has_live_data = bool(api_data_dict) or bool(api_daily)

            if not has_live_data:
                logger.info(
                    f"Station {station.external_id} ({station.name}): API returned no live data. "
                    f"Last known data: {latest_ts_str}. Using availability.latest as recorded_at."
                )
                # Update coordinates if provided
                api_lat = cls.parse_coordinate(st_info.get("latitude"))
                api_lon = cls.parse_coordinate(st_info.get("longitude"))
                cls.update_station_coordinates(station, api_lat, api_lon)

                # Create a marker observation with the real last-known timestamp (all telemetry None)
                # This ensures the 24h OFFLINE check uses the real station last-data time
                return cls.store_automatic_observation(
                    station,
                    api_recorded_at,
                    temperature=None, humidity=None, rainfall_mm=None,
                    wind_speed_kmh=None, wind_direction="", pressure_hpa=None,
                    wave_height_m=None, tide_level_mm=None, peak_period_s=None,
                    solar_radiation=None, wind_gust_kmh=None,
                    sea_surface_temp=None, battery_voltage=None,
                    condition_text="No Live Data",
                )

            # 1. Update station coordinates from API response in backend DB
            api_lat = cls.parse_coordinate(st_info.get("latitude"))
            api_lon = cls.parse_coordinate(st_info.get("longitude"))
            cls.update_station_coordinates(station, api_lat, api_lon)

            summary = data.get("summary", {})
            daily = summary.get("daily", {})
            precip = summary.get("precipitation", {})

            # 2. Extract type-aware telemetry data
            # Temperature: marine buoys expose sea-surface rather than air
            # temperature, and do not report atmospheric pressure.
            if station.station_type == WeatherStation.StationType.BUOY:
                raw_temp = get_daily_val(daily, "sea_surface_temperature", "latest")
                pressure = None
            else:
                raw_temp = get_daily_val(daily, "air_temperature", "latest")
                pressure = cls.parse_decimal(get_daily_val(daily, "non_coordinate_pressure", "latest"))
            temperature = cls.parse_decimal(raw_temp)

            # Humidity
            humidity = cls.parse_decimal(get_daily_val(daily, "relative_humidity", "latest"))

            # Wind
            ws_val = get_daily_val(daily, "wind_speed", "latest")
            wind_speed = cls.parse_wind_measurement_kmh(ws_val)
            wd_deg = get_daily_val(daily, "wind_direction", "latest")
            wind_dir = cls.degrees_to_compass(wd_deg)

            wg_val = get_daily_val(daily, "maximum_wind_gust_speed", "latest")
            wind_gust = cls.parse_wind_measurement_kmh(wg_val)

            # Precipitation
            precip_today = precip.get("today_mm")
            rainfall = cls.parse_decimal(precip_today)

            # Tide Gauge Specific
            tide_val = get_daily_val(daily, "Tide_level", "latest")
            tide_level = cls.parse_decimal(tide_val)

            # Buoy Specific
            swh_val = get_daily_val(daily, "significant_wave_height", "latest")
            wave_height = cls.parse_decimal(swh_val)
            pp_val = get_daily_val(daily, "peak_period", "latest")
            peak_period = cls.parse_decimal(pp_val)
            sst_val = get_daily_val(daily, "sea_surface_temperature", "latest")
            sea_temp = cls.parse_decimal(sst_val)

            # AWS Extended Fields
            sr_val = get_daily_val(daily, "solar_radiation", "latest")
            solar_rad = cls.parse_decimal(sr_val)
            bv_val = get_daily_val(daily, "battery_voltage", "latest") or get_daily_val(daily, "battery_status", "latest")
            battery_v = cls.parse_decimal(bv_val)

            # Condition text generator
            if station.station_type == WeatherStation.StationType.TIDE_GAUGE:
                condition = f"Tide Level: {tide_level} mm" if tide_level else "Normal Tide Range"
            elif station.station_type == WeatherStation.StationType.BUOY:
                condition = f"Wave Height: {wave_height} m" if wave_height else "Normal Ocean State"
            elif rainfall and rainfall > 0:
                condition = f"Rainfall: {rainfall} mm"
            elif temperature:
                condition = "Clear / Sunny" if (solar_rad and solar_rad > 500) else "Active Monitoring"

        else:
            logger.warning(
                "No response from the DNMG station-data API for station %s; no observation was created.",
                station.external_id,
            )
            return None

        # A daily max/min has no timestamp for the individual reading, so it is
        # deliberately ignored above. Retain the precise time-series value if
        # the current endpoint does not provide an explicit latest/current one.
        if time_series_observation is not None:
            def current_or_series(value, field_name):
                return value if value is not None else getattr(time_series_observation, field_name)

            temperature = current_or_series(temperature, 'temperature')
            humidity = current_or_series(humidity, 'humidity')
            rainfall = current_or_series(rainfall, 'rainfall_mm')
            wind_speed = current_or_series(wind_speed, 'wind_speed_kmh')
            pressure = current_or_series(pressure, 'pressure_hpa')
            wave_height = current_or_series(wave_height, 'wave_height_m')
            tide_level = current_or_series(tide_level, 'tide_level_mm')
            peak_period = current_or_series(peak_period, 'peak_period_s')
            solar_rad = current_or_series(solar_rad, 'solar_radiation')
            wind_gust = current_or_series(wind_gust, 'wind_gust_kmh')
            sea_temp = current_or_series(sea_temp, 'sea_surface_temp')
            battery_v = current_or_series(battery_v, 'battery_voltage')
            wind_dir = wind_dir or time_series_observation.wind_direction

        # Save one observation for the API timestamp; repeated requests update it.
        obs = cls.store_automatic_observation(
            station,
            api_recorded_at,
            temperature=temperature,
            humidity=humidity,
            rainfall_mm=rainfall,
            wind_speed_kmh=wind_speed,
            wind_direction=wind_dir,
            pressure_hpa=pressure,
            wave_height_m=wave_height,
            tide_level_mm=tide_level,
            peak_period_s=peak_period,
            solar_radiation=solar_rad,
            wind_gust_kmh=wind_gust,
            sea_surface_temp=sea_temp,
            battery_voltage=battery_v,
            condition_text=condition,
        )
        return obs

    @classmethod
    def get_station_snapshot(cls, station, current_time=None):
        """Return the single source of truth used by the public map and staff dashboard.

        History deliberately includes every stored observation from the rolling last
        24 hours, rather than an arbitrary number of records.
        """
        current_time = current_time or now()
        latest_observation = station.observations.order_by('-recorded_at').first()
        observations_24h = list(
            station.observations.filter(
                recorded_at__gte=current_time - timedelta(hours=24),
                recorded_at__lte=current_time,
            ).order_by('recorded_at')
        )

        # API parameters can arrive at slightly different timestamps. A newer
        # wind-only row must not replace the previous temperature, humidity, or
        # pressure shown to users. Fill only missing fields from the most recent
        # available value in the same 24-hour station history; genuine zero
        # readings such as zero wind or rainfall are preserved.
        if latest_observation:
            zeroed_core_telemetry = all(
                getattr(latest_observation, field_name) == 0
                for field_name in ("temperature", "humidity", "pressure_hpa")
            )
            for field_name in cls.TELEMETRY_FIELDS:
                latest_value = getattr(latest_observation, field_name)
                is_missing = latest_value in (None, '')
                # A 0 hPa pressure reading is not valid station telemetry. If
                # temperature, humidity, and pressure are all zero, the API has
                # likewise supplied a no-data placeholder rather than readings.
                is_zero_placeholder = (
                    (field_name == "pressure_hpa" and latest_value == 0)
                    or (
                        zeroed_core_telemetry
                        and field_name in ("temperature", "humidity", "pressure_hpa")
                    )
                )
                if not is_missing and not is_zero_placeholder:
                    continue
                for observation in reversed(observations_24h):
                    # Do not use the placeholder row itself as its own
                    # fallback; otherwise a zeroed API payload is preserved
                    # instead of falling back to the previous valid reading.
                    if observation.pk == latest_observation.pk:
                        continue
                    fallback_value = getattr(observation, field_name)
                    if fallback_value not in (None, ''):
                        setattr(latest_observation, field_name, fallback_value)
                        break

        is_online = bool(
            latest_observation
            and latest_observation.recorded_at
            and current_time - latest_observation.recorded_at <= cls.ONLINE_WINDOW
        )
        local_updated_at = localtime(latest_observation.recorded_at) if latest_observation else None
        return {
            'station': station,
            'obs': latest_observation,
            'observations_24h': observations_24h,
            'is_online': is_online,
            'updated_at': local_updated_at,
        }

    @staticmethod
    def get_chart_observations(observations, interval_minutes=15, end_time=None):
        """Build fixed display buckets without changing stored observation times.

        A category chart gives every point equal horizontal spacing. Returning a
        complete configured grid prevents irregular updates from looking as
        though they arrived at regular intervals. Each bucket retains its newest
        source observation; empty buckets remain ``None`` so the chart draws a
        visible gap instead of implying data that was never received.
        """
        if end_time is None:
            end_time = now()
        local_end_time = localtime(end_time).replace(second=0, microsecond=0)
        local_end_time -= timedelta(minutes=local_end_time.minute % interval_minutes)
        bucket_count = (24 * 60) // interval_minutes
        first_bucket = local_end_time - timedelta(
            minutes=interval_minutes * (bucket_count - 1)
        )

        observations_by_bucket = {}
        for observation in observations:
            if not observation.recorded_at:
                continue
            local_recorded_at = localtime(observation.recorded_at)
            bucket_time = local_recorded_at.replace(
                minute=local_recorded_at.minute - (local_recorded_at.minute % interval_minutes),
                second=0,
                microsecond=0,
            )
            if first_bucket <= bucket_time <= local_end_time:
                observations_by_bucket[bucket_time] = observation

        return [
            (
                first_bucket + timedelta(minutes=interval_minutes * index),
                observations_by_bucket.get(
                    first_bucket + timedelta(minutes=interval_minutes * index)
                ),
            )
            for index in range(bucket_count)
        ]

    @classmethod
    def uses_fifteen_minute_chart(cls, station):
        """Return whether this station uses the public 15-minute chart grid."""
        return cls.chart_interval_minutes(station) == 15

    @classmethod
    def chart_interval_minutes(cls, station):
        """Return the station-specific public chart interval, if configured."""
        return (
            cls.CHART_INTERVALS_BY_STATION_TYPE.get(station.station_type)
            or cls.CHART_INTERVALS_BY_STATION_ID.get(station.external_id)
        )

    @staticmethod
    def get_raw_chart_observations(observations):
        """Return every received observation at its original local timestamp."""
        return [
            (localtime(observation.recorded_at), observation)
            for observation in observations
            if observation.recorded_at
        ]

    @classmethod
    def get_dashboard_stations_data(cls):
        """
        Returns all 15 stations grouped by station category (AWS, Tide Gauge, Buoy)
        with coordinates and latest live observation data for the dashboard.
        Evaluates the shared five-hour status rule: ONLINE if data is within
        the last five hours, OFFLINE otherwise.
        All timestamps converted to Timor-Leste local time (Asia/Dili, GMT+9).
        """
        stations = WeatherStation.objects.all().order_by('external_id')
        current_time = now()
        
        aws_list = []
        tide_list = []
        buoy_list = []
        online_counter = 0

        for st in stations:
            snapshot = cls.get_station_snapshot(st, current_time)
            obs = snapshot['obs']
            is_online = snapshot['is_online']
            local_updated_at = snapshot['updated_at']
            if is_online:
                online_counter += 1
            elif local_updated_at is None and st.updated_at:
                local_updated_at = localtime(st.updated_at)

            item = {
                'id': st.id,
                'external_id': st.external_id or st.code,
                'name': st.name,
                'code': st.code,
                'municipality': st.get_municipality_display(),
                'latitude': float(st.latitude),
                'longitude': float(st.longitude),
                'elevation': float(st.elevation) if st.elevation else 0.0,
                'station_type': st.station_type,
                'station_type_display': st.get_station_type_display(),
                'is_online': is_online,
                'online_status': "ONLINE" if is_online else "OFFLINE",
                'status': st.status,
                'status_display': st.get_status_display(),
                'obs': obs,
                'observations_24h': snapshot['observations_24h'],
                # updated_at is already converted to Timor-Leste local time (GMT+9)
                'updated_at': local_updated_at,
            }

            if st.station_type == WeatherStation.StationType.TIDE_GAUGE:
                tide_list.append(item)
            elif st.station_type == WeatherStation.StationType.BUOY:
                buoy_list.append(item)
            else:
                aws_list.append(item)

        return {
            'aws_stations': aws_list,
            'tide_stations': tide_list,
            'buoy_stations': buoy_list,
            'total_count': len(aws_list) + len(tide_list) + len(buoy_list),
            'synced_count': online_counter
        }


class AwosDiliSyncService:
    """Copy the small Dili AWOS working set from its read-only MariaDB source.

    AWOS timestamps are UTC. Django stores aware timestamps in UTC and renders
    them in ``TIME_ZONE`` (Asia/Dili), so this service never changes a source
    timestamp to local wall-clock time before persistence.
    """

    STATION_CODE = "WPDL"
    STATION_DEFAULTS = {
        "name": "Dili Airport AWOS",
        "municipality": Municipality.DILI,
        "latitude": Decimal("-8.546600"),
        "longitude": Decimal("125.525000"),
        "elevation": Decimal("8.00"),
        "station_type": WeatherStation.StationType.AWOS,
        "status": WeatherStation.Status.ACTIVE,
    }
    NUMERIC_VARIABLES = {
        "temperature": ("1Min", "AT10Ma"),
        "humidity": ("1Min", "RH10Ma"),
        "dew_point_c": ("1Min", "DP10Ma"),
        "pressure_hpa": ("1Min", "QNH10Ma"),
        "wind_speed_kmh": ("10Sec", "WS10Ma_A"),
        "wind_direction": ("10Sec", "WD10Ma_A"),
        "wind_gust_kmh": ("10Sec", "WS10Mg_A"),
        "visibility_m": ("1Min", "Vis10Ma_A"),
        "runway_visual_range_m": ("1Min", "RVR10Ma_A"),
    }
    METAR_VARIABLE = ("Metar", "_Metar")
    # Campbell's aviation wind variables use knots. Persist their equivalent
    # in km/h so the shared WeatherObservation model and public station map
    # keep one consistent unit; the airport page converts them back to knots.
    WIND_SPEED_KNOTS_TO_KMH = Decimal("1.852")
    QUANTUM = Decimal("0.01")

    @classmethod
    def is_configured(cls):
        return bool(
            settings.AWOS_DILI_DATABASE_URL
            and settings.AWOS_DILI_USER
            and settings.AWOS_DILI_PASSWORD
        )

    @classmethod
    def connection_options(cls):
        """Return safe PyMySQL options for the configured AWOS source."""
        if not cls.is_configured():
            raise ValueError("Dili AWOS MariaDB credentials are not configured.")
        database_url = urlparse(settings.AWOS_DILI_DATABASE_URL)
        if database_url.scheme not in {"mysql", "mariadb"}:
            raise ValueError("AWOS_DILI_DATABASE_URL must start with mysql:// or mariadb://")
        database_name = database_url.path.strip("/")
        if not database_url.hostname or not database_name:
            raise ValueError("AWOS_DILI_DATABASE_URL must include a host and database name.")
        if database_url.username or database_url.password:
            raise ValueError("Put AWOS credentials in AWOS_DILI_USER and AWOS_DILI_PASSWORD, not the URL.")
        return {
            "host": database_url.hostname,
            "port": database_url.port or 3306,
            "user": settings.AWOS_DILI_USER,
            "password": settings.AWOS_DILI_PASSWORD,
            "database": database_name,
            "autocommit": True,
            "connect_timeout": 10,
            "read_timeout": 10,
            "write_timeout": 10,
            "cursorclass": pymysql.cursors.DictCursor,
        }

    @classmethod
    def fetch_active_values(cls):
        """Fetch only the selected WPDL records from the AWOS ``active`` table."""
        requested_variables = tuple(cls.NUMERIC_VARIABLES.values()) + (cls.METAR_VARIABLE,)
        placeholders = ", ".join(["(%s, %s)"] * len(requested_variables))
        parameters = [cls.STATION_CODE]
        for group_name, variable_name in requested_variables:
            parameters.extend((group_name, variable_name))
        query = (
            "SELECT GroupName, VariableName, UpdateDate, CurrentValue, CurrentQuality, CurrentASCII "
            "FROM active WHERE StationName = %s "
            f"AND (GroupName, VariableName) IN ({placeholders})"
        )
        connection = pymysql.connect(**cls.connection_options())
        try:
            with connection.cursor() as cursor:
                cursor.execute(query, parameters)
                return {
                    (row["GroupName"], row["VariableName"]): row
                    for row in cursor.fetchall()
                }
        finally:
            connection.close()

    @classmethod
    def parse_decimal(cls, value):
        if value is None:
            return None
        try:
            return Decimal(str(value)).quantize(cls.QUANTUM, rounding=ROUND_HALF_UP)
        except (InvalidOperation, TypeError, ValueError):
            return None

    @classmethod
    def source_timestamp(cls, value):
        """Treat MariaDB's naive AWOS datetimes as UTC source timestamps."""
        if value is None:
            return None
        if not is_aware(value):
            value = make_aware(value, datetime_timezone.utc)
        return value.astimezone(datetime_timezone.utc)

    @classmethod
    def latest_observation_timestamp(cls, values):
        timestamps = [
            cls.source_timestamp(row.get("UpdateDate"))
            for variable in cls.NUMERIC_VARIABLES.values()
            if (row := values.get(variable)) is not None
        ]
        timestamps = [timestamp for timestamp in timestamps if timestamp is not None]
        if not timestamps:
            return None
        # AWOS wind values update every ten seconds. Store one portal snapshot
        # per UTC minute, as agreed, rather than reproducing that high-volume stream.
        return max(timestamps).replace(second=0, microsecond=0)

    @classmethod
    def get_station(cls):
        return WeatherStation.objects.get_or_create(
            code=cls.STATION_CODE,
            defaults=cls.STATION_DEFAULTS,
        )[0]

    @classmethod
    def observation_values(cls, values):
        def numeric(field_name):
            row = values.get(cls.NUMERIC_VARIABLES[field_name])
            return cls.parse_decimal(row.get("CurrentValue")) if row else None

        def wind_speed_kmh(field_name):
            row = values.get(cls.NUMERIC_VARIABLES[field_name])
            if not row or row.get("CurrentValue") is None:
                return None
            try:
                return (Decimal(str(row["CurrentValue"])) * cls.WIND_SPEED_KNOTS_TO_KMH).quantize(
                    cls.QUANTUM,
                    rounding=ROUND_HALF_UP,
                )
            except (InvalidOperation, TypeError, ValueError):
                return None

        wind_direction_degrees = numeric("wind_direction")
        return {
            "temperature": numeric("temperature"),
            "humidity": numeric("humidity"),
            "dew_point_c": numeric("dew_point_c"),
            "pressure_hpa": numeric("pressure_hpa"),
            "wind_speed_kmh": wind_speed_kmh("wind_speed_kmh"),
            "wind_direction": DNMGStationSyncService.degrees_to_compass(wind_direction_degrees),
            "wind_gust_kmh": wind_speed_kmh("wind_gust_kmh"),
            "visibility_m": numeric("visibility_m"),
            "runway_visual_range_m": numeric("runway_visual_range_m"),
            "condition_text": "AWOS Live Monitoring",
        }

    @classmethod
    def wind_kmh_to_knots(cls, value):
        """Convert a stored AWOS wind value to the aviation display unit."""
        if value is None:
            return None
        try:
            return (Decimal(str(value)) / cls.WIND_SPEED_KNOTS_TO_KMH).quantize(
                Decimal("0.1"),
                rounding=ROUND_HALF_UP,
            )
        except (InvalidOperation, TypeError, ValueError):
            return None

    @classmethod
    def store_metar(cls, station, values):
        row = values.get(cls.METAR_VARIABLE)
        if not row:
            return None
        raw_report = (row.get("CurrentASCII") or "").replace("\r", " ").replace("\n", " ").strip()
        reported_at = cls.source_timestamp(row.get("UpdateDate"))
        if not raw_report or not raw_report.startswith("METAR ") or reported_at is None:
            return None
        report, _ = AwosMetarReport.objects.update_or_create(
            station=station,
            reported_at=reported_at,
            defaults={"raw_report": raw_report},
        )
        return report

    @classmethod
    def purge_expired_records(cls, station):
        observation_cutoff = now() - timedelta(hours=settings.AWOS_DILI_OBSERVATION_RETENTION_HOURS)
        metar_cutoff = now() - timedelta(days=settings.AWOS_DILI_METAR_RETENTION_DAYS)
        observations_deleted, _ = WeatherObservation.objects.filter(
            station=station,
            recorded_by__isnull=True,
            recorded_at__lt=observation_cutoff,
        ).delete()
        reports_deleted, _ = AwosMetarReport.objects.filter(
            station=station,
            reported_at__lt=metar_cutoff,
        ).delete()
        return observations_deleted, reports_deleted

    @classmethod
    def sync(cls):
        """Synchronize one current AWOS snapshot and its latest METAR report."""
        if not cls.is_configured():
            return {"status": "disabled"}
        try:
            active_values = cls.fetch_active_values()
        except (pymysql.MySQLError, ValueError, OSError) as error:
            logger.warning("Unable to read Dili AWOS MariaDB: %s", error)
            return {"status": "failed", "reason": str(error)}

        recorded_at = cls.latest_observation_timestamp(active_values)
        if recorded_at is None:
            return {"status": "no_data"}

        station = cls.get_station()
        observation = DNMGStationSyncService.store_automatic_observation(
            station,
            recorded_at,
            **cls.observation_values(active_values),
        )
        report = cls.store_metar(station, active_values)
        observations_deleted, reports_deleted = cls.purge_expired_records(station)
        return {
            "status": "synced",
            "station": station,
            "observation": observation,
            "metar": report,
            "observations_deleted": observations_deleted,
            "metar_reports_deleted": reports_deleted,
        }


class DNMG10DayForecastService:
    """
    Fetches and caches 10-day regional forecast data from ms-api.dnmg.gov.tl API:
    https://ms-api.dnmg.gov.tl/api/v1/get-alert/?model=ECMWF-IFS&variable={var}&admin_level=1&use_pcode=false
    Supports variables: tp (rainfall), heat, cold, wind, rh, thi, cloud_cover.
    """
    API_BASE_URL = "https://ms-api.dnmg.gov.tl/api/v1/get-alert/"
    CACHE_TIMEOUT = 300  # 5 minutes fresh cache
    STALE_CACHE_TIMEOUT = 3600  # retain the last known forecast for outages
    REQUEST_TIMEOUT = 5

    VARIABLE_META = {
        'tp': {'name': 'Total Rainfall', 'unit': 'mm', 'icon': 'bi-cloud-rain-fill'},
        'heat': {'name': 'High Temperature', 'unit': '°C', 'icon': 'bi-thermometer-high'},
        'cold': {'name': 'Low Temperature', 'unit': '°C', 'icon': 'bi-thermometer-snow'},
        'wind': {'name': 'Wind Speed', 'unit': 'km/h', 'icon': 'bi-wind'},
        'rh': {'name': 'Relative Humidity', 'unit': '%', 'icon': 'bi-droplet-half'},
        'thi': {'name': 'Temperature-Humidity Index', 'unit': 'THI', 'icon': 'bi-activity'},
        'cloud_cover': {'name': 'Cloud Cover', 'unit': '%', 'icon': 'bi-clouds-fill'},
    }

    @classmethod
    def _cache_keys(cls, variable, model):
        base = f"dnmg_10day_{model}_{variable}"
        return base, f"{base}_stale"

    @classmethod
    def get_cached_forecast(cls, variable='tp', model='ECMWF-IFS', allow_stale=True):
        """Return cached forecast data without making a public request wait on DNS/API I/O."""
        if variable not in cls.VARIABLE_META:
            variable = 'tp'
        cache_key, stale_cache_key = cls._cache_keys(variable, model)
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
        return cache.get(stale_cache_key) if allow_stale else None

    @classmethod
    def fetch_forecast(cls, variable='tp', model='ECMWF-IFS'):
        if variable not in cls.VARIABLE_META:
            variable = 'tp'

        cache_key, stale_cache_key = cls._cache_keys(variable, model)
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        url = f"{cls.API_BASE_URL}?model={model}&variable={variable}&admin_level=1&use_pcode=false"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "DNMG-Portal/1.0 (+https://dnmg.gov.tl)"}
        )
        data = None
        try:
            with urllib.request.urlopen(req, timeout=cls.REQUEST_TIMEOUT) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode('utf-8'))
                    cache.set(cache_key, data, cls.CACHE_TIMEOUT)
                    cache.set(stale_cache_key, data, cls.STALE_CACHE_TIMEOUT)
        except Exception as e:
            logger.warning(f"Unable to fetch 10-day forecast API for variable {variable}: {e}")
            data = cache.get(stale_cache_key)

        return data


class METNorwayForecastService:
    """Cached municipal point forecasts from MET Norway Locationforecast.

    The provider supplies model guidance, not DNMG observations. Requests are
    made only by the scheduled backend refresh, with the required identifying
    User-Agent and provider-controlled expiry respected in the cache.
    """

    API_URL = "https://api.met.no/weatherapi/locationforecast/2.0/compact"
    USER_AGENT = "DNMG Portal/1.0 (+https://dnmg.gov.tl; info@dnmg.gov.tl)"
    REQUEST_TIMEOUT = 8
    CACHE_KEY = "met_norway_municipality_hourly_forecast_v3"
    STALE_CACHE_TIMEOUT = 6 * 60 * 60
    DEFAULT_CACHE_TIMEOUT = 60 * 60
    TIMOR_LESTE_TIMEZONE = ZoneInfo("Asia/Dili")

    # Municipal reference points include Atauro, which is present in the public
    # municipality boundary data but does not yet have a WeatherStation choice.
    MUNICIPALITY_LOCATIONS = (
        ("Aileu", -8.728, 125.566, 913),
        ("Ainaro", -8.993, 125.509, 827),
        ("Atauro", -8.255, 125.582, 28),
        ("Baucau", -8.471, 126.458, 510),
        ("Bobonaro", -9.020, 125.327, 841),
        ("Cova Lima", -9.177, 125.150, 202),
        ("Dili", -8.557, 125.578, 12),
        ("Ermera", -8.752, 125.400, 734),
        ("Lautem", -8.444, 126.894, 50),
        ("Liquica", -8.588, 125.341, 12),
        ("Manatuto", -8.514, 126.012, 20),
        ("Manufahi", -9.012, 125.759, 320),
        ("Oecusse", -9.198, 124.354, 15),
        ("Viqueque", -8.872, 126.364, 39),
    )

    @classmethod
    def get_cached_forecast(cls, allow_stale=True):
        cached = cache.get(cls.CACHE_KEY)
        if not cached:
            return []
        if cached["expires_at"] > time.time() or allow_stale:
            return cached["conditions"]
        return []

    @staticmethod
    def _number(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _cache_timeout(cls, headers):
        expires = headers.get("Expires") if headers else None
        if not expires:
            return cls.DEFAULT_CACHE_TIMEOUT
        try:
            timeout = int(parsedate_to_datetime(expires).timestamp() - time.time())
        except (TypeError, ValueError, IndexError, OverflowError):
            return cls.DEFAULT_CACHE_TIMEOUT
        return max(60, timeout)

    @classmethod
    def _normalise_condition(cls, municipality, payload):
        times = payload.get("properties", {}).get("timeseries", [])
        if not times:
            return None

        parsed_times = []
        for entry in times:
            parsed_time = parse_datetime(entry.get("time", ""))
            if parsed_time is None:
                continue
            if not is_aware(parsed_time):
                parsed_time = make_aware(parsed_time, datetime_timezone.utc)
            parsed_times.append((parsed_time, entry))

        if not parsed_times:
            return None

        forecast = parsed_times[0][1]
        details = forecast.get("data", {}).get("instant", {}).get("details", {})
        rain = forecast.get("data", {}).get("next_1_hours", {}).get("details", {})
        temperature = cls._number(details.get("air_temperature"))
        humidity = cls._number(details.get("relative_humidity"))
        wind_speed = cls._number(details.get("wind_speed"))
        precipitation = cls._number(rain.get("precipitation_amount"))
        forecast_time = parse_datetime(forecast.get("time", ""))
        if forecast_time is None:
            return None

        return {
            "name": municipality,
            "temperature": round(temperature, 1) if temperature is not None else None,
            "humidity": round(humidity, 1) if humidity is not None else None,
            "rainfall": round(precipitation, 1) if precipitation is not None else None,
            "wind_speed": round(wind_speed * 3.6, 1) if wind_speed is not None else None,
            "forecast_time": localtime(
                now(), cls.TIMOR_LESTE_TIMEZONE
            ).replace(minute=0, second=0, microsecond=0).strftime("%H:%M"),
        }

    @classmethod
    def fetch_municipality_forecast(cls):
        cached = cache.get(cls.CACHE_KEY)
        if cached and cached["expires_at"] > time.time():
            return cached["conditions"]

        conditions = []
        cache_timeout = cls.DEFAULT_CACHE_TIMEOUT
        for municipality, latitude, longitude, altitude in cls.MUNICIPALITY_LOCATIONS:
            query = urlencode({
                "lat": latitude,
                "lon": longitude,
                "altitude": altitude,
            })
            request = urllib.request.Request(
                f"{cls.API_URL}?{query}",
                headers={"User-Agent": cls.USER_AGENT},
            )
            try:
                with urllib.request.urlopen(request, timeout=cls.REQUEST_TIMEOUT) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                    cache_timeout = min(cache_timeout, cls._cache_timeout(response.headers))
            except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
                logger.warning("MET Norway forecast unavailable for %s: %s", municipality, exc)
                continue

            condition = cls._normalise_condition(municipality, payload)
            if condition:
                conditions.append(condition)

        if conditions:
            cache.set(
                cls.CACHE_KEY,
                {
                    "conditions": conditions,
                    "expires_at": time.time() + cache_timeout,
                },
                cache_timeout + cls.STALE_CACHE_TIMEOUT,
            )
            return conditions
        return cached["conditions"] if cached else []
