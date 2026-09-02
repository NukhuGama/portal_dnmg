from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from pathlib import Path
from django.utils.translation import gettext_lazy as _
from core.widgets import AdminFileInput
from .models import (
    Employee, EmployeeEducation, EmployeeDocument, Department, DepartmentSection,
    StaffLevel, DownloadableFile, DownloadCategory,
)


class RestrictedUploadFormMixin:
    """Validate size and allow-listed extensions before files reach storage."""

    allowed_extensions = frozenset()

    def clean_file(self):
        uploaded_file = self.cleaned_data.get('file')
        if not uploaded_file:
            return uploaded_file
        extension = Path(uploaded_file.name).suffix.lower()
        if extension not in self.allowed_extensions:
            raise ValidationError(_('This file type is not allowed.'))
        if uploaded_file.size > settings.MAX_UPLOAD_SIZE:
            limit_mb = settings.MAX_UPLOAD_SIZE // (1024 * 1024)
            raise ValidationError(_('Files must be %(limit)s MB or smaller.'), params={'limit': limit_mb})
        return uploaded_file


class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ['name', 'code', 'description', 'head', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('e.g. Meteorology Division')}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('e.g. MET-DIV')}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'head': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class DepartmentSectionForm(forms.ModelForm):
    class Meta:
        model = DepartmentSection
        fields = ['department', 'name', 'code', 'description', 'order', 'is_active']
        widgets = {
            'department': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class StaffLevelForm(forms.ModelForm):
    class Meta:
        model = StaffLevel
        fields = ['name', 'code', 'rank', 'description', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('e.g. Senior Officer')}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('e.g. SNR-OFF')}),
            'rank': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class EmployeeForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = [
            'employee_number', 'user_account', 'photo',
            'full_name', 'gender', 'date_of_birth', 'nationality',
            'phone', 'email',
            'department', 'section', 'position', 'employment_type', 'staff_level',
            'start_date', 'contract_end_date', 'employment_status',
            'notes',
        ]
        widgets = {
            'employee_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('e.g. DNMG-2024-001')}),
            'user_account': forms.Select(attrs={'class': 'form-select'}),
            'photo': AdminFileInput(attrs={'class': 'form-control'}),
            'full_name': forms.TextInput(attrs={'class': 'form-control'}),
            'gender': forms.Select(attrs={'class': 'form-select'}),
            'date_of_birth': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'nationality': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'department': forms.Select(attrs={'class': 'form-select'}),
            'section': forms.Select(attrs={'class': 'form-select'}),
            'position': forms.TextInput(attrs={'class': 'form-control'}),
            'employment_type': forms.Select(attrs={'class': 'form-select'}),
            'staff_level': forms.Select(attrs={'class': 'form-select'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'contract_end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'employment_status': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        department = cleaned_data.get('department')
        section = cleaned_data.get('section')
        if not section:
            return cleaned_data
        if department is None:
            cleaned_data['department'] = section.department
        elif section.department_id != department.pk:
            self.add_error('section', _('The selected section belongs to a different department.'))
        return cleaned_data


class EmployeeEducationForm(forms.ModelForm):
    class Meta:
        model = EmployeeEducation
        fields = ['degree', 'institution', 'field_of_study', 'year_completed']
        widgets = {
            'degree': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('e.g. Master’s Degree')}),
            'institution': forms.TextInput(attrs={'class': 'form-control'}),
            'field_of_study': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('e.g. Meteorology')}),
            'year_completed': forms.NumberInput(attrs={'class': 'form-control', 'min': 1900, 'max': 2100}),
        }


class EmployeeDocumentForm(RestrictedUploadFormMixin, forms.ModelForm):
    allowed_extensions = frozenset({
        '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.odt', '.ods', '.rtf',
        '.txt', '.csv', '.zip', '.jpg', '.jpeg', '.png',
    })
    class Meta:
        model = EmployeeDocument
        fields = ['title', 'document_type', 'file']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('e.g. Employment Contract 2024')}),
            'document_type': forms.Select(attrs={'class': 'form-select'}),
            'file': AdminFileInput(attrs={'class': 'form-control'}),
        }


class ContractRenewForm(forms.Form):
    new_contract_end_date = forms.DateField(
        label=_('New Contract End Date'),
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    notes = forms.CharField(
        label=_('Renewal Notes'),
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2})
    )


class HRReportFilterForm(forms.Form):
    EXPORT_TABLE_CHOICES = (
        ('staff_directory', _('Staff Directory')),
        ('staff_information', _('Staff Information')),
        ('employment_details', _('Employment Details')),
        ('education_information', _('Education Information')),
        ('staff_documents', _('Staff Documents')),
        ('departments', _('Departments')),
        ('sections', _('Sections')),
    )
    EXPORT_FIELD_GROUPS = (
        ('staff_directory', _('Staff Directory'), (
            ('staff_directory:employee_number', _('Employee Number')),
            ('staff_directory:full_name', _('Name')),
            ('staff_directory:department', _('Department')),
            ('staff_directory:section', _('Section')),
            ('staff_directory:position', _('Position')),
            ('staff_directory:education_summary', _('Education')),
            ('staff_directory:employment_type', _('Employment Type')),
            ('staff_directory:staff_level', _('Staff Level')),
            ('staff_directory:employment_status', _('Employment Status')),
            ('staff_directory:phone', _('Phone')),
            ('staff_directory:email', _('Email')),
        )),
        ('staff_information', _('Staff Information'), (
            ('staff_information:employee_number', _('Employee Number')),
            ('staff_information:full_name', _('Name')),
            ('staff_information:gender', _('Gender')),
            ('staff_information:date_of_birth', _('Date of Birth')),
            ('staff_information:nationality', _('Nationality')),
            ('staff_information:phone', _('Phone')),
            ('staff_information:email', _('Email')),
        )),
        ('employment_details', _('Employment Details'), (
            ('employment_details:employee_number', _('Employee Number')),
            ('employment_details:full_name', _('Name')),
            ('employment_details:department', _('Department')),
            ('employment_details:section', _('Section')),
            ('employment_details:position', _('Position')),
            ('employment_details:employment_type', _('Employment Type')),
            ('employment_details:staff_level', _('Staff Level')),
            ('employment_details:start_date', _('Start Date')),
            ('employment_details:contract_end_date', _('Contract End Date')),
            ('employment_details:employment_status', _('Employment Status')),
        )),
        ('education_information', _('Education Information'), (
            ('education_information:employee_number', _('Employee Number')),
            ('education_information:employee_name', _('Name')),
            ('education_information:department', _('Department')),
            ('education_information:degree', _('Degree / Qualification')),
            ('education_information:institution', _('Institution')),
            ('education_information:field_of_study', _('Field of Study')),
            ('education_information:year_completed', _('Year Completed')),
        )),
        ('staff_documents', _('Staff Documents'), (
            ('staff_documents:employee_number', _('Employee Number')),
            ('staff_documents:employee_name', _('Name')),
            ('staff_documents:title', _('Document Title')),
            ('staff_documents:document_type', _('Document Type')),
            ('staff_documents:uploaded_at', _('Uploaded Date')),
        )),
        ('departments', _('Departments'), (
            ('departments:name', _('Department')),
            ('departments:code', _('Code')),
            ('departments:head', _('Head of Department')),
            ('departments:active_sections', _('Active Sections')),
            ('departments:status', _('Status')),
        )),
        ('sections', _('Sections'), (
            ('sections:department', _('Department')),
            ('sections:name', _('Section')),
            ('sections:code', _('Code')),
            ('sections:description', _('Description')),
            ('sections:order', _('Display Order')),
            ('sections:status', _('Status')),
        )),
    )
    EXPORT_FIELD_CHOICES = tuple(
        choice for _section, _label, choices in EXPORT_FIELD_GROUPS for choice in choices
    )

    data_sections = forms.MultipleChoiceField(
        label=_('Tables to Include'),
        choices=EXPORT_TABLE_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'})
    )
    export_fields = forms.MultipleChoiceField(
        label=_('Fields to Include'),
        choices=EXPORT_FIELD_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'})
    )
    department = forms.ChoiceField(
        label=_('Department'), required=False,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    section = forms.ChoiceField(
        label=_('Section'), required=False,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    gender = forms.ChoiceField(
        label=_('Gender'), required=False,
        choices=[('', _('All Genders'))] + list(Employee.Gender.choices),
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    employment_type = forms.ChoiceField(
        label=_('Employment Type'), required=False,
        choices=[('', _('All Types'))] + list(Employee.EmploymentType.choices),
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    staff_level = forms.ChoiceField(
        label=_('Staff Level'), required=False,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    employment_status = forms.ChoiceField(
        label=_('Employment Status'), required=False,
        choices=[('', _('All Statuses'))] + list(Employee.EmploymentStatus.choices),
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    position = forms.CharField(
        label=_('Position'), required=False,
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': _('e.g. Officer')})
    )
    education = forms.CharField(
        label=_('Education'), required=False,
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': _('Degree, institution, or field')})
    )
    date_from = forms.DateField(
        label=_('Start Date From'), required=False,
        widget=forms.DateInput(attrs={'class': 'form-control form-control-sm', 'type': 'date'})
    )
    date_to = forms.DateField(
        label=_('Start Date To'), required=False,
        widget=forms.DateInput(attrs={'class': 'form-control form-control-sm', 'type': 'date'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        dept_choices = [('', _('All Departments'))] + [
            (d.id, d.name) for d in Department.objects.filter(is_active=True).order_by('name')
        ]
        level_choices = [('', _('All Levels'))] + [
            (sl.id, sl.name) for sl in StaffLevel.objects.filter(is_active=True).order_by('rank')
        ]
        section_choices = [('', _('All Sections'))] + [
            (section.id, f'{section.department.code} · {section.name}')
            for section in DepartmentSection.objects.filter(is_active=True).select_related('department').order_by(
                'department__name', 'order', 'name'
            )
        ]
        self.fields['department'].choices = dept_choices
        self.fields['staff_level'].choices = level_choices
        self.fields['section'].choices = section_choices


class DownloadableFileForm(RestrictedUploadFormMixin, forms.ModelForm):
    allowed_extensions = frozenset({
        '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.odt', '.ods', '.rtf',
        '.txt', '.csv', '.zip', '.jpg', '.jpeg', '.png', '.webp',
    })
    class Meta:
        model = DownloadableFile
        fields = ['title', 'category', 'description', 'tags', 'file', 'file_type', 'version', 'access_level']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'tags': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('e.g. annual, report, 2024')}),
            'file': AdminFileInput(attrs={'class': 'form-control'}),
            'file_type': forms.Select(attrs={'class': 'form-select'}),
            'version': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('e.g. 1.0')}),
            'access_level': forms.Select(attrs={'class': 'form-select'}),
        }


class DownloadCategoryForm(forms.ModelForm):
    class Meta:
        model = DownloadCategory
        fields = ['name', 'slug', 'description', 'order']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'slug': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
        }
