# ──────────────────────────────────────────────────────────────
# Templates Manager — Admin Registration
# ──────────────────────────────────────────────────────────────
from django.contrib import admin

from .models import EmailTemplate


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ["name", "owner", "description", "created_at"]
    search_fields = ["name", "description", "owner__username", "owner__email"]
    list_filter = ["owner"]
    readonly_fields = ["id", "created_at", "updated_at"]
