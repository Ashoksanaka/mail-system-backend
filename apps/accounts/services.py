# ──────────────────────────────────────────────────────────────
# Accounts — identity provisioning
# ──────────────────────────────────────────────────────────────
from __future__ import annotations

import logging
from typing import Any, Mapping, Optional, Tuple

from clerk_backend_api import Clerk
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction

from .credentials import ensure_sender_email
from .models import ClerkIdentity

User = get_user_model()
logger = logging.getLogger(__name__)


def _claim_str(payload: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = payload.get(key)
        if value:
            return str(value)
    return ""


def _email_from_clerk_user(clerk_user) -> str:
    """Extract primary email from a Clerk Backend API User object."""
    if clerk_user is None:
        return ""

    addresses = getattr(clerk_user, "email_addresses", None) or []
    primary_id = getattr(clerk_user, "primary_email_address_id", None)

    if primary_id:
        for addr in addresses:
            if getattr(addr, "id", None) == primary_id:
                email = getattr(addr, "email_address", "") or ""
                if email:
                    return str(email)

    for addr in addresses:
        email = getattr(addr, "email_address", "") or ""
        if email:
            return str(email)
    return ""


def fetch_clerk_user_email(clerk_user_id: str) -> str:
    """Look up the user's primary email via Clerk Backend API."""
    secret = getattr(settings, "CLERK_SECRET_KEY", "") or ""
    if not secret or not clerk_user_id:
        return ""
    try:
        sdk = Clerk(bearer_auth=secret)
        clerk_user = sdk.users.get(user_id=clerk_user_id)
        return _email_from_clerk_user(clerk_user)
    except Exception:
        logger.exception(
            "Failed to fetch Clerk user email for %s", clerk_user_id
        )
        return ""


def resolve_signup_email(payload: Mapping[str, Any], clerk_user_id: str) -> str:
    email = _claim_str(payload, "email", "primary_email_address")
    if email:
        return email
    return fetch_clerk_user_email(clerk_user_id)


@transaction.atomic
def get_or_create_user_from_clerk_payload(
    payload: Mapping[str, Any],
) -> Tuple[Any, ClerkIdentity]:
    """
    Resolve or provision a local Django user from verified Clerk claims.
    Uses clerk_user_id (sub) as the immutable identity key.
    Locks SMTP sender_email once a signup address is known.
    """
    clerk_user_id = str(payload.get("sub") or "").strip()
    if not clerk_user_id:
        raise ValueError("Clerk token payload is missing sub.")

    email = resolve_signup_email(payload, clerk_user_id)
    first_name = _claim_str(payload, "first_name", "given_name")
    last_name = _claim_str(payload, "last_name", "family_name")

    try:
        identity = (
            ClerkIdentity.objects.select_for_update()
            .select_related("user")
            .get(clerk_user_id=clerk_user_id)
        )
        updated = False
        # Profile email may sync for display; SMTP sender is locked separately.
        if email and identity.email != email:
            identity.email = email
            updated = True
        if first_name and identity.first_name != first_name:
            identity.first_name = first_name
            updated = True
        if last_name and identity.last_name != last_name:
            identity.last_name = last_name
            updated = True
        if updated:
            identity.save(
                update_fields=["email", "first_name", "last_name", "updated_at"]
            )

        user = identity.user
        user_updates = []
        if email and user.email != email:
            user.email = email
            user_updates.append("email")
        if first_name and user.first_name != first_name:
            user.first_name = first_name
            user_updates.append("first_name")
        if last_name and user.last_name != last_name:
            user.last_name = last_name
            user_updates.append("last_name")
        if user_updates:
            user.save(update_fields=user_updates)

        if not identity.is_active or not user.is_active:
            raise PermissionError("Clerk identity is inactive.")

        ensure_sender_email(user, email or identity.email)
        return user, identity
    except ClerkIdentity.DoesNotExist:
        pass

    username = f"clerk_{clerk_user_id}"
    if len(username) > 150:
        username = username[:150]

    try:
        user = User(
            username=username,
            email=email or "",
            first_name=first_name,
            last_name=last_name,
            is_staff=False,
            is_superuser=False,
            is_active=True,
        )
        user.set_unusable_password()
        user.save()
        identity = ClerkIdentity.objects.create(
            user=user,
            clerk_user_id=clerk_user_id,
            email=email,
            first_name=first_name,
            last_name=last_name,
            is_active=True,
        )
        ensure_sender_email(user, email)
        return user, identity
    except IntegrityError:
        # Concurrent first request — re-fetch the winner.
        identity = ClerkIdentity.objects.select_related("user").get(
            clerk_user_id=clerk_user_id
        )
        if not identity.is_active or not identity.user.is_active:
            raise PermissionError("Clerk identity is inactive.")
        ensure_sender_email(identity.user, email or identity.email)
        return identity.user, identity


def resolve_user_from_clerk_payload(payload: Optional[Mapping[str, Any]]):
    if not payload:
        return None
    user, _identity = get_or_create_user_from_clerk_payload(payload)
    return user
