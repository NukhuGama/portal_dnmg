# Generated manually to preserve the existing staff records schema evolution.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hr', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='employee',
            name='salary_grade',
        ),
        migrations.AddField(
            model_name='employee',
            name='education_level',
            field=models.CharField(blank=True, max_length=100, verbose_name='Highest Education Level'),
        ),
        migrations.AddField(
            model_name='employee',
            name='field_of_study',
            field=models.CharField(blank=True, max_length=150, verbose_name='Field of Study'),
        ),
        migrations.AddField(
            model_name='employee',
            name='institution',
            field=models.CharField(blank=True, max_length=200, verbose_name='Institution'),
        ),
        migrations.AddField(
            model_name='employee',
            name='graduation_year',
            field=models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='Graduation Year'),
        ),
    ]
