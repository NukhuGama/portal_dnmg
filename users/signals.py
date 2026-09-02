from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver
from .models import AuditLog

def get_client_ip(request):
    if not request:
        return None
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

@receiver(user_logged_in)
def log_user_logged_in(sender, request, user, **kwargs):
    ip = get_client_ip(request)
    ua = request.META.get('HTTP_USER_AGENT', '') if request else ''
    AuditLog.objects.create(
        user=user,
        action="USER_LOGIN_SUCCESS",
        ip_address=ip,
        user_agent=ua,
        details={"message": f"User {user.username} logged in successfully."}
    )

@receiver(user_logged_out)
def log_user_logged_out(sender, request, user, **kwargs):
    if user:
        ip = get_client_ip(request)
        ua = request.META.get('HTTP_USER_AGENT', '') if request else ''
        AuditLog.objects.create(
            user=user,
            action="USER_LOGOUT",
            ip_address=ip,
            user_agent=ua,
            details={"message": f"User {user.username} logged out."}
        )

@receiver(user_login_failed)
def log_user_login_failed(sender, credentials, request, **kwargs):
    ip = get_client_ip(request)
    ua = request.META.get('HTTP_USER_AGENT', '') if request else ''
    username = credentials.get('username', 'Unknown')
    AuditLog.objects.create(
        user=None,
        action="USER_LOGIN_FAILED",
        ip_address=ip,
        user_agent=ua,
        details={"attempted_username": username, "message": f"Failed login attempt for username: {username}."}
    )
