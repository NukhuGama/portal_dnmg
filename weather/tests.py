import json
from datetime import timedelta, timezone as datetime_timezone
from decimal import Decimal
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo

from django.test import TestCase, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils.timezone import localtime, now
from users.models import PortalPermission, Role, User
from .forms import OfficialForecastForm
from .models import (
    EarlyWarning, Municipality, OfficialForecast, OfficialForecastImage, WeatherForecast,
    AwosMetarReport, WeatherObservation, WeatherStation,
)

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


class AwosDiliSyncServiceTestCase(TestCase):
    def active_values(self, observed_at):
        source_time = observed_at.astimezone(datetime_timezone.utc).replace(tzinfo=None)

        def value(current_value, group_name, variable_name):
            return {
                'GroupName': group_name,
                'VariableName': variable_name,
                'UpdateDate': source_time,
                'CurrentValue': current_value,
                'CurrentQuality': 0,
                'CurrentASCII': '',
            }

        return {
            ('1Min', 'AT10Ma'): value(29.286, '1Min', 'AT10Ma'),
            ('1Min', 'RH10Ma'): value(68.1132, '1Min', 'RH10Ma'),
            ('1Min', 'DP10Ma'): value(22.7891, '1Min', 'DP10Ma'),
            ('1Min', 'QNH10Ma'): value(1012.87, '1Min', 'QNH10Ma'),
            ('10Sec', 'WS10Ma_A'): value(10, '10Sec', 'WS10Ma_A'),
            ('10Sec', 'WD10Ma_A'): value(51, '10Sec', 'WD10Ma_A'),
            ('10Sec', 'WS10Mg_A'): value(16.7333, '10Sec', 'WS10Mg_A'),
            ('1Min', 'Vis10Ma_A'): value(11749.6, '1Min', 'Vis10Ma_A'),
            ('1Min', 'RVR10Ma_A'): value(4000, '1Min', 'RVR10Ma_A'),
            ('Metar', '_Metar'): {
                **value(None, 'Metar', '_Metar'),
                'CurrentASCII': 'METAR WPDL 290600Z AUTO 06011KT 9999 29/23 Q1013=',
            },
        }

    @override_settings(
        AWOS_DILI_DATABASE_URL='mariadb://awos.example.test:3306/metlog',
        AWOS_DILI_USER='awos_reader',
        AWOS_DILI_PASSWORD='test-password',
        AWOS_DILI_OBSERVATION_RETENTION_HOURS=48,
        AWOS_DILI_METAR_RETENTION_DAYS=30,
    )
    def test_sync_stores_a_minute_snapshot_and_raw_metar(self):
        from .services import AwosDiliSyncService

        observed_at = now().replace(second=42, microsecond=0)
        with patch.object(
            AwosDiliSyncService,
            'fetch_active_values',
            return_value=self.active_values(observed_at),
        ):
            result = AwosDiliSyncService.sync()

        self.assertEqual(result['status'], 'synced')
        station = WeatherStation.objects.get(code='WPDL')
        self.assertEqual(station.station_type, WeatherStation.StationType.AWOS)
        observation = WeatherObservation.objects.get(station=station)
        self.assertEqual(observation.recorded_at.second, 0)
        self.assertEqual(observation.temperature, Decimal('29.29'))
        self.assertEqual(observation.dew_point_c, Decimal('22.79'))
        self.assertEqual(observation.pressure_hpa, Decimal('1012.87'))
        self.assertEqual(observation.wind_speed_kmh, Decimal('18.52'))
        self.assertEqual(observation.wind_gust_kmh, Decimal('30.99'))
        self.assertEqual(observation.wind_direction, 'NE')
        self.assertEqual(observation.visibility_m, Decimal('11749.60'))
        self.assertEqual(observation.runway_visual_range_m, Decimal('4000.00'))
        report = AwosMetarReport.objects.get(station=station)
        self.assertTrue(report.raw_report.startswith('METAR WPDL '))

    @override_settings(
        AWOS_DILI_DATABASE_URL='mariadb://awos.example.test:3306/metlog',
        AWOS_DILI_USER='awos_reader',
        AWOS_DILI_PASSWORD='test-password',
        AWOS_DILI_OBSERVATION_RETENTION_HOURS=48,
        AWOS_DILI_METAR_RETENTION_DAYS=30,
    )
    def test_sync_removes_only_expired_automatic_awos_records(self):
        from .services import AwosDiliSyncService

        station = AwosDiliSyncService.get_station()
        old_time = now() - timedelta(days=31)
        WeatherObservation.objects.create(station=station, recorded_at=old_time)
        AwosMetarReport.objects.create(
            station=station,
            reported_at=old_time,
            raw_report='METAR WPDL 010000Z AUTO 00000KT CAVOK 25/20 Q1010=',
        )
        with patch.object(
            AwosDiliSyncService,
            'fetch_active_values',
            return_value=self.active_values(now()),
        ):
            result = AwosDiliSyncService.sync()

        self.assertEqual(result['observations_deleted'], 1)
        self.assertEqual(result['metar_reports_deleted'], 1)
        self.assertEqual(WeatherObservation.objects.filter(station=station).count(), 1)
        self.assertEqual(AwosMetarReport.objects.filter(station=station).count(), 1)


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


class OfficialForecastTestCase(TestCase):
    def setUp(self):
        self.meteorologist = User.objects.create_user(
            username='official_forecast_meteorologist',
            password='password123',
            role=User.Role.METEOROLOGIST,
        )
        self.draft = OfficialForecast.objects.create(
            title='Draft national forecast',
            forecast_period=OfficialForecast.ForecastPeriod.ONE_DAY,
            valid_from=now().date(),
            valid_to=now().date(),
            coverage='Timor-Leste',
            summary='Internal draft forecast.',
            status=OfficialForecast.Status.DRAFT,
            created_by=self.meteorologist,
        )
        self.published = OfficialForecast.objects.create(
            title='Published national forecast',
            forecast_period=OfficialForecast.ForecastPeriod.THREE_DAY,
            valid_from=now().date(),
            valid_to=(now() + timedelta(days=2)).date(),
            coverage='Timor-Leste',
            summary='Published public forecast.',
            status=OfficialForecast.Status.PUBLISHED,
            created_by=self.meteorologist,
            published_by=self.meteorologist,
            published_at=now(),
        )

    def test_public_list_only_shows_published_forecasts(self):
        response = self.client.get(reverse('weather:public_official_forecast_list'))

        self.assertContains(response, self.published.title)
        self.assertNotContains(response, self.draft.title)

    def test_public_detail_hides_draft_forecasts(self):
        response = self.client.get(reverse('weather:public_official_forecast_detail', args=[self.draft.pk]))

        self.assertEqual(response.status_code, 404)

    def test_meteorologist_can_create_and_publish_official_forecast(self):
        self.client.force_login(self.meteorologist)
        response = self.client.post(reverse('weather:official_forecast_create'), {
            'title': 'Seven-day operational forecast',
            'forecast_period': OfficialForecast.ForecastPeriod.SEVEN_DAY,
            'valid_from': now().date(),
            'valid_to': (now() + timedelta(days=6)).date(),
            'coverage': 'Timor-Leste',
            'summary': '<p><i class="bi bi-cloud-sun"></i> Official seven-day summary.</p>',
            'notes': 'Prepare for locally heavy rainfall.',
            'status': OfficialForecast.Status.PUBLISHED,
            'images-TOTAL_FORMS': '0',
            'images-INITIAL_FORMS': '0',
            'images-MIN_NUM_FORMS': '0',
            'images-MAX_NUM_FORMS': '1000',
            'attachments-TOTAL_FORMS': '0',
            'attachments-INITIAL_FORMS': '0',
            'attachments-MIN_NUM_FORMS': '0',
            'attachments-MAX_NUM_FORMS': '1000',
        })

        forecast = OfficialForecast.objects.get(title='Seven-day operational forecast')
        self.assertRedirects(response, reverse('weather:official_forecast_list'))
        self.assertEqual(forecast.status, OfficialForecast.Status.PUBLISHED)
        self.assertEqual(forecast.created_by, self.meteorologist)
        self.assertEqual(forecast.published_by, self.meteorologist)
        self.assertIsNotNone(forecast.published_at)
        self.assertIn('<i class="bi bi-cloud-sun"></i>', forecast.summary)

    def test_official_forecast_edit_form_uses_the_responsive_upload_grid(self):
        self.client.force_login(self.meteorologist)

        response = self.client.get(
            reverse('weather:official_forecast_update', args=[self.draft.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'admin-upload-row')
        self.assertContains(response, 'images_form_list')
        self.assertContains(response, 'attachments_form_list')
        self.assertContains(response, 'data-editor-icon="water"')
        self.assertContains(response, 'data-editor-icon="chat-left-text"')
        self.assertContains(response, 'data-editor-emoji="🌊"')
        self.assertContains(response, 'data-rich-editor-target="#id_summary"')

    def test_rich_forecast_content_keeps_safe_formatting_and_removes_scripts(self):
        form = OfficialForecastForm(data={
            'title': 'Formatted forecast',
            'forecast_period': OfficialForecast.ForecastPeriod.ONE_DAY,
            'valid_from': now().date(),
            'valid_to': now().date(),
            'coverage': 'Timor-Leste',
            'summary': '<div>First paragraph</div><div><span style="font-weight: 700">Heavy rain</span></div><h2>General Conditions</h2><ul><li>Heavy rain</li></ul><script>alert(1)</script>',
            'notes': 'Internal drafting note.',
            'status': OfficialForecast.Status.DRAFT,
        })

        self.assertTrue(form.is_valid())
        self.assertIn('<p>First paragraph</p><p><strong>Heavy rain</strong></p>', form.cleaned_data['summary'])
        self.assertIn('<h2>General Conditions</h2>', form.cleaned_data['summary'])
        self.assertIn('<ul><li>Heavy rain</li></ul>', form.cleaned_data['summary'])
        self.assertNotIn('<script>', form.cleaned_data['summary'])

    def test_rich_forecast_content_keeps_bootstrap_weather_icons(self):
        form = OfficialForecastForm(data={
            'title': 'Icon forecast',
            'forecast_period': OfficialForecast.ForecastPeriod.ONE_DAY,
            'valid_from': now().date(),
            'valid_to': now().date(),
            'coverage': 'Timor-Leste',
            'summary': (
                '<p><i class="bi bi-cloud-sun" aria-hidden="true"></i> Partly cloudy '
                '<i class="bi bi-cloud-rain" onclick="alert(1)"></i> Rain possible '
                '<i class="bi bi-cloud-sun text-danger"></i></p>'
            ),
            'notes': '',
            'status': OfficialForecast.Status.DRAFT,
        })

        self.assertTrue(form.is_valid())
        summary = form.cleaned_data['summary']
        self.assertIn('<i class="bi bi-cloud-sun"></i>', summary)
        self.assertIn('<i class="bi bi-cloud-rain"></i>', summary)
        self.assertNotIn('onclick', summary)
        self.assertNotIn('text-danger', summary)

    def test_icon_before_a_forecast_heading_is_saved_on_the_same_line(self):
        form = OfficialForecastForm(data={
            'title': 'Forecast section heading',
            'forecast_period': OfficialForecast.ForecastPeriod.ONE_DAY,
            'valid_from': now().date(),
            'valid_to': now().date(),
            'coverage': 'Timor-Leste',
            'summary': '<i class="bi bi-cloud-sun"></i><h2>Kondisaun Jerál</h2>',
            'notes': '',
            'status': OfficialForecast.Status.DRAFT,
        })

        self.assertTrue(form.is_valid())
        self.assertEqual(
            form.cleaned_data['summary'],
            '<h2><i class="bi bi-cloud-sun"></i> Kondisaun Jerál</h2>',
        )

    def test_new_tab_forecast_links_always_use_safe_rel_attributes(self):
        form = OfficialForecastForm(data={
            'title': 'Safe forecast link',
            'forecast_period': OfficialForecast.ForecastPeriod.ONE_DAY,
            'valid_from': now().date(),
            'valid_to': now().date(),
            'coverage': 'Timor-Leste',
            'summary': '<p><a href="https://example.com" target="_blank" rel="opener">Read more</a></p>',
            'notes': '',
            'status': OfficialForecast.Status.DRAFT,
        })

        self.assertTrue(form.is_valid())
        self.assertIn(
            '<a href="https://example.com" target="_blank" rel="noopener noreferrer">Read more</a>',
            form.cleaned_data['summary'],
        )
        self.assertNotIn('rel="opener"', form.cleaned_data['summary'])

    @override_settings(MAX_UPLOAD_SIZE=1)
    def test_official_forecast_rejects_an_oversized_attachment(self):
        form = OfficialForecastForm(
            data={
                'title': 'Oversized attachment forecast',
                'forecast_period': OfficialForecast.ForecastPeriod.ONE_DAY,
                'valid_from': now().date(),
                'valid_to': now().date(),
                'coverage': 'Timor-Leste',
                'summary': 'A short forecast summary.',
                'notes': '',
                'status': OfficialForecast.Status.DRAFT,
            },
            files={'attachment': SimpleUploadedFile('advisory.txt', b'12')},
        )

        self.assertFalse(form.is_valid())
        self.assertIn('attachment', form.errors)

    def test_gallery_image_is_used_when_a_forecast_has_no_cover_image(self):
        with TemporaryDirectory() as media_root, self.settings(MEDIA_ROOT=media_root):
            gallery_image = OfficialForecastImage.objects.create(
                forecast=self.published,
                image=SimpleUploadedFile(
                    'forecast-map.gif',
                    b'GIF87a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;',
                    content_type='image/gif',
                ),
                caption='Rainfall outlook',
                sort_order=1,
            )

            self.assertEqual(self.published.primary_image.name, gallery_image.image.name)

    def test_uploaded_forecast_images_are_saved_and_rendered_publicly(self):
        gif_bytes = (
            b'GIF87a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9'
            b'\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
        )

        with TemporaryDirectory() as media_root, self.settings(MEDIA_ROOT=media_root):
            self.client.force_login(self.meteorologist)
            response = self.client.post(
                reverse('weather:official_forecast_update', args=[self.published.pk]),
                {
                    'title': self.published.title,
                    'forecast_period': self.published.forecast_period,
                    'valid_from': self.published.valid_from,
                    'valid_to': self.published.valid_to,
                    'coverage': self.published.coverage,
                    'summary': self.published.summary,
                    'notes': self.published.notes,
                    'image': SimpleUploadedFile(
                        'public-cover.gif', gif_bytes, content_type='image/gif'
                    ),
                    'status': OfficialForecast.Status.PUBLISHED,
                    'images-TOTAL_FORMS': '1',
                    'images-INITIAL_FORMS': '0',
                    'images-MIN_NUM_FORMS': '0',
                    'images-MAX_NUM_FORMS': '1000',
                    'images-0-image': SimpleUploadedFile(
                        'public-gallery.gif', gif_bytes, content_type='image/gif'
                    ),
                    'images-0-caption': 'Public rainfall map',
                    'images-0-sort_order': '1',
                    'attachments-TOTAL_FORMS': '0',
                    'attachments-INITIAL_FORMS': '0',
                    'attachments-MIN_NUM_FORMS': '0',
                    'attachments-MAX_NUM_FORMS': '1000',
                },
            )

            self.assertRedirects(response, reverse('weather:official_forecast_list'))
            self.published.refresh_from_db()
            gallery_image = self.published.images.get()
            self.assertTrue(self.published.image.storage.exists(self.published.image.name))
            self.assertTrue(gallery_image.image.storage.exists(gallery_image.image.name))

            list_response = self.client.get(reverse('weather:public_official_forecast_list'))
            detail_response = self.client.get(
                reverse('weather:public_official_forecast_detail', args=[self.published.pk])
            )
            self.assertContains(list_response, self.published.image.url)
            self.assertContains(detail_response, self.published.image.url, count=3)
            self.assertContains(detail_response, gallery_image.image.url, count=2)


class Phase3SyncAndApiTestCase(TestCase):
    def test_home_uses_cached_forecast_without_calling_the_external_service(self):
        from django.core.cache import cache
        from weather.services import DNMG10DayForecastService

        cache.set('dnmg_10day_ECMWF-IFS_tp', {'Dili': []}, 300)
        with patch.object(DNMG10DayForecastService, 'fetch_forecast') as fetch_forecast:
            response = self.client.get(reverse('core:home'))
        self.assertEqual(response.status_code, 200)
        fetch_forecast.assert_not_called()

    def test_met_norway_municipality_forecast_is_cached_and_normalized(self):
        from django.core.cache.backends.locmem import LocMemCache
        from weather.services import METNorwayForecastService

        test_cache = LocMemCache('met-norway-forecast-test', {})
        payload = {
            'properties': {
                'timeseries': [{
                    'time': now().isoformat(),
                    'data': {
                        'instant': {
                            'details': {
                                'air_temperature': 28.0,
                                'relative_humidity': 70.0,
                                'wind_speed': 5.0,
                            },
                        },
                        'next_1_hours': {
                            'details': {'precipitation_amount': 1.2},
                        },
                    },
                }],
            },
        }
        response = MagicMock()
        response.read.return_value = json.dumps(payload).encode('utf-8')
        response.headers = {}
        response.__enter__.return_value = response

        with patch('weather.services.cache', test_cache), patch(
            'weather.services.urllib.request.urlopen', return_value=response,
        ) as urlopen:
            conditions = METNorwayForecastService.fetch_municipality_forecast()

            self.assertEqual(len(conditions), 14)
            self.assertEqual(conditions[0]['name'], 'Aileu')
            self.assertEqual(conditions[0]['humidity'], 70.0)
            self.assertEqual(conditions[0]['temperature'], 28.0)
            self.assertEqual(conditions[0]['rainfall'], 1.2)
            self.assertEqual(conditions[0]['wind_speed'], 18.0)
            self.assertEqual(urlopen.call_count, 14)
            request = urlopen.call_args.args[0]
            self.assertIn('DNMG Portal', request.get_header('User-agent'))
            METNorwayForecastService.fetch_municipality_forecast()
            self.assertEqual(urlopen.call_count, 14)

    def test_met_norway_forecast_displays_current_timor_leste_hour(self):
        from weather.services import METNorwayForecastService

        current_time = now().replace(second=0, microsecond=0)
        payload = {
            'properties': {
                'timeseries': [
                    {'time': (current_time - timedelta(hours=1)).isoformat()},
                    {'time': (current_time + timedelta(hours=1)).isoformat()},
                ],
            },
        }

        with patch('weather.services.now', return_value=current_time):
            condition = METNorwayForecastService._normalise_condition('Dili', payload)

        expected_local_hour = localtime(
            current_time,
            ZoneInfo('Asia/Dili'),
        ).replace(minute=0).strftime('%H:%M')
        self.assertEqual(condition['forecast_time'], expected_local_hour)

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
            'maximum_wind_gust_speed': [{'value': 6.25, 'start_time': '2026-08-07T23:10:00Z'}],
            'wind_direction': [{'value': 220.42, 'start_time': '2026-08-07T23:10:00Z'}],
        })

        self.assertEqual(float(observation.temperature), 25.97)
        self.assertEqual(observation.humidity, Decimal('53.19'))
        self.assertEqual(observation.wind_speed_kmh, Decimal('19.37'))
        self.assertEqual(observation.wind_gust_kmh, Decimal('22.50'))
        self.assertEqual(observation.wind_direction, 'SW')
        self.assertEqual(localtime(observation.recorded_at).strftime('%Y-%m-%d %H:%M %z'), '2026-08-08 08:10 +0900')

    def test_manual_station_coordinates_are_not_replaced_by_provider_sync(self):
        from .services import DNMGStationSyncService

        station = WeatherStation.objects.create(
            external_id=19980,
            name='Manual coordinate station',
            code='MANUAL-19980',
            municipality=Municipality.DILI,
            latitude='-8.550000',
            longitude='125.570000',
        )

        DNMGStationSyncService.update_station_coordinates(
            station, Decimal('-8.579800'), Decimal('125.362788')
        )
        station.refresh_from_db()

        self.assertEqual(station.coordinate_source, WeatherStation.CoordinateSource.MANUAL)
        self.assertEqual(station.latitude, Decimal('-8.550000'))
        self.assertEqual(station.longitude, Decimal('125.570000'))

    def test_provider_managed_station_coordinates_can_be_refreshed(self):
        from .services import DNMGStationSyncService

        station = WeatherStation.objects.create(
            external_id=19981,
            name='Provider coordinate station',
            code='PROVIDER-19981',
            municipality=Municipality.DILI,
            latitude='-8.550000',
            longitude='125.570000',
            coordinate_source=WeatherStation.CoordinateSource.PROVIDER,
        )

        DNMGStationSyncService.update_station_coordinates(
            station, Decimal('-8.579800'), Decimal('125.362788')
        )
        station.refresh_from_db()

        self.assertEqual(station.latitude, Decimal('-8.579800'))
        self.assertEqual(station.longitude, Decimal('125.362788'))

    def test_provider_initialized_stations_allow_coordinate_refreshes(self):
        from .services import DNMGStationSyncService, INITIAL_STATIONS_DATA

        with patch.object(DNMGStationSyncService, 'fetch_and_store_observation', return_value=None):
            DNMGStationSyncService._sync_all_stations()

        station = WeatherStation.objects.get(
            external_id=INITIAL_STATIONS_DATA[0]['external_id']
        )
        self.assertEqual(
            station.coordinate_source,
            WeatherStation.CoordinateSource.PROVIDER,
        )

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

    def test_current_wind_measurements_are_converted_from_ms_to_kmh(self):
        from .services import DNMGStationSyncService

        station = WeatherStation.objects.create(
            external_id=19988,
            name='Wind conversion test station',
            code='WIND-CONVERSION-19988',
            municipality=Municipality.DILI,
            latitude='-8.553200',
            longitude='125.574700',
        )
        recorded_at = now() - timedelta(minutes=1)
        time_series_payload = {
            'wind_speed': [{'value': '5.00', 'start_time': recorded_at.isoformat()}],
            'maximum_wind_gust_speed': [{'value': '6.00', 'start_time': recorded_at.isoformat()}],
        }
        current_payload = {
            'station': {'availability': {'latest': recorded_at.isoformat()}},
            'summary': {'daily': {
                'wind_speed': {'latest': {'value': '5.38'}},
                'maximum_wind_gust_speed': {'latest': {'value': '7.25'}},
            }},
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

        self.assertEqual(observation.wind_speed_kmh, Decimal('19.37'))
        self.assertEqual(observation.wind_gust_kmh, Decimal('26.10'))

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

    def test_station_snapshot_marks_data_older_than_five_hours_offline(self):
        from .services import DNMGStationSyncService

        station = WeatherStation.objects.create(
            external_id=19991,
            name='Stale status station',
            code='STALE-19991',
            municipality=Municipality.DILI,
            latitude='-8.553200',
            longitude='125.574700',
        )
        current_time = now()
        WeatherObservation.objects.create(
            station=station,
            temperature='24.00',
            recorded_at=current_time - timedelta(hours=5, minutes=1),
        )

        snapshot = DNMGStationSyncService.get_station_snapshot(station, current_time)

        self.assertFalse(snapshot['is_online'])

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
            'wind_speed': [
                {'value': '5.00', 'start_time': first_time.isoformat()},
                {'value': '5.38', 'start_time': latest_time.isoformat()},
            ],
            'maximum_wind_gust_speed': [
                {'value': '6.00', 'start_time': first_time.isoformat()},
                {'value': '7.25', 'start_time': latest_time.isoformat()},
            ],
        })

        stored = list(station.observations.order_by('recorded_at'))

        self.assertEqual(len(stored), 2)
        self.assertEqual(stored[0].temperature, Decimal('24.12'))
        self.assertEqual(stored[1].temperature, Decimal('25.34'))
        self.assertEqual(stored[1].humidity, Decimal('70.22'))
        self.assertEqual(stored[0].wind_speed_kmh, Decimal('18.00'))
        self.assertEqual(stored[1].wind_speed_kmh, Decimal('19.37'))
        self.assertEqual(stored[0].wind_gust_kmh, Decimal('21.60'))
        self.assertEqual(stored[1].wind_gust_kmh, Decimal('26.10'))

    def test_chart_history_uses_latest_observation_in_each_15_minute_bucket(self):
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
            [first, non_interval_reading, second_interval],
            15,
            hour_start + timedelta(minutes=30),
        )
        chart_observations_by_time = {
            timestamp: observation
            for timestamp, observation in chart_observations
            if observation is not None
        }

        self.assertEqual(len(chart_observations), 96)
        self.assertEqual(chart_observations_by_time[localtime(hour_start)], first)
        self.assertEqual(
            chart_observations_by_time[localtime(hour_start + timedelta(minutes=15))],
            non_interval_reading,
        )
        self.assertEqual(
            chart_observations_by_time[localtime(hour_start + timedelta(minutes=30))],
            second_interval,
        )

    def test_chart_history_keeps_empty_15_minute_buckets_as_gaps(self):
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
            15,
            hour_start + timedelta(minutes=45),
        )
        chart_observations_by_time = dict(chart_observations)

        self.assertEqual(
            chart_observations_by_time[localtime(hour_start + timedelta(minutes=15))],
            irregular,
        )
        self.assertEqual(
            chart_observations_by_time[localtime(hour_start + timedelta(minutes=30))],
            second,
        )
        self.assertIsNone(
            chart_observations_by_time[localtime(hour_start + timedelta(minutes=45))]
        )

    def test_raw_chart_history_keeps_every_irregular_aws_observation(self):
        from .services import DNMGStationSyncService

        station = WeatherStation.objects.create(
            external_id=19994,
            name='Raw AWS chart test station',
            code='RAW-AWS-19994',
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

        chart_observations = DNMGStationSyncService.get_raw_chart_observations(
            [first, irregular],
        )

        self.assertEqual(
            chart_observations,
            [
                (localtime(hour_start), first),
                (localtime(hour_start + timedelta(minutes=17)), irregular),
            ],
        )
        self.assertFalse(DNMGStationSyncService.uses_fifteen_minute_chart(station))
        self.assertIsNone(DNMGStationSyncService.chart_interval_minutes(station))
        station.external_id = 15404
        self.assertTrue(DNMGStationSyncService.uses_fifteen_minute_chart(station))
        self.assertEqual(DNMGStationSyncService.chart_interval_minutes(station), 15)
        station.external_id = 15403
        self.assertEqual(DNMGStationSyncService.chart_interval_minutes(station), 30)
        station.station_type = WeatherStation.StationType.TIDE_GAUGE
        station.external_id = 15401
        self.assertEqual(DNMGStationSyncService.chart_interval_minutes(station), 10)

    def test_dnmg_sync_service(self):
        from django.core.cache import cache
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
            cache.delete(DNMGStationSyncService.SYNC_LOCK_CACHE_KEY)
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

    def test_interactive_map_supports_bookmarkable_marine_station_filters(self):
        url = reverse('weather:interactive_map')

        for station_type in ('AWOS', 'MARINE', 'TIDE_GAUGE', 'BUOY'):
            with self.subTest(station_type=station_type):
                response = self.client.get(url, {'station_type': station_type})
                self.assertEqual(response.context['selected_station_type'], station_type)
                self.assertContains(response, f'var activeStationType = "{station_type}";')
                self.assertContains(response, f'data-type="{station_type}" aria-pressed="true"')

        invalid_response = self.client.get(url, {'station_type': 'INVALID'})
        self.assertEqual(invalid_response.context['selected_station_type'], 'ALL')

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
