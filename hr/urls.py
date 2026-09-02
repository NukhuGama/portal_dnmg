from django.urls import path
from . import views

app_name = 'hr'

urlpatterns = [
    # Dashboard
    path('', views.HRDashboardView.as_view(), name='dashboard'),

    # Employee Management
    path('employees/', views.EmployeeListView.as_view(), name='employee_list'),
    path('employees/add/', views.EmployeeCreateView.as_view(), name='employee_create'),
    path('employees/<int:pk>/', views.EmployeeDetailView.as_view(), name='employee_detail'),
    path('employees/<int:pk>/edit/', views.EmployeeUpdateView.as_view(), name='employee_update'),
    path('employees/<int:pk>/delete/', views.EmployeeDeleteView.as_view(), name='employee_delete'),
    path('employees/<int:employee_pk>/education/add/', views.EmployeeEducationCreateView.as_view(), name='education_create'),
    path('education/<int:pk>/edit/', views.EmployeeEducationUpdateView.as_view(), name='education_update'),
    path('education/<int:pk>/delete/', views.EmployeeEducationDeleteView.as_view(), name='education_delete'),

    # Employee Documents
    path('employees/<int:pk>/documents/upload/', views.EmployeeDocumentUploadView.as_view(), name='employee_doc_upload'),
    path('documents/<int:pk>/download/', views.EmployeeDocumentDownloadView.as_view(), name='employee_doc_download'),
    path('documents/<int:pk>/delete/', views.EmployeeDocumentDeleteView.as_view(), name='employee_doc_delete'),

    # Department Management
    path('departments/', views.DepartmentListView.as_view(), name='department_list'),
    path('departments/add/', views.DepartmentCreateView.as_view(), name='department_create'),
    path('departments/<int:pk>/', views.DepartmentDetailView.as_view(), name='department_detail'),
    path('departments/<int:pk>/edit/', views.DepartmentUpdateView.as_view(), name='department_update'),
    path('departments/<int:pk>/delete/', views.DepartmentDeleteView.as_view(), name='department_delete'),

    # Department Sections
    path('sections/', views.DepartmentSectionListView.as_view(), name='section_list'),
    path('sections/add/', views.DepartmentSectionCreateView.as_view(), name='section_create'),
    path('sections/<int:pk>/edit/', views.DepartmentSectionUpdateView.as_view(), name='section_update'),
    path('sections/<int:pk>/delete/', views.DepartmentSectionDeleteView.as_view(), name='section_delete'),

    # Staff Levels
    path('staff-levels/', views.StaffLevelListView.as_view(), name='staff_level_list'),
    path('staff-levels/add/', views.StaffLevelCreateView.as_view(), name='staff_level_create'),
    path('staff-levels/<int:pk>/edit/', views.StaffLevelUpdateView.as_view(), name='staff_level_update'),

    # Contract Monitoring
    path('contracts/', views.ContractMonitoringView.as_view(), name='contract_monitoring'),
    path('contracts/<int:pk>/renew/', views.ContractRenewView.as_view(), name='contract_renew'),
    path('contracts/<int:pk>/mark-expired/', views.ContractMarkExpiredView.as_view(), name='contract_mark_expired'),

    # HR Reports
    path('reports/', views.HRReportView.as_view(), name='reports'),
    path('reports/export/', views.HRReportExportView.as_view(), name='report_export'),

    # Downloads Module
    path('downloads/', views.DownloadListView.as_view(), name='download_list'),
    path('downloads/upload/', views.DownloadCreateView.as_view(), name='download_create'),
    path('downloads/<uuid:pk>/edit/', views.DownloadUpdateView.as_view(), name='download_update'),
    path('downloads/<uuid:pk>/delete/', views.DownloadDeleteView.as_view(), name='download_delete'),
    path('downloads/<uuid:pk>/get/', views.FileDownloadTrackerView.as_view(), name='download_file'),
]
