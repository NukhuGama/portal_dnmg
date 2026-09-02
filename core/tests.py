from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from hr.models import Department
from weather.models import EarlyWarning


class ProfilePagesTests(TestCase):
    def test_home_includes_the_asynchronous_seismic_summary(self):
        response = self.client.get(reverse('core:home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-seismic-home-summary')
        self.assertContains(response, '/seismic/api/home-summary/')

    def test_home_keeps_all_active_warnings_above_the_seismic_summary(self):
        now = timezone.now()
        warning_titles = ('Heavy rain warning', 'Coastal wind warning')
        for title in warning_titles:
            EarlyWarning.objects.create(
                title=title, severity=EarlyWarning.Severity.WARNING, region='Dili',
                description='Follow official safety guidance.', valid_from=now, valid_to=now + timedelta(hours=4),
            )

        response = self.client.get(reverse('core:home'))
        page = response.content.decode()

        self.assertContains(response, 'Priority information')
        self.assertLess(page.index(warning_titles[0]), page.index('data-seismic-home-summary'))
        self.assertLess(page.index(warning_titles[1]), page.index('data-seismic-home-summary'))

    def test_home_only_displays_currently_public_warnings(self):
        now = timezone.now()
        EarlyWarning.objects.create(title='Live warning', severity=EarlyWarning.Severity.WARNING, region='Dili', description='Current', valid_from=now - timedelta(hours=1), valid_to=now + timedelta(hours=1))
        EarlyWarning.objects.create(title='Expired warning', severity=EarlyWarning.Severity.WARNING, region='Dili', description='Old', valid_from=now - timedelta(days=2), valid_to=now - timedelta(hours=1))

        response = self.client.get(reverse('core:home'))

        self.assertContains(response, 'Live warning')
        self.assertNotContains(response, 'Expired warning')

    def test_about_page_displays_mission_content(self):
        response = self.client.get(reverse('core:about_dnmg'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Our Mission')
        self.assertContains(response, '24/7 Meteorological Monitoring')

    def test_compact_header_keeps_login_and_language_controls_available(self):
        response = self.client.get(reverse('core:about_dnmg'))

        self.assertContains(response, 'navbar-expand-xxl')
        self.assertContains(response, 'langDropdownMobile')
        self.assertContains(response, 'public-login-button')

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
