from users.permissions import PortalPermissionRequiredMixin


class CMSManagementAccessMixin(PortalPermissionRequiredMixin):
    """CMS views set ``permission_code`` for their exact server-side action."""
    permission_code = 'news.view'
