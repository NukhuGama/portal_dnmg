"""Shared form widgets for Portal DNMG administration screens."""

from pathlib import Path

from django.forms.widgets import ClearableFileInput


class AdminFileInput(ClearableFileInput):
    """Show the existing upload by filename while allowing a safe replacement."""

    template_name = 'widgets/admin_file_input.html'

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        widget = context['widget']
        widget['display_name'] = ''
        widget['current_url'] = ''
        if value:
            try:
                widget['display_name'] = Path(value.name).name
                widget['current_url'] = value.url
            except (AttributeError, ValueError):
                # A missing legacy file should not prevent the edit form loading.
                pass
        return context
