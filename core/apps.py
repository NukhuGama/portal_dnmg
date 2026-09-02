from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = 'core'

    def ready(self):
        # Register deployment checks for durable user-uploaded media.
        from . import checks  # noqa: F401
