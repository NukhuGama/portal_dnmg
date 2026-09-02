from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


PERMISSIONS = [
    ('dashboard.view', 'dashboard', 'View dashboard'),
    ('news.view', 'news', 'View News'), ('news.create', 'news', 'Add News'), ('news.edit', 'news', 'Edit News'), ('news.delete', 'news', 'Delete News'), ('news.publish', 'news', 'Publish News'), ('news.download', 'news', 'Download News'), ('news.approve', 'news', 'Approve News'), ('news.archive', 'news', 'Archive News'),
    ('bulletins.view', 'bulletins', 'View Bulletins'), ('bulletins.create', 'bulletins', 'Add Bulletins'), ('bulletins.edit', 'bulletins', 'Edit Bulletins'), ('bulletins.delete', 'bulletins', 'Delete Bulletins'), ('bulletins.publish', 'bulletins', 'Publish Bulletins'), ('bulletins.download', 'bulletins', 'Download Bulletins'), ('bulletins.approve', 'bulletins', 'Approve Bulletins'), ('bulletins.disseminate', 'bulletins', 'Disseminate Bulletins'), ('bulletins.archive', 'bulletins', 'Archive Bulletins'),
    ('careers.view', 'careers', 'View Jobs'), ('careers.create', 'careers', 'Add Jobs'), ('careers.edit', 'careers', 'Edit Jobs'), ('careers.delete', 'careers', 'Delete Jobs'), ('careers.publish', 'careers', 'Publish Jobs'), ('careers.close', 'careers', 'Close Jobs'), ('careers.download', 'careers', 'Download Jobs'),
    ('weather_stations.view', 'weather_stations', 'View Stations'), ('weather_stations.create', 'weather_stations', 'Add Stations'), ('weather_stations.edit', 'weather_stations', 'Edit Stations'), ('weather_stations.delete', 'weather_stations', 'Delete Stations'), ('weather_stations.download', 'weather_stations', 'Download Station Data'), ('weather_stations.history', 'weather_stations', 'View Station History'), ('weather_stations.data_gap_alert', 'weather_stations', 'Receive Data Gap Alerts'), ('weather_stations.drift_alert', 'weather_stations', 'Receive Drift Alerts'), ('weather_stations.manage_configuration', 'weather_stations', 'Manage Station Configuration'),
    ('observations.view', 'observations', 'View Observations'), ('observations.create', 'observations', 'Add Observations'), ('observations.edit', 'observations', 'Edit Observations'), ('observations.delete', 'observations', 'Delete Observations'), ('observations.download', 'observations', 'Download Observations'), ('observations.export', 'observations', 'Export Observations'), ('observations.approve', 'observations', 'Approve Observations'),
    ('forecasts.view', 'forecasts', 'View Forecasts'), ('forecasts.create', 'forecasts', 'Add Forecasts'), ('forecasts.edit', 'forecasts', 'Edit Forecasts'), ('forecasts.delete', 'forecasts', 'Delete Forecasts'), ('forecasts.publish', 'forecasts', 'Publish Forecasts'), ('forecasts.approve', 'forecasts', 'Approve Forecasts'), ('forecasts.download', 'forecasts', 'Download Forecasts'), ('forecasts.disseminate', 'forecasts', 'Disseminate Forecasts'),
    ('users.view', 'users', 'View Users'), ('users.create', 'users', 'Add User'), ('users.edit', 'users', 'Edit User'), ('users.delete', 'users', 'Delete User'), ('users.activate', 'users', 'Activate User'), ('users.deactivate', 'users', 'Deactivate User'), ('users.reset_password', 'users', 'Reset User Password'), ('users.assign_role', 'users', 'Assign Role'), ('users.change_role', 'users', 'Change User Role'), ('users.detail', 'users', 'View User Details'),
    ('roles.view', 'roles', 'View Roles'), ('roles.create', 'roles', 'Add Role'), ('roles.edit', 'roles', 'Edit Role'), ('roles.delete', 'roles', 'Delete Role'), ('roles.activate', 'roles', 'Activate Role'), ('roles.deactivate', 'roles', 'Deactivate Role'), ('roles.assign_permissions', 'roles', 'Assign Permissions'), ('roles.assign_users', 'roles', 'Assign Roles to Users'),
    ('permissions.view', 'permissions', 'View Permissions'), ('permissions.create', 'permissions', 'Add Permission'), ('permissions.edit', 'permissions', 'Edit Permission'), ('permissions.delete', 'permissions', 'Delete Permission'),
    ('audit_trails.view', 'audit_trails', 'View Audit Trails'), ('audit_trails.search', 'audit_trails', 'Search Audit Trails'), ('audit_trails.filter', 'audit_trails', 'Filter Audit Trails'), ('audit_trails.export', 'audit_trails', 'Export Audit Trails'), ('audit_trails.download', 'audit_trails', 'Download Audit Trails'),
    ('hr_dashboard.view', 'hr_dashboard', 'View Dashboard'), ('hr_dashboard.reports', 'hr_dashboard', 'View Reports'), ('hr_dashboard.statistics', 'hr_dashboard', 'View Statistics'), ('hr_dashboard.export_reports', 'hr_dashboard', 'Export Reports'), ('hr_dashboard.download_reports', 'hr_dashboard', 'Download Reports'),
    ('staff.view', 'staff', 'View Staff'), ('staff.create', 'staff', 'Add Staff'), ('staff.edit', 'staff', 'Edit Staff'), ('staff.delete', 'staff', 'Delete Staff'), ('staff.detail', 'staff', 'View Staff Details'), ('staff.export', 'staff', 'Export Staff'), ('staff.download', 'staff', 'Download Staff'),
    ('departments.view', 'departments', 'View Departments'), ('departments.create', 'departments', 'Add Department'), ('departments.edit', 'departments', 'Edit Department'), ('departments.delete', 'departments', 'Delete Department'), ('departments.assign_staff', 'departments', 'Assign Staff'),
    ('staff_levels.view', 'staff_levels', 'View Staff Levels'), ('staff_levels.create', 'staff_levels', 'Add Staff Level'), ('staff_levels.edit', 'staff_levels', 'Edit Staff Level'), ('staff_levels.delete', 'staff_levels', 'Delete Staff Level'),
    ('contracts.view', 'contracts', 'View Contracts'), ('contracts.create', 'contracts', 'Add Contract'), ('contracts.edit', 'contracts', 'Edit Contract'), ('contracts.delete', 'contracts', 'Delete Contract'), ('contracts.detail', 'contracts', 'View Contract Details'), ('contracts.monitor', 'contracts', 'Monitor Contracts'), ('contracts.track_expiration', 'contracts', 'Track Contract Expiration'), ('contracts.alerts', 'contracts', 'Receive Contract Alerts'), ('contracts.download', 'contracts', 'Download Contracts'), ('contracts.export', 'contracts', 'Export Contracts'),
    ('fr_reports.view', 'fr_reports', 'View FR Reports'), ('fr_reports.create', 'fr_reports', 'Add FR Reports'), ('fr_reports.edit', 'fr_reports', 'Edit FR Reports'), ('fr_reports.delete', 'fr_reports', 'Delete FR Reports'), ('fr_reports.approve', 'fr_reports', 'Approve FR Reports'), ('fr_reports.download', 'fr_reports', 'Download FR Reports'), ('fr_reports.export', 'fr_reports', 'Export FR Reports'),
    ('downloads.view', 'downloads', 'View Downloads'), ('downloads.upload', 'downloads', 'Upload Downloads'), ('downloads.edit', 'downloads', 'Edit Downloads'), ('downloads.delete', 'downloads', 'Delete Downloads'), ('downloads.download', 'downloads', 'Download Files'), ('downloads.approve', 'downloads', 'Approve Downloads'), ('downloads.manage_categories', 'downloads', 'Manage Download Categories'),
]


def create_system_permissions(apps, schema_editor):
    Permission = apps.get_model('users', 'PortalPermission')
    for code, module, name in PERMISSIONS:
        Permission.objects.get_or_create(code=code, defaults={'module': module, 'name': name, 'is_system': True})


class Migration(migrations.Migration):
    dependencies = [('users', '0002_audit_log_indexes')]

    operations = [
        migrations.CreateModel(
            name='PortalPermission',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=100, unique=True, verbose_name='Permission Code')),
                ('module', models.CharField(max_length=50, verbose_name='Module')),
                ('name', models.CharField(max_length=150, verbose_name='Permission Name')),
                ('description', models.TextField(blank=True, verbose_name='Description')),
                ('is_system', models.BooleanField(default=False, verbose_name='System Permission')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'verbose_name': 'Portal Permission', 'verbose_name_plural': 'Portal Permissions', 'ordering': ['module', 'code']},
        ),
        migrations.CreateModel(
            name='Role',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True, verbose_name='Role Name')),
                ('description', models.TextField(blank=True, verbose_name='Description')),
                ('is_active', models.BooleanField(default=True, verbose_name='Active')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('permissions', models.ManyToManyField(blank=True, related_name='roles', to='users.portalpermission', verbose_name='Permissions')),
            ],
            options={'verbose_name': 'Role', 'verbose_name_plural': 'Roles', 'ordering': ['name']},
        ),
        migrations.AddField(
            model_name='user',
            name='access_role',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='users', to='users.role', verbose_name='Assigned Role'),
        ),
        migrations.RunPython(create_system_permissions, migrations.RunPython.noop),
    ]
