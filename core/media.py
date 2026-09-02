"""Small, storage-agnostic helpers for user-uploaded media."""

from urllib.parse import unquote, urlparse

from django.conf import settings
from django.core.files.storage import default_storage


def media_available(field_file):
    """Return whether a FieldFile still exists, without leaking storage errors."""
    try:
        return bool(field_file and field_file.name and field_file.storage.exists(field_file.name))
    except Exception:
        return False


def media_name_available(name):
    try:
        return bool(name and default_storage.exists(name))
    except Exception:
        return False


def media_url_available(url):
    """Check a local media URL, treating non-media URLs as available."""
    parsed_path = urlparse(url).path
    media_url = settings.MEDIA_URL
    if not parsed_path.startswith(media_url):
        return True
    return media_name_available(unquote(parsed_path[len(media_url):]))
