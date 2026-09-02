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
