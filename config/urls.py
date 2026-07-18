# ──────────────────────────────────────────────────────────────
# URL Configuration — Bulk Email Dispatch Platform
# ──────────────────────────────────────────────────────────────
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def healthcheck(_request):
    """Unauthenticated liveness probe for load balancers / CI deploy checks."""
    return JsonResponse({"status": "ok"})


urlpatterns = [
    # Django admin
    path("admin/", admin.site.urls),
    path("api/health/", healthcheck, name="healthcheck"),
    # API endpoints
    path("api/account/", include("apps.accounts.urls")),
    path("api/templates/", include("apps.templates_manager.urls")),
    path("api/dispatch/", include("apps.dispatch.urls")),
]

