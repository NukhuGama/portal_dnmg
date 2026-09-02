"""Small infrastructure views that are intentionally outside language routes."""

from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse


def healthz(request):
    """Report whether this Django process can reach PostgreSQL and its cache."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        cache.set("dnmg:healthcheck", "ok", timeout=10)
        if cache.get("dnmg:healthcheck") != "ok":
            raise RuntimeError("Cache health check did not return its test value.")
    except Exception:
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})
