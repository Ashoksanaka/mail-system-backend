# ──────────────────────────────────────────────────────────────
# Accounts — Clerk identity mapping + per-user SMTP credentials
# ──────────────────────────────────────────────────────────────
from django.conf import settings
from django.db import models


class ClerkIdentity(models.Model):
    """
    Maps an immutable Clerk user id (sub) to a local Django user.
    Application users authenticate via Clerk; Django User remains for
    ownership FKs and admin compatibility.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="clerk_identity",
    )
    clerk_user_id = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="Clerk user id (JWT sub), e.g. user_...",
    )
    email = models.EmailField(blank=True, default="")
    first_name = models.CharField(max_length=150, blank=True, default="")
    last_name = models.CharField(max_length=150, blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Clerk Identity"
        verbose_name_plural = "Clerk Identities"

    def __str__(self):
        return f"{self.clerk_user_id} → {self.user_id}"


class UserSmtpCredential(models.Model):
    """
    Per-user Gmail SMTP settings.
    sender_email is locked to the Clerk signup address and never accepted
    from the client. The app password is stored Fernet-encrypted.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="smtp_credential",
    )
    sender_email = models.EmailField(
        blank=True,
        default="",
        help_text="Immutable sender address from Clerk signup",
    )
    app_password_encrypted = models.TextField(
        blank=True,
        default="",
        help_text="Fernet-encrypted Gmail app password",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "User SMTP Credential"
        verbose_name_plural = "User SMTP Credentials"

    def __str__(self):
        return f"SMTP for {self.user_id} ({self.sender_email or 'no email'})"

    @property
    def has_app_password(self) -> bool:
        return bool(self.app_password_encrypted)

    @property
    def is_configured(self) -> bool:
        return bool(self.sender_email) and self.has_app_password
