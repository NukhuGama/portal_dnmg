import json
from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlsplit

from django.test import TestCase
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils.timezone import localtime, now
from users.models import PortalPermission, Role, User
from .models import WeatherStation, WeatherObservation, WeatherForecast, EarlyWarning, Municipality

class WeatherModelTestCase(TestCase):
    def setUp(self):
        self.meteorologist = User.objects.create_user(
            username="met_officer",
            password="password123",
            role=User.Role.METEOROLOGIST
        )
        self.public_user = User.objects.create_user(
            username="public_user",
            password="password123",
            role=User.Role.PUBLIC
        )
        self.station = WeatherStation.objects.create(
            name="Dili Airport AWS",
            code="DILI-AWS-01",
            municipality=Municipality.DILI,
            latitude="-8.555890",
            longitude="125.573610",
            elevation=8.5,
            station_type=WeatherStation.StationType.AWS,
            status=WeatherStation.Status.ACTIVE
        )

    def test_station_creation(self):
        self.assertEqual(self.station.code, "DILI-AWS-01")
        self.assertEqual(str(self.station), "Dili Airport AWS (DILI-AWS-01) - Dili")

    def test_observation_creation(self):
        obs = WeatherObservation.objects.create(
            station=self.station,
            temperature=29.5,
            humidity=75,
            recorded_at=now(),
            recorded_by=self.meteorologist
        )
        self.assertEqual(obs.temperature, 29.5)
        self.assertEqual(obs.station, self.station)

    def test_forecast_creation(self):
        forecast = WeatherForecast.objects.create(
            municipality=Municipality.DILI,
            forecast_date=now().date(),
            temp_min=24,
            temp_max=32,
            condition="Partly Cloudy",
            rain_probability=20,
            issued_by=self.meteorologist
        )
        self.assertEqual(forecast.municipality, Municipality.DILI)
        self.assertEqual(forecast.temp_max, 32)

    def test_forecast_is_unique_per_municipality_and_date(self):
        values = {
            'municipality': Municipality.DILI,
            'forecast_date': now().date(),
            'temp_min': 24,
            'temp_max': 32,
            'condition': 'Partly Cloudy',
            'issued_by': self.meteorologist,
        }
        WeatherForecast.objects.create(**values)
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                WeatherForecast.objects.create(**values)

    def test_early_warning_creation(self):
        warning = EarlyWarning.objects.create(
            title="Heavy Rainfall Warning",
            severity=EarlyWarning.Severity.DANGER,
            region="Viqueque & Lautem",
            description="Landslide risk in mountainous areas.",
            valid_from=now(),
            valid_to=now(),
            issued_by=self.meteorologist
        )
        self.assertEqual(warning.severity, EarlyWarning.Severity.DANGER)
        self.assertTrue(warning.is_active)


class WeatherPermissionsTestCase(TestCase):
    def setUp(self):
        self.meteorologist = User.objects.create_user(
            username="met_officer2",
            password="password123",
            role=User.Role.METEOROLOGIST
        )
        self.public_user = User.objects.create_user(
            username="public_user2",
            password="password123",
            role=User.Role.PUBLIC
        )

    def test_meteorologist_can_access_station_list(self):
        self.client.force_login(self.meteorologist)
        response = self.client.get(reverse('weather:station_list'))
        self.assertEqual(response.status_code, 200)

    def test_public_user_cannot_access_station_list(self):
        self.client.force_login(self.public_user)
        response = self.client.get(reverse('weather:station_list'))
        self.assertEqual(response.status_code, 403)

    def test_custom_early_warning_view_permission_does_not_grant_creation(self):
        warning_view, _ = PortalPermission.objects.get_or_create(
            code='early_warnings.view',
            defaults={
                'module': 'early_warnings',
                'name': 'View Early Warnings',
                'is_system': True,
            },
        )
        role = Role.objects.create(name='Early Warning Reader')
        role.permissions.add(warning_view)
        user = User.objects.create_user(
            username='early_warning_reader',
            password='password123',
            access_role=role,
        )

        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse('weather:warning_list')).status_code, 200)
        self.assertEqual(self.client.get(reverse('weather:warning_create')).status_code, 403)


class Phase3SyncAndApiTestCase(TestCase):
    def test_home_uses_cached_forecast_without_calling_the_external_service(self):
        from django.core.cache import cache
        from weather.services import DNMG10DayForecastService

        cache.set('dnmg_10day_ECMWF-IFS_tp', {'Dili': []}, 300)
        with patch.object(DNMG10DayForecastService, 'fetch_forecast') as fetch_forecast:
            response = self.client.get(reverse('core:home'))
        self.assertEqual(response.status_code, 200)
        fetch_forecast.assert_not_called()

    def test_station_data_history_url_uses_a_24_hour_timor_leste_window(self):
        from .services import DNMGStationSyncService

        # 13:00 in Dili is 04:00 UTC. The request is calculated in Dili first,
        # then converted to the UTC timestamps required by the station API.
        dilli_end_time = DNMGStationSyncService.parse_api_timestamp('2026-08-08T04:00:00Z')
        url = DNMGStationSyncService.build_last_24_hours_api_url(15404, dilli_end_time)
        parsed_url = urlsplit(url)
        query = parse_qs(parsed_url.query)

        self.assertEqual(parsed_url.path, '/station-data/15404')
        self.assertEqual(query['all_params'], ['true'])
        self.assertEqual(query['start_time'], ['2026-08-07T04:00:00Z'])
        self.assertEqual(query['end_time'], ['2026-08-08T04:00:00Z'])
        self.assertEqual(query['tz'], ['Asia/Dili'])

    def test_station_api_timestamp_is_converted_to_timor_leste_time(self):
        from .services import DNMGStationSyncService

        timestamp = DNMGStationSyncService.parse_api_timestamp('2026-08-07T23:10:00Z')

        self.assertIsNotNone(timestamp)
        self.assertEqual(timestamp.strftime('%Y-%m-%d %H:%M %z'), '2026-08-08 08:10 +0900')

    def test_time_series_response_uses_latest_values_and_local_time(self):
        from .services import DNMGStationSyncService

        station = WeatherStation.objects.create(
            external_id=19999,
            name='Time-series test station',
            code='TIME-SERIES-19999',
            municipality=Municipality.LIQUICA,
            latitude='-8.57',
            longitude='125.36',
        )
        observation = DNMGStationSyncService.store_time_series_observation(station, {
            'station': {'latitude': -8.5798, 'longitude': 125.362788},
            'air_temperature': [{'value': 25.97, 'start_time': '2026-08-07T23:10:00Z'}],
            'relative_humidity': [{'value': 53.19, 'start_time': '2026-08-07T23:10:00Z'}],
            'wind_speed': [{'value': 5.38, 'start_time': '2026-08-07T23:10:00Z'}],
            'wind_direction': [{'value': 220.42, 'start_time': '2026-08-07T23:10:00Z'}],
        })

        self.assertEqual(float(observation.temperature), 25.97)
        self.assertEqual(observation.humidity, Decimal('53.19'))
        self.assertEqual(observation.wind_direction, 'SW')
        self.assertEqual(localtime(observation.recorded_at).strftime('%Y-%m-%d %H:%M %z'), '2026-08-08 08:10 +0900')

    def test_tide_gauge_nested_environmental_data_includes_temperature_and_pressure(self):
        from .services import DNMGStationSyncService

        station = WeatherStation.objects.create(
            external_id=19994,
            name='Nested telemetry tide gauge',
            code='TIDE-NESTED-19994',
            station_type=WeatherStation.StationType.TIDE_GAUGE,
            municipality=Municipality.DILI,
            latitude='-8.553200',
            longitude='125.574700',
        )
        recorded_at = now() - timedelta(minutes=5)
        observation = DNMGStationSyncService.store_time_series_observation(station, {
            'data': {
                'Air Temperature': [{'reading': '28.76', 'timestamp': recorded_at.isoformat()}],
                'Air Pressure': [{'measurement': '1009.35', 'time': recorded_at.isoformat()}],
                'Tide Level': [{'value': '906.20', 'start_time': recorded_at.isoformat()}],
            },
        })

        self.assertEqual(observation.temperature, Decimal('28.76'))
        self.assertEqual(observation.pressure_hpa, Decimal('1009.35'))
        self.assertEqual(observation.tide_level_mm, Decimal('906.20'))

    def test_tide_gauge_flat_api_observations_include_temperature_and_pressure(self):
        from .services import DNMGStationSyncService

        station = WeatherStation.objects.create(
            external_id=19990,
            name='Flat telemetry tide gauge',
            code='TIDE-FLAT-19990',
            station_type=WeatherStation.StationType.TIDE_GAUGE,
            municipality=Municipality.DILI,
            latitude='-8.553200',
            longitude='125.574700',
        )
        recorded_at = now() - timedelta(minutes=5)
        observation = DNMGStationSyncService.store_time_series_observation(station, {
            'data': [
                {'parameter': 'Air Temperature', 'value': '28.90', 'timestamp_utc': recorded_at.isoformat()},
                {'parameter': 'Station Pressure', 'value': '1009.35', 'timestamp_utc': recorded_at.isoformat()},
                {'parameter': 'Tide Level', 'value': '906.20', 'timestamp_utc': recorded_at.isoformat()},
            ],
        })

        self.assertEqual(observation.temperature, Decimal('28.90'))
        self.assertEqual(observation.pressure_hpa, Decimal('1009.35'))
        self.assertEqual(observation.tide_level_mm, Decimal('906.20'))

    def test_buoy_uses_sea_surface_temperature_and_peak_period(self):
        from .services import DNMGStationSyncService

        station = WeatherStation.objects.create(
            external_id=19989,
            name='Buoy telemetry test station',
            code='BUOY-19989',
            station_type=WeatherStation.StationType.BUOY,
            municipality=Municipality.DILI,
            latitude='-8.524000',
            longitude='124.592000',
        )
        recorded_at = now() - timedelta(minutes=5)
        observation = DNMGStationSyncService.store_time_series_observation(station, {
            'sea_surface_temperature': [{'value': '28.40', 'start_time': recorded_at.isoformat()}],
            'peak_period': [{'value': '9.80', 'start_time': recorded_at.isoformat()}],
        })

        self.assertEqual(observation.temperature, Decimal('28.40'))
        self.assertEqual(observation.sea_surface_temp, Decimal('28.40'))
        self.assertEqual(observation.peak_period_s, Decimal('9.80'))
        self.assertIsNone(observation.pressure_hpa)

    def test_forced_sync_bypasses_the_station_response_cache(self):
        from .services import DNMGStationSyncService

        station = WeatherStation.objects.create(
            external_id=19993,
            name='Force-sync cache test station',
            code='FORCE-CACHE-19993',
            municipality=Municipality.DILI,
            latitude='-8.553200',
            longitude='125.574700',
        )
        payload = {
            'air_temperature': [
                {'value': '28.90', 'start_time': (now() - timedelta(minutes=1)).isoformat()},
            ],
        }
        with patch('weather.services.cache.get', return_value={'air_temperature': []}), patch(
            'weather.services.urllib.request.urlopen'
        ) as urlopen:
            response = urlopen.return_value.__enter__.return_value
            response.status = 200
            response.read.return_value = json.dumps(payload).encode('utf-8')

            observation = DNMGStationSyncService.fetch_and_store_observation(station, force=True)

        self.assertEqual(observation.temperature, Decimal('28.90'))
        self.assertEqual(urlopen.call_count, 2)

    def test_tide_gauge_uses_current_api_values_when_time_series_omits_them(self):
        from .services import DNMGStationSyncService

        station = WeatherStation.objects.create(
            external_id=19992,
            name='Current API tide gauge test',
            code='TIDE-CURRENT-19992',
            station_type=WeatherStation.StationType.TIDE_GAUGE,
            municipality=Municipality.DILI,
            latitude='-8.553200',
            longitude='125.574700',
        )
        recorded_at = now() - timedelta(minutes=1)
        time_series_payload = {
            'tide_level': [{'value': '906.20', 'start_time': recorded_at.isoformat()}],
        }
        current_payload = {
            'station': {'availability': {'latest': recorded_at.isoformat()}},
            'summary': {
                'daily': {
                    'air_temperature': {'latest': {'value': '28.90'}},
                    'non_coordinate_pressure': {'latest': {'value': '1009.35'}},
                    'Tide_level': {'latest': {'value': '906.20'}},
                },
            },
        }
        with patch('weather.services.cache.get', return_value=None), patch(
            'weather.services.urllib.request.urlopen'
        ) as urlopen:
            first_response = MagicMock()
            first_response.status = 200
            first_response.read.return_value = json.dumps(time_series_payload).encode('utf-8')
            second_response = MagicMock()
            second_response.status = 200
            second_response.read.return_value = json.dumps(current_payload).encode('utf-8')
            first_context = MagicMock()
            first_context.__enter__.return_value = first_response
            second_context = MagicMock()
            second_context.__enter__.return_value = second_response
            urlopen.side_effect = [first_context, second_context]

            observation = DNMGStationSyncService.fetch_and_store_observation(station, force=True)

        self.assertEqual(observation.temperature, Decimal('28.90'))
        self.assertEqual(observation.pressure_hpa, Decimal('1009.35'))
        self.assertEqual(observation.recorded_at, recorded_at)

    def test_daily_maximum_does_not_replace_a_timestamped_api_reading(self):
        from .services import DNMGStationSyncService

        station = WeatherStation.objects.create(
            external_id=19991,
            name='Timestamp accuracy test station',
            code='TIMESTAMP-19991',
            municipality=Municipality.MANATUTO,
            latitude='-8.536900',
            longitude='126.013500',
        )
        recorded_at = now() - timedelta(minutes=1)
        time_series_payload = {
            'air_temperature': [{'value': '27.37', 'start_time': recorded_at.isoformat()}],
        }
        current_payload = {
            'station': {'availability': {'latest': recorded_at.isoformat()}},
            'summary': {'daily': {'air_temperature': {'max': {'value': '28.38'}}}},
        }
        with patch('weather.services.cache.get', return_value=None), patch(
            'weather.services.urllib.request.urlopen'
        ) as urlopen:
            first_response = MagicMock(status=200)
            first_response.read.return_value = json.dumps(time_series_payload).encode('utf-8')
            second_response = MagicMock(status=200)
            second_response.read.return_value = json.dumps(current_payload).encode('utf-8')
            first_context = MagicMock()
            first_context.__enter__.return_value = first_response
            second_context = MagicMock()
            second_context.__enter__.return_value = second_response
            urlopen.side_effect = [first_context, second_context]

            observation = DNMGStationSyncService.fetch_and_store_observation(station, force=True)

        self.assertEqual(observation.temperature, Decimal('27.37'))
        self.assertEqual(observation.recorded_at, recorded_at)

    def test_station_snapshot_includes_all_and_only_last_24_hours(self):
        from .services import DNMGStationSyncService

        station = WeatherStation.objects.create(
            external_id=19998,
            name='24-hour test station',
            code='SNAPSHOT-19998',
            municipality=Municipality.DILI,
            latitude='-8.553200',
            longitude='125.574700',
        )
        current_time = now()
        old_observation = WeatherObservation.objects.create(
            station=station,
            temperature=Decimal('20.00'),
            recorded_at=current_time - timedelta(hours=24, seconds=1),
        )
        first_recent = WeatherObservation.objects.create(
            station=station,
            temperature=Decimal('21.11'),
            recorded_at=current_time - timedelta(hours=23),
        )
        latest_recent = WeatherObservation.objects.create(
            station=station,
            temperature=Decimal('22.22'),
            recorded_at=current_time - timedelta(minutes=5),
        )

        snapshot = DNMGStationSyncService.get_station_snapshot(station, current_time)

        self.assertTrue(snapshot['is_online'])
        self.assertEqual(snapshot['obs'], latest_recent)
        self.assertEqual(snapshot['observations_24h'], [first_recent, latest_recent])
        self.assertNotIn(old_observation, snapshot['observations_24h'])

    def test_station_snapshot_uses_last_known_value_for_missing_latest_fields(self):
        from .services import DNMGStationSyncService

        station = WeatherStation.objects.create(
            external_id=19994,
            name='Partial telemetry station',
            code='PARTIAL-19994',
            municipality=Municipality.DILI,
            latitude='-8.553200',
            longitude='125.574700',
        )
        current_time = now()
        complete_observation = WeatherObservation.objects.create(
            station=station,
            temperature='24.50',
            humidity='72.30',
            pressure_hpa='1008.40',
            recorded_at=current_time - timedelta(minutes=10),
        )
        newest_partial_observation = WeatherObservation.objects.create(
            station=station,
            temperature=None,
            humidity=None,
            pressure_hpa=None,
            wind_speed_kmh='3.20',
            recorded_at=current_time - timedelta(minutes=2),
        )

        snapshot = DNMGStationSyncService.get_station_snapshot(station, current_time)

        self.assertEqual(snapshot['obs'].pk, newest_partial_observation.pk)
        self.assertEqual(snapshot['obs'].temperature, Decimal('24.50'))
        self.assertEqual(snapshot['obs'].humidity, Decimal('72.30'))
        self.assertEqual(snapshot['obs'].pressure_hpa, Decimal('1008.40'))
        self.assertEqual(snapshot['obs'].wind_speed_kmh, Decimal('3.20'))
        self.assertIsNone(snapshot['observations_24h'][-1].temperature)

    def test_station_snapshot_preserves_a_genuine_zero_value(self):
        from .services import DNMGStationSyncService

        station = WeatherStation.objects.create(
            external_id=19993,
            name='Zero-value station',
            code='ZERO-19993',
            municipality=Municipality.DILI,
            latitude='-8.553200',
            longitude='125.574700',
        )
        current_time = now()
        WeatherObservation.objects.create(
            station=station,
            temperature='25.00',
            recorded_at=current_time - timedelta(minutes=10),
        )
        WeatherObservation.objects.create(
            station=station,
            temperature='0.00',
            recorded_at=current_time - timedelta(minutes=2),
        )

        snapshot = DNMGStationSyncService.get_station_snapshot(station, current_time)

        self.assertEqual(snapshot['obs'].temperature, Decimal('0.00'))

    def test_station_snapshot_replaces_a_zeroed_core_telemetry_placeholder(self):
        from .services import DNMGStationSyncService

        station = WeatherStation.objects.create(
            external_id=19992,
            name='Zero-placeholder station',
            code='ZERO-PLACEHOLDER-19992',
            municipality=Municipality.DILI,
            latitude='-8.553200',
            longitude='125.574700',
        )
        current_time = now()
        WeatherObservation.objects.create(
            station=station,
            temperature='24.00',
            humidity='70.00',
            pressure_hpa='1009.00',
            recorded_at=current_time - timedelta(minutes=10),
        )
        WeatherObservation.objects.create(
            station=station,
            temperature='0.00',
            humidity='0.00',
            pressure_hpa='0.00',
            recorded_at=current_time - timedelta(minutes=2),
        )

        snapshot = DNMGStationSyncService.get_station_snapshot(station, current_time)

        self.assertEqual(snapshot['obs'].temperature, Decimal('24.00'))
        self.assertEqual(snapshot['obs'].humidity, Decimal('70.00'))
        self.assertEqual(snapshot['obs'].pressure_hpa, Decimal('1009.00'))

    def test_decimal_and_coordinate_parsing_preserve_required_precision(self):
        from .services import DNMGStationSyncService

        self.assertEqual(DNMGStationSyncService.parse_decimal('25.975'), Decimal('25.98'))
        self.assertEqual(DNMGStationSyncService.parse_decimal('53.19'), Decimal('53.19'))
        self.assertEqual(
            DNMGStationSyncService.parse_coordinate('125.362788'),
            Decimal('125.362788'),
        )

    def test_time_series_sync_stores_all_available_samples_from_last_24_hours(self):
        from .services import DNMGStationSyncService

        station = WeatherStation.objects.create(
            external_id=19997,
            name='Time-series history test station',
            code='HISTORY-19997',
            municipality=Municipality.DILI,
            latitude='-8.553200',
            longitude='125.574700',
        )
        first_time = now() - timedelta(hours=23)
        latest_time = now() - timedelta(minutes=5)

        DNMGStationSyncService.store_time_series_observation(station, {
            'station': {'latitude': '-8.553200', 'longitude': '125.574700'},
            'air_temperature': [
                {'value': '24.12', 'start_time': first_time.isoformat()},
                {'value': '25.34', 'start_time': latest_time.isoformat()},
            ],
            'relative_humidity': [
                {'value': '71.01', 'start_time': first_time.isoformat()},
                {'value': '70.22', 'start_time': latest_time.isoformat()},
            ],
        })

        stored = list(station.observations.order_by('recorded_at'))

        self.assertEqual(len(stored), 2)
        self.assertEqual(stored[0].temperature, Decimal('24.12'))
        self.assertEqual(stored[1].temperature, Decimal('25.34'))
        self.assertEqual(stored[1].humidity, Decimal('70.22'))

    def test_chart_history_uses_only_exact_30_minute_api_timestamps(self):
        from .services import DNMGStationSyncService

        station = WeatherStation.objects.create(
            external_id=19996,
            name='Chart interval test station',
            code='CHART-19996',
            municipality=Municipality.DILI,
            latitude='-8.553200',
            longitude='125.574700',
        )
        hour_start = now().replace(minute=0, second=0, microsecond=0)
        first = WeatherObservation.objects.create(
            station=station, temperature='20.00', recorded_at=hour_start,
        )
        non_interval_reading = WeatherObservation.objects.create(
            station=station, temperature='21.00', recorded_at=hour_start + timedelta(minutes=29),
        )
        second_interval = WeatherObservation.objects.create(
            station=station, temperature='22.00', recorded_at=hour_start + timedelta(minutes=30),
        )

        chart_observations = DNMGStationSyncService.get_chart_observations(
            [first, non_interval_reading, second_interval], 30,
        )

        self.assertEqual(len(chart_observations), 2)
        self.assertEqual(chart_observations[0][1], first)
        self.assertEqual(chart_observations[1][1], second_interval)
        self.assertNotIn(non_interval_reading, [observation for _, observation in chart_observations])

    def test_chart_history_preserves_irregular_aws_api_timestamps(self):
        from .services import DNMGStationSyncService

        station = WeatherStation.objects.create(
            external_id=19995,
            name='Irregular AWS chart test station',
            code='IRREGULAR-AWS-19995',
            station_type=WeatherStation.StationType.AWS,
            municipality=Municipality.DILI,
            latitude='-8.553200',
            longitude='125.574700',
        )
        hour_start = now().replace(minute=0, second=0, microsecond=0)
        first = WeatherObservation.objects.create(
            station=station, temperature='20.00', recorded_at=hour_start,
        )
        irregular = WeatherObservation.objects.create(
            station=station, temperature='21.00', recorded_at=hour_start + timedelta(minutes=17),
        )
        second = WeatherObservation.objects.create(
            station=station, temperature='22.00', recorded_at=hour_start + timedelta(minutes=30),
        )

        chart_observations = DNMGStationSyncService.get_chart_observations(
            [first, irregular, second],
            30,
            include_irregular=True,
        )

        self.assertEqual([observation for _, observation in chart_observations], [first, irregular, second])
        self.assertEqual(chart_observations[1][0].minute, 17)

    def test_dnmg_sync_service(self):
        from .services import DNMGStationSyncService

        def store_test_observation(station, force=False):
            return WeatherObservation.objects.create(
                station=station,
                temperature='25.00',
                recorded_at=now(),
                condition_text='Test synchronization',
            )

        # Unit tests must not depend on the availability or DNS configuration
        # of the external station API.
        with patch.object(
            DNMGStationSyncService,
            'fetch_and_store_observation',
            side_effect=store_test_observation,
        ):
            results = DNMGStationSyncService.sync_all_stations(force=True)
        self.assertEqual(len(results), 15)
        self.assertEqual(WeatherStation.objects.count(), 15)

        # Verify Tide Gauge station external ID 15401
        dili_tg = WeatherStation.objects.get(external_id=15401)
        self.assertEqual(dili_tg.station_type, WeatherStation.StationType.TIDE_GAUGE)
        self.assertIsNotNone(dili_tg.observations.first())

    def test_live_station_geojson_api_reads_stored_data_without_synchronizing(self):
        from .services import DNMGStationSyncService

        station = WeatherStation.objects.create(
            external_id=19996,
            name='Map API database-only test station',
            code='MAP-API-19996',
            municipality=Municipality.DILI,
            latitude='-8.553200',
            longitude='125.574700',
        )
        WeatherObservation.objects.create(
            station=station,
            temperature=Decimal('27.50'),
            recorded_at=now() - timedelta(minutes=1),
        )
        url = reverse('weather:api_live_stations')
        with patch.object(DNMGStationSyncService, 'sync_all_stations') as sync_all_stations:
            response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["type"], "FeatureCollection")
        self.assertEqual(len(data["features"]), 1)
        self.assertEqual(data["features"][0]["properties"]["name"], station.name)
        sync_all_stations.assert_not_called()

    def test_interactive_map_view(self):
        url = reverse('weather:interactive_map')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'weather/interactive_map.html')
        self.assertEqual(response.context['map_mode'], 'observations')
        self.assertContains(response, 'id="live_filter_pill"')
        self.assertContains(response, 'id="live_station_search"')
        self.assertNotContains(response, 'id="forecast_control_overlay"')

    def test_interactive_map_only_shows_currently_valid_warnings(self):
        current_time = now()
        EarlyWarning.objects.create(
            title='Current warning', severity=EarlyWarning.Severity.WARNING,
            region='Dili', description='Current', valid_from=current_time - timedelta(hours=1),
            valid_to=current_time + timedelta(hours=1), is_active=True,
        )
        EarlyWarning.objects.create(
            title='Expired warning', severity=EarlyWarning.Severity.WARNING,
            region='Dili', description='Expired', valid_from=current_time - timedelta(days=2),
            valid_to=current_time - timedelta(hours=1), is_active=True,
        )
        response = self.client.get(reverse('weather:interactive_map'))
        warnings = list(response.context['active_warnings'])
        self.assertEqual([warning.title for warning in warnings], ['Current warning'])

    def test_forecast_map_view_is_separate_from_live_observations(self):
        response = self.client.get(reverse('weather:forecast_map'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'weather/interactive_map.html')
        self.assertEqual(response.context['map_mode'], 'forecast')
        self.assertContains(response, 'id="forecast_control_overlay"')
        self.assertNotContains(response, 'id="live_filter_pill"')
        self.assertNotContains(response, 'id="live_station_search"')


class WeatherSearchAndFilterTestCase(TestCase):
    def setUp(self):
        self.meteorologist = User.objects.create_user(
            username="met_tester",
            password="password123",
            role=User.Role.METEOROLOGIST
        )
        self.editor = User.objects.create_user(
            username="editor_tester",
            password="password123",
            role=User.Role.EDITOR
        )
        self.hr_officer = User.objects.create_user(
            username="hr_tester",
            password="password123",
            role=User.Role.HR_OFFICER
        )
        self.station1 = WeatherStation.objects.create(
            name="Dili Station",
            code="DILI-01",
            municipality=Municipality.DILI,
            latitude="-8.55",
            longitude="125.57",
            station_type=WeatherStation.StationType.AWS,
            status=WeatherStation.Status.ACTIVE
        )
        self.station2 = WeatherStation.objects.create(
            name="Baucau Station",
            code="BAU-01",
            municipality=Municipality.BAUCAU,
            latitude="-8.47",
            longitude="126.45",
            station_type=WeatherStation.StationType.TIDE_GAUGE,
            status=WeatherStation.Status.MAINTENANCE
        )
        self.obs1 = WeatherObservation.objects.create(
            station=self.station1,
            temperature=31.0,
            condition_text="Sunny Day",
            recorded_at=now(),
            recorded_by=self.meteorologist
        )
        self.obs2 = WeatherObservation.objects.create(
            station=self.station2,
            temperature=24.5,
            condition_text="Heavy Rain",
            recorded_at=now(),
            recorded_by=self.meteorologist
        )

    def test_observation_station_filter(self):
        self.client.force_login(self.meteorologist)
        url = reverse('weather:observation_list') + f"?station={self.station1.id}"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        observations = response.context['observations']
        self.assertIn(self.obs1, observations)
        self.assertNotIn(self.obs2, observations)

    def test_observation_keyword_search(self):
        self.client.force_login(self.meteorologist)
        url = reverse('weather:observation_list') + "?q=Sunny"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        observations = response.context['observations']
        self.assertIn(self.obs1, observations)
        self.assertNotIn(self.obs2, observations)

    def test_user_rbac_properties(self):
        # Meteorologist
        self.assertTrue(self.meteorologist.can_access_technical_weather)
        self.assertTrue(self.meteorologist.can_access_early_warnings)
        self.assertFalse(self.meteorologist.can_access_cms)
        self.assertFalse(self.meteorologist.can_access_user_management)
        self.assertFalse(self.meteorologist.can_access_audit_logs)

        # Editor
        self.assertTrue(self.editor.can_access_cms)
        self.assertFalse(self.editor.can_access_technical_weather)
        self.assertFalse(self.editor.can_access_early_warnings)

        # HR Officer
        self.assertFalse(self.hr_officer.can_access_user_management)
        self.assertFalse(self.hr_officer.can_access_cms)
        self.assertFalse(self.hr_officer.can_access_technical_weather)
