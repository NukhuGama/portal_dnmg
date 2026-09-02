import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hr', '0004_hr_schema_integrity'),
    ]

    operations = [
        migrations.AddField(
            model_name='employee',
            name='section',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='employees',
                to='hr.departmentsection',
                verbose_name='Section',
            ),
        ),
        migrations.AddIndex(
            model_name='employee',
            index=models.Index(fields=['section', 'employment_status'], name='hr_emp_section_status_idx'),
        ),
        migrations.RunSQL(
            sql="""
                CREATE OR REPLACE FUNCTION hr_employee_section_dept_sync()
                RETURNS trigger AS $$
                DECLARE
                    selected_department_id bigint;
                BEGIN
                    IF NEW.section_id IS NULL THEN
                        RETURN NEW;
                    END IF;

                    SELECT department_id INTO selected_department_id
                    FROM hr_departmentsection
                    WHERE id = NEW.section_id;

                    IF NEW.department_id IS NULL THEN
                        NEW.department_id := selected_department_id;
                    ELSIF NEW.department_id <> selected_department_id THEN
                        RAISE EXCEPTION 'Employee section must belong to the selected department'
                            USING ERRCODE = '23514';
                    END IF;
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql;
            """,
            reverse_sql="""
                DROP FUNCTION IF EXISTS hr_employee_section_dept_sync();
            """,
        ),
        migrations.RunSQL(
            sql="""
                CREATE TRIGGER hr_employee_section_dept_sync_trigger
                BEFORE INSERT OR UPDATE OF department_id, section_id ON hr_employee
                FOR EACH ROW EXECUTE FUNCTION hr_employee_section_dept_sync();
            """,
            reverse_sql="""
                DROP TRIGGER IF EXISTS hr_employee_section_dept_sync_trigger ON hr_employee;
            """,
        ),
    ]
