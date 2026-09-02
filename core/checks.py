"""Django system checks for durable application storage."""

import os
from pathlib import Path

from django.conf import settings
from django.core.checks import Error, Tags, register


@register(Tags.files)
def check_media_root_writable(app_configs, **kwargs):
    """Report a clear configuration error before uploads fail at request time."""
    media_root = Path(settings.MEDIA_ROOT)
    hint = (
        "Create the mounted media directory and make it writable by the Django "
        "container user (UID/GID 1000)."
    )

    if not media_root.exists():
        return [Error(
            f"MEDIA_ROOT does not exist: {media_root}",
            hint=hint,
            id='core.E001',
        )]
    if not media_root.is_dir():
        return [Error(
            f"MEDIA_ROOT is not a directory: {media_root}",
            hint=hint,
            id='core.E002',
        )]
    if not os.access(media_root, os.W_OK | os.X_OK):
        return [Error(
            f"MEDIA_ROOT is not writable by the Django process: {media_root}",
            hint=hint,
            id='core.E003',
        )]
    return []
