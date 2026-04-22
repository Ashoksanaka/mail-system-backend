# ──────────────────────────────────────────────────────────────
# URL Configuration — Bulk Email Dispatch Platform
# ──────────────────────────────────────────────────────────────
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    # Django admin
    path("admin/", admin.site.urls),
    # API endpoints
    path("api/templates/", include("apps.templates_manager.urls")),
    path("api/dispatch/", include("apps.dispatch.urls")),
]
