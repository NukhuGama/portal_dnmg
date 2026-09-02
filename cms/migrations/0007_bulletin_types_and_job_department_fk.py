import django.db.models.deletion
from django.db import migrations, models


def migrate_job_departments(apps, schema_editor):
    Department = apps.get_model('hr', 'Department')
    JobOpening = apps.get_model('cms', 'JobOpening')

    department_by_label = {}
    for department in Department.objects.all().only('id', 'name', 'code'):
        for label in (department.name, department.code):
            normalized = label.strip().casefold()
            if normalized:
                department_by_label.setdefault(normalized, set()).add(department.pk)

    unmatched = []
    ambiguous = []
    updates = []
    for job in JobOpening.objects.exclude(department='').only('id', 'department'):
        department_ids = department_by_label.get(job.department.strip().casefold(), set())
        if len(department_ids) == 1:
            updates.append((job.pk, next(iter(department_ids))))
        elif len(department_ids) > 1:
            ambiguous.append(job.pk)
        else:
            unmatched.append(job.pk)

    if unmatched or ambiguous:
        failures = []
        if unmatched:
            failures.append('unmatched job-opening department values for IDs ' + str(unmatched[:10]))
        if ambiguous:
            failures.append('ambiguous job-opening department values for IDs ' + str(ambiguous[:10]))
        raise RuntimeError(
            'Cannot convert JobOpening.department to a foreign key without losing data. '
            'Create or correct the matching HR departments, then rerun migrate: '
            + '; '.join(failures)
        )

    for job_id, department_id in updates:
        JobOpening.objects.filter(pk=job_id).update(department_fk_id=department_id)


class Migration(migrations.Migration):

    dependencies = [
        ('cms', '0006_cms_query_indexes'),
        ('hr', '0005_employee_section'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='officialbulletin',
            name='cms_bulletin_type_valid',
        ),
        migrations.AddConstraint(
            model_name='officialbulletin',
            constraint=models.CheckConstraint(
                condition=models.Q(bulletin_type__in=[
                    'DAILY_SYNOPTIC', 'WEEKLY_SYNOPTIC', 'MONTHLY_CLIMATE',
                    'SEASONAL_CLIMATE', 'ANNUAL_CLIMATE', 'MARINE', 'SEISMIC', 'SPECIAL',
                ]),
                name='cms_bulletin_type_valid',
            ),
        ),
        migrations.AddField(
            model_name='jobopening',
            name='department_fk',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='job_openings',
                to='hr.department',
                verbose_name='Department',
            ),
        ),
        migrations.RunPython(migrate_job_departments, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='jobopening',
            name='department',
        ),
        migrations.RenameField(
            model_name='jobopening',
            old_name='department_fk',
            new_name='department',
        ),
    ]
