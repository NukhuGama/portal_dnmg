import datetime
import tempfile
from django.test import TestCase, RequestFactory
from django.test.utils import override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import HttpResponse
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils.timezone import now
from django.contrib.messages.storage.fallback import FallbackStorage
from users.models import AuditLog, Role, PortalPermission
from users.middleware import AuditLogMiddleware, SessionTimeoutMiddleware

User = get_user_model()

class CustomUserTestCase(TestCase):
    def test_create_user_with_role(self):
        user = User.objects.create_user(
            username="teststaff",
            password="testpassword",
            role=User.Role.METEOROLOGIST
        )
        self.assertEqual(user.role, User.Role.METEOROLOGIST)
        self.assertTrue(user.is_internal_staff)

    def test_public_user_is_not_staff(self):
        user = User.objects.create_user(
            username="publicuser",
            password="testpassword",
            role=User.Role.PUBLIC
        )
        self.assertEqual(user.role, User.Role.PUBLIC)
        self.assertFalse(user.is_internal_staff)


class CustomAuthenticationTestCase(TestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(
            username="staff1",
            password="testpassword123",
            role=User.Role.METEOROLOGIST,
            first_name="Staff",
            email="staff@dnmg.gov.tl"
        )
        self.public_user = User.objects.create_user(
            username="public1",
            password="testpassword123",
            role=User.Role.PUBLIC,
            email="public@gmail.com"
        )

    def test_login_denied_for_public_users(self):
        # Post request to login with public user credentials
        response = self.client.post(reverse('users:login'), {
            'username': 'public1',
            'password': 'testpassword123'
        })
        self.assertEqual(response.status_code, 200) # Re-renders login on fail
        self.assertFalse('_auth_user_id' in self.client.session)

    def test_login_allowed_for_internal_staff(self):
        response = self.client.post(reverse('users:login'), {
            'username': 'staff1',
            'password': 'testpassword123'
        })
        # Successful login redirects to home
        self.assertEqual(response.status_code, 302)
        self.assertTrue('_auth_user_id' in self.client.session)

    def test_public_portal_shows_admin_return_link_only_to_internal_staff(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse('core:home'))
        self.assertContains(response, 'Admin Portal')
        self.assertContains(response, reverse('users:dashboard'))

        self.client.force_login(self.public_user)
        response = self.client.get(reverse('core:home'))
        self.assertNotContains(response, reverse('users:dashboard'))


class SessionTimeoutTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username="staff2",
            password="testpassword",
            role=User.Role.METEOROLOGIST
        )

    def test_middleware_does_not_timeout_within_limit(self):
        # Create request and session
        request = self.factory.get(reverse('users:profile'))
        request.user = self.user
        
        # Manually attach session
        session = self.client.session
        session['last_activity'] = now().isoformat()
        request.session = session
        
        # Run middleware
        middleware = SessionTimeoutMiddleware(get_response=lambda r: r)
        middleware(request)
        
        # User remains logged in
        self.assertTrue(request.user.is_authenticated)

    def test_middleware_times_out_after_limit(self):
        request = self.factory.get(reverse('users:profile'))
        request.user = self.user
        
        # Attach session with last activity more than 1800 seconds ago
        session = self.client.session
        past_time = now() - datetime.timedelta(seconds=1900)
        session['last_activity'] = past_time.isoformat()
        request.session = session
        
        # Add messages engine support
        messages = FallbackStorage(request)
        setattr(request, '_messages', messages)

        middleware = SessionTimeoutMiddleware(get_response=lambda r: r)
        response = middleware(request)
        
        # Middleware redirects to login url due to timeout
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.endswith(reverse('users:login')))


class AuditLogMiddlewareTestCase(TestCase):
    def test_logs_only_submitted_field_names_and_handles_unresolved_paths(self):
        user = User.objects.create_user(username='auditor', password='testpassword', role=User.Role.ADMIN)
        request = RequestFactory().post('/not-a-real-route/', {
            'employee_notes': 'Confidential employee detail',
            'password': 'must-not-be-stored',
        })
        request.user = user

        response = AuditLogMiddleware(lambda _request: HttpResponse(status=204))(request)

        self.assertEqual(response.status_code, 204)
        audit = AuditLog.objects.get(user=user)
        self.assertEqual(audit.details['view_name'], 'unresolved')
        self.assertIn('employee_notes', audit.details['submitted_fields'])
        self.assertNotIn('password', audit.details['submitted_fields'])
        self.assertNotIn('Confidential employee detail', str(audit.details))
        self.assertNotIn('must-not-be-stored', str(audit.details))


class UserManagementTestCase(TestCase):
    def setUp(self):
        self.super_admin = User.objects.create_superuser(
            username="superadmin",
            password="adminpassword123",
            role=User.Role.SUPER_ADMIN,
            email="superadmin@dnmg.gov.tl"
        )
        self.admin_user = User.objects.create_user(
            username="admin1",
            password="adminpassword123",
            role=User.Role.ADMIN,
            email="admin1@dnmg.gov.tl"
        )
        self.hr_officer = User.objects.create_user(
            username="hrofficer1",
            password="hrpassword123",
            role=User.Role.HR_OFFICER,
            email="hrofficer1@dnmg.gov.tl"
        )
        self.meteorologist = User.objects.create_user(
            username="met1",
            password="metpassword123",
            role=User.Role.METEOROLOGIST,
            email="met1@dnmg.gov.tl"
        )

    def test_user_list_page_access_controls(self):
        # 1. Super Admin access (Allowed)
        self.client.force_login(self.super_admin)
        response = self.client.get(reverse('users:user_list'))
        self.assertEqual(response.status_code, 200)

        # 2. Admin access (Allowed)
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('users:user_list'))
        self.assertEqual(response.status_code, 200)

        # 3. HR Officer access (Blocked: raises 403)
        self.client.force_login(self.hr_officer)
        response = self.client.get(reverse('users:user_list'))
        self.assertEqual(response.status_code, 403)

        # 4. Meteorologist access (Blocked: raises 403)
        self.client.force_login(self.meteorologist)
        response = self.client.get(reverse('users:user_list'))
        self.assertEqual(response.status_code, 403)

    def test_hr_officer_redirected_to_hr_dashboard(self):
        self.client.force_login(self.hr_officer)
        response = self.client.get(reverse('users:dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('hr:dashboard'), response.url)

    def test_admin_can_reset_staff_password(self):
        self.client.force_login(self.admin_user)
        response = self.client.post(
            reverse('users:user_reset_password', kwargs={'pk': self.meteorologist.pk}),
            {
                'password': 'newpassword789',
                'password_confirm': 'newpassword789'
            }
        )
        self.assertEqual(response.status_code, 302) # Redirects to user list
        
        # Check that the meteorologist can now log in with the new password
        self.client.logout()
        response = self.client.post(reverse('users:login'), {
            'username': 'met1',
            'password': 'newpassword789'
        })
        self.assertEqual(response.status_code, 302) # Redirects to dashboard

    def test_every_staff_user_can_change_their_own_password_from_profile(self):
        self.client.force_login(self.meteorologist)
        response = self.client.post(
            reverse('users:profile_password_change'),
            {
                'old_password': 'metpassword123',
                'new_password1': 'updated-password-456',
                'new_password2': 'updated-password-456',
            },
        )
        self.assertRedirects(response, reverse('users:profile'))
        self.meteorologist.refresh_from_db()
        self.assertTrue(self.meteorologist.check_password('updated-password-456'))

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_staff_user_can_upload_profile_picture(self):
        self.client.force_login(self.meteorologist)
        image = SimpleUploadedFile(
            'profile.png',
            (
                b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR'
                b'\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06'
                b'\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\x0d'
                b'IDAT\x08\xd7c\xf8\xcf\xc0\xf0\x1f\x00\x05\x00\x01\xff'
                b'\x89\x99=\x1d\x00\x00\x00\x00IEND\xaeB\x60\x82'
            ),
            content_type='image/png',
        )
        response = self.client.post(
            reverse('users:profile'),
            {
                'first_name': 'Meteorologist',
                'last_name': 'One',
                'email': 'met1@example.test',
                'phone_number': '',
                'profile_picture': image,
            },
        )

        self.assertRedirects(response, reverse('users:profile'))
        self.meteorologist.refresh_from_db()
        self.assertTrue(self.meteorologist.profile_picture.name.startswith('profiles/'))


class GranularRoleManagementTestCase(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username='rbac-superuser', password='password123', email='root@example.test',
        )
        self.role = Role.objects.create(name='News Reader', description='Can view news only.')
        self.news_view = PortalPermission.objects.get(code='news.view')
        self.news_create = PortalPermission.objects.get(code='news.create')
        self.role.permissions.add(self.news_view)
        self.user = User.objects.create_user(
            username='news-reader', password='password123', email='reader@example.test', access_role=self.role,
        )

    def test_custom_role_grants_only_its_selected_permissions(self):
        self.assertTrue(self.user.is_internal_staff)
        self.assertTrue(self.user.has_portal_permission('news.view'))
        self.assertFalse(self.user.has_portal_permission('news.create'))
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('cms:admin_news_list')).status_code, 200)
        self.assertEqual(self.client.get(reverse('cms:news_create')).status_code, 403)

    def test_inactive_role_immediately_removes_access(self):
        self.role.is_active = False
        self.role.save()
        self.user.refresh_from_db()
        self.assertFalse(self.user.has_portal_permission('news.view'))
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('cms:admin_news_list')).status_code, 403)

    def test_only_django_superuser_can_manage_roles(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('users:role_list')).status_code, 403)
        self.client.force_login(self.superuser)
        self.assertEqual(self.client.get(reverse('users:role_list')).status_code, 200)
        self.assertEqual(self.client.get(reverse('users:role_detail', kwargs={'pk': self.role.pk})).status_code, 200)
        response = self.client.post(reverse('users:role_create'), {
            'name': 'News Editor', 'description': 'Editor', 'is_active': 'on',
            'permissions': [self.news_view.pk, self.news_create.pk],
        })
        self.assertRedirects(response, reverse('users:role_list'))
        self.assertTrue(Role.objects.filter(name='News Editor', permissions=self.news_create).exists())
        self.assertTrue(AuditLog.objects.filter(action='ROLE_CREATED').exists())
