"""Repair legacy HR Employee tables that were created without an ID primary key.

``hr.0003`` creates EmployeeEducation, which references ``hr_employee.id``.
Legacy deployments may have employee ID values but no database primary-key
constraint, so validate the existing values and restore that invariant first.
"""

from django.db import migrations


REPAIR_EMPLOYEE_PRIMARY_KEY = """
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'hr_employee'::regclass
          AND contype = 'p'
    ) THEN
        RETURN;
    END IF;

    IF EXISTS (SELECT 1 FROM hr_employee WHERE id IS NULL) THEN
        RAISE EXCEPTION
            'Cannot repair hr_employee: id contains NULL values. Restore or correct the legacy table before migrating.';
    END IF;

    IF EXISTS (
        SELECT id
        FROM hr_employee
        GROUP BY id
        HAVING COUNT(*) > 1
    ) THEN
        RAISE EXCEPTION
            'Cannot repair hr_employee: id contains duplicate values. Restore or correct the legacy table before migrating.';
    END IF;

    ALTER TABLE hr_employee
        ADD CONSTRAINT hr_employee_pkey PRIMARY KEY (id);
END
$$;
"""


class Migration(migrations.Migration):

    dependencies = [
        ('hr', '0002_repair_hr_department_primary_key'),
    ]

    operations = [
        migrations.RunSQL(REPAIR_EMPLOYEE_PRIMARY_KEY, migrations.RunSQL.noop),
    ]
