"""Centralised portal permission definitions and server-side checks."""
from collections import OrderedDict

from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.utils.translation import gettext_lazy as _


ROLE_LEVELS = {
    'PUBLIC': 0,
    'HR_OFFICER': 1, 'METEOROLOGIST': 1, 'CLIMATE_OFFICER': 1,
    'MARINE_OFFICER': 1, 'SEISMIC_OFFICER': 1, 'EDITOR': 1, 'RESEARCHER': 1,
    'ADMIN': 2,
    'SUPER_ADMIN': 3,
}


# A new module only needs an entry here and a data migration to be available to
# the role manager.  Codes intentionally use ``module.action`` consistently.
PERMISSION_CATALOG = OrderedDict([
    ('dashboard', ('Dashboard', [('view', 'View dashboard')])),
    ('news', ('News', [('view', 'View News'), ('create', 'Add News'), ('edit', 'Edit News'), ('delete', 'Delete News'), ('publish', 'Publish News'), ('download', 'Download News'), ('approve', 'Approve News'), ('archive', 'Archive News')])),
    ('bulletins', ('Official Bulletins', [('view', 'View Bulletins'), ('create', 'Add Bulletins'), ('edit', 'Edit Bulletins'), ('delete', 'Delete Bulletins'), ('publish', 'Publish Bulletins'), ('download', 'Download Bulletins'), ('approve', 'Approve Bulletins'), ('disseminate', 'Disseminate Bulletins'), ('archive', 'Archive Bulletins')])),
    ('careers', ('Careers / Jobs', [('view', 'View Jobs'), ('create', 'Add Jobs'), ('edit', 'Edit Jobs'), ('delete', 'Delete Jobs'), ('publish', 'Publish Jobs'), ('close', 'Close Jobs'), ('download', 'Download Jobs')])),
    ('weather_stations', ('Weather Stations', [('view', 'View Stations'), ('create', 'Add Stations'), ('edit', 'Edit Stations'), ('delete', 'Delete Stations'), ('download', 'Download Station Data'), ('history', 'View Station History'), ('data_gap_alert', 'Receive Data Gap Alerts'), ('drift_alert', 'Receive Drift Alerts'), ('manage_configuration', 'Manage Station Configuration')])),
    ('observations', ('Observations', [('view', 'View Observations'), ('create', 'Add Observations'), ('edit', 'Edit Observations'), ('delete', 'Delete Observations'), ('download', 'Download Observations'), ('export', 'Export Observations'), ('approve', 'Approve Observations')])),
    ('forecasts', ('Forecasts', [('view', 'View Forecasts'), ('create', 'Add Forecasts'), ('edit', 'Edit Forecasts'), ('delete', 'Delete Forecasts'), ('publish', 'Publish Forecasts'), ('approve', 'Approve Forecasts'), ('download', 'Download Forecasts'), ('disseminate', 'Disseminate Forecasts')])),
    ('early_warnings', ('Early Warnings / Alerts', [('view', 'View Early Warnings'), ('create', 'Create Early Warnings'), ('edit', 'Edit Early Warnings'), ('publish', 'Publish / Activate Alerts'), ('archive', 'Archive / Deactivate Alerts')])),
    ('users', ('User Management', [('view', 'View Users'), ('create', 'Add User'), ('edit', 'Edit User'), ('delete', 'Delete User'), ('activate', 'Activate User'), ('deactivate', 'Deactivate User'), ('reset_password', 'Reset User Password'), ('assign_role', 'Assign Role'), ('change_role', 'Change User Role'), ('detail', 'View User Details')])),
    ('roles', ('Role Management', [('view', 'View Roles'), ('create', 'Add Role'), ('edit', 'Edit Role'), ('delete', 'Delete Role'), ('activate', 'Activate Role'), ('deactivate', 'Deactivate Role'), ('assign_permissions', 'Assign Permissions'), ('assign_users', 'Assign Roles to Users')])),
    ('permissions', ('Permission Management', [('view', 'View Permissions'), ('create', 'Add Permission'), ('edit', 'Edit Permission'), ('delete', 'Delete Permission')])),
    ('audit_trails', ('Audit Trails', [('view', 'View Audit Trails'), ('search', 'Search Audit Trails'), ('filter', 'Filter Audit Trails'), ('export', 'Export Audit Trails'), ('download', 'Download Audit Trails')])),
    ('hr_dashboard', ('HR Dashboard', [('view', 'View Dashboard'), ('reports', 'View Reports'), ('statistics', 'View Statistics'), ('export_reports', 'Export Reports'), ('download_reports', 'Download Reports')])),
    ('staff', ('Staff Directory', [('view', 'View Staff'), ('create', 'Add Staff'), ('edit', 'Edit Staff'), ('delete', 'Delete Staff'), ('detail', 'View Staff Details'), ('export', 'Export Staff'), ('download', 'Download Staff')])),
    ('departments', ('Departments', [('view', 'View Departments'), ('create', 'Add Department'), ('edit', 'Edit Department'), ('delete', 'Delete Department'), ('assign_staff', 'Assign Staff')])),
    ('staff_levels', ('Staff Levels', [('view', 'View Staff Levels'), ('create', 'Add Staff Level'), ('edit', 'Edit Staff Level'), ('delete', 'Delete Staff Level')])),
    ('contracts', ('Contract Monitoring', [('view', 'View Contracts'), ('create', 'Add Contract'), ('edit', 'Edit Contract'), ('delete', 'Delete Contract'), ('detail', 'View Contract Details'), ('monitor', 'Monitor Contracts'), ('track_expiration', 'Track Contract Expiration'), ('alerts', 'Receive Contract Alerts'), ('download', 'Download Contracts'), ('export', 'Export Contracts')])),
    ('fr_reports', ('FR Reports', [('view', 'View FR Reports'), ('create', 'Add FR Reports'), ('edit', 'Edit FR Reports'), ('delete', 'Delete FR Reports'), ('approve', 'Approve FR Reports'), ('download', 'Download FR Reports'), ('export', 'Export FR Reports')])),
    ('downloads', ('Downloads Hub', [('view', 'View Downloads'), ('upload', 'Upload Downloads'), ('edit', 'Edit Downloads'), ('delete', 'Delete Downloads'), ('download', 'Download Files'), ('approve', 'Approve Downloads'), ('manage_categories', 'Manage Download Categories')])),
])


def permission_rows():
    """Return deterministic model-ready rows for the built-in catalogue."""
    return [
        {'code': f'{module}.{action}', 'module': module, 'name': name, 'is_system': True}
        for module, (_module_name, actions) in PERMISSION_CATALOG.items()
        for action, name in actions
    ]


def module_label(module):
    return PERMISSION_CATALOG.get(module, (module.replace('_', ' ').title(), ()))[0]


class PortalPermissionRequiredMixin(LoginRequiredMixin):
    """Reusable server-side guard for normal and HTMX requests alike."""
    permission_code = None
    any_permission_codes = ()
    raise_exception = True

    def has_required_permission(self):
        user = self.request.user
        if self.permission_code:
            return user.has_portal_permission(self.permission_code)
        if self.any_permission_codes:
            return user.has_any_portal_permission(*self.any_permission_codes)
        return False

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path(), self.get_login_url(), self.get_redirect_field_name())
        if not self.has_required_permission():
            raise PermissionDenied(_("You do not have permission to perform this action."))
        return super().dispatch(request, *args, **kwargs)


class UserManagementAccessMixin(PortalPermissionRequiredMixin):
    """Shared guard for user-management views; subclasses set their action."""
    permission_code = 'users.view'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and kwargs.get('pk'):
            from .models import User
            target = User.objects.select_related('access_role').filter(pk=kwargs['pk']).first()
            if target and not can_manage_user(request.user, target):
                raise PermissionDenied(_("You cannot manage a user at a higher authority level."))
        return super().dispatch(request, *args, **kwargs)


def can_manage_role(user, role):
    """Authority boundary for viewing or managing a role."""
    return user.is_superuser or role.authority_level <= effective_authority_level(user)


def can_assign_role(user, role):
    """Permission boundary for assigning a role to another account."""
    if not can_manage_role(user, role):
        return False
    return user.is_superuser or all(
        user.has_portal_permission(permission.code)
        for permission in role.permissions.all()
    )


def manageable_role_ids(user, roles):
    return [role.pk for role in roles if can_manage_role(user, role)]


def effective_authority_level(user):
    """Return the single authority level used by every hierarchy decision."""
    if user.is_superuser:
        return 100
    role_level = ROLE_LEVELS.get(user.role, 0)
    custom_level = 0
    if user.access_role_id and user.access_role.is_active:
        custom_level = user.access_role.authority_level
    return max(role_level, custom_level)


def can_manage_user(manager, target):
    if not can_view_user(manager, target):
        return False
    if target.is_superuser and not manager.is_superuser:
        return False
    return True


def can_view_user(manager, target):
    """Whether the account belongs in the manager's visible user scope."""
    if target.is_superuser:
        # Django superusers are outside the delegated portal hierarchy.  Only
        # another Django superuser may view or manage those accounts.
        return manager.is_superuser
    return effective_authority_level(target) <= effective_authority_level(manager)


def log_security_event(request, action, details):
    """Use the existing central audit trail for RBAC changes."""
    from .models import AuditLog
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR', '')
    AuditLog.objects.create(
        user=request.user if request.user.is_authenticated else None,
        action=action,
        ip_address=forwarded_for.split(',')[0].strip() if forwarded_for else request.META.get('REMOTE_ADDR'),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
        details=details,
    )
