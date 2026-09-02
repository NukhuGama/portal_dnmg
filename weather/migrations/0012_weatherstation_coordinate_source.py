from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('weather', '0011_officialforecastattachment_officialforecastimage'),
    ]

    operations = [
        migrations.AddField(
            model_name='weatherstation',
            name='coordinate_source',
            field=models.CharField(
                choices=[
                    ('MANUAL', 'Set manually in Admin DNMG'),
                    ('PROVIDER', 'Updated from station provider'),
                ],
                default='MANUAL',
                help_text='Manual coordinates are kept when live station data is synchronized.',
                max_length=12,
                verbose_name='Coordinate Source',
            ),
        ),
        migrations.AddConstraint(
            model_name='weatherstation',
            constraint=models.CheckConstraint(
                condition=models.Q(('coordinate_source__in', ['MANUAL', 'PROVIDER'])),
                name='weather_station_coordinate_source_valid',
            ),
        ),
    ]
