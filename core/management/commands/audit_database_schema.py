"""Report primary-key, foreign-key, constraint, and index coverage from PostgreSQL."""

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.models import Count, F, Q


SUPPORTED_PK_TYPES = {
    'AutoField', 'BigAutoField', 'SmallAutoField', 'UUIDField',
    # django_session deliberately uses its opaque session key as the primary key.
    'CharField', 'IntegerField', 'BigIntegerField',
}
SYSTEM_TABLES = {'django_migrations'}


class Command(BaseCommand):
    help = (
        'Audit every database table for primary keys, foreign keys, constraints, '
        'and indexes. Use --fail-on-issues in deployment checks.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--fail-on-issues',
            action='store_true',
            help='Exit with a non-zero status if the audit finds an issue.',
        )

    @staticmethod
    def _sample_ids(queryset):
        return list(queryset.values_list('pk', flat=True)[:10])

    def _application_data_issues(self, table_names):
        """Check rules that need meaningful data, in addition to database metadata."""
        issues = []

        def table_exists(model):
            return model._meta.db_table in table_names

        WeatherStation = apps.get_model('weather', 'WeatherStation')
        WeatherForecast = apps.get_model('weather', 'WeatherForecast')
        EarlyWarning = apps.get_model('weather', 'EarlyWarning')
        Employee = apps.get_model('hr', 'Employee')
        EmployeeEducation = apps.get_model('hr', 'EmployeeEducation')
        Department = apps.get_model('hr', 'Department')
        DepartmentSection = apps.get_model('hr', 'DepartmentSection')

        checks = (
            ('weather station coordinate range', WeatherStation, Q(latitude__lt=-90) | Q(latitude__gt=90) | Q(longitude__lt=-180) | Q(longitude__gt=180)),
            ('forecast temperature range', WeatherForecast, Q(temp_min__gt=F('temp_max'))),
            ('forecast rain probability range', WeatherForecast, Q(rain_probability__lt=0) | Q(rain_probability__gt=100)),
            ('early-warning validity range', EarlyWarning, Q(valid_to__lte=F('valid_from'))),
            ('employee contract date range', Employee, Q(contract_end_date__isnull=False, contract_end_date__lt=F('start_date'))),
            ('education completion year', EmployeeEducation, Q(year_completed__lt=1900)),
        )
        for label, model, predicate in checks:
            if table_exists(model):
                invalid = model.objects.filter(predicate)
                if invalid.exists():
                    issues.append(f'{label} has invalid rows with IDs {self._sample_ids(invalid)}.')

        if table_exists(DepartmentSection):
            duplicate_codes = (
                DepartmentSection.objects.exclude(code='')
                .values('department_id', 'code')
                .annotate(total=Count('pk'))
                .filter(total__gt=1)
            )
            if duplicate_codes.exists():
                issues.append('Department sections have duplicate non-empty codes within a department.')

        if table_exists(Employee) and table_exists(DepartmentSection):
            mismatched_sections = Employee.objects.filter(section__isnull=False).exclude(
                department_id=F('section__department_id')
            )
            if mismatched_sections.exists():
                issues.append(
                    'Employees have a section outside their selected department: '
                    f'{self._sample_ids(mismatched_sections)}.'
                )

        if table_exists(Department):
            invalid_heads = Department.objects.filter(head__isnull=False).exclude(
                head__department_id=F('pk')
            )
            if invalid_heads.exists():
                issues.append(
                    'Departments have a head who is not assigned to that department: '
                    f'{self._sample_ids(invalid_heads)}.'
                )

        return issues

    def handle(self, *args, **options):
        if connection.vendor != 'postgresql':
            raise CommandError(
                f'This audit is intended for PostgreSQL; the configured database is {connection.vendor!r}.'
            )

        model_by_table = {
            model._meta.db_table: model
            for model in apps.get_models(include_auto_created=True)
            if model._meta.managed and not model._meta.proxy
        }
        issues = []

        with connection.cursor() as cursor:
            table_names = sorted(connection.introspection.table_names(cursor))
            self.stdout.write(f'PostgreSQL schema audit: {len(table_names)} tables')

            for table_name in table_names:
                description = connection.introspection.get_table_description(cursor, table_name)
                columns = {column.name: column for column in description}
                constraints = connection.introspection.get_constraints(cursor, table_name)
                primary_keys = [
                    (name, metadata) for name, metadata in constraints.items()
                    if metadata['primary_key']
                ]
                foreign_keys = [
                    metadata for metadata in constraints.values() if metadata['foreign_key']
                ]
                indexes = [
                    name for name, metadata in constraints.items()
                    if metadata['index'] and not metadata['primary_key']
                ]

                self.stdout.write(
                    f'  {table_name}: PK={len(primary_keys)}, FK={len(foreign_keys)}, indexes={len(indexes)}'
                )

                if len(primary_keys) != 1:
                    issues.append(f'{table_name} must have exactly one primary-key constraint.')
                elif len(primary_keys[0][1]['columns']) != 1:
                    issues.append(f'{table_name} has a composite primary key; Django requires a single-column key.')
                else:
                    pk_column = primary_keys[0][1]['columns'][0]
                    if columns[pk_column].null_ok:
                        issues.append(f'{table_name}.{pk_column} primary key allows NULL.')

                model = model_by_table.get(table_name)
                if model is None:
                    if table_name not in SYSTEM_TABLES:
                        issues.append(f'{table_name} is not mapped to an installed Django model and needs ownership review.')
                    continue

                pk_type = model._meta.pk.get_internal_type()
                if pk_type not in SUPPORTED_PK_TYPES:
                    issues.append(
                        f'{table_name}.{model._meta.pk.column} uses unsupported primary-key type {pk_type}.'
                    )

                for declared_constraint in model._meta.constraints:
                    if declared_constraint.name not in constraints:
                        issues.append(
                            f'{table_name} is missing declared constraint '
                            f'{declared_constraint.name!r}.'
                        )
                for declared_index in model._meta.indexes:
                    if declared_index.name not in constraints:
                        issues.append(
                            f'{table_name} is missing declared index {declared_index.name!r}.'
                        )

                for field in model._meta.fields:
                    if not field.many_to_one and not field.one_to_one:
                        continue
                    if not any(field.column in item['columns'] for item in foreign_keys):
                        issues.append(
                            f'{table_name}.{field.column} has no database foreign-key constraint.'
                        )

            if 'hr_employee' in table_names:
                cursor.execute(
                    """
                    SELECT EXISTS (
                        SELECT 1 FROM pg_trigger
                        WHERE tgname = 'hr_employee_section_dept_sync_trigger'
                          AND NOT tgisinternal
                    )
                    """
                )
                if not cursor.fetchone()[0]:
                    issues.append('hr_employee is missing the department/section integrity trigger.')

            expected_triggers = {
                'hr_department': 'hr_department_head_department_check_trigger',
                'hr_employee': 'hr_employee_department_head_check_trigger',
                'hr_departmentsection': 'hr_section_department_change_check_trigger',
            }
            for table_name, trigger_name in expected_triggers.items():
                if table_name not in table_names:
                    continue
                cursor.execute(
                    """
                    SELECT EXISTS (
                        SELECT 1 FROM pg_trigger
                        WHERE tgname = %s AND NOT tgisinternal
                    )
                    """,
                    [trigger_name],
                )
                if not cursor.fetchone()[0]:
                    issues.append(f'{table_name} is missing the {trigger_name} integrity trigger.')

        issues.extend(self._application_data_issues(set(table_names)))

        if issues:
            self.stdout.write(self.style.WARNING('\nIssues requiring review:'))
            for issue in issues:
                self.stdout.write(self.style.WARNING(f'  - {issue}'))
            if options['fail_on_issues']:
                raise CommandError(f'Schema audit found {len(issues)} issue(s).')
        else:
            self.stdout.write(self.style.SUCCESS('\nSchema audit passed: all reviewed tables have valid PK/FK metadata and data rules.'))
