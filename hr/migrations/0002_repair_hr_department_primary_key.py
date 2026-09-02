"""Repair legacy HR Department tables that were created without an ID primary key.

Some early production databases have ``hr_department.id`` values but no
primary-key/unique constraint.  PostgreSQL correctly rejects the later
DepartmentSection foreign key in that state.  This migration validates the
legacy data first and changes only the missing database constraint.
"""

from django.db import migrations


REPAIR_DEPARTMENT_PRIMARY_KEY = """
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'hr_department'::regclass
          AND contype = 'p'
    ) THEN
        RETURN;
    END IF;

    IF EXISTS (SELECT 1 FROM hr_department WHERE id IS NULL) THEN
        RAISE EXCEPTION
            'Cannot repair hr_department: id contains NULL values. Restore or correct the legacy table before migrating.';
    END IF;

    IF EXISTS (
        SELECT id
        FROM hr_department
        GROUP BY id
        HAVING COUNT(*) > 1
    ) THEN
        RAISE EXCEPTION
            'Cannot repair hr_department: id contains duplicate values. Restore or correct the legacy table before migrating.';
    END IF;

    ALTER TABLE hr_department
        ADD CONSTRAINT hr_department_pkey PRIMARY KEY (id);
END
$$;
"""


class Migration(migrations.Migration):

    dependencies = [
        ('hr', '0002_employee_education_information_remove_salary_grade'),
    ]

    operations = [
        migrations.RunSQL(REPAIR_DEPARTMENT_PRIMARY_KEY, migrations.RunSQL.noop),
    ]
