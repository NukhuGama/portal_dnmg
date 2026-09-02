"""Reusable database queries for public weather products."""

from django.utils import timezone

from .models import EarlyWarning


def current_public_warnings(at=None):
    """Return active warnings whose public validity window includes ``at``."""
    reference_time = at or timezone.now()
    return EarlyWarning.objects.filter(
        is_active=True,
        valid_from__lte=reference_time,
        valid_to__gte=reference_time,
    ).order_by('-valid_from')
