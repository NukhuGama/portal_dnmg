from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import HttpResponse, FileResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView, FormView
)

from .forms import (
    EmployeeForm, EmployeeEducationForm, EmployeeDocumentForm, DepartmentForm,
    DepartmentSectionForm, StaffLevelForm,
    ContractRenewForm, HRReportFilterForm, DownloadableFileForm, DownloadCategoryForm
)
from .models import (
    Employee, EmployeeEducation, EmployeeDocument, Department, DepartmentSection,
    StaffLevel, DownloadableFile, DownloadCategory,
)
from .permissions import HRManagementRequiredMixin, HRViewRequiredMixin
from .services import (
    HRDashboardService, ContractMonitoringService, HRReportService, HRAuditService
)
from core.media import media_available


# ──────────────────────────────────────────────────────────────────
# HR Dashboard
# ──────────────────────────────────────────────────────────────────

class HRDashboardView(HRViewRequiredMixin, TemplateView):
    permission_code = 'hr_dashboard.view'
    template_name = 'hr/dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['stats'] = HRDashboardService.get_stats()
        ctx['gender_chart'] = HRDashboardService.get_gender_chart_data()
        ctx['employment_type_chart'] = HRDashboardService.get_employment_type_chart_data()
        ctx['department_chart'] = HRDashboardService.get_department_chart_data()
        ctx['staff_level_chart'] = HRDashboardService.get_staff_level_chart_data()
        ctx['status_chart'] = HRDashboardService.get_employment_status_chart_data()
        ctx['age_chart'] = HRDashboardService.get_age_distribution_chart_data()
        ctx['growth_chart'] = HRDashboardService.get_staff_growth_chart_data()
        ctx['expiring_30'] = ContractMonitoringService.expiring_within(30).count()
        ctx['expiring_60'] = ContractMonitoringService.expiring_within(60).count()
        ctx['expiring_90'] = ContractMonitoringService.expiring_within(90).count()
        ctx['expired_count'] = ContractMonitoringService.expired().count()
        return ctx


# ──────────────────────────────────────────────────────────────────
# Employee Management
# ──────────────────────────────────────────────────────────────────

class EmployeeListView(HRViewRequiredMixin, ListView):
    permission_code = 'staff.view'
    model = Employee
    template_name = 'hr/employee_list.html'
    context_object_name = 'employees'
    paginate_by = 20

    def get_queryset(self):
        qs = Employee.objects.select_related('department', 'section', 'staff_level').prefetch_related('education_records')
        q = self.request.GET.get('q', '').strip()
        department = self.request.GET.get('department', '').strip()
        section = self.request.GET.get('section', '').strip()
        employment_type = self.request.GET.get('employment_type', '').strip()
        employment_status = self.request.GET.get('employment_status', '').strip()
        gender = self.request.GET.get('gender', '').strip()
        staff_level = self.request.GET.get('staff_level', '').strip()
        position = self.request.GET.get('position', '').strip()
        education = self.request.GET.get('education', '').strip()
        if q:
            qs = qs.filter(
                Q(full_name__icontains=q) |
                Q(employee_number__icontains=q) |
                Q(position__icontains=q) |
                Q(email__icontains=q) |
                Q(section__name__icontains=q) |
                Q(education_records__degree__icontains=q) |
                Q(education_records__institution__icontains=q) |
                Q(education_records__field_of_study__icontains=q)
            )
        if department:
            qs = qs.filter(department_id=department)
        if section:
            qs = qs.filter(section_id=section)
        if employment_type:
            qs = qs.filter(employment_type=employment_type)
        if employment_status:
            qs = qs.filter(employment_status=employment_status)
        if gender:
            qs = qs.filter(gender=gender)
        if staff_level:
            qs = qs.filter(staff_level_id=staff_level)
        if position:
            qs = qs.filter(position__icontains=position)
        if education:
            qs = qs.filter(
                Q(education_records__degree__icontains=education) |
                Q(education_records__institution__icontains=education) |
                Q(education_records__field_of_study__icontains=education)
            )
        return qs.distinct().order_by('full_name')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['departments'] = Department.objects.filter(is_active=True).order_by('name')
        ctx['sections'] = DepartmentSection.objects.filter(is_active=True).select_related('department').order_by('department__name', 'order', 'name')
        ctx['staff_levels'] = StaffLevel.objects.filter(is_active=True).order_by('rank', 'name')
        ctx['employment_types'] = Employee.EmploymentType.choices
        ctx['employment_statuses'] = Employee.EmploymentStatus.choices
        ctx['genders'] = Employee.Gender.choices
        ctx['search_query'] = self.request.GET.get('q', '')
        ctx['selected_dept'] = self.request.GET.get('department', '')
        ctx['selected_section'] = self.request.GET.get('section', '')
        ctx['selected_type'] = self.request.GET.get('employment_type', '')
        ctx['selected_status'] = self.request.GET.get('employment_status', '')
        ctx['selected_gender'] = self.request.GET.get('gender', '')
        ctx['selected_staff_level'] = self.request.GET.get('staff_level', '')
        ctx['selected_position'] = self.request.GET.get('position', '')
        ctx['selected_education'] = self.request.GET.get('education', '')
        return ctx


class EmployeeDetailView(HRViewRequiredMixin, DetailView):
    permission_code = 'staff.detail'
    model = Employee
    template_name = 'hr/employee_detail.html'
    context_object_name = 'employee'

    def get_queryset(self):
        return Employee.objects.select_related('department', 'section', 'staff_level').prefetch_related(
            'education_records', 'documents'
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['documents'] = self.object.documents.all()
        ctx['education_records'] = self.object.education_records.all()
        ctx['doc_form'] = EmployeeDocumentForm()
        return ctx


class EmployeeCreateView(HRManagementRequiredMixin, CreateView):
    permission_code = 'staff.create'
    model = Employee
    form_class = EmployeeForm
    template_name = 'hr/employee_form.html'

    def get_success_url(self):
        return reverse_lazy('hr:employee_detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        response = super().form_valid(form)
        HRAuditService.log(
            self.request, 'HR_EMPLOYEE_CREATED',
            {'employee_id': self.object.pk, 'name': self.object.full_name}
        )
        messages.success(self.request, _("Employee record created successfully."))
        return response

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['page_title'] = _('Add New Employee')
        ctx['employee'] = None
        return ctx


class EmployeeUpdateView(HRManagementRequiredMixin, UpdateView):
    permission_code = 'staff.edit'
    model = Employee
    form_class = EmployeeForm
    template_name = 'hr/employee_form.html'

    def get_success_url(self):
        return reverse_lazy('hr:employee_detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        old = Employee.objects.get(pk=self.object.pk)
        response = super().form_valid(form)
        HRAuditService.log(
            self.request, 'HR_EMPLOYEE_UPDATED',
            {'employee_id': self.object.pk, 'name': self.object.full_name, 'status': self.object.employment_status}
        )
        messages.success(self.request, _("Employee record updated successfully."))
        return response

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['page_title'] = _('Edit Employee')
        ctx['employee'] = self.object
        ctx['education_form'] = EmployeeEducationForm()
        ctx['education_records'] = self.object.education_records.all()
        return ctx


class EmployeeDeleteView(HRManagementRequiredMixin, DeleteView):
    permission_code = 'staff.delete'
    model = Employee
    template_name = 'hr/employee_confirm_delete.html'
    success_url = reverse_lazy('hr:employee_list')

    def form_valid(self, form):
        HRAuditService.log(
            self.request, 'HR_EMPLOYEE_DELETED',
            {'employee_id': self.object.pk, 'name': self.object.full_name}
        )
        messages.success(self.request, _("Employee record deleted."))
        return super().form_valid(form)


class EmployeeEducationCreateView(HRManagementRequiredMixin, CreateView):
    permission_code = 'staff.edit'
    model = EmployeeEducation
    form_class = EmployeeEducationForm
    template_name = 'hr/education_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.employee = get_object_or_404(Employee, pk=kwargs['employee_pk'])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.employee = self.employee
        response = super().form_valid(form)
        HRAuditService.log(self.request, 'HR_EDUCATION_CREATED', {
            'employee_id': self.employee.pk, 'education_id': self.object.pk, 'degree': self.object.degree,
        })
        messages.success(self.request, _("Education record added."))
        return response

    def get_success_url(self):
        next_url = self.request.POST.get('next') or self.request.GET.get('next')
        if next_url and url_has_allowed_host_and_scheme(
            next_url, allowed_hosts={self.request.get_host()}, require_https=self.request.is_secure()
        ):
            return next_url
        return reverse_lazy('hr:employee_detail', kwargs={'pk': self.employee.pk}) + '#tab-education'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['employee'] = self.employee
        context['page_title'] = _('Add Education')
        context['next_url'] = self.request.GET.get('next', '')
        return context


class EmployeeEducationUpdateView(HRManagementRequiredMixin, UpdateView):
    permission_code = 'staff.edit'
    model = EmployeeEducation
    form_class = EmployeeEducationForm
    template_name = 'hr/education_form.html'

    def form_valid(self, form):
        response = super().form_valid(form)
        HRAuditService.log(self.request, 'HR_EDUCATION_UPDATED', {
            'employee_id': self.object.employee_id, 'education_id': self.object.pk, 'degree': self.object.degree,
        })
        messages.success(self.request, _("Education record updated."))
        return response

    def get_success_url(self):
        return reverse_lazy('hr:employee_detail', kwargs={'pk': self.object.employee_id}) + '#tab-education'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['employee'] = self.object.employee
        context['page_title'] = _('Edit Education')
        return context


class EmployeeEducationDeleteView(HRManagementRequiredMixin, DeleteView):
    permission_code = 'staff.delete'
    model = EmployeeEducation
    template_name = 'hr/education_confirm_delete.html'

    def form_valid(self, form):
        employee_id, education_id, degree = self.object.employee_id, self.object.pk, self.object.degree
        response = super().form_valid(form)
        HRAuditService.log(self.request, 'HR_EDUCATION_DELETED', {
            'employee_id': employee_id, 'education_id': education_id, 'degree': degree,
        })
        messages.success(self.request, _("Education record deleted."))
        return response

    def get_success_url(self):
        return reverse_lazy('hr:employee_detail', kwargs={'pk': self.object.employee_id}) + '#tab-education'


class EmployeeDocumentUploadView(HRManagementRequiredMixin, View):
    permission_code = 'staff.edit'
    def post(self, request, pk):
        employee = get_object_or_404(Employee, pk=pk)
        form = EmployeeDocumentForm(request.POST, request.FILES)
        if form.is_valid():
            doc = form.save(commit=False)
            doc.employee = employee
            doc.save()
            HRAuditService.log(
                request, 'HR_DOCUMENT_UPLOADED',
                {'employee_id': employee.pk, 'doc_title': doc.title}
            )
            messages.success(request, _("Document uploaded successfully."))
        else:
            messages.error(request, _("Failed to upload document. Please check the file."))
        return redirect('hr:employee_detail', pk=pk)


class EmployeeDocumentDeleteView(HRManagementRequiredMixin, View):
    permission_code = 'staff.delete'
    def post(self, request, pk):
        doc = get_object_or_404(EmployeeDocument, pk=pk)
        employee_pk = doc.employee.pk
        HRAuditService.log(
            request, 'HR_DOCUMENT_DELETED',
            {'employee_id': employee_pk, 'doc_title': doc.title}
        )
        doc.file.delete(save=False)
        doc.delete()
        messages.success(request, _("Document deleted."))
        return redirect('hr:employee_detail', pk=employee_pk)


class EmployeeDocumentDownloadView(HRViewRequiredMixin, View):
    """Serve confidential employee records only after an HR permission check."""
    permission_code = 'staff.view'

    def get(self, request, pk):
        doc = get_object_or_404(EmployeeDocument, pk=pk)
        if not media_available(doc.file):
            messages.info(request, _("No files or data available."))
            return redirect('hr:employee_detail', pk=doc.employee_id)
        HRAuditService.log(request, 'HR_DOCUMENT_DOWNLOADED', {
            'employee_id': doc.employee_id,
            'document_id': doc.pk,
            'document_type': doc.document_type,
        })
        try:
            return FileResponse(
                doc.file.open('rb'), as_attachment=True,
                filename=doc.file.name.rsplit('/', 1)[-1],
            )
        except (FileNotFoundError, OSError, ValueError):
            messages.info(request, _("No files or data available."))
            return redirect('hr:employee_detail', pk=doc.employee_id)


# ──────────────────────────────────────────────────────────────────
# Department Management
# ──────────────────────────────────────────────────────────────────

class DepartmentListView(HRViewRequiredMixin, ListView):
    permission_code = 'departments.view'
    model = Department
    template_name = 'hr/department_list.html'
    context_object_name = 'departments'
    paginate_by = 20

    def get_queryset(self):
        qs = Department.objects.select_related('head').all()
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(name__icontains=q) | qs.filter(code__icontains=q)
        return qs.order_by('name')


class DepartmentDetailView(HRViewRequiredMixin, DetailView):
    permission_code = 'departments.view'
    model = Department
    template_name = 'hr/department_detail.html'
    context_object_name = 'department'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['employees'] = self.object.employees.select_related('staff_level').order_by('full_name')
        ctx['sections'] = self.object.sections.order_by('order', 'name')
        return ctx


class DepartmentCreateView(HRManagementRequiredMixin, CreateView):
    permission_code = 'departments.create'
    model = Department
    form_class = DepartmentForm
    template_name = 'hr/department_form.html'
    success_url = reverse_lazy('hr:department_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        HRAuditService.log(
            self.request, 'HR_DEPARTMENT_CREATED',
            {'dept_id': self.object.pk, 'name': self.object.name}
        )
        messages.success(self.request, _("Department created successfully."))
        return response

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['page_title'] = _('Add Department')
        return ctx


class DepartmentUpdateView(HRManagementRequiredMixin, UpdateView):
    permission_code = 'departments.edit'
    model = Department
    form_class = DepartmentForm
    template_name = 'hr/department_form.html'
    success_url = reverse_lazy('hr:department_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        HRAuditService.log(
            self.request, 'HR_DEPARTMENT_UPDATED',
            {'dept_id': self.object.pk, 'name': self.object.name}
        )
        messages.success(self.request, _("Department updated."))
        return response

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['page_title'] = _('Edit Department')
        return ctx


class DepartmentDeleteView(HRManagementRequiredMixin, DeleteView):
    permission_code = 'departments.delete'
    model = Department
    template_name = 'hr/department_confirm_delete.html'
    success_url = reverse_lazy('hr:department_list')

    def form_valid(self, form):
        HRAuditService.log(
            self.request, 'HR_DEPARTMENT_DELETED',
            {'dept_id': self.object.pk, 'name': self.object.name}
        )
        messages.success(self.request, _("Department deleted."))
        return super().form_valid(form)


class DepartmentSectionListView(HRViewRequiredMixin, ListView):
    permission_code = 'departments.view'
    model = DepartmentSection
    template_name = 'hr/section_list.html'
    context_object_name = 'sections'
    paginate_by = 20

    def get_queryset(self):
        queryset = DepartmentSection.objects.select_related('department').all()
        department_id = self.request.GET.get('department', '').strip()
        q = self.request.GET.get('q', '').strip()
        if department_id:
            queryset = queryset.filter(department_id=department_id)
        if q:
            queryset = queryset.filter(name__icontains=q) | queryset.filter(code__icontains=q)
        return queryset.order_by('department__name', 'order', 'name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['departments'] = Department.objects.order_by('name')
        context['selected_department'] = self.request.GET.get('department', '')
        context['search_query'] = self.request.GET.get('q', '')
        return context


class DepartmentSectionCreateView(HRManagementRequiredMixin, CreateView):
    permission_code = 'departments.create'
    model = DepartmentSection
    form_class = DepartmentSectionForm
    template_name = 'hr/section_form.html'
    success_url = reverse_lazy('hr:section_list')

    def get_initial(self):
        initial = super().get_initial()
        if self.request.GET.get('department', '').isdigit():
            initial['department'] = self.request.GET['department']
        return initial

    def form_valid(self, form):
        response = super().form_valid(form)
        HRAuditService.log(self.request, 'HR_DEPARTMENT_SECTION_CREATED', {
            'section_id': self.object.pk, 'department_id': self.object.department_id, 'name': self.object.name,
        })
        messages.success(self.request, _("Section created successfully."))
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = _('Add Department Section')
        return context


class DepartmentSectionUpdateView(HRManagementRequiredMixin, UpdateView):
    permission_code = 'departments.edit'
    model = DepartmentSection
    form_class = DepartmentSectionForm
    template_name = 'hr/section_form.html'
    success_url = reverse_lazy('hr:section_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        HRAuditService.log(self.request, 'HR_DEPARTMENT_SECTION_UPDATED', {
            'section_id': self.object.pk, 'department_id': self.object.department_id, 'name': self.object.name,
        })
        messages.success(self.request, _("Section updated."))
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = _('Edit Department Section')
        return context


class DepartmentSectionDeleteView(HRManagementRequiredMixin, DeleteView):
    permission_code = 'departments.delete'
    model = DepartmentSection
    template_name = 'hr/section_confirm_delete.html'
    success_url = reverse_lazy('hr:section_list')

    def form_valid(self, form):
        HRAuditService.log(self.request, 'HR_DEPARTMENT_SECTION_DELETED', {
            'section_id': self.object.pk, 'department_id': self.object.department_id, 'name': self.object.name,
        })
        messages.success(self.request, _("Section deleted."))
        return super().form_valid(form)


# ──────────────────────────────────────────────────────────────────
# Staff Levels
# ──────────────────────────────────────────────────────────────────

class StaffLevelListView(HRManagementRequiredMixin, ListView):
    permission_code = 'staff_levels.view'
    model = StaffLevel
    template_name = 'hr/staff_level_list.html'
    context_object_name = 'staff_levels'

    def get_queryset(self):
        return StaffLevel.objects.order_by('rank', 'name')


class StaffLevelCreateView(HRManagementRequiredMixin, CreateView):
    permission_code = 'staff_levels.create'
    model = StaffLevel
    form_class = StaffLevelForm
    template_name = 'hr/staff_level_form.html'
    success_url = reverse_lazy('hr:staff_level_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, _("Staff level created."))
        return response


class StaffLevelUpdateView(HRManagementRequiredMixin, UpdateView):
    permission_code = 'staff_levels.edit'
    model = StaffLevel
    form_class = StaffLevelForm
    template_name = 'hr/staff_level_form.html'
    success_url = reverse_lazy('hr:staff_level_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, _("Staff level updated."))
        return response


# ──────────────────────────────────────────────────────────────────
# Contract Monitoring
# ──────────────────────────────────────────────────────────────────

class ContractMonitoringView(HRManagementRequiredMixin, TemplateView):
    permission_code = 'contracts.view'
    template_name = 'hr/contract_monitoring.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['expiring_30'] = ContractMonitoringService.expiring_within(30)
        ctx['expiring_60'] = ContractMonitoringService.expiring_within(60)
        ctx['expiring_90'] = ContractMonitoringService.expiring_within(90)
        ctx['expired'] = ContractMonitoringService.expired()
        ctx['recently_renewed'] = ContractMonitoringService.recently_renewed()
        ctx['renew_form'] = ContractRenewForm()
        return ctx


class ContractRenewView(HRManagementRequiredMixin, View):
    permission_code = 'contracts.edit'
    def post(self, request, pk):
        employee = get_object_or_404(Employee, pk=pk)
        form = ContractRenewForm(request.POST)
        if form.is_valid():
            old_end = employee.contract_end_date
            employee.contract_end_date = form.cleaned_data['new_contract_end_date']
            if form.cleaned_data.get('notes'):
                employee.notes = (employee.notes or '') + f"\n[{timezone.localdate()}] Contract renewed: {form.cleaned_data['notes']}"
            employee.save()
            HRAuditService.log(
                request, 'HR_CONTRACT_RENEWED',
                {'employee_id': employee.pk, 'name': employee.full_name,
                 'old_end_date': str(old_end), 'new_end_date': str(employee.contract_end_date)}
            )
            messages.success(request, _("Contract renewed successfully."))
        else:
            messages.error(request, _("Invalid renewal date."))
        return redirect('hr:contract_monitoring')


class ContractMarkExpiredView(HRManagementRequiredMixin, View):
    permission_code = 'contracts.edit'
    def post(self, request, pk):
        employee = get_object_or_404(Employee, pk=pk)
        employee.employment_status = Employee.EmploymentStatus.TERMINATED
        employee.save()
        HRAuditService.log(
            request, 'HR_CONTRACT_MARKED_EXPIRED',
            {'employee_id': employee.pk, 'name': employee.full_name}
        )
        messages.success(request, _("Contract marked as expired. Employee status set to Terminated."))
        return redirect('hr:contract_monitoring')


# ──────────────────────────────────────────────────────────────────
# HR Reports
# ──────────────────────────────────────────────────────────────────

class HRReportView(HRManagementRequiredMixin, FormView):
    permission_code = 'hr_dashboard.reports'
    template_name = 'hr/reports.html'
    form_class = HRReportFilterForm

    def get(self, request, *args, **kwargs):
        form = self.get_form()
        if any(request.GET.values()):
            form = HRReportFilterForm(request.GET)
            if form.is_valid():
                employees = HRReportService.get_filtered_queryset(
                    department=form.cleaned_data.get('department') or None,
                    gender=form.cleaned_data.get('gender') or None,
                    employment_type=form.cleaned_data.get('employment_type') or None,
                    staff_level=form.cleaned_data.get('staff_level') or None,
                    employment_status=form.cleaned_data.get('employment_status') or None,
                    section=form.cleaned_data.get('section') or None,
                    position=form.cleaned_data.get('position') or None,
                    education=form.cleaned_data.get('education') or None,
                    date_from=form.cleaned_data.get('date_from') or None,
                    date_to=form.cleaned_data.get('date_to') or None,
                )
            else:
                employees = HRReportService.get_filtered_queryset()
        else:
            employees = HRReportService.get_filtered_queryset()

        return self.render_to_response(self.get_context_data(form=form, employees=employees))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['employees'] = kwargs.get('employees')
        ctx['export_field_groups'] = HRReportFilterForm.EXPORT_FIELD_GROUPS
        return ctx


class HRReportExportView(HRManagementRequiredMixin, View):
    permission_code = 'hr_dashboard.export_reports'
    def handle_export(self, request):
        data = request.POST if request.method == 'POST' else request.GET
        export_format = data.get('format', 'excel').lower()
        data_sections = data.getlist('data_sections')
        valid_sections = {choice for choice, _label in HRReportFilterForm.EXPORT_TABLE_CHOICES}
        data_sections = [section for section in data_sections if section in valid_sections]
        export_fields = data.getlist('export_fields')
        valid_fields = {choice for choice, _label in HRReportFilterForm.EXPORT_FIELD_CHOICES}
        export_fields = [field for field in export_fields if field in valid_fields]
        if not data_sections:
            messages.error(request, _("Select at least one table to export."))
            return redirect('hr:reports')
        if export_fields:
            data_sections = [
                section for section in data_sections
                if any(field.startswith(f'{section}:') for field in export_fields)
            ]
            if not data_sections:
                messages.error(request, _("Select at least one field for a selected table."))
                return redirect('hr:reports')

        # Parse selected employee IDs if provided
        raw_selected = data.getlist('selected_ids')
        selected_ids = []
        for val in raw_selected:
            if isinstance(val, str) and ',' in val:
                selected_ids.extend([v.strip() for v in val.split(',') if v.strip().isdigit()])
            elif str(val).isdigit():
                selected_ids.append(int(val))

        qs = HRReportService.get_filtered_queryset(
            selected_ids=selected_ids or None,
            q=data.get('q', '').strip() or None,
            position=data.get('position', '').strip() or None,
            section=data.get('section') or None,
            education=data.get('education', '').strip() or None,
            department=data.get('department') or None,
            gender=data.get('gender') or None,
            employment_type=data.get('employment_type') or None,
            staff_level=data.get('staff_level') or None,
            employment_status=data.get('employment_status') or None,
            date_from=data.get('date_from') or None,
            date_to=data.get('date_to') or None,
        )

        HRAuditService.log(request, 'HR_REPORT_EXPORTED', {
            'format': export_format,
            'data_sections': data_sections,
            'export_fields': export_fields,
            'count': qs.count(),
            'selected_only': bool(selected_ids),
        })

        filename_base = f"dnmg_hr_export_{timezone.localdate()}"

        if export_format == 'excel':
            response = HttpResponse(
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = f'attachment; filename="{filename_base}.xlsx"'
            HRReportService.export_excel(qs, response, data_sections, data.get('department') or None, export_fields)
            return response

        if export_format == 'pdf':
            response = HttpResponse(content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{filename_base}.pdf"'
            HRReportService.export_pdf(qs, response, data_sections, data.get('department') or None, export_fields)
            return response

        if export_format == 'csv':
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="{filename_base}.csv"'
            HRReportService.export_csv(qs, response, data_sections, data.get('department') or None, export_fields)
            return response

        messages.error(request, _("Unsupported export format."))
        return redirect('hr:employee_list')

    def get(self, request, *args, **kwargs):
        return self.handle_export(request)

    def post(self, request, *args, **kwargs):
        return self.handle_export(request)



# ──────────────────────────────────────────────────────────────────
# Downloads Module
# ──────────────────────────────────────────────────────────────────

class DownloadListView(HRViewRequiredMixin, ListView):
    permission_code = 'downloads.view'
    model = DownloadableFile
    template_name = 'hr/download_list.html'
    context_object_name = 'files'
    paginate_by = 20

    def get_queryset(self):
        qs = DownloadableFile.objects.select_related('category', 'uploaded_by').all()
        # Non-HR-managers see staff-level files; managers see all
        if not self.request.user.can_manage_hr:
            qs = qs.filter(access_level=DownloadableFile.AccessLevel.STAFF)
        q = self.request.GET.get('q', '').strip()
        category = self.request.GET.get('category', '').strip()
        file_type = self.request.GET.get('file_type', '').strip()
        if q:
            qs = qs.filter(title__icontains=q) | qs.filter(tags__icontains=q) | qs.filter(description__icontains=q)
        if category:
            qs = qs.filter(category_id=category)
        if file_type:
            qs = qs.filter(file_type=file_type)
        return qs.order_by('-created_at')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['categories'] = DownloadCategory.objects.order_by('order', 'name')
        ctx['file_types'] = DownloadableFile.FileType.choices
        ctx['search_query'] = self.request.GET.get('q', '')
        return ctx


class DownloadCreateView(HRManagementRequiredMixin, CreateView):
    permission_code = 'downloads.upload'
    model = DownloadableFile
    form_class = DownloadableFileForm
    template_name = 'hr/download_form.html'
    success_url = reverse_lazy('hr:download_list')

    def form_valid(self, form):
        form.instance.uploaded_by = self.request.user
        response = super().form_valid(form)
        HRAuditService.log(
            self.request, 'HR_DOWNLOAD_UPLOADED',
            {'file_id': str(self.object.id), 'title': self.object.title}
        )
        messages.success(self.request, _("File uploaded successfully."))
        return response


class DownloadUpdateView(HRManagementRequiredMixin, UpdateView):
    permission_code = 'downloads.edit'
    model = DownloadableFile
    form_class = DownloadableFileForm
    template_name = 'hr/download_form.html'
    success_url = reverse_lazy('hr:download_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, _("File updated."))
        return response


class DownloadDeleteView(HRManagementRequiredMixin, DeleteView):
    permission_code = 'downloads.delete'
    model = DownloadableFile
    template_name = 'hr/download_confirm_delete.html'
    success_url = reverse_lazy('hr:download_list')

    def form_valid(self, form):
        HRAuditService.log(
            self.request, 'HR_DOWNLOAD_DELETED',
            {'file_id': str(self.object.id), 'title': self.object.title}
        )
        self.object.file.delete(save=False)
        messages.success(self.request, _("File deleted."))
        return super().form_valid(form)


class FileDownloadTrackerView(HRViewRequiredMixin, View):
    permission_code = 'downloads.download'
    """Serves the file, increments download_count, and logs the download."""
    def get(self, request, pk):
        dl_file = get_object_or_404(DownloadableFile, pk=pk)
        if not media_available(dl_file.file):
            messages.info(request, _("No files or data available."))
            return redirect('hr:download_list')
        # Staff-only files require management or view access (already enforced by mixin)
        dl_file.download_count += 1
        dl_file.save(update_fields=['download_count'])
        HRAuditService.log(
            request, 'HR_FILE_DOWNLOADED',
            {'file_id': str(dl_file.id), 'title': dl_file.title, 'count': dl_file.download_count}
        )
        try:
            return FileResponse(dl_file.file.open('rb'), as_attachment=True, filename=dl_file.file.name.split('/')[-1])
        except (FileNotFoundError, OSError, ValueError):
            messages.info(request, _("No files or data available."))
            return redirect('hr:download_list')
