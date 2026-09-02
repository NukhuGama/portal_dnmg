from django.db import migrations


PERMISSIONS = [
    ('early_warnings.view', 'early_warnings', 'View Early Warnings'),
    ('early_warnings.create', 'early_warnings', 'Create Early Warnings'),
    ('early_warnings.edit', 'early_warnings', 'Edit Early Warnings'),
    ('early_warnings.publish', 'early_warnings', 'Publish / Activate Alerts'),
    ('early_warnings.archive', 'early_warnings', 'Archive / Deactivate Alerts'),
]


def create_early_warning_permissions(apps, schema_editor):
    Permission = apps.get_model('users', 'PortalPermission')
    database = schema_editor.connection.alias
    for code, module, name in PERMISSIONS:
        Permission.objects.using(database).get_or_create(
            code=code,
            defaults={'module': module, 'name': name, 'is_system': True},
        )


class Migration(migrations.Migration):
    dependencies = [('users', '0003_role_permission_management')]

    operations = [
        migrations.RunPython(create_early_warning_permissions, migrations.RunPython.noop),
    ]
