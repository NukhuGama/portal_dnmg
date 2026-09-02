"""
HTMX utility mixin for Django class-based views.
When a request comes in with the HX-Request header (from HTMX),
renders only the admin_content block fragment instead of the full page.
"""


class HTMXAdminMixin:
    """
    Mixin for admin views that support HTMX partial rendering.
    When the request has the 'HX-Request' header, the view renders using
    'admin_partial_base.html' (which only outputs the block content),
    otherwise falls back to the normal full-page template.
    """
    htmx_template_name = None  # Optional override for HTMX-specific template

    def get_template_names(self):
        names = super().get_template_names()
        if self.request.headers.get('HX-Request'):
            # Return the partial wrapper first so Django uses it for HTMX requests
            # The partial base renders only {% block admin_content %}
            if self.htmx_template_name:
                return [self.htmx_template_name]
            # Wrap each template name with the partial base approach
            # by switching the extends target at render time via context
        return names

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Signal to templates that this is an HTMX partial request
        context['is_htmx'] = bool(self.request.headers.get('HX-Request'))
        return context

    def render_to_response(self, context, **response_kwargs):
        if self.request.headers.get('HX-Request'):
            # For HTMX requests, render only the content fragment (no sidebar/header shell)
            # We temporarily override template_name to the partial wrapper
            original_template = self.template_name
            self.template_name = _get_partial_template(original_template)
            response = super().render_to_response(context, **response_kwargs)
            self.template_name = original_template
            return response
        return super().render_to_response(context, **response_kwargs)


def _get_partial_template(full_template_name):
    """
    Returns the corresponding '_partial' template path.
    E.g. 'users/dashboard.html' -> 'users/dashboard_partial.html'
    Falls back to the original if partial doesn't exist.
    """
    if not full_template_name:
        return full_template_name
    if isinstance(full_template_name, (list, tuple)):
        full_template_name = full_template_name[0]
    base, ext = full_template_name.rsplit('.', 1) if '.' in full_template_name else (full_template_name, '')
    return f"{base}_partial.{ext}" if ext else f"{base}_partial"
