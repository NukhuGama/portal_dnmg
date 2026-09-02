from django.db import migrations, models
from django.db.models import Count, F, Q


def verify_existing_values(apps, schema_editor):
    """Validate legacy rows before their rules become database constraints."""
    DepartmentSection = apps.get_model('hr', 'DepartmentSection')
    Employee = apps.get_model('hr', 'Employee')
    EmployeeEducation = apps.get_model('hr', 'EmployeeEducation')
    EmployeeDocument = apps.get_model('hr', 'EmployeeDocument')
    DownloadableFile = apps.get_model('hr', 'DownloadableFile')

    duplicate_codes = list(
        DepartmentSection.objects.exclude(code='')
        .values('department_id', 'code')
        .annotate(total=Count('pk'))
        .filter(total__gt=1)[:10]
    )
    invalid = {
        'employee genders': Employee.objects.exclude(gender__in=['M', 'F', 'O']),
        'employee employment types': Employee.objects.exclude(
            employment_type__in=['PERMANENT', 'CONTRACT', 'CONSULTANT', 'INTERN']
        ),
        'employee employment statuses': Employee.objects.exclude(
            employment_status__in=['ACTIVE', 'ON_LEAVE', 'RETIRED', 'RESIGNED', 'TERMINATED']
        ),
        'employee contract dates': Employee.objects.filter(
            contract_end_date__isnull=False,
            contract_end_date__lt=F('start_date'),
        ),
        'education completion years': EmployeeEducation.objects.filter(year_completed__lt=1900),
        'employee document types': EmployeeDocument.objects.exclude(
            document_type__in=['CONTRACT', 'ID', 'CERTIFICATE', 'OTHER']
        ),
        'downloadable file types': DownloadableFile.objects.exclude(
            file_type__in=['PDF', 'EXCEL', 'WORD', 'ZIP', 'IMAGE', 'OTHER']
        ),
        'downloadable file access levels': DownloadableFile.objects.exclude(
            access_level__in=['PUBLIC', 'STAFF']
        ),
    }
    failures = [
        f"duplicate non-empty department section codes: {duplicate_codes}"
    ] if duplicate_codes else []
    failures.extend(
        f"{label}: {list(queryset.values_list('pk', flat=True)[:10])}"
        for label, queryset in invalid.items()
        if queryset.exists()
    )
    if failures:
        raise RuntimeError(
            'Cannot apply HR schema integrity constraints because existing rows '
            'are invalid. Correct these records, then rerun migrate: ' + '; '.join(failures)
        )


class Migration(migrations.Migration):

    dependencies = [
        ('hr', '0003_departmentsection_employeeeducation_remove_employee_education_fields'),
    ]

    operations = [
        migrations.RunPython(verify_existing_values, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='departmentsection',
            constraint=models.UniqueConstraint(
                fields=('department', 'code'),
                condition=~Q(code=''),
                name='unique_nonblank_section_code_per_dept',
            ),
        ),
        migrations.AddConstraint(
            model_name='employee',
            constraint=models.CheckConstraint(
                condition=Q(gender__in=['M', 'F', 'O']),
                name='hr_employee_gender_valid',
            ),
        ),
        migrations.AddConstraint(
            model_name='employee',
            constraint=models.CheckConstraint(
                condition=Q(employment_type__in=['PERMANENT', 'CONTRACT', 'CONSULTANT', 'INTERN']),
                name='hr_employee_type_valid',
            ),
        ),
        migrations.AddConstraint(
            model_name='employee',
            constraint=models.CheckConstraint(
                condition=Q(employment_status__in=['ACTIVE', 'ON_LEAVE', 'RETIRED', 'RESIGNED', 'TERMINATED']),
                name='hr_employee_status_valid',
            ),
        ),
        migrations.AddConstraint(
            model_name='employee',
            constraint=models.CheckConstraint(
                condition=Q(contract_end_date__isnull=True) | Q(contract_end_date__gte=F('start_date')),
                name='hr_employee_contract_dates_valid',
            ),
        ),
        migrations.AddIndex(
            model_name='employee',
            index=models.Index(fields=['department', 'employment_status'], name='hr_employee_dept_status_idx'),
        ),
        migrations.AddIndex(
            model_name='employee',
            index=models.Index(fields=['employment_status', 'contract_end_date'], name='hr_emp_status_contract_idx'),
        ),
        migrations.AddConstraint(
            model_name='employeeeducation',
            constraint=models.CheckConstraint(
                condition=Q(year_completed__isnull=True) | Q(year_completed__gte=1900),
                name='hr_education_year_valid',
            ),
        ),
        migrations.AddIndex(
            model_name='employeeeducation',
            index=models.Index(fields=['employee', '-year_completed'], name='hr_education_employee_year_idx'),
        ),
        migrations.AddConstraint(
            model_name='employeedocument',
            constraint=models.CheckConstraint(
                condition=Q(document_type__in=['CONTRACT', 'ID', 'CERTIFICATE', 'OTHER']),
                name='hr_document_type_valid',
            ),
        ),
        migrations.AddConstraint(
            model_name='downloadablefile',
            constraint=models.CheckConstraint(
                condition=Q(file_type__in=['PDF', 'EXCEL', 'WORD', 'ZIP', 'IMAGE', 'OTHER']),
                name='hr_download_file_type_valid',
            ),
        ),
        migrations.AddConstraint(
            model_name='downloadablefile',
            constraint=models.CheckConstraint(
                condition=Q(access_level__in=['PUBLIC', 'STAFF']),
                name='hr_download_access_valid',
            ),
        ),
        migrations.AddIndex(
            model_name='downloadablefile',
            index=models.Index(fields=['access_level', '-created_at'], name='hr_download_access_created_idx'),
        ),
        migrations.AddIndex(
            model_name='downloadablefile',
            index=models.Index(fields=['category', '-created_at'], name='hr_download_cat_created_idx'),
        ),
    ]
