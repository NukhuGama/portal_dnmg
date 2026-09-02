from decimal import Decimal, ROUND_HALF_UP

from django.db import migrations


CONVERSION_FACTOR = Decimal("3.6")
TWO_DECIMAL_PLACES = Decimal("0.01")


def convert_api_wind_gusts_to_kmh(apps, schema_editor):
    """Convert existing API-created wind-gust values from m/s to km/h once."""
    WeatherObservation = apps.get_model("weather", "WeatherObservation")

    # Manual staff entries already use the km/h form field. API-created entries
    # have no recorded_by user and are the only values converted here.
    observations = WeatherObservation.objects.filter(
        recorded_by__isnull=True,
        wind_gust_kmh__isnull=False,
    ).iterator()

    for observation in observations:
        observation.wind_gust_kmh = (
            observation.wind_gust_kmh * CONVERSION_FACTOR
        ).quantize(TWO_DECIMAL_PLACES, rounding=ROUND_HALF_UP)
        observation.save(update_fields=["wind_gust_kmh"])


class Migration(migrations.Migration):

    dependencies = [
        ("weather", "0008_convert_api_wind_speeds_to_kmh"),
    ]

    operations = [
        migrations.RunPython(convert_api_wind_gusts_to_kmh, migrations.RunPython.noop),
    ]
