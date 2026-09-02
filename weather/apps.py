from django.apps import AppConfig


class WeatherConfig(AppConfig):
    # Match the primary-key type already defined by the existing Weather migrations.
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'weather'
