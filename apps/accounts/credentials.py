# ──────────────────────────────────────────────────────────────
# Per-user SMTP credential helpers
# ──────────────────────────────────────────────────────────────
from __future__ import annotations

from typing import Tuple

from .crypto import decrypt_secret, encrypt_secret
from .models import UserSmtpCredential


def get_or_create_smtp_credential(user) -> UserSmtpCredential:
    credential, _created = UserSmtpCredential.objects.get_or_create(user=user)
    return credential


def ensure_sender_email(user, email: str) -> UserSmtpCredential:
    """
    Lock sender_email the first time a non-empty address is known.
    Subsequent calls never overwrite an existing sender_email.
    """
    credential = get_or_create_smtp_credential(user)
    cleaned = (email or "").strip()
    if cleaned and not credential.sender_email:
        credential.sender_email = cleaned
        credential.save(update_fields=["sender_email", "updated_at"])
    return credential


def set_app_password(user, app_password: str) -> UserSmtpCredential:
    cleaned = (app_password or "").strip().replace(" ", "")
    if not cleaned:
        raise ValueError("App password cannot be empty.")
    if len(cleaned) < 8:
        raise ValueError("App password is too short.")

    credential = get_or_create_smtp_credential(user)
    if not credential.sender_email:
        raise ValueError(
            "Sender email is not available yet. Sign out and sign in again, "
            "or contact support."
        )
    credential.app_password_encrypted = encrypt_secret(cleaned)
    credential.save(update_fields=["app_password_encrypted", "updated_at"])
    return credential


def smtp_status(user) -> dict:
    credential = get_or_create_smtp_credential(user)
    return {
        "sender_email": credential.sender_email or "",
        "has_app_password": credential.has_app_password,
    }


def load_smtp_login(user) -> Tuple[str, str]:
    """
    Return (sender_email, app_password) for SMTP login.
    Raises ValueError / CredentialsEncryptionError when unusable.
    """
    try:
        credential = UserSmtpCredential.objects.get(user=user)
    except UserSmtpCredential.DoesNotExist as exc:
        raise ValueError(
            "SMTP credentials are not configured. Add your Gmail app password in Settings."
        ) from exc

    if not credential.sender_email:
        raise ValueError("Sender email is missing for this account.")
    if not credential.has_app_password:
        raise ValueError(
            "Gmail app password is not configured. Add it in Settings before dispatching."
        )

    password = decrypt_secret(credential.app_password_encrypted)
    return credential.sender_email, password


def user_has_configured_smtp(user) -> bool:
    try:
        credential = user.smtp_credential
    except UserSmtpCredential.DoesNotExist:
        return False
    return credential.is_configured
