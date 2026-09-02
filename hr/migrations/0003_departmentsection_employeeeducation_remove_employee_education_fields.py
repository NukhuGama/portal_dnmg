from django.db import migrations, models
import django.db.models.deletion


REPAIR_LEGACY_HR_PRIMARY_KEYS = """
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'hr_department'::regclass AND contype = 'p'
    ) THEN
        IF EXISTS (SELECT 1 FROM hr_department WHERE id IS NULL) OR EXISTS (
            SELECT id FROM hr_department GROUP BY id HAVING COUNT(*) > 1
        ) THEN
            RAISE EXCEPTION
                'Cannot repair hr_department primary key: id contains NULL or duplicate values.';
        END IF;
        ALTER TABLE hr_department ADD CONSTRAINT hr_department_pkey PRIMARY KEY (id);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'hr_employee'::regclass AND contype = 'p'
    ) THEN
        IF EXISTS (SELECT 1 FROM hr_employee WHERE id IS NULL) OR EXISTS (
            SELECT id FROM hr_employee GROUP BY id HAVING COUNT(*) > 1
        ) THEN
            RAISE EXCEPTION
                'Cannot repair hr_employee primary key: id contains NULL or duplicate values.';
        END IF;
        ALTER TABLE hr_employee ADD CONSTRAINT hr_employee_pkey PRIMARY KEY (id);
    END IF;
END
$$;
"""


def migrate_existing_education(apps, schema_editor):
    Employee = apps.get_model('hr', 'Employee')
    EmployeeEducation = apps.get_model('hr', 'EmployeeEducation')
    for employee in Employee.objects.all().iterator():
        if any((employee.education_level, employee.field_of_study, employee.institution, employee.graduation_year)):
            EmployeeEducation.objects.create(
                employee=employee,
                degree=employee.education_level or 'Qualification',
                institution=employee.institution or '',
                field_of_study=employee.field_of_study or '',
                year_completed=employee.graduation_year,
            )


class Migration(migrations.Migration):

    dependencies = [
        ('hr', '0002_employee_education_information_remove_salary_grade'),
    ]

    operations = [
        migrations.RunSQL(REPAIR_LEGACY_HR_PRIMARY_KEYS, migrations.RunSQL.noop),
        migrations.CreateModel(
            name='DepartmentSection',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=150, verbose_name='Section Name')),
                ('code', models.CharField(blank=True, max_length=30, verbose_name='Section Code')),
                ('description', models.TextField(blank=True, verbose_name='Description')),
                ('order', models.PositiveSmallIntegerField(default=0, verbose_name='Display Order')),
                ('is_active', models.BooleanField(default=True, verbose_name='Active')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('department', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sections', to='hr.department', verbose_name='Department')),
            ],
            options={
                'verbose_name': 'Department Section',
                'verbose_name_plural': 'Department Sections',
                'ordering': ['department__name', 'order', 'name'],
            },
        ),
        migrations.CreateModel(
            name='EmployeeEducation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('degree', models.CharField(max_length=150, verbose_name='Degree / Qualification')),
                ('institution', models.CharField(max_length=200, verbose_name='Institution')),
                ('field_of_study', models.CharField(blank=True, max_length=150, verbose_name='Field of Study')),
                ('year_completed', models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='Year Completed')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('employee', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='education_records', to='hr.employee', verbose_name='Employee')),
            ],
            options={
                'verbose_name': 'Education Record',
                'verbose_name_plural': 'Education Records',
                'ordering': ['-year_completed', '-id'],
            },
        ),
        migrations.AddConstraint(
            model_name='departmentsection',
            constraint=models.UniqueConstraint(fields=('department', 'name'), name='unique_section_name_per_department'),
        ),
        migrations.RunPython(migrate_existing_education, migrations.RunPython.noop),
        migrations.RemoveField(model_name='employee', name='education_level'),
        migrations.RemoveField(model_name='employee', name='field_of_study'),
        migrations.RemoveField(model_name='employee', name='institution'),
        migrations.RemoveField(model_name='employee', name='graduation_year'),
    ]
