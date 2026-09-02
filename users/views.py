from django.contrib.auth import login as auth_login
from django.contrib.auth.views import (
    LoginView, LogoutView, PasswordResetView, PasswordResetDoneView,
    PasswordResetConfirmView, PasswordResetCompleteView, PasswordChangeView
)
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView, ListView, DetailView, CreateView, UpdateView, DeleteView, FormView, View
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.utils.timezone import now
from django.contrib.sessions.models import Session
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect

from .forms import (
    CustomLoginForm, UserProfileForm, UserPasswordChangeForm, UserCreateForm,
    UserEditForm, AdminPasswordResetForm, RoleForm, PortalPermissionForm,
)
from .models import User, AuditLog, Role, PortalPermission
from .permissions import (
    PortalPermissionRequiredMixin, UserManagementAccessMixin,
    ROLE_LEVELS, can_view_user, can_manage_user, effective_authority_level,
    manageable_role_ids, log_security_event, module_label,
)

class CustomLoginView(LoginView):
    form_class = CustomLoginForm
    template_name = 'users/login.html'
    redirect_authenticated_user = True

    def form_valid(self, form):
        user = form.get_user()
        
        # Limit logins to internal staff as specified by the user
        if not user.is_internal_staff:
            messages.error(self.request, _("Access denied. Public users do not have access to the administrative system."))
            return self.form_invalid(form)

        auth_login(self.request, user)
        
        # Remember Me logic
        remember_me = form.cleaned_data.get('remember_me')
        if not remember_me:
            # Session expires when browser closes
            self.request.session.set_expiry(0)
        else:
            # Keep logged in for 30 days
            self.request.session.set_expiry(2592000)
            
        messages.success(self.request, _(f"Welcome back, {user.first_name or user.username}!"))
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        """Land custom-role users on the first module they can actually open."""
        user = self.request.user
        destinations = (
            ('dashboard.view', 'users:dashboard'),
            ('hr_dashboard.view', 'hr:dashboard'),
            ('staff.view', 'hr:employee_list'),
            ('news.view', 'cms:admin_news_list'),
            ('bulletins.view', 'cms:admin_bulletin_list'),
            ('careers.view', 'cms:admin_career_list'),
            ('weather_stations.view', 'weather:station_list'),
            ('observations.view', 'weather:observation_list'),
            ('forecasts.view', 'weather:forecast_list'),
            ('users.view', 'users:user_list'),
            ('downloads.view', 'hr:download_list'),
        )
        for permission_code, view_name in destinations:
            if user.has_portal_permission(permission_code):
                return reverse(view_name)
        return reverse('users:profile')


class CustomLogoutView(LogoutView):
    next_page = 'core:home'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            messages.info(request, _("You have logged out successfully."))
        return super().dispatch(request, *args, **kwargs)


class ProfileView(LoginRequiredMixin, UpdateView):
    model = User
    form_class = UserProfileForm
    template_name = 'users/profile.html'
    success_url = reverse_lazy('users:profile')

    def get_object(self, queryset=None):
        return self.request.user

    def form_valid(self, form):
        messages.success(self.request, _("Your profile has been updated successfully."))
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['profile_form'] = context['form']
        context['password_form'] = UserPasswordChangeForm(user=self.request.user)
        return context


class ProfilePasswordChangeView(LoginRequiredMixin, PasswordChangeView):
    """Allow every authenticated user to change only their own password."""

    form_class = UserPasswordChangeForm
    template_name = 'users/profile.html'
    success_url = reverse_lazy('users:profile')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['profile_form'] = UserProfileForm(instance=self.request.user)
        context['password_form'] = context['form']
        return context

    def form_valid(self, form):
        messages.success(self.request, _("Your password has been updated successfully."))
        return super().form_valid(form)


# Custom Password Reset Views
class CustomPasswordResetView(PasswordResetView):
    template_name = 'users/password_reset_form.html'
    email_template_name = 'users/password_reset_email.html'
    success_url = reverse_lazy('users:password_reset_done')
    
    def form_valid(self, form):
        messages.info(self.request, _("We have sent password reset instructions to your email address."))
        return super().form_valid(form)


class CustomPasswordResetDoneView(PasswordResetDoneView):
    template_name = 'users/password_reset_done.html'


class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = 'users/password_reset_confirm.html'
    success_url = reverse_lazy('users:password_reset_complete')
    
    def form_valid(self, form):
        messages.success(self.request, _("Your password has been reset successfully. You can now log in with your new password."))
        return super().form_valid(form)


class CustomPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = 'users/password_reset_complete.html'


# Activity/Audit Log Viewer for staff
class AuditLogListView(PortalPermissionRequiredMixin, ListView):
    permission_code = 'audit_trails.view'
    model = AuditLog
    template_name = 'users/audit_logs.html'
    context_object_name = 'logs'
    paginate_by = 20

    def get_queryset(self):
        queryset = AuditLog.objects.select_related('user').all()

        q = self.request.GET.get('q')
        if q:
            queryset = queryset.filter(
                Q(action__icontains=q) |
                Q(user__username__icontains=q) |
                Q(ip_address__icontains=q)
            )
        date_from = self.request.GET.get('date_from')
        if date_from:
            queryset = queryset.filter(timestamp__date__gte=date_from)
        date_to = self.request.GET.get('date_to')
        if date_to:
            queryset = queryset.filter(timestamp__date__lte=date_to)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('q', '')
        context['date_from'] = self.request.GET.get('date_from', '')
        context['date_to'] = self.request.GET.get('date_to', '')
        return context


# Staff Dashboard View
class StaffDashboardView(PortalPermissionRequiredMixin, TemplateView):
    permission_code = 'dashboard.view'
    template_name = 'users/dashboard.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.role == User.Role.HR_OFFICER and not request.user.is_superuser:
            return redirect('hr:dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # User/Staff counters
        total_users = User.objects.count()
        active_users = User.objects.filter(is_active=True).count()
        
        # Online users calculation via active sessions
        active_sessions = Session.objects.filter(expire_date__gte=now())
        session_user_ids = set()
        for session in active_sessions:
            try:
                uid = session.get_decoded().get('_auth_user_id')
                if uid:
                    session_user_ids.add(int(uid))
            except Exception:
                pass
        online_users = User.objects.filter(id__in=session_user_ids).count()

        # Role distribution query
        role_breakdown = User.objects.values('role').annotate(count=Count('role'))
        role_stats = []
        for item in role_breakdown:
            role_label = dict(User.Role.choices).get(item['role'], item['role'])
            role_stats.append({
                'role': item['role'],
                'label': role_label,
                'count': item['count']
            })

        # Station telemetry summary from DNMG API
        from weather.services import DNMGStationSyncService
        station_dashboard_data = DNMGStationSyncService.get_dashboard_stations_data()

        context.update({
            'total_users': total_users,
            'active_users': active_users,
            'online_users': online_users,
            'role_stats': role_stats,
            'recent_logs': AuditLog.objects.select_related('user').all()[:8],
            'aws_stations': station_dashboard_data['aws_stations'],
            'tide_stations': station_dashboard_data['tide_stations'],
            'buoy_stations': station_dashboard_data['buoy_stations'],
            'total_stations_count': station_dashboard_data['total_count'],
            'synced_stations_count': station_dashboard_data['synced_count'],
        })
        return context


# User CRUD Management Views
class UserListView(UserManagementAccessMixin, ListView):
    model = User
    template_name = 'users/user_list.html'
    context_object_name = 'users_list'
    paginate_by = 10

    def get_queryset(self):
        queryset = User.objects.all().order_by('-date_joined')
        if not self.request.user.is_superuser:
            manageable_ids = [user.pk for user in queryset.select_related('access_role')
                              if can_view_user(self.request.user, user)]
            queryset = queryset.filter(pk__in=manageable_ids)
            
        # Search filter
        q = self.request.GET.get('q')
        if q:
            queryset = queryset.filter(
                Q(username__icontains=q) |
                Q(first_name__icontains=q) |
                Q(last_name__icontains=q) |
                Q(email__icontains=q)
            )
            
        # Role filter
        role = self.request.GET.get('role')
        if role:
            queryset = queryset.filter(role=role)

        # Active status filter
        is_active = self.request.GET.get('is_active')
        if is_active in ['1', 'true', 'True']:
            queryset = queryset.filter(is_active=True)
        elif is_active in ['0', 'false', 'False']:
            queryset = queryset.filter(is_active=False)
            
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        manager_level = effective_authority_level(self.request.user)
        context['role_choices'] = [choice for choice in User.Role.choices
                                   if self.request.user.is_superuser or
                                   ROLE_LEVELS.get(choice[0], 0) <= manager_level]
        context['selected_role'] = self.request.GET.get('role', '')
        context['selected_active'] = self.request.GET.get('is_active', '')
        context['search_query'] = self.request.GET.get('q', '')
        return context


class UserCreateView(UserManagementAccessMixin, CreateView):
    permission_code = 'users.create'
    model = User
    form_class = UserCreateForm
    template_name = 'users/user_form.html'
    success_url = reverse_lazy('users:user_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request_user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.object.access_role_id:
            log_security_event(self.request, 'ROLE_ASSIGNED_TO_USER', {
                'user_id': self.object.pk, 'username': self.object.username,
                'previous_role': None, 'new_role': self.object.access_role.name,
            })
        messages.success(self.request, _(f"User account for '{self.object.username}' was created successfully."))
        return response


class UserUpdateView(UserManagementAccessMixin, UpdateView):
    permission_code = 'users.edit'
    model = User
    form_class = UserEditForm
    template_name = 'users/user_form.html'
    success_url = reverse_lazy('users:user_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request_user'] = self.request.user
        return kwargs

    def get_object(self, queryset=None):
        user = super().get_object(queryset)
        # ModelForm validation mutates its instance before ``form_valid``;
        # capture this value here so the audit trail records the real change.
        self._previous_role_name = user.access_role.name if user.access_role_id else user.get_role_display()
        return user

    def form_valid(self, form):
        previous_role = getattr(self, '_previous_role_name', self.object.get_effective_role_display())
        response = super().form_valid(form)
        new_role = self.object.access_role.name if self.object.access_role_id else self.object.get_role_display()
        if previous_role != new_role:
            log_security_event(self.request, 'USER_ROLE_CHANGED', {
                'user_id': self.object.pk, 'username': self.object.username,
                'previous_role': previous_role, 'new_role': new_role,
            })
        messages.success(self.request, _(f"User account for '{self.object.username}' was updated successfully."))
        return response


class UserToggleActiveView(UserManagementAccessMixin, View):
    def post(self, request, pk, *args, **kwargs):
        user = get_object_or_404(User, pk=pk)
        required_code = 'users.activate' if not user.is_active else 'users.deactivate'
        if not request.user.has_portal_permission(required_code):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied(_("You do not have permission to change this account status."))
        
        if user == request.user:
            messages.error(request, _("Action invalid. You cannot deactivate your own account."))
            return redirect('users:user_list')

        user.is_active = not user.is_active
        user.save()
        
        action_str = "activated" if user.is_active else "deactivated"
        messages.success(request, _(f"User account '{user.username}' was successfully {action_str}."))
        
        # Force logout if user is deactivated
        if not user.is_active:
            self._force_logout(user)
            
        return redirect('users:user_list')

    def _force_logout(self, user):
        active_sessions = Session.objects.filter(expire_date__gte=now())
        for session in active_sessions:
            try:
                data = session.get_decoded()
                if data.get('_auth_user_id') == str(user.id):
                    session.delete()
            except Exception:
                pass


class UserForceLogoutView(UserManagementAccessMixin, View):
    permission_code = 'users.edit'
    def post(self, request, pk, *args, **kwargs):
        user = get_object_or_404(User, pk=pk)
        
        if user == request.user:
            messages.error(request, _("You cannot force logout your current session. Use logout."))
            return redirect('users:user_list')

        active_sessions = Session.objects.filter(expire_date__gte=now())
        count = 0
        for session in active_sessions:
            try:
                data = session.get_decoded()
                if data.get('_auth_user_id') == str(user.id):
                    session.delete()
                    count += 1
            except Exception:
                pass
                
        messages.success(request, _(f"Terminated {count} active session(s) for user '{user.username}'."))
        return redirect('users:user_list')


class UserPasswordResetAdminView(UserManagementAccessMixin, FormView):
    permission_code = 'users.reset_password'
    template_name = 'users/admin_password_reset.html'
    form_class = AdminPasswordResetForm
    success_url = reverse_lazy('users:user_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['target_user'] = get_object_or_404(User, pk=self.kwargs['pk'])
        return context

    def form_valid(self, form):
        user = get_object_or_404(User, pk=self.kwargs['pk'])
        
        user.set_password(form.cleaned_data['password'])
        user.save()
        messages.success(self.request, _(f"Password for user '{user.username}' has been updated successfully."))
        return super().form_valid(form)


# ──────────────────────────────────────────────────────────────────
# Role and permission management (permission-based access)
# ──────────────────────────────────────────────────────────────────

class RoleListView(PortalPermissionRequiredMixin, ListView):
    permission_code = 'roles.view'
    model = Role
    template_name = 'users/role_list.html'
    context_object_name = 'roles'

    def get_queryset(self):
        roles = Role.objects.prefetch_related('permissions').all()
        return roles.filter(pk__in=manageable_role_ids(self.request.user, roles))


class RoleDetailView(PortalPermissionRequiredMixin, DetailView):
    permission_code = 'roles.view'
    model = Role
    template_name = 'users/role_detail.html'
    context_object_name = 'role'

    def get_queryset(self):
        roles = Role.objects.prefetch_related('permissions').all()
        return roles.filter(pk__in=manageable_role_ids(self.request.user, roles))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        grouped = {}
        for permission in self.object.permissions.all().order_by('module', 'code'):
            grouped.setdefault(module_label(permission.module), []).append(permission)
        context['permissions_by_module'] = grouped
        assigned_users = self.object.users.select_related('access_role').order_by('username')
        if not self.request.user.is_superuser:
            assigned_users = [user for user in assigned_users
                              if can_view_user(self.request.user, user)]
        context['assigned_users'] = assigned_users
        return context


class RoleFormContextMixin:
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        grouped = {}
        permissions = PortalPermission.objects.order_by('module', 'code')
        if not self.request.user.is_superuser:
            permissions = [permission for permission in permissions
                           if self.request.user.has_portal_permission(permission.code)]
        for permission in permissions:
            grouped.setdefault(module_label(permission.module), []).append(permission)
        context['permission_groups'] = grouped
        return context


class RoleCreateView(PortalPermissionRequiredMixin, RoleFormContextMixin, CreateView):
    permission_code = 'roles.create'
    model = Role
    form_class = RoleForm
    template_name = 'users/role_form.html'
    success_url = reverse_lazy('users:role_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request_user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        log_security_event(self.request, 'ROLE_CREATED', {
            'role_id': self.object.pk, 'role_name': self.object.name,
            'permissions': list(self.object.permissions.values_list('code', flat=True)),
        })
        messages.success(self.request, _("Role created successfully."))
        return response


class RoleUpdateView(PortalPermissionRequiredMixin, RoleFormContextMixin, UpdateView):
    permission_code = 'roles.edit'
    model = Role
    form_class = RoleForm
    template_name = 'users/role_form.html'
    success_url = reverse_lazy('users:role_list')

    def get_queryset(self):
        roles = Role.objects.prefetch_related('permissions').all()
        return roles.filter(pk__in=manageable_role_ids(self.request.user, roles))

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request_user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        previous_permissions = set(self.object.permissions.values_list('code', flat=True))
        previous = {
            'name': self.object.name,
            'description': self.object.description,
            'authority_level': self.object.authority_level,
            'is_active': self.object.is_active,
        }
        response = super().form_valid(form)
        new_permissions = set(self.object.permissions.values_list('code', flat=True))
        log_security_event(self.request, 'ROLE_UPDATED', {
            'role_id': self.object.pk, 'previous': previous,
            'new': {
                'name': self.object.name,
                'description': self.object.description,
                'authority_level': self.object.authority_level,
                'is_active': self.object.is_active,
            },
            'permissions_added': sorted(new_permissions - previous_permissions),
            'permissions_removed': sorted(previous_permissions - new_permissions),
        })
        messages.success(self.request, _("Role updated successfully."))
        return response


class RoleDeleteView(PortalPermissionRequiredMixin, DeleteView):
    permission_code = 'roles.delete'
    model = Role
    template_name = 'users/role_confirm_delete.html'
    success_url = reverse_lazy('users:role_list')

    def get_queryset(self):
        roles = Role.objects.prefetch_related('permissions').all()
        return roles.filter(pk__in=manageable_role_ids(self.request.user, roles))

    def form_valid(self, form):
        details = {'role_id': self.object.pk, 'role_name': self.object.name, 'assigned_user_ids': list(self.object.users.values_list('pk', flat=True))}
        log_security_event(self.request, 'ROLE_DELETED', details)
        messages.success(self.request, _("Role deleted. Assigned users no longer have that role."))
        return super().form_valid(form)


class RoleToggleActiveView(PortalPermissionRequiredMixin, View):
    permission_code = None

    def has_required_permission(self):
        roles = Role.objects.prefetch_related('permissions').all()
        role = get_object_or_404(
            roles.filter(pk__in=manageable_role_ids(self.request.user, roles)),
            pk=self.kwargs['pk'],
        )
        required_code = 'roles.activate' if not role.is_active else 'roles.deactivate'
        return self.request.user.has_portal_permission(required_code)

    def post(self, request, pk):
        roles = Role.objects.prefetch_related('permissions').all()
        role = get_object_or_404(
            roles.filter(pk__in=manageable_role_ids(request.user, roles)), pk=pk,
        )
        previous = role.is_active
        role.is_active = not previous
        role.save(update_fields=['is_active', 'updated_at'])
        log_security_event(request, 'ROLE_ACTIVATED' if role.is_active else 'ROLE_DEACTIVATED', {
            'role_id': role.pk, 'role_name': role.name, 'previous_status': previous, 'new_status': role.is_active,
        })
        messages.success(request, _("Role activated.") if role.is_active else _("Role deactivated."))
        return redirect('users:role_list')


class PermissionListView(PortalPermissionRequiredMixin, ListView):
    permission_code = 'permissions.view'
    model = PortalPermission
    template_name = 'users/permission_list.html'
    context_object_name = 'permissions'


class PermissionCreateView(PortalPermissionRequiredMixin, CreateView):
    permission_code = 'permissions.create'
    model = PortalPermission
    form_class = PortalPermissionForm
    template_name = 'users/permission_form.html'
    success_url = reverse_lazy('users:permission_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        log_security_event(self.request, 'PERMISSION_CREATED', {'permission_id': self.object.pk, 'code': self.object.code})
        return response


class PermissionUpdateView(PortalPermissionRequiredMixin, UpdateView):
    permission_code = 'permissions.edit'
    model = PortalPermission
    form_class = PortalPermissionForm
    template_name = 'users/permission_form.html'
    success_url = reverse_lazy('users:permission_list')

    def form_valid(self, form):
        previous = {'code': self.object.code, 'module': self.object.module, 'name': self.object.name}
        response = super().form_valid(form)
        log_security_event(self.request, 'PERMISSION_UPDATED', {'permission_id': self.object.pk, 'previous': previous, 'new': {'code': self.object.code, 'module': self.object.module, 'name': self.object.name}})
        return response


class PermissionDeleteView(PortalPermissionRequiredMixin, DeleteView):
    permission_code = 'permissions.delete'
    model = PortalPermission
    template_name = 'users/permission_confirm_delete.html'
    success_url = reverse_lazy('users:permission_list')

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object.is_system:
            messages.error(request, _("Built-in permissions cannot be deleted; remove them from roles instead."))
            return redirect('users:permission_list')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        log_security_event(self.request, 'PERMISSION_DELETED', {'permission_id': self.object.pk, 'code': self.object.code})
        return super().form_valid(form)
