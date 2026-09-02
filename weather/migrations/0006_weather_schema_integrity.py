from django.db import migrations, models
from django.db.models import F, Q


def verify_existing_values(apps, schema_editor):
    """Stop before adding constraints if legacy data would violate them."""
    WeatherStation = apps.get_model('weather', 'WeatherStation')
    WeatherForecast = apps.get_model('weather', 'WeatherForecast')
    EarlyWarning = apps.get_model('weather', 'EarlyWarning')

    invalid = {
        'weather station municipalities': WeatherStation.objects.exclude(municipality__in=[
            'AILEU', 'AINARO', 'BAUCAU', 'BOBONARO', 'COVA_LIMA', 'DILI', 'ERMERA',
            'LAUTEM', 'LIQUICA', 'MANATUTO', 'MANUFAHI', 'OECUSSE', 'VIQUEQUE',
        ]),
        'weather station types': WeatherStation.objects.exclude(station_type__in=[
            'AWS', 'AWOS', 'SYNOPTIC', 'TIDE_GAUGE', 'BUOY', 'AGROMET', 'HYDROMET', 'SEISMIC',
        ]),
        'weather station statuses': WeatherStation.objects.exclude(
            status__in=['ACTIVE', 'MAINTENANCE', 'INACTIVE']
        ),
        'weather station coordinates': WeatherStation.objects.filter(
            Q(latitude__lt=-90) | Q(latitude__gt=90) |
            Q(longitude__lt=-180) | Q(longitude__gt=180)
        ),
        'forecast temperature ranges': WeatherForecast.objects.filter(temp_min__gt=F('temp_max')),
        'forecast municipalities': WeatherForecast.objects.exclude(municipality__in=[
            'AILEU', 'AINARO', 'BAUCAU', 'BOBONARO', 'COVA_LIMA', 'DILI', 'ERMERA',
            'LAUTEM', 'LIQUICA', 'MANATUTO', 'MANUFAHI', 'OECUSSE', 'VIQUEQUE',
        ]),
        'forecast rain probabilities': WeatherForecast.objects.filter(
            Q(rain_probability__lt=0) | Q(rain_probability__gt=100)
        ),
        'early-warning severities': EarlyWarning.objects.exclude(
            severity__in=['info', 'warning', 'danger']
        ),
        'early-warning validity ranges': EarlyWarning.objects.filter(valid_to__lte=F('valid_from')),
    }
    failures = [
        f"{label}: {list(queryset.values_list('pk', flat=True)[:10])}"
        for label, queryset in invalid.items()
        if queryset.exists()
    ]
    if failures:
        raise RuntimeError(
            'Cannot apply weather schema integrity constraints because existing '
            'rows are invalid. Correct these records, then rerun migrate: ' + '; '.join(failures)
        )


class Migration(migrations.Migration):

    dependencies = [
        ('weather', '0005_alter_weatherobservation_sea_surface_temp_and_more'),
    ]

    operations = [
        migrations.RunPython(verify_existing_values, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='weatherstation',
            constraint=models.CheckConstraint(
                condition=Q(municipality__in=[
                    'AILEU', 'AINARO', 'BAUCAU', 'BOBONARO', 'COVA_LIMA', 'DILI', 'ERMERA',
                    'LAUTEM', 'LIQUICA', 'MANATUTO', 'MANUFAHI', 'OECUSSE', 'VIQUEQUE',
                ]),
                name='weather_station_municipality_valid',
            ),
        ),
        migrations.AddConstraint(
            model_name='weatherstation',
            constraint=models.CheckConstraint(
                condition=Q(station_type__in=[
                    'AWS', 'AWOS', 'SYNOPTIC', 'TIDE_GAUGE', 'BUOY', 'AGROMET',
                    'HYDROMET', 'SEISMIC',
                ]),
                name='weather_station_type_valid',
            ),
        ),
        migrations.AddConstraint(
            model_name='weatherstation',
            constraint=models.CheckConstraint(
                condition=Q(status__in=['ACTIVE', 'MAINTENANCE', 'INACTIVE']),
                name='weather_station_status_valid',
            ),
        ),
        migrations.AddConstraint(
            model_name='weatherstation',
            constraint=models.CheckConstraint(
                condition=Q(latitude__gte=-90) & Q(latitude__lte=90),
                name='weather_station_latitude_range',
            ),
        ),
        migrations.AddConstraint(
            model_name='weatherstation',
            constraint=models.CheckConstraint(
                condition=Q(longitude__gte=-180) & Q(longitude__lte=180),
                name='weather_station_longitude_range',
            ),
        ),
        migrations.AddIndex(
            model_name='weatherobservation',
            index=models.Index(fields=['station', '-recorded_at'], name='weather_obs_station_time_idx'),
        ),
        migrations.AddConstraint(
            model_name='weatherforecast',
            constraint=models.CheckConstraint(
                condition=Q(municipality__in=[
                    'AILEU', 'AINARO', 'BAUCAU', 'BOBONARO', 'COVA_LIMA', 'DILI', 'ERMERA',
                    'LAUTEM', 'LIQUICA', 'MANATUTO', 'MANUFAHI', 'OECUSSE', 'VIQUEQUE',
                ]),
                name='weather_forecast_municipality_valid',
            ),
        ),
        migrations.AddConstraint(
            model_name='weatherforecast',
            constraint=models.CheckConstraint(
                condition=Q(temp_min__lte=F('temp_max')),
                name='weather_forecast_temperature_range',
            ),
        ),
        migrations.AddConstraint(
            model_name='weatherforecast',
            constraint=models.CheckConstraint(
                condition=Q(rain_probability__gte=0) & Q(rain_probability__lte=100),
                name='weather_forecast_rain_probability_range',
            ),
        ),
        migrations.AddConstraint(
            model_name='earlywarning',
            constraint=models.CheckConstraint(
                condition=Q(severity__in=['info', 'warning', 'danger']),
                name='weather_warning_severity_valid',
            ),
        ),
        migrations.AddConstraint(
            model_name='earlywarning',
            constraint=models.CheckConstraint(
                condition=Q(valid_to__gt=F('valid_from')),
                name='weather_warning_validity_range',
            ),
        ),
        migrations.AddIndex(
            model_name='earlywarning',
            index=models.Index(fields=['is_active', '-valid_from'], name='weather_warning_active_idx'),
        ),
    ]
