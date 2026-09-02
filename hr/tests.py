from datetime import date
from dateutil.relativedelta import relativedelta
from django.test import TestCase
from django.test import TransactionTestCase
from django.db import IntegrityError, connection, transaction
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from unittest import skipUnless
from users.models import User, AuditLog
from .models import Department, DepartmentSection, StaffLevel, Employee, EmployeeEducation, EmployeeDocument, DownloadCategory, DownloadableFile
from .services import HRDashboardService, ContractMonitoringService, HRReportService
from .forms import EmployeeDocumentForm, EmployeeForm


class HRModelTestCase(TestCase):
    def setUp(self):
        self.dept = Department.objects.create(
            name="Meteorology Division",
            code="MET-DIV",
            description="Weather forecasting and observations"
        )
        self.level = StaffLevel.objects.create(
            name="Senior Meteorologist",
            code="SNR-MET",
            rank=1
        )
        self.employee = Employee.objects.create(
            employee_number="DNMG-2026-001",
            full_name="Maria Costa",
            gender=Employee.Gender.FEMALE,
            date_of_birth=date(1990, 5, 15),
            nationality="Timorese",
            department=self.dept,
            position="Chief Meteorologist",
            employment_type=Employee.EmploymentType.CONTRACT,
            staff_level=self.level,
            start_date=date(2022, 1, 1),
            contract_end_date=date.today() + relativedelta(days=20),
            employment_status=Employee.EmploymentStatus.ACTIVE
        )

    def test_department_str_and_count(self):
        self.assertEqual(str(self.dept), "Meteorology Division (MET-DIV)")
        self.assertEqual(self.dept.employee_count, 1)

    def test_employee_properties(self):
        self.assertEqual(str(self.employee), "Maria Costa [DNMG-2026-001]")
        self.assertTrue(self.employee.is_contract_expiring_soon)
        self.assertFalse(self.employee.is_contract_expired)
        self.assertEqual(self.employee.contract_days_remaining, 20)
        self.assertIsNotNone(self.employee.age)

    def test_staff_directory_uses_repeatable_education_records_not_salary_grade(self):
        form = EmployeeForm()
        self.assertNotIn('education_level', form.fields)
        self.assertNotIn('salary_grade', form.fields)
        education = EmployeeEducation.objects.create(
            employee=self.employee, degree='Bachelor of Science', institution='UNTL', year_completed=2012,
        )
        self.assertEqual(self.employee.education_records.get(), education)

    def test_sections_are_associated_with_their_department(self):
        section = DepartmentSection.objects.create(department=self.dept, name='Forecasting Section')
        self.assertEqual(section.department, self.dept)
        self.assertEqual(self.dept.section_count, 1)
        response = self.client.get(reverse('core:dnmg_structure'))
        self.assertContains(response, 'Forecasting Section')

    def test_employee_section_must_belong_to_their_department(self):
        other_department = Department.objects.create(name='Climate Division', code='CLIMATE-DIV')
        section = DepartmentSection.objects.create(department=other_department, name='Climate Services')
        form = EmployeeForm(data={
            'employee_number': 'DNMG-2026-003',
            'full_name': 'Section Test',
            'gender': Employee.Gender.FEMALE,
            'department': self.dept.pk,
            'section': section.pk,
            'position': 'Officer',
            'employment_type': Employee.EmploymentType.PERMANENT,
            'start_date': '2026-01-01',
            'employment_status': Employee.EmploymentStatus.ACTIVE,
        })
        self.assertFalse(form.is_valid())
        self.assertIn('section', form.errors)

    def test_department_head_must_belong_to_the_department(self):
        other_department = Department.objects.create(name='Climate Division', code='CLIMATE-DIV')
        other_employee = Employee.objects.create(
            employee_number='DNMG-2026-004',
            full_name='Other Department Head',
            gender=Employee.Gender.MALE,
            department=other_department,
            position='Officer',
            start_date=date(2026, 1, 1),
        )
        self.dept.head = other_employee
        with self.assertRaisesMessage(ValidationError, 'The department head must be assigned to this department.'):
            self.dept.full_clean()

    def test_employee_document_form_rejects_executables(self):
        form = EmployeeDocumentForm(
            data={'title': 'Unsafe', 'document_type': EmployeeDocument.DocumentType.OTHER},
            files={'file': SimpleUploadedFile('unsafe.exe', b'not allowed')},
        )
        self.assertFalse(form.is_valid())
        self.assertIn('file', form.errors)


@skipUnless(connection.vendor == 'postgresql', 'PostgreSQL relationship triggers are database-specific.')
class HRPostgreSQLRelationshipIntegrityTestCase(TransactionTestCase):
    def setUp(self):
        self.first_department = Department.objects.create(name='Forecasting', code='FORECAST')
        self.second_department = Department.objects.create(name='Climate', code='CLIMATE')
        self.employee = Employee.objects.create(
            employee_number='DNMG-PG-001',
            full_name='Trigger Test Employee',
            gender=Employee.Gender.FEMALE,
            department=self.first_department,
            position='Officer',
            start_date=date(2026, 1, 1),
        )
        self.section = DepartmentSection.objects.create(
            department=self.first_department,
            name='Forecasting Operations',
        )
        self.employee.section = self.section
        self.employee.save(update_fields=['section'])

    def test_database_prevents_invalid_head_and_section_department_changes(self):
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                Department.objects.filter(pk=self.second_department.pk).update(head=self.employee)

        Department.objects.filter(pk=self.first_department.pk).update(head=self.employee)
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                Employee.objects.filter(pk=self.employee.pk).update(department=self.second_department)

        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                DepartmentSection.objects.filter(pk=self.section.pk).update(department=self.second_department)


class HRSecurityAndRBACTestCase(TestCase):
    def setUp(self):
        from django.utils.translation import activate
        activate('en')
        self.super_admin = User.objects.create_user(
            username="superadmin", password="password123", role=User.Role.SUPER_ADMIN, is_superuser=True
        )
        self.hr_officer = User.objects.create_user(
            username="hrofficer", password="password123", role=User.Role.HR_OFFICER
        )
        self.meteorologist = User.objects.create_user(
            username="meteorologist", password="password123", role=User.Role.METEOROLOGIST
        )
        self.public_user = User.objects.create_user(
            username="publicuser", password="password123", role=User.Role.PUBLIC
        )

        self.dept = Department.objects.create(name="IT Department", code="IT")
        self.employee = Employee.objects.create(
            employee_number="DNMG-002",
            full_name="John Doe",
            gender=Employee.Gender.MALE,
            department=self.dept,
            position="Developer",
            start_date=date(2023, 1, 1),
            employment_status=Employee.EmploymentStatus.ACTIVE
        )

    def test_unauthenticated_access_blocked(self):
        """Unauthenticated requests to HR URLs must redirect to login."""
        response = self.client.get(reverse('hr:dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/auth/login/', response.url)

    def test_employee_document_download_requires_hr_permission(self):
        document = EmployeeDocument.objects.create(
            employee=self.employee,
            title='Employment Contract',
            document_type=EmployeeDocument.DocumentType.CONTRACT,
            file=SimpleUploadedFile('contract.pdf', b'%PDF-1.4 test'),
        )
        self.addCleanup(document.file.delete, save=False)
        url = reverse('hr:employee_doc_download', kwargs={'pk': document.pk})

        self.assertEqual(self.client.get(url).status_code, 302)

        self.client.force_login(self.meteorologist)
        self.assertEqual(self.client.get(url).status_code, 403)

        self.client.force_login(self.hr_officer)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Disposition'], 'attachment; filename="contract.pdf"')
        self.assertEqual(b''.join(response.streaming_content), b'%PDF-1.4 test')

    def test_public_user_fully_blocked(self):
        """Public users must receive 403 Forbidden on all HR URLs."""
        self.client.force_login(self.public_user)
        for url_name in ['hr:dashboard', 'hr:employee_list', 'hr:department_list',
                          'hr:download_list']:
            response = self.client.get(reverse(url_name))
            self.assertEqual(response.status_code, 403,
                             msg=f"Expected 403 for PUBLIC on {url_name}")

    def test_internal_staff_other_roles_fully_blocked(self):
        """
        Meteorologist and ALL non-HR roles must be completely blocked (403)
        from every HR URL, including the read-only staff directory.
        HR data is strictly private to SUPER_ADMIN, ADMIN, and HR_OFFICER only.
        """
        self.client.force_login(self.meteorologist)

        # All read-only views are blocked
        response = self.client.get(reverse('hr:dashboard'))
        self.assertEqual(response.status_code, 403)

        response = self.client.get(reverse('hr:employee_list'))
        self.assertEqual(response.status_code, 403)

        response = self.client.get(reverse('hr:department_list'))
        self.assertEqual(response.status_code, 403)

        response = self.client.get(reverse('hr:download_list'))
        self.assertEqual(response.status_code, 403)

        # Management views are also blocked
        response = self.client.get(reverse('hr:employee_create'))
        self.assertEqual(response.status_code, 403)

        response = self.client.get(reverse('hr:contract_monitoring'))
        self.assertEqual(response.status_code, 403)

        response = self.client.get(reverse('hr:reports'))
        self.assertEqual(response.status_code, 403)

    def test_editor_role_fully_blocked(self):
        """Editor role must also be blocked from all HR URLs."""
        editor = User.objects.create_user(
            username="editor_test", password="password123", role=User.Role.EDITOR
        )
        self.client.force_login(editor)

        response = self.client.get(reverse('hr:dashboard'))
        self.assertEqual(response.status_code, 403)

        response = self.client.get(reverse('hr:employee_list'))
        self.assertEqual(response.status_code, 403)

    def test_hr_officer_full_access(self):
        """HR Officers have full access to all HR URLs."""
        self.client.force_login(self.hr_officer)
        response = self.client.get(reverse('hr:dashboard'))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse('hr:employee_list'))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse('hr:employee_create'))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse('hr:department_list'))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse('hr:contract_monitoring'))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse('hr:reports'))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse('hr:download_list'))
        self.assertEqual(response.status_code, 200)



class HRServicesAndReportsTestCase(TestCase):
    def setUp(self):
        self.hr_officer = User.objects.create_user(
            username="hr_tester", password="password123", role=User.Role.HR_OFFICER
        )
        self.dept = Department.objects.create(name="Climate Services", code="CS")
        self.emp1 = Employee.objects.create(
            employee_number="DNMG-101",
            full_name="Alice Smith",
            gender=Employee.Gender.FEMALE,
            department=self.dept,
            position="Climate Officer",
            employment_type=Employee.EmploymentType.PERMANENT,
            start_date=date(2020, 1, 1),
            employment_status=Employee.EmploymentStatus.ACTIVE
        )
        self.emp2 = Employee.objects.create(
            employee_number="DNMG-102",
            full_name="Bob Jones",
            gender=Employee.Gender.MALE,
            department=self.dept,
            position="Assistant Researcher",
            employment_type=Employee.EmploymentType.CONTRACT,
            start_date=date(2024, 1, 1),
            contract_end_date=date.today() + relativedelta(days=15),
            employment_status=Employee.EmploymentStatus.ACTIVE
        )

    def test_dashboard_stats_aggregation(self):
        stats = HRDashboardService.get_stats()
        self.assertEqual(stats['total_employees'], 2)
        self.assertEqual(stats['active_employees'], 2)
        self.assertEqual(stats['permanent'], 1)
        self.assertEqual(stats['contract'], 1)
        self.assertEqual(stats['male'], 1)
        self.assertEqual(stats['female'], 1)

    def test_contract_monitoring_service(self):
        expiring = ContractMonitoringService.expiring_within(30)
        self.assertIn(self.emp2, expiring)
        self.assertNotIn(self.emp1, expiring)

    def test_report_export_csv(self):
        from django.utils.translation import activate
        activate('en')
        self.client.force_login(self.hr_officer)
        url = reverse('hr:report_export') + "?format=csv&data_sections=staff_information"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn(b'DNMG-101', response.content)
        self.assertIn(b'Alice Smith', response.content)
        self.assertTrue(AuditLog.objects.filter(action='HR_REPORT_EXPORTED').exists())

    def test_report_export_buttons_bypass_htmx_boosting(self):
        """Downloads must bypass HTMX and initialise after fragment swaps."""
        self.client.force_login(self.hr_officer)
        response = self.client.get(reverse('hr:reports'))
        self.assertContains(response, 'name="format" value="excel" hx-boost="false"')
        self.assertContains(response, 'name="format" value="pdf" hx-boost="false"')
        self.assertContains(response, 'name="format" value="csv" hx-boost="false"')
        self.assertContains(response, '(function initializeReportExport()')

    def test_add_employee_uses_an_explicit_non_boosted_post_form(self):
        self.client.force_login(self.hr_officer)
        response = self.client.get(reverse('hr:employee_create'))
        self.assertContains(response, 'method="post" enctype="multipart/form-data" action="')
        self.assertContains(response, 'hx-boost="false"')

    def test_education_export_can_be_selected(self):
        EmployeeEducation.objects.create(
            employee=self.emp1, degree='Master of Science', institution='UNTL', field_of_study='Climate Science', year_completed=2024,
        )
        self.client.force_login(self.hr_officer)
        response = self.client.get(reverse('hr:report_export'), {
            'format': 'csv', 'data_sections': ['staff_information', 'education_information'],
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Staff Information', response.content)
        self.assertIn(b'Education Records', response.content)
        self.assertIn(b'Degree / Qualification', response.content)
        self.assertIn(b'Master of Science', response.content)

    def test_education_export_keeps_multiple_records_and_selected_fields_only(self):
        EmployeeEducation.objects.create(
            employee=self.emp1, degree='Bachelor of Science', institution='UNTL', field_of_study='Meteorology', year_completed=2020,
        )
        EmployeeEducation.objects.create(
            employee=self.emp1, degree='Master of Science', institution='UNTL', field_of_study='Climate Science', year_completed=2024,
        )
        self.client.force_login(self.hr_officer)
        response = self.client.get(reverse('hr:report_export'), {
            'format': 'csv',
            'data_sections': ['education_information'],
            'export_fields': [
                'education_information:employee_name',
                'education_information:degree',
                'education_information:year_completed',
            ],
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Name,Degree / Qualification,Year Completed', response.content)
        self.assertIn(b'Bachelor of Science', response.content)
        self.assertIn(b'Master of Science', response.content)
        self.assertNotIn(b'Institution', response.content)

    def test_staff_directory_export_has_education_column_and_detailed_records(self):
        EmployeeEducation.objects.create(
            employee=self.emp1, degree='Bachelor of Science', institution='UNTL', year_completed=2020,
        )
        EmployeeEducation.objects.create(
            employee=self.emp1, degree='Master of Science', institution='UNTL', year_completed=2024,
        )
        self.client.force_login(self.hr_officer)
        response = self.client.get(reverse('hr:report_export'), {
            'format': 'csv',
            'data_sections': ['staff_directory', 'education_information'],
            'export_fields': [
                'staff_directory:full_name',
                'staff_directory:education_summary',
                'education_information:employee_name',
                'education_information:degree',
            ],
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Name,Education', response.content)
        self.assertIn(b'Bachelor of Science', response.content)
        self.assertIn(b'Master of Science', response.content)
        self.assertIn(b'Education Records', response.content)

    def test_education_export_is_available_in_excel_and_pdf(self):
        EmployeeEducation.objects.create(
            employee=self.emp1, degree='Master of Science', institution='UNTL', year_completed=2024,
        )
        self.client.force_login(self.hr_officer)
        selected = ['education_information:employee_name', 'education_information:degree']
        excel = self.client.get(reverse('hr:report_export'), {
            'format': 'excel', 'data_sections': ['education_information'], 'export_fields': selected,
        })
        self.assertEqual(excel.status_code, 200)
        self.assertEqual(excel['Content-Type'], 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        pdf = self.client.get(reverse('hr:report_export'), {
            'format': 'pdf', 'data_sections': ['education_information'], 'export_fields': selected,
        })
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf['Content-Type'], 'application/pdf')
        self.assertTrue(pdf.content.startswith(b'%PDF'))

    def test_hr_report_filters_and_exports_by_education(self):
        EmployeeEducation.objects.create(
            employee=self.emp1, degree='Master of Science', institution='UNTL', field_of_study='Climate Science', year_completed=2024,
        )
        self.client.force_login(self.hr_officer)
        query = {
            'data_sections': ['education_information'],
            'export_fields': ['education_information:employee_name', 'education_information:degree'],
            'education': 'Climate Science',
            'position': 'Climate Officer',
        }
        report = self.client.get(reverse('hr:reports'), query)
        self.assertEqual(report.status_code, 200)
        self.assertEqual(list(report.context['employees']), [self.emp1])
        exported = self.client.get(reverse('hr:report_export'), {'format': 'csv', **query})
        self.assertEqual(exported.status_code, 200)
        self.assertIn(b'Master of Science', exported.content)
        self.assertNotIn(b'Bob Jones', exported.content)

    def test_export_requires_a_selected_table(self):
        self.client.force_login(self.hr_officer)
        response = self.client.get(reverse('hr:report_export'), {'format': 'csv'})
        self.assertRedirects(response, reverse('hr:reports'))

    def test_education_records_can_be_added_individually(self):
        self.client.force_login(self.hr_officer)
        response = self.client.post(reverse('hr:education_create', kwargs={'employee_pk': self.emp1.pk}), {
            'degree': 'Bachelor of Science',
            'institution': 'UNTL',
            'field_of_study': 'Meteorology',
            'year_completed': 2020,
        })
        self.assertRedirects(response, f"{reverse('hr:employee_detail', kwargs={'pk': self.emp1.pk})}#tab-education")
        self.assertTrue(EmployeeEducation.objects.filter(employee=self.emp1, degree='Bachelor of Science').exists())

    def test_employee_edit_page_adds_education_without_leaving_admin_workflow(self):
        self.client.force_login(self.hr_officer)
        edit_url = reverse('hr:employee_update', kwargs={'pk': self.emp1.pk})
        response = self.client.get(edit_url)
        self.assertContains(response, 'addEducationModal')
        self.assertContains(response, 'Education Information')
        response = self.client.post(reverse('hr:education_create', kwargs={'employee_pk': self.emp1.pk}), {
            'degree': 'Diploma in Meteorology',
            'institution': 'UNTL',
            'next': f'{edit_url}#education-information',
        })
        self.assertRedirects(response, f'{edit_url}#education-information')
        self.assertTrue(EmployeeEducation.objects.filter(employee=self.emp1, degree='Diploma in Meteorology').exists())

    def test_directory_filters_by_education_and_returns_each_employee_once(self):
        section = DepartmentSection.objects.create(department=self.dept, name='Climate Analysis')
        self.emp1.section = section
        self.emp1.save()
        EmployeeEducation.objects.create(
            employee=self.emp1, degree='Bachelor of Science', institution='UNTL', year_completed=2020,
        )
        EmployeeEducation.objects.create(
            employee=self.emp1, degree='Master of Science', institution='UNTL', year_completed=2024,
        )
        self.client.force_login(self.hr_officer)
        response = self.client.get(reverse('hr:employee_list'), {
            'department': self.dept.pk,
            'section': section.pk,
            'education': 'Science',
            'position': 'Climate',
        })
        self.assertEqual(response.status_code, 200)
        employees = list(response.context['employees'])
        self.assertEqual(employees, [self.emp1])
        self.assertContains(response, 'Education')
        edit_response = self.client.get(reverse('hr:employee_update', kwargs={'pk': self.emp1.pk}))
        self.assertContains(edit_response, 'Education Information')
        self.assertContains(edit_response, 'Add Education')

    def test_report_export_excel(self):
        from django.utils.translation import activate
        activate('en')
        self.client.force_login(self.hr_officer)
        url = reverse('hr:report_export') + "?format=excel&data_sections=staff_information&data_sections=education_information"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    def test_report_export_pdf(self):
        from django.utils.translation import activate
        activate('en')
        self.client.force_login(self.hr_officer)
        url = reverse('hr:report_export') + "?format=pdf&data_sections=staff_information"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF'))

    def test_report_export_selected_only(self):
        from django.utils.translation import activate
        activate('en')
        self.client.force_login(self.hr_officer)
        url = reverse('hr:report_export')
        response = self.client.post(url, {
            'format': 'csv',
            'selected_ids': [self.emp1.id],
            'data_sections': ['staff_information'],
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Alice Smith', response.content)
        self.assertNotIn(b'Bob Jones', response.content)
