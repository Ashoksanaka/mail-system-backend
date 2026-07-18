# ──────────────────────────────────────────────────────────────
# Clerk token verification helpers
# ──────────────────────────────────────────────────────────────
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional

from clerk_backend_api import AuthenticateRequestOptions, authenticate_request
from django.conf import settings


@dataclass
class BearerRequest:
    """Minimal request adapter for non-HTTP contexts (e.g. WebSockets)."""

    headers: Mapping[str, str]


def build_authenticate_options() -> AuthenticateRequestOptions:
    authorized_parties = getattr(settings, "CLERK_AUTHORIZED_PARTIES", None) or None
    return AuthenticateRequestOptions(
        secret_key=settings.CLERK_SECRET_KEY or None,
        jwt_key=settings.CLERK_JWT_KEY or None,
        authorized_parties=authorized_parties,
        accepts_token=["session_token"],
    )


def verify_clerk_request(request) -> Any:
    """Verify Clerk session token on a Django HttpRequest (or adapter)."""
    return authenticate_request(request, build_authenticate_options())


def verify_clerk_bearer_token(token: str) -> Any:
    """Verify a raw Bearer session token (WebSocket handshake)."""
    return verify_clerk_request(BearerRequest(headers={"Authorization": f"Bearer {token}"}))


def extract_clerk_user_id(payload: Optional[Mapping[str, Any]]) -> Optional[str]:
    if not payload:
        return None
    sub = payload.get("sub")
    return str(sub) if sub else None
