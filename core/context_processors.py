from weather.queries import current_public_warnings


def htmx(request):
    """
    Context processor to support HTMX partial page swaps cleanly across all templates.
    When request.htmx is True, admin_base resolves to 'htmx_admin_base.html' (content fragment only).
    Otherwise, admin_base resolves to 'admin_base.html' (full layout shell).
    """
    is_htmx = getattr(request, 'htmx', False)
    return {
        'admin_base': 'htmx_admin_base.html' if is_htmx else 'admin_base.html',
        'public_base': 'htmx_public_base.html' if is_htmx else 'base.html',
        'is_htmx': is_htmx,
    }


def active_site_alerts(request):
    """Expose current DNMG alerts to the shared public layout.

    The validity rule lives in ``weather.queries`` so the global banner,
    warning list, warning details, and observation map stay consistent.
    """
    return {'site_alerts': current_public_warnings()}
