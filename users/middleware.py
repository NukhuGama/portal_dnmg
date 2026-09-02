import datetime
import logging
from django.conf import settings
from django.contrib.auth import logout
from django.contrib import messages
from django.shortcuts import redirect
from django.utils.timezone import now
from django.urls import Resolver404, resolve
from django.db import DatabaseError
from .models import AuditLog


logger = logging.getLogger(__name__)

class SessionTimeoutMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            last_activity_str = request.session.get('last_activity')
            if last_activity_str:
                try:
                    last_activity = datetime.datetime.fromisoformat(last_activity_str)
                    elapsed = (now() - last_activity).total_seconds()
                    timeout = getattr(settings, 'SESSION_TIMEOUT_SECONDS', 1800)
                    
                    if elapsed > timeout:
                        logout(request)
                        messages.warning(request, "Your session has expired due to inactivity. Please log in again.")
                        return redirect(settings.LOGIN_URL)
                except ValueError:
                    pass
            
            request.session['last_activity'] = now().isoformat()
            
        response = self.get_response(request)
        return response


class AuditLogMiddleware:
    max_logged_fields = 30

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Process the request to get the response
        response = self.get_response(request)
        
        # Log authenticated mutations, but never copy submitted values into the
        # audit table. Forms may contain passwords, employee PII, documents,
        # and large article bodies.
        if request.user.is_authenticated and request.method in ['POST', 'PUT', 'DELETE', 'PATCH']:
            self._log_mutation(request, response)
            
        return response

    def _log_mutation(self, request, response):
        try:
            try:
                resolved_url = resolve(request.path_info)
                view_name = resolved_url.view_name or request.path_info
                args, kwargs = resolved_url.args, resolved_url.kwargs
            except Resolver404:
                view_name = "unresolved"
                args, kwargs = (), {}

            submitted_fields = []
            if request.method == 'POST':
                submitted_fields = [
                    key for key in request.POST.keys()
                    if 'password' not in key.lower() and 'csrf' not in key.lower()
                ][:self.max_logged_fields]

            AuditLog.objects.create(
                user=request.user,
                action=f"{request.method} {view_name}",
                ip_address=self._get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
                details={
                    'path': request.path[:500],
                    'view_name': view_name,
                    'args': args,
                    'kwargs': kwargs,
                    'method': request.method,
                    'status_code': response.status_code,
                    'submitted_fields': submitted_fields,
                    'submitted_file_fields': list(request.FILES.keys())[:self.max_logged_fields],
                },
            )
        except (DatabaseError, TypeError, ValueError):
            # Audit logging must never turn an otherwise valid user request
            # into a 500 response.
            logger.exception("Unable to write audit log for %s %s", request.method, request.path)

    def _get_client_ip(self, request):
        if getattr(settings, 'AUDIT_TRUST_PROXY_HEADERS', False):
            return request.META.get('HTTP_X_REAL_IP') or request.META.get('REMOTE_ADDR')
        return request.META.get('REMOTE_ADDR')
