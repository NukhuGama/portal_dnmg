from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', views.CustomLogoutView.as_view(), name='logout'),
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('profile/password/', views.ProfilePasswordChangeView.as_view(), name='profile_password_change'),
    path('audit-logs/', views.AuditLogListView.as_view(), name='audit_logs'),
    path('dashboard/', views.StaffDashboardView.as_view(), name='dashboard'),
    
    # User CRUD management
    path('users/', views.UserListView.as_view(), name='user_list'),
    path('users/create/', views.UserCreateView.as_view(), name='user_create'),
    path('users/<int:pk>/update/', views.UserUpdateView.as_view(), name='user_update'),
    path('users/<int:pk>/toggle/', views.UserToggleActiveView.as_view(), name='user_toggle_active'),
    path('users/<int:pk>/force-logout/', views.UserForceLogoutView.as_view(), name='user_force_logout'),
    path('users/<int:pk>/reset-password/', views.UserPasswordResetAdminView.as_view(), name='user_reset_password'),

    # Granular role and permission management (permission-based access)
    path('roles/', views.RoleListView.as_view(), name='role_list'),
    path('roles/create/', views.RoleCreateView.as_view(), name='role_create'),
    path('roles/<int:pk>/', views.RoleDetailView.as_view(), name='role_detail'),
    path('roles/<int:pk>/update/', views.RoleUpdateView.as_view(), name='role_update'),
    path('roles/<int:pk>/delete/', views.RoleDeleteView.as_view(), name='role_delete'),
    path('roles/<int:pk>/toggle/', views.RoleToggleActiveView.as_view(), name='role_toggle_active'),
    path('permissions/', views.PermissionListView.as_view(), name='permission_list'),
    path('permissions/create/', views.PermissionCreateView.as_view(), name='permission_create'),
    path('permissions/<int:pk>/update/', views.PermissionUpdateView.as_view(), name='permission_update'),
    path('permissions/<int:pk>/delete/', views.PermissionDeleteView.as_view(), name='permission_delete'),
    
    # Password Reset flow
    path('password-reset/', views.CustomPasswordResetView.as_view(), name='password_reset'),
    path('password-reset/done/', views.CustomPasswordResetDoneView.as_view(), name='password_reset_done'),
    path('password-reset/confirm/<uidb64>/<token>/', views.CustomPasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('password-reset/complete/', views.CustomPasswordResetCompleteView.as_view(), name='password_reset_complete'),
]
