from types import SimpleNamespace
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import translation
from django.utils.timezone import now

from cms.forms import JobOpeningAttachmentForm, NewsArticleForm, OfficialBulletinForm
from core.service_catalog import SERVICE_LANDINGS
from hr.models import Department
from hr.forms import DownloadableFileForm, EmployeeDocumentForm, EmployeeForm
from core.widgets import AdminFileInput
from users.forms import UserCreateForm, UserEditForm, UserProfileForm
from weather.forms import OfficialForecastAttachmentForm, OfficialForecastForm, OfficialForecastImageForm
from weather.models import AwosMetarReport, EarlyWarning, Municipality, WeatherObservation, WeatherStation


class ProfilePagesTests(TestCase):
    def test_public_service_landing_pages_are_available_without_operational_data(self):
        pages = (
            ('core:climate', 'Climate'),
            ('core:air_quality', 'Air Quality'),
            ('core:marine', 'Marine'),
            ('core:aviation', 'Aviation'),
            ('core:data_maps', 'Data & Maps'),
            ('core:dss', 'Decision Support Systems'),
            ('weather:public_overview', 'Weather'),
            ('weather:public_warning_list', 'Early Warnings'),
        )

        for url_name, expected_heading in pages:
            with self.subTest(url_name=url_name):
                response = self.client.get(reverse(url_name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, expected_heading)

    def test_public_weather_overview_uses_an_honest_empty_state(self):
        response = self.client.get(reverse('weather:public_overview'))

        self.assertContains(response, 'No current station observation is available.')

    def test_aviation_page_lists_supported_airports(self):
        response = self.client.get(reverse('core:aviation'))

        self.assertEqual(response.status_code, 200)
        for airport in SERVICE_LANDINGS['aviation']['airports']:
            with self.subTest(airport_slug=airport['slug']):
                self.assertContains(response, str(airport['name']))
                self.assertContains(response, str(airport['official_name']))

        self.assertContains(response, 'id="airport-dili"')
        self.assertContains(response, 'id="airport-suai"')
        self.assertContains(response, 'id="airport-oecusse"')
        self.assertContains(
            response,
            reverse('core:aviation_airport_detail', args=['dili']),
        )

    def test_aviation_page_shows_stored_dili_awos_observation_and_metar(self):
        station = WeatherStation.objects.create(
            name='Dili Airport AWOS',
            code='WPDL',
            municipality=Municipality.DILI,
            latitude='-8.546600',
            longitude='125.525000',
            station_type=WeatherStation.StationType.AWOS,
        )
        WeatherObservation.objects.create(
            station=station,
            temperature='29.10',
            humidity='68.00',
            dew_point_c='22.50',
            pressure_hpa='1012.80',
            wind_speed_kmh='18.52',
            wind_direction='NE',
            wind_gust_kmh='30.99',
            visibility_m='9999.00',
            runway_visual_range_m='4000.00',
            recorded_at=now(),
        )
        AwosMetarReport.objects.create(
            station=station,
            reported_at=now(),
            raw_report='METAR WPDL 290600Z AUTO 06011KT 9999 29/23 Q1013=',
        )

        response = self.client.get(reverse('core:aviation_airport_detail', args=['dili']))

        self.assertContains(response, 'Presidente Nicolau Lobato Airport (WPDL)')
        self.assertContains(response, 'AWOS observations and METAR')
        self.assertContains(response, 'data-awos-field="wind_speed">10.0')
        self.assertContains(response, 'data-awos-field="wind_gust">16.7')
        self.assertContains(response, 'METAR WPDL 290600Z AUTO 06011KT 9999 29/23 Q1013=')
        self.assertContains(response, 'data-awos-field="metar_local_display"')
        self.assertContains(response, 'Timor-Leste')
        self.assertContains(response, 'airport-awos-dashboard')
        self.assertContains(response, 'data-awos-auto-refresh')
        self.assertContains(response, 'Aviation wind')
        self.assertNotContains(response, 'Runway 08')
        self.assertNotContains(response, 'Runway 26')
        self.assertContains(
            response,
            f'{reverse("weather:interactive_map")}?station_type=AWOS',
        )

        live_response = self.client.get(
            reverse('core:dili_awos_live_observation'),
        )
        self.assertEqual(live_response.status_code, 200)
        self.assertEqual(live_response['Cache-Control'], 'no-store')
        live_payload = live_response.json()
        self.assertTrue(live_payload['available'])
        self.assertEqual(live_payload['observation']['temperature'], '29.1')
        self.assertEqual(live_payload['observation']['wind_speed'], '10.0')
        self.assertTrue(live_payload['metar']['local_display'].endswith('UTC+9'))
        self.assertEqual(
            live_payload['metar']['raw_report'],
            'METAR WPDL 290600Z AUTO 06011KT 9999 29/23 Q1013=',
        )

    def test_active_alerts_are_prioritized_and_link_to_public_details(self):
        current_time = now()
        warning = EarlyWarning.objects.create(
            title='Heavy rainfall advisory',
            severity=EarlyWarning.Severity.WARNING,
            region='Dili and Ermera',
            description='Avoid flood-prone areas.',
            valid_from=current_time - timedelta(hours=1),
            valid_to=current_time + timedelta(hours=2),
        )

        response = self.client.get(reverse('core:home'))
        detail_response = self.client.get(
            reverse('weather:public_warning_detail', args=[warning.pk])
        )

        self.assertContains(response, 'Active early warnings')
        self.assertContains(response, reverse('weather:public_warning_detail', args=[warning.pk]))
        self.assertContains(response, 'severity-badge--warning')
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, 'warning-hero--warning')
        self.assertContains(detail_response, warning.get_severity_display())

    def test_public_header_includes_complete_service_menu_structure(self):
        response = self.client.get(reverse('core:about_dnmg'))

        for label in (
            'Weather', 'Climate', 'Air Quality', 'Marine', 'Aviation', 'Seismic',
            'Data & Maps', 'News & Notices', 'DSS Systems', 'About DNMG',
            'Climate Monitoring', 'Current Air Quality', 'Marine Forecast',
            'Live marine observations', 'Tide gauge stations', 'Marine buoy stations',
            'Live airport weather', 'Earthquake Explorer', 'Data/API Information',
            'Official Bulletins', 'Contact Information',
        ):
            with self.subTest(label=label):
                self.assertContains(response, label)

        self.assertContains(response, 'aviation-nav-menu')
        self.assertContains(response, 'structured-nav-menu')
        self.assertContains(response, 'News, announcements & media')
        self.assertContains(response, 'Structure & departments')
        self.assertContains(response, 'Downloads & publications')
        self.assertContains(response, 'Warnings & bulletins')
        self.assertContains(response, 'METAR')
        self.assertContains(response, 'TAF')
        for station_type in ('MARINE', 'TIDE_GAUGE', 'BUOY'):
            self.assertContains(
                response,
                f'{reverse("weather:interactive_map")}?station_type={station_type}',
            )

    def test_new_navigation_labels_are_translated_in_tetun_and_portuguese(self):
        expected_labels = {
            'tet': (
                'Tempu', 'Aviasaun', 'Estasaun Sukat Nivel Tasi (Tide Gauge)',
                'Estasaun Boia Marítima(Marine Buoy)', 'Aeroportu sira', 'Sistema DSS', 'Login',
            ),
            'pt': (
                'Meteorologia', 'Aviação', 'Estações maregráficas',
                'Estações de boias marítimas', 'Aeroportos', 'Sistemas DSS', 'Login',
            ),
        }

        for language, labels in expected_labels.items():
            with self.subTest(language=language), translation.override(language):
                response = self.client.get(reverse('core:about_dnmg'))
                for label in labels:
                    self.assertContains(response, label)

    def test_service_navigation_anchors_are_stable_across_languages(self):
        service_anchors = {
            'core:climate': ((), 'climate-monitoring'),
            'core:air_quality': ((), 'current-air-quality'),
            'core:marine': ((), 'marine-forecast'),
            'core:aviation_airport_detail': (('dili',), 'airport-observations'),
            'core:data_maps': ((), 'dataapi-information'),
        }

        for language in ('en', 'tet', 'pt'):
            with translation.override(language):
                for url_name, (args, anchor) in service_anchors.items():
                    with self.subTest(language=language, url_name=url_name):
                        response = self.client.get(reverse(url_name, args=args))
                        self.assertContains(response, f'id="{anchor}"')

    def test_about_page_displays_mission_content(self):
        response = self.client.get(reverse('core:about_dnmg'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Our Mission')
        self.assertContains(response, '24/7 Meteorological Monitoring')
        self.assertContains(response, 'public-nav-link')
        self.assertContains(response, 'public-nav-menu')

    def test_compact_header_keeps_login_and_language_controls_available(self):
        response = self.client.get(reverse('core:about_dnmg'))

        self.assertContains(response, 'navbar-expand-xxl')
        self.assertContains(response, 'langDropdownMobile')
        self.assertContains(response, 'public-login-button')

    def test_authenticated_header_highlights_the_account_menu(self):
        user = get_user_model().objects.create_user(
            username='header-profile-user-with-a-long-name',
            password='test-password',
        )
        self.client.force_login(user)

        response = self.client.get(reverse('core:about_dnmg'))

        self.assertContains(response, reverse('users:profile'))
        self.assertContains(response, 'public-profile-button')
        self.assertContains(response, 'public-account-button__name')
        self.assertContains(response, 'aria-label="Account menu"')
        self.assertContains(response, 'My Profile')

    def test_admin_shell_includes_shared_mobile_navigation_hooks(self):
        user = get_user_model().objects.create_user(
            username='admin-shell-user',
            password='test-password',
        )
        self.client.force_login(user)

        response = self.client.get(reverse('users:profile'))

        self.assertContains(response, 'admin-sidebar-backdrop')
        self.assertContains(response, 'admin-main-viewport')
        self.assertContains(response, 'admin-content')

    def test_admin_file_widget_shows_the_current_filename(self):
        uploaded_file = SimpleNamespace(
            name='official_forecasts/images/national-advisory-map.png',
            url='/media/official_forecasts/images/national-advisory-map.png',
        )

        rendered = AdminFileInput(attrs={'class': 'form-control'}).render('image', uploaded_file)

        self.assertIn('Current file', rendered)
        self.assertIn('national-advisory-map.png', rendered)
        self.assertNotIn('official_forecasts/images/national-advisory-map.png</a>', rendered)

    def test_all_standard_editable_upload_fields_use_the_shared_widget(self):
        upload_fields = (
            (OfficialForecastForm(), 'image'),
            (OfficialForecastForm(), 'attachment'),
            (OfficialForecastImageForm(), 'image'),
            (OfficialForecastAttachmentForm(), 'file'),
            (NewsArticleForm(), 'featured_image'),
            (OfficialBulletinForm(), 'pdf_file'),
            (JobOpeningAttachmentForm(), 'file'),
            (EmployeeForm(), 'photo'),
            (EmployeeDocumentForm(), 'file'),
            (DownloadableFileForm(), 'file'),
            (UserProfileForm(), 'profile_picture'),
            (UserCreateForm(), 'profile_picture'),
            (UserEditForm(instance=get_user_model()()), 'profile_picture'),
        )

        for form, field_name in upload_fields:
            with self.subTest(form=form.__class__.__name__, field=field_name):
                self.assertIsInstance(form.fields[field_name].widget, AdminFileInput)

    def test_structure_uses_active_hr_departments(self):
        department = Department.objects.create(name='Climate Services', code='CLIMATE')

        response = self.client.get(reverse('core:dnmg_structure'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Director')
        self.assertContains(response, department.name)

        department.name = 'Updated Climate Services'
        department.save()
        response = self.client.get(reverse('core:dnmg_structure'))
        self.assertContains(response, 'Updated Climate Services')

        department.delete()
        response = self.client.get(reverse('core:dnmg_structure'))
        self.assertNotContains(response, 'Updated Climate Services')
