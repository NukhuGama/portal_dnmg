"""Presentation helpers for safely formatted CMS content."""

from django import template
from django.utils.safestring import mark_safe

from cms.sanitizers import sanitize_job_html

register = template.Library()


@register.filter
def job_rich_text(value):
    """Sanitize on render as defense in depth for legacy job records."""
    return mark_safe(sanitize_job_html(value))
