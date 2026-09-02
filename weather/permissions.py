from users.permissions import PortalPermissionRequiredMixin


class TechnicalStaffRequiredMixin(PortalPermissionRequiredMixin):
    """Weather views declare the exact permission they require."""
    permission_code = 'weather_stations.view'


class EarlyWarningViewRequiredMixin(PortalPermissionRequiredMixin):
    permission_code = 'early_warnings.view'


class EarlyWarningCreateRequiredMixin(PortalPermissionRequiredMixin):
    permission_code = 'early_warnings.create'


class EarlyWarningEditRequiredMixin(PortalPermissionRequiredMixin):
    permission_code = 'early_warnings.edit'
