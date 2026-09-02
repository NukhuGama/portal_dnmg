from users.permissions import PortalPermissionRequiredMixin


class HRManagementRequiredMixin(PortalPermissionRequiredMixin):
    """Compatibility name for HR mutations; subclasses set a permission code."""
    permission_code = 'staff.edit'


class HRViewRequiredMixin(PortalPermissionRequiredMixin):
    """Compatibility name for HR reads; subclasses set a permission code."""
    permission_code = 'hr_dashboard.view'
