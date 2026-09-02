from decimal import Decimal, ROUND_HALF_UP

from django.db import migrations


KNOTS_TO_KMH = Decimal("1.852")
PREVIOUS_MS_TO_KMH = Decimal("3.6")
TWO_DECIMAL_PLACES = Decimal("0.01")


def correct_awos_wind_units(apps, schema_editor):
    """Repair WPDL automatic records written before AWOS knots were identified."""
    WeatherStation = apps.get_model("weather", "WeatherStation")
    WeatherObservation = apps.get_model("weather", "WeatherObservation")
    station_ids = WeatherStation.objects.filter(
        code="WPDL",
        station_type="AWOS",
    ).values_list("id", flat=True)
    conversion_factor = KNOTS_TO_KMH / PREVIOUS_MS_TO_KMH

    observations = WeatherObservation.objects.filter(
        station_id__in=station_ids,
        recorded_by__isnull=True,
    ).iterator()
    for observation in observations:
        changed_fields = []
        for field_name in ("wind_speed_kmh", "wind_gust_kmh"):
            value = getattr(observation, field_name)
            if value is not None:
                setattr(
                    observation,
                    field_name,
                    (value * conversion_factor).quantize(
                        TWO_DECIMAL_PLACES,
                        rounding=ROUND_HALF_UP,
                    ),
                )
                changed_fields.append(field_name)
        if changed_fields:
            observation.save(update_fields=changed_fields)


class Migration(migrations.Migration):
    dependencies = [
        ("weather", "0013_weatherobservation_dew_point_c_and_more"),
    ]

    operations = [
        migrations.RunPython(correct_awos_wind_units, migrations.RunPython.noop),
    ]
