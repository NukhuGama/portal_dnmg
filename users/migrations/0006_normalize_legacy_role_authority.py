from django.db import migrations


def normalize_legacy_role_authority(apps, schema_editor):
    Role = apps.get_model('users', 'Role')
    for role in Role.objects.all():
        normalized_name = ''.join(character for character in role.name.lower() if character.isalnum())
        if normalized_name in {'superadmin', 'superadministrator'}:
            role.authority_level = 3
            role.save(update_fields=['authority_level'])
        elif normalized_name in {'admin', 'administrator'}:
            role.authority_level = 2
            role.save(update_fields=['authority_level'])


class Migration(migrations.Migration):
    dependencies = [('users', '0005_role_authority_level')]

    operations = [migrations.RunPython(normalize_legacy_role_authority, migrations.RunPython.noop)]
