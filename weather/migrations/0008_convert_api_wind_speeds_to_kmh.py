from decimal import Decimal, ROUND_HALF_UP

from django.db import migrations


CONVERSION_FACTOR = Decimal("3.6")
TWO_DECIMAL_PLACES = Decimal("0.01")
MAX_WIND_SPEED_KMH = Decimal("9999.99")
UPDATE_BATCH_SIZE = 500


def convert_api_wind_speeds_to_kmh(apps, schema_editor):
    """Convert existing API-created observations from m/s to km/h once."""
    WeatherObservation = apps.get_model("weather", "WeatherObservation")

    # API synchronization creates observations without a recorded_by user.
    # Manual staff-entered observations already use the km/h form field and
    # must not be converted a second time.
    observations = WeatherObservation.objects.filter(
        recorded_by__isnull=True,
        wind_speed_kmh__isnull=False,
    ).iterator()

    updates = []
    for observation in observations:
        converted_wind_speed = (
            observation.wind_speed_kmh * CONVERSION_FACTOR
        ).quantize(TWO_DECIMAL_PLACES, rounding=ROUND_HALF_UP)
        # Discard malformed provider readings that cannot fit the telemetry field.
        observation.wind_speed_kmh = (
            converted_wind_speed
            if converted_wind_speed.copy_abs() <= MAX_WIND_SPEED_KMH
            else None
        )
        updates.append(observation)

        if len(updates) == UPDATE_BATCH_SIZE:
            WeatherObservation.objects.bulk_update(
                updates, ["wind_speed_kmh"], batch_size=UPDATE_BATCH_SIZE
            )
            updates.clear()

    if updates:
        WeatherObservation.objects.bulk_update(
            updates, ["wind_speed_kmh"], batch_size=UPDATE_BATCH_SIZE
        )


class Migration(migrations.Migration):

    dependencies = [
        ("weather", "0007_forecast_unique_constraint"),
    ]

    operations = [
        migrations.RunPython(convert_api_wind_speeds_to_kmh, migrations.RunPython.noop),
    ]
