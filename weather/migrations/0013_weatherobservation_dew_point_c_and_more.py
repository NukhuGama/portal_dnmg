from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('weather', '0012_weatherstation_coordinate_source'),
    ]

    operations = [
        migrations.AddField(
            model_name='weatherobservation',
            name='dew_point_c',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=5,
                null=True,
                verbose_name='Dew Point (°C)',
            ),
        ),
        migrations.AddField(
            model_name='weatherobservation',
            name='runway_visual_range_m',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=8,
                null=True,
                verbose_name='Runway Visual Range (m)',
            ),
        ),
        migrations.AddField(
            model_name='weatherobservation',
            name='visibility_m',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=8,
                null=True,
                verbose_name='Visibility (m)',
            ),
        ),
        migrations.CreateModel(
            name='AwosMetarReport',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reported_at', models.DateTimeField(verbose_name='Reported At')),
                ('raw_report', models.CharField(max_length=1000, verbose_name='Raw METAR')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('station', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='awos_metar_reports',
                    to='weather.weatherstation',
                    verbose_name='Station',
                )),
            ],
            options={
                'verbose_name': 'AWOS METAR Report',
                'verbose_name_plural': 'AWOS METAR Reports',
                'ordering': ['-reported_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='awosmetarreport',
            constraint=models.UniqueConstraint(
                fields=('station', 'reported_at'),
                name='weather_awos_metar_station_time_unique',
            ),
        ),
        migrations.AddIndex(
            model_name='awosmetarreport',
            index=models.Index(
                fields=['station', '-reported_at'],
                name='weather_metar_station_time_idx',
            ),
        ),
    ]
