from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('weather', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='weatherstation',
            name='external_id',
            field=models.IntegerField(blank=True, help_text='API ID e.g., 15401', null=True, unique=True, verbose_name='External API ID'),
        ),
        migrations.AlterField(
            model_name='weatherstation',
            name='station_type',
            field=models.CharField(
                choices=[
                    ('AWS', 'Automated Weather Station (AWS)'),
                    ('AWOS', 'Automated Weather Observing System (AWOS)'),
                    ('SYNOPTIC', 'Synoptic Station'),
                    ('TIDE_GAUGE', 'Tide Gauge Station'),
                    ('BUOY', 'Marine Buoy Station'),
                    ('AGROMET', 'Agrometeorological Station'),
                    ('HYDROMET', 'Hydrometeorological Station'),
                    ('SEISMIC', 'Seismic Monitoring Station')
                ],
                default='AWS',
                max_length=20,
                verbose_name='Station Type'
            ),
        ),
        migrations.AddField(
            model_name='weatherobservation',
            name='tide_level_mm',
            field=models.DecimalField(blank=True, decimal_places=2, max_length=7, max_digits=7, null=True, verbose_name='Tide Level (mm)'),
        ),
        migrations.AddField(
            model_name='weatherobservation',
            name='peak_period_s',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True, verbose_name='Peak Period (s)'),
        ),
    ]
