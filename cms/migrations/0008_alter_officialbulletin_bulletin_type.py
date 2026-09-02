from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cms', '0007_bulletin_types_and_job_department_fk'),
    ]

    operations = [
        migrations.AlterField(
            model_name='officialbulletin',
            name='bulletin_type',
            field=models.CharField(
                choices=[
                    ('DAILY_SYNOPTIC', 'Daily Synoptic Bulletin'),
                    ('WEEKLY_SYNOPTIC', 'Weekly Synoptic Bulletin'),
                    ('MONTHLY_CLIMATE', 'Monthly Climate Outlook'),
                    ('SEASONAL_CLIMATE', 'Seasonal Climate Outlook'),
                    ('ANNUAL_CLIMATE', 'Annual Climate Report'),
                    ('MARINE', 'Marine Bulletin'),
                    ('SEISMIC', 'Seismic Event Summary'),
                    ('SPECIAL', 'Special Hydrometeorological Report'),
                ],
                default='DAILY_SYNOPTIC',
                max_length=30,
                verbose_name='Bulletin Type',
            ),
        ),
    ]
