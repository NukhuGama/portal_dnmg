from django.db import migrations
from django.db.models import F


def verify_existing_relationships(apps, schema_editor):
    Department = apps.get_model('hr', 'Department')
    DepartmentSection = apps.get_model('hr', 'DepartmentSection')
    Employee = apps.get_model('hr', 'Employee')

    mismatched_employees = Employee.objects.filter(section__isnull=False).exclude(
        department_id=F('section__department_id')
    )
    invalid_heads = Department.objects.filter(head__isnull=False).exclude(
        head__department_id=F('pk')
    )
    failures = []
    if mismatched_employees.exists():
        failures.append(
            'employees whose section belongs to another department: '
            + str(list(mismatched_employees.values_list('pk', flat=True)[:10]))
        )
    if invalid_heads.exists():
        failures.append(
            'departments whose head is assigned elsewhere: '
            + str(list(invalid_heads.values_list('pk', flat=True)[:10]))
        )
    if failures:
        raise RuntimeError(
            'Cannot apply HR relationship integrity rules. Correct these records, then rerun migrate: '
            + '; '.join(failures)
        )


class Migration(migrations.Migration):

    dependencies = [
        ('hr', '0005_employee_section'),
    ]

    operations = [
        migrations.RunPython(verify_existing_relationships, migrations.RunPython.noop),
        migrations.RunSQL(
            sql="""
                CREATE OR REPLACE FUNCTION hr_department_head_department_check()
                RETURNS trigger AS $$
                BEGIN
                    IF NEW.head_id IS NOT NULL AND NOT EXISTS (
                        SELECT 1
                        FROM hr_employee
                        WHERE id = NEW.head_id AND department_id = NEW.id
                    ) THEN
                        RAISE EXCEPTION 'Department head must be assigned to that department'
                            USING ERRCODE = '23514';
                    END IF;
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql;
            """,
            reverse_sql="DROP FUNCTION IF EXISTS hr_department_head_department_check();",
        ),
        migrations.RunSQL(
            sql="""
                CREATE TRIGGER hr_department_head_department_check_trigger
                BEFORE INSERT OR UPDATE OF head_id ON hr_department
                FOR EACH ROW EXECUTE FUNCTION hr_department_head_department_check();
            """,
            reverse_sql="DROP TRIGGER IF EXISTS hr_department_head_department_check_trigger ON hr_department;",
        ),
        migrations.RunSQL(
            sql="""
                CREATE OR REPLACE FUNCTION hr_employee_department_head_check()
                RETURNS trigger AS $$
                BEGIN
                    IF NEW.department_id IS DISTINCT FROM OLD.department_id AND EXISTS (
                        SELECT 1
                        FROM hr_department
                        WHERE head_id = NEW.id AND id IS DISTINCT FROM NEW.department_id
                    ) THEN
                        RAISE EXCEPTION 'Move or clear this employee as department head before changing department'
                            USING ERRCODE = '23514';
                    END IF;
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql;
            """,
            reverse_sql="DROP FUNCTION IF EXISTS hr_employee_department_head_check();",
        ),
        migrations.RunSQL(
            sql="""
                CREATE TRIGGER hr_employee_department_head_check_trigger
                BEFORE UPDATE OF department_id ON hr_employee
                FOR EACH ROW EXECUTE FUNCTION hr_employee_department_head_check();
            """,
            reverse_sql="DROP TRIGGER IF EXISTS hr_employee_department_head_check_trigger ON hr_employee;",
        ),
        migrations.RunSQL(
            sql="""
                CREATE OR REPLACE FUNCTION hr_section_department_change_check()
                RETURNS trigger AS $$
                BEGIN
                    IF NEW.department_id IS DISTINCT FROM OLD.department_id AND EXISTS (
                        SELECT 1
                        FROM hr_employee
                        WHERE section_id = NEW.id
                          AND department_id IS DISTINCT FROM NEW.department_id
                    ) THEN
                        RAISE EXCEPTION 'Cannot move a section while its employees belong to another department'
                            USING ERRCODE = '23514';
                    END IF;
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql;
            """,
            reverse_sql="DROP FUNCTION IF EXISTS hr_section_department_change_check();",
        ),
        migrations.RunSQL(
            sql="""
                CREATE TRIGGER hr_section_department_change_check_trigger
                BEFORE UPDATE OF department_id ON hr_departmentsection
                FOR EACH ROW EXECUTE FUNCTION hr_section_department_change_check();
            """,
            reverse_sql="DROP TRIGGER IF EXISTS hr_section_department_change_check_trigger ON hr_departmentsection;",
        ),
    ]
