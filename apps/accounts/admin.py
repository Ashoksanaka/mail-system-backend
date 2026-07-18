from django.contrib import admin

from .models import ClerkIdentity, UserSmtpCredential


@admin.register(ClerkIdentity)
class ClerkIdentityAdmin(admin.ModelAdmin):
    list_display = ("clerk_user_id", "email", "user", "is_active", "created_at")
    search_fields = ("clerk_user_id", "email", "user__username")
    list_filter = ("is_active",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(UserSmtpCredential)
class UserSmtpCredentialAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "sender_email",
        "has_password",
        "created_at",
        "updated_at",
    )
    search_fields = ("sender_email", "user__username", "user__email")
    readonly_fields = (
        "sender_email",
        "app_password_encrypted",
        "created_at",
        "updated_at",
    )

    @admin.display(boolean=True, description="Has app password")
    def has_password(self, obj):
        return obj.has_app_password
