from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory

from apps.accounts.authentication import ClerkAuthentication
from apps.accounts.models import ClerkIdentity
from apps.accounts.services import get_or_create_user_from_clerk_payload

User = get_user_model()


def _signed_in_state(sub="user_abc123", **extra):
    payload = {"sub": sub, "email": "alice@example.com", **extra}
    return SimpleNamespace(
        is_signed_in=True,
        reason=None,
        payload=payload,
    )


def _signed_out_state(reason="token-invalid"):
    return SimpleNamespace(
        is_signed_in=False,
        reason=SimpleNamespace(value=reason, name="TOKEN_INVALID"),
        payload=None,
    )


@override_settings(
    CLERK_SECRET_KEY="sk_test_dummy",
    CLERK_JWT_KEY="",
    CLERK_AUTHORIZED_PARTIES=["http://localhost:3000"],
)
class ClerkAuthenticationTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.auth = ClerkAuthentication()

    def test_missing_credentials_returns_none(self):
        request = self.factory.get("/api/templates/")
        with patch(
            "apps.accounts.authentication.verify_clerk_request",
            return_value=_signed_out_state(),
        ):
            self.assertIsNone(self.auth.authenticate(request))

    def test_invalid_bearer_raises(self):
        request = self.factory.get(
            "/api/templates/", HTTP_AUTHORIZATION="Bearer bad-token"
        )
        with patch(
            "apps.accounts.authentication.verify_clerk_request",
            return_value=_signed_out_state(),
        ):
            from rest_framework.exceptions import AuthenticationFailed

            with self.assertRaises(AuthenticationFailed):
                self.auth.authenticate(request)

    def test_valid_token_provisions_user(self):
        request = self.factory.get(
            "/api/templates/", HTTP_AUTHORIZATION="Bearer good-token"
        )
        with patch(
            "apps.accounts.authentication.verify_clerk_request",
            return_value=_signed_in_state(),
        ):
            user, payload = self.auth.authenticate(request)

        self.assertEqual(payload["sub"], "user_abc123")
        self.assertTrue(ClerkIdentity.objects.filter(clerk_user_id="user_abc123").exists())
        self.assertFalse(user.has_usable_password())
        self.assertFalse(user.is_staff)

    def test_provisioning_is_idempotent(self):
        payload = {"sub": "user_same", "email": "same@example.com"}
        user1, identity1 = get_or_create_user_from_clerk_payload(payload)
        user2, identity2 = get_or_create_user_from_clerk_payload(payload)
        self.assertEqual(user1.id, user2.id)
        self.assertEqual(identity1.id, identity2.id)
        self.assertEqual(User.objects.filter(username__startswith="clerk_").count(), 1)
