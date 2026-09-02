from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _


class PortalPermission(models.Model):
    """One assignable capability, identified by a stable ``module.action`` code."""
    code = models.CharField(max_length=100, unique=True, verbose_name=_('Permission Code'))
    module = models.CharField(max_length=50, verbose_name=_('Module'))
    name = models.CharField(max_length=150, verbose_name=_('Permission Name'))
    description = models.TextField(blank=True, verbose_name=_('Description'))
    is_system = models.BooleanField(default=False, verbose_name=_('System Permission'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['module', 'code']
        verbose_name = _('Portal Permission')
        verbose_name_plural = _('Portal Permissions')

    def __str__(self):
        return f'{self.code} — {self.name}'


class Role(models.Model):
    """A custom role whose permissions are applied directly to assigned users."""
    class AuthorityLevel(models.IntegerChoices):
        STANDARD = 0, _('Standard')
        STAFF = 1, _('Staff')
        ADMIN = 2, _('Administrator')
        SUPER_ADMIN = 3, _('Super Administrator')

    name = models.CharField(max_length=100, unique=True, verbose_name=_('Role Name'))
    description = models.TextField(blank=True, verbose_name=_('Description'))
    is_active = models.BooleanField(default=True, verbose_name=_('Active'))
    authority_level = models.PositiveSmallIntegerField(
        choices=AuthorityLevel.choices, default=AuthorityLevel.STANDARD,
        verbose_name=_('Authority Level'),
        help_text=_('Controls which accounts and roles this role may manage. The name alone never grants authority.'),
    )
    permissions = models.ManyToManyField(PortalPermission, blank=True, related_name='roles', verbose_name=_('Permissions'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = _('Role')
        verbose_name_plural = _('Roles')

    def __str__(self):
        return self.name

class User(AbstractUser):
    class Role(models.TextChoices):
        SUPER_ADMIN = 'SUPER_ADMIN', _('Super Administrator')
        ADMIN = 'ADMIN', _('Administrator')
        HR_OFFICER = 'HR_OFFICER', _('HR Officer')
        METEOROLOGIST = 'METEOROLOGIST', _('Meteorologist')
        CLIMATE_OFFICER = 'CLIMATE_OFFICER', _('Climate Officer')
        MARINE_OFFICER = 'MARINE_OFFICER', _('Marine Officer')
        SEISMIC_OFFICER = 'SEISMIC_OFFICER', _('Seismic Officer')
        EDITOR = 'EDITOR', _('Editor')
        RESEARCHER = 'RESEARCHER', _('Researcher')
        PUBLIC = 'PUBLIC', _('Public User')

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.PUBLIC,
        verbose_name=_('Role')
    )
    profile_picture = models.ImageField(
        upload_to='profiles/',
        blank=True,
        null=True,
        verbose_name=_('Profile Picture')
    )
    phone_number = models.CharField(
        max_length=20,
        blank=True,
        verbose_name=_('Phone Number')
    )
    access_role = models.ForeignKey(
        'users.Role',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users',
        verbose_name=_('Assigned Role'),
    )

    class Meta:
        verbose_name = _('User')
        verbose_name_plural = _('Users')
        constraints = [
            models.CheckConstraint(
                condition=models.Q(role__in=[
                    'SUPER_ADMIN', 'ADMIN', 'HR_OFFICER', 'METEOROLOGIST',
                    'CLIMATE_OFFICER', 'MARINE_OFFICER', 'SEISMIC_OFFICER',
                    'EDITOR', 'RESEARCHER', 'PUBLIC',
                ]),
                name='users_user_role_valid',
            ),
        ]

    def __str__(self):
        return f"{self.username} ({self.get_effective_role_display()})"

    def get_effective_role_display(self):
        return self.access_role.name if self.access_role_id else self.get_role_display()

    def has_portal_permission(self, code):
        """Return the effective permission; superusers always retain full access."""
        if self.is_superuser:
            return True
        if not self.is_active:
            return False
        if self.access_role_id:
            return self.access_role.is_active and self.access_role.permissions.filter(code=code).exists()

        # Preserve all existing deployments until each account is moved to a
        # custom role.  New custom-role users never use this fallback.
        legacy_permissions = self._legacy_permission_codes()
        return code in legacy_permissions

    def has_any_portal_permission(self, *codes):
        return any(self.has_portal_permission(code) for code in codes)

    def _legacy_permission_codes(self):
        from .permissions import PERMISSION_CATALOG
        all_codes = {f'{module}.{action}' for module, (_label, actions) in PERMISSION_CATALOG.items() for action, _name in actions}
        if self.role in [self.Role.SUPER_ADMIN, self.Role.ADMIN]:
            return all_codes - {code for code in all_codes if code.startswith(('roles.', 'permissions.'))}
        codes = {'dashboard.view'}
        if self.role == self.Role.EDITOR:
            codes.update(code for code in all_codes if code.startswith(('news.', 'bulletins.', 'careers.')))
        if self.role in [self.Role.METEOROLOGIST, self.Role.CLIMATE_OFFICER, self.Role.MARINE_OFFICER, self.Role.SEISMIC_OFFICER]:
            codes.update(code for code in all_codes if code.startswith(('weather_stations.', 'observations.', 'forecasts.', 'early_warnings.')))
        if self.role in [self.Role.METEOROLOGIST, self.Role.CLIMATE_OFFICER]:
            codes.update(code for code in all_codes if code.startswith('forecasts.'))
        if self.role == self.Role.HR_OFFICER:
            codes.update(code for code in all_codes if code.startswith(('hr_dashboard.', 'staff.', 'departments.', 'staff_levels.', 'contracts.', 'downloads.')))
        return codes

    @property
    def is_internal_staff(self):
        """Check if user belongs to internal staff (i.e. not a Public user)."""
        return self.role != self.Role.PUBLIC or self.access_role_id is not None or self.is_superuser

    @property
    def can_access_cms(self):
        """Check if user has access to CMS management (News & Bulletins)."""
        return self.has_any_portal_permission('news.view', 'bulletins.view', 'careers.view')

    @property
    def can_access_technical_weather(self):
        """Check if user has access to weather stations, observations, and forecasts."""
        return self.has_any_portal_permission('weather_stations.view', 'observations.view', 'forecasts.view')

    @property
    def can_access_early_warnings(self):
        """Check if user has access to early warning management."""
        return self.has_portal_permission('early_warnings.view')

    @property
    def can_access_user_management(self):
        """Check if user has access to user accounts management."""
        return self.has_portal_permission('users.view')

    @property
    def can_access_audit_logs(self):
        """Check if user has full access to system audit logs."""
        return self.has_portal_permission('audit_trails.view')

    @property
    def can_manage_hr(self):
        """Check if user has full HR management access (Employee CRUD, Departments, Contracts, Reports)."""
        return self.has_any_portal_permission('staff.create', 'departments.create', 'staff_levels.create', 'contracts.edit', 'downloads.upload')

    @property
    def can_view_hr(self):
        """Check if user can view the HR module (SUPER_ADMIN, ADMIN, HR_OFFICER only)."""
        return self.has_any_portal_permission('hr_dashboard.view', 'staff.view', 'departments.view', 'downloads.view')




class AuditLog(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
        verbose_name=_('User')
    )
    action = models.CharField(max_length=255, verbose_name=_('Action'))
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name=_('IP Address'))
    user_agent = models.TextField(null=True, blank=True, verbose_name=_('User Agent'))
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name=_('Timestamp'))
    details = models.JSONField(default=dict, blank=True, verbose_name=_('Details'))

    class Meta:
        ordering = ['-timestamp']
        verbose_name = _('Audit Log')
        verbose_name_plural = _('Audit Logs')
        indexes = [
            models.Index(fields=['user', '-timestamp'], name='users_audit_user_time_idx'),
            models.Index(fields=['-timestamp'], name='users_audit_timestamp_idx'),
        ]

    def __str__(self):
        username = self.user.username if self.user else "Anonymous"
        return f"{username} - {self.action} @ {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
