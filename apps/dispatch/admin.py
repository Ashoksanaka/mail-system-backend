# ──────────────────────────────────────────────────────────────
# Dispatch — Admin Registration
# ──────────────────────────────────────────────────────────────
from django.contrib import admin

from .models import DispatchJob, DispatchLog


@admin.register(DispatchJob)
class DispatchJobAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "template",
        "status",
        "total_recipients",
        "sent_count",
        "failed_count",
        "created_at",
    ]
    list_filter = ["status"]
    search_fields = ["id"]
    readonly_fields = ["id", "created_at", "completed_at"]


@admin.register(DispatchLog)
class DispatchLogAdmin(admin.ModelAdmin):
    list_display = ["job", "recipient_email", "status", "sent_at"]
    list_filter = ["status"]
    search_fields = ["recipient_email", "recipient_name"]
    readonly_fields = ["id", "sent_at"]
