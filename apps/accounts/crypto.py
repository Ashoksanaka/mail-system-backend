# ──────────────────────────────────────────────────────────────
# Fernet helpers for encrypting per-user SMTP app passwords
# ──────────────────────────────────────────────────────────────
from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings

_cached_key = None
_cached_fernet = None


class CredentialsEncryptionError(Exception):
    """Raised when encryption configuration or ciphertext is invalid."""


def _fernet() -> Fernet:
    global _cached_key, _cached_fernet
    key = (getattr(settings, "CREDENTIALS_ENCRYPTION_KEY", "") or "").strip()
    if not key:
        raise CredentialsEncryptionError(
            "CREDENTIALS_ENCRYPTION_KEY is not configured."
        )
    if _cached_fernet is None or _cached_key != key:
        try:
            _cached_fernet = Fernet(
                key.encode("utf-8") if isinstance(key, str) else key
            )
            _cached_key = key
        except Exception as exc:
            raise CredentialsEncryptionError(
                "CREDENTIALS_ENCRYPTION_KEY is not a valid Fernet key."
            ) from exc
    return _cached_fernet


def encrypt_secret(plaintext: str) -> str:
    if plaintext is None:
        raise ValueError("Cannot encrypt empty secret.")
    token = _fernet().encrypt(plaintext.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_secret(ciphertext: str) -> str:
    if not ciphertext:
        raise CredentialsEncryptionError("No encrypted secret stored.")
    try:
        return _fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise CredentialsEncryptionError("Failed to decrypt stored secret.") from exc
