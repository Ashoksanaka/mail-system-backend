# ──────────────────────────────────────────────────────────────
# Templates Manager — Admin Registration
# ──────────────────────────────────────────────────────────────
from django.contrib import admin

from .models import EmailTemplate


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ["name", "description", "created_at"]
    search_fields = ["name", "description"]
    readonly_fields = ["id", "created_at", "updated_at"]
