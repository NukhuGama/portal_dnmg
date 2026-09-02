from django.db import migrations, models


def verify_existing_values(apps, schema_editor):
    User = apps.get_model('users', 'User')
    invalid = User.objects.exclude(role__in=[
        'SUPER_ADMIN', 'ADMIN', 'HR_OFFICER', 'METEOROLOGIST',
        'CLIMATE_OFFICER', 'MARINE_OFFICER', 'SEISMIC_OFFICER',
        'EDITOR', 'RESEARCHER', 'PUBLIC',
    ])
    if invalid.exists():
        raise RuntimeError(
            'Cannot apply user role constraint; invalid user IDs: '
            f"{list(invalid.values_list('pk', flat=True)[:10])}."
        )


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(verify_existing_values, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='user',
            constraint=models.CheckConstraint(
                condition=models.Q(role__in=[
                    'SUPER_ADMIN', 'ADMIN', 'HR_OFFICER', 'METEOROLOGIST',
                    'CLIMATE_OFFICER', 'MARINE_OFFICER', 'SEISMIC_OFFICER',
                    'EDITOR', 'RESEARCHER', 'PUBLIC',
                ]),
                name='users_user_role_valid',
            ),
        ),
        migrations.AddIndex(
            model_name='auditlog',
            index=models.Index(fields=['user', '-timestamp'], name='users_audit_user_time_idx'),
        ),
        migrations.AddIndex(
            model_name='auditlog',
            index=models.Index(fields=['-timestamp'], name='users_audit_timestamp_idx'),
        ),
    ]
