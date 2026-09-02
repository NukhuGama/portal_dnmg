import uuid
from django.db import models
from django.db.models import F, Q
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.conf import settings


class Department(models.Model):
    """DNMG Department model."""
    name = models.CharField(_('Department Name'), max_length=150, unique=True)
    code = models.CharField(_('Department Code'), max_length=20, unique=True)
    description = models.TextField(_('Description'), blank=True)
    # head is set after Employee model is defined (use string ref)
    head = models.ForeignKey(
        'Employee', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='leads_department', verbose_name=_('Head of Department')
    )
    is_active = models.BooleanField(_('Active'), default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Department')
        verbose_name_plural = _('Departments')
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.code})"

    def clean(self):
        super().clean()
        if self.head_id and self.head.department_id != self.pk:
            raise ValidationError({
                'head': _('The department head must be assigned to this department.'),
            })

    @property
    def employee_count(self):
        return self.employees.filter(employment_status=Employee.EmploymentStatus.ACTIVE).count()

    @property
    def section_count(self):
        return self.sections.filter(is_active=True).count()


class DepartmentSection(models.Model):
    """An organisational section belonging to one department."""

    department = models.ForeignKey(
        Department, on_delete=models.CASCADE, related_name='sections',
        verbose_name=_('Department')
    )
    name = models.CharField(_('Section Name'), max_length=150)
    code = models.CharField(_('Section Code'), max_length=30, blank=True)
    description = models.TextField(_('Description'), blank=True)
    order = models.PositiveSmallIntegerField(_('Display Order'), default=0)
    is_active = models.BooleanField(_('Active'), default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Department Section')
        verbose_name_plural = _('Department Sections')
        ordering = ['department__name', 'order', 'name']
        constraints = [
            models.UniqueConstraint(fields=['department', 'name'], name='unique_section_name_per_department'),
            models.UniqueConstraint(
                fields=['department', 'code'],
                condition=~Q(code=''),
                name='unique_nonblank_section_code_per_dept',
            ),
        ]

    def __str__(self):
        return f"{self.department.name} – {self.name}"

    def clean(self):
        super().clean()
        if not self.pk:
            return
        mismatched_employee_exists = self.employees.exclude(
            department_id=self.department_id
        ).exists()
        if mismatched_employee_exists:
            raise ValidationError({
                'department': _(
                    'This section cannot move to another department while it has employees '
                    'assigned to its current department.'
                ),
            })


class StaffLevel(models.Model):
    """Configurable staff grades / hierarchy levels."""
    name = models.CharField(_('Level Name'), max_length=100, unique=True)
    code = models.CharField(_('Code'), max_length=30, unique=True)
    rank = models.PositiveSmallIntegerField(
        _('Rank Order'), default=0,
        help_text=_('Lower number = higher rank (1 = most senior)')
    )
    description = models.TextField(_('Description'), blank=True)
    is_active = models.BooleanField(_('Active'), default=True)

    class Meta:
        verbose_name = _('Staff Level')
        verbose_name_plural = _('Staff Levels')
        ordering = ['rank', 'name']

    def __str__(self):
        return f"{self.name} ({self.code})"


class Employee(models.Model):
    """Core Employee record."""

    class Gender(models.TextChoices):
        MALE = 'M', _('Male')
        FEMALE = 'F', _('Female')
        OTHER = 'O', _('Other')

    class EmploymentType(models.TextChoices):
        PERMANENT = 'PERMANENT', _('Permanent')
        CONTRACT = 'CONTRACT', _('Contract')
        CONSULTANT = 'CONSULTANT', _('Consultant')
        INTERN = 'INTERN', _('Intern')

    class EmploymentStatus(models.TextChoices):
        ACTIVE = 'ACTIVE', _('Active')
        ON_LEAVE = 'ON_LEAVE', _('On Leave')
        RETIRED = 'RETIRED', _('Retired')
        RESIGNED = 'RESIGNED', _('Resigned')
        TERMINATED = 'TERMINATED', _('Terminated')

    # Identification
    employee_number = models.CharField(_('Employee Number'), max_length=30, unique=True)
    user_account = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='employee_profile',
        verbose_name=_('Linked User Account')
    )
    photo = models.ImageField(
        _('Photo'), upload_to='hr/photos/', blank=True, null=True
    )

    # Personal Info
    full_name = models.CharField(_('Full Name'), max_length=200)
    gender = models.CharField(_('Gender'), max_length=1, choices=Gender.choices)
    date_of_birth = models.DateField(_('Date of Birth'), null=True, blank=True)
    nationality = models.CharField(_('Nationality'), max_length=100, default='Timorese')

    # Contact
    phone = models.CharField(_('Phone Number'), max_length=30, blank=True)
    email = models.EmailField(_('Email Address'), blank=True)

    # Employment Details
    department = models.ForeignKey(
        Department, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='employees', verbose_name=_('Department')
    )
    section = models.ForeignKey(
        DepartmentSection, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='employees', verbose_name=_('Section')
    )
    position = models.CharField(_('Position / Job Title'), max_length=150)
    employment_type = models.CharField(
        _('Employment Type'), max_length=20, choices=EmploymentType.choices,
        default=EmploymentType.PERMANENT
    )
    staff_level = models.ForeignKey(
        StaffLevel, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='employees', verbose_name=_('Staff Level / Grade')
    )

    # Contract Dates
    start_date = models.DateField(_('Start Date'))
    contract_end_date = models.DateField(_('Contract End Date'), null=True, blank=True)

    # Status
    employment_status = models.CharField(
        _('Employment Status'), max_length=20,
        choices=EmploymentStatus.choices, default=EmploymentStatus.ACTIVE
    )

    # Extra
    notes = models.TextField(_('Notes'), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Employee')
        verbose_name_plural = _('Employees')
        ordering = ['full_name']
        constraints = [
            models.CheckConstraint(
                condition=Q(gender__in=['M', 'F', 'O']),
                name='hr_employee_gender_valid',
            ),
            models.CheckConstraint(
                condition=Q(employment_type__in=['PERMANENT', 'CONTRACT', 'CONSULTANT', 'INTERN']),
                name='hr_employee_type_valid',
            ),
            models.CheckConstraint(
                condition=Q(employment_status__in=['ACTIVE', 'ON_LEAVE', 'RETIRED', 'RESIGNED', 'TERMINATED']),
                name='hr_employee_status_valid',
            ),
            models.CheckConstraint(
                condition=Q(contract_end_date__isnull=True) | Q(contract_end_date__gte=F('start_date')),
                name='hr_employee_contract_dates_valid',
            ),
        ]
        indexes = [
            models.Index(fields=['department', 'employment_status'], name='hr_employee_dept_status_idx'),
            models.Index(fields=['section', 'employment_status'], name='hr_emp_section_status_idx'),
            models.Index(fields=['employment_status', 'contract_end_date'], name='hr_emp_status_contract_idx'),
        ]

    def __str__(self):
        return f"{self.full_name} [{self.employee_number}]"

    def clean(self):
        super().clean()
        if not self.section_id:
            return
        section_department_id = self.section.department_id
        if self.department_id is None:
            self.department_id = section_department_id
        elif self.department_id != section_department_id:
            raise ValidationError({
                'section': _('The selected section belongs to a different department.'),
            })

    @property
    def age(self):
        if self.date_of_birth:
            today = timezone.localdate()
            return today.year - self.date_of_birth.year - (
                (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
            )
        return None

    @property
    def contract_days_remaining(self):
        if self.contract_end_date:
            return (self.contract_end_date - timezone.localdate()).days
        return None

    @property
    def is_contract_expiring_soon(self):
        remaining = self.contract_days_remaining
        return remaining is not None and 0 <= remaining <= 90

    @property
    def is_contract_expired(self):
        remaining = self.contract_days_remaining
        return remaining is not None and remaining < 0


class EmployeeEducation(models.Model):
    """A qualification recorded against an employee; staff may have many."""

    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name='education_records',
        verbose_name=_('Employee')
    )
    degree = models.CharField(_('Degree / Qualification'), max_length=150)
    institution = models.CharField(_('Institution'), max_length=200)
    field_of_study = models.CharField(_('Field of Study'), max_length=150, blank=True)
    year_completed = models.PositiveSmallIntegerField(_('Year Completed'), null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Education Record')
        verbose_name_plural = _('Education Records')
        ordering = ['-year_completed', '-id']
        constraints = [
            models.CheckConstraint(
                condition=Q(year_completed__isnull=True) | Q(year_completed__gte=1900),
                name='hr_education_year_valid',
            ),
        ]
        indexes = [
            models.Index(fields=['employee', '-year_completed'], name='hr_education_employee_year_idx'),
        ]

    def __str__(self):
        return f"{self.employee.full_name} – {self.degree}"


class EmployeeDocument(models.Model):
    """Documents attached to an employee (contract, ID, certificates, etc.)."""

    class DocumentType(models.TextChoices):
        CONTRACT = 'CONTRACT', _('Contract')
        ID = 'ID', _('Identification')
        CERTIFICATE = 'CERTIFICATE', _('Certificate')
        OTHER = 'OTHER', _('Other')

    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE,
        related_name='documents', verbose_name=_('Employee')
    )
    title = models.CharField(_('Document Title'), max_length=200)
    document_type = models.CharField(
        _('Document Type'), max_length=20, choices=DocumentType.choices,
        default=DocumentType.OTHER
    )
    file = models.FileField(_('File'), upload_to='hr/documents/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Employee Document')
        verbose_name_plural = _('Employee Documents')
        ordering = ['-uploaded_at']
        constraints = [
            models.CheckConstraint(
                condition=Q(document_type__in=['CONTRACT', 'ID', 'CERTIFICATE', 'OTHER']),
                name='hr_document_type_valid',
            ),
        ]

    def __str__(self):
        return f"{self.employee.full_name} – {self.title}"


# ─────────────────────────────────────────────
# Downloads Module
# ─────────────────────────────────────────────

class DownloadCategory(models.Model):
    """Category for downloadable files."""
    name = models.CharField(_('Category Name'), max_length=100, unique=True)
    slug = models.SlugField(unique=True)
    description = models.TextField(_('Description'), blank=True)
    order = models.PositiveSmallIntegerField(_('Display Order'), default=0)

    class Meta:
        verbose_name = _('Download Category')
        verbose_name_plural = _('Download Categories')
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


class DownloadableFile(models.Model):
    """Centralized downloadable files hub."""

    class FileType(models.TextChoices):
        PDF = 'PDF', _('PDF Document')
        EXCEL = 'EXCEL', _('Excel Spreadsheet')
        WORD = 'WORD', _('Word Document')
        ZIP = 'ZIP', _('ZIP Archive')
        IMAGE = 'IMAGE', _('Image')
        OTHER = 'OTHER', _('Other')

    class AccessLevel(models.TextChoices):
        PUBLIC = 'PUBLIC', _('Public (Visible on public website)')
        STAFF = 'STAFF', _('Staff Only (Internal access required)')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(_('Title'), max_length=255)
    category = models.ForeignKey(
        DownloadCategory, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='files', verbose_name=_('Category')
    )
    description = models.TextField(_('Description'), blank=True)
    tags = models.CharField(
        _('Tags'), max_length=500, blank=True,
        help_text=_('Comma-separated tags for search')
    )
    file = models.FileField(_('File'), upload_to='hr/downloads/')
    file_type = models.CharField(
        _('File Type'), max_length=10, choices=FileType.choices, default=FileType.OTHER
    )
    version = models.CharField(_('Version'), max_length=30, blank=True, default='1.0')
    access_level = models.CharField(
        _('Access Level'), max_length=10,
        choices=AccessLevel.choices, default=AccessLevel.STAFF
    )
    download_count = models.PositiveIntegerField(_('Download Count'), default=0)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='uploaded_downloads',
        verbose_name=_('Uploaded By')
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Downloadable File')
        verbose_name_plural = _('Downloadable Files')
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                condition=Q(file_type__in=['PDF', 'EXCEL', 'WORD', 'ZIP', 'IMAGE', 'OTHER']),
                name='hr_download_file_type_valid',
            ),
            models.CheckConstraint(
                condition=Q(access_level__in=['PUBLIC', 'STAFF']),
                name='hr_download_access_valid',
            ),
        ]
        indexes = [
            models.Index(fields=['access_level', '-created_at'], name='hr_download_access_created_idx'),
            models.Index(fields=['category', '-created_at'], name='hr_download_cat_created_idx'),
        ]

    def __str__(self):
        return f"{self.title} (v{self.version})"

    @property
    def is_public(self):
        return self.access_level == self.AccessLevel.PUBLIC
