from unittest.mock import patch

from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.credentials import ensure_sender_email, load_smtp_login
from apps.accounts.crypto import decrypt_secret, encrypt_secret
from apps.accounts.models import ClerkIdentity, UserSmtpCredential
from apps.dispatch.models import DispatchJob
from apps.templates_manager.models import EmailTemplate

User = get_user_model()
TEST_FERNET_KEY = Fernet.generate_key().decode()


def _auth_as(user):
    payload = {"sub": user.clerk_identity.clerk_user_id}

    def _authenticate(request):
        return (user, payload)

    return patch(
        "apps.accounts.authentication.ClerkAuthentication.authenticate",
        side_effect=_authenticate,
    )


@override_settings(
    CREDENTIALS_ENCRYPTION_KEY=TEST_FERNET_KEY,
    CLERK_SECRET_KEY="sk_test_dummy",
    CLERK_AUTHORIZED_PARTIES=["http://localhost:3000"],
)
class SmtpCredentialTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="smtp_user", password="x")
        self.user.set_unusable_password()
        self.user.save()
        ClerkIdentity.objects.create(
            user=self.user,
            clerk_user_id="user_smtp",
            email="sender@example.com",
        )
        UserSmtpCredential.objects.create(
            user=self.user,
            sender_email="sender@example.com",
        )

    def test_encrypt_round_trip(self):
        token = encrypt_secret("abcd-efgh-ijkl-mnop")
        self.assertNotEqual(token, "abcd-efgh-ijkl-mnop")
        self.assertEqual(decrypt_secret(token), "abcd-efgh-ijkl-mnop")

    def test_get_smtp_status(self):
        with _auth_as(self.user):
            response = self.client.get("/api/account/smtp/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["sender_email"], "sender@example.com")
        self.assertFalse(response.json()["has_app_password"])

    def test_put_rejects_sender_email_change(self):
        with _auth_as(self.user):
            response = self.client.put(
                "/api/account/smtp/",
                {
                    "sender_email": "evil@example.com",
                    "app_password": "abcd-efgh-ijkl-mnop",
                },
                format="json",
            )
        self.assertEqual(response.status_code, 400)

    def test_put_saves_encrypted_password(self):
        with _auth_as(self.user):
            response = self.client.put(
                "/api/account/smtp/",
                {"app_password": "abcd efgh ijkl mnop"},
                format="json",
            )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["has_app_password"])
        credential = UserSmtpCredential.objects.get(user=self.user)
        self.assertTrue(credential.app_password_encrypted)
        self.assertNotIn("abcd", credential.app_password_encrypted)
        email, password = load_smtp_login(self.user)
        self.assertEqual(email, "sender@example.com")
        self.assertEqual(password, "abcdefghijklmnop")

    def test_start_dispatch_blocked_without_password(self):
        template = EmailTemplate.objects.create(
            owner=self.user,
            name="T",
            subject="Hi {{name}}",
            description="d",
            body="Hello {{name}}",
        )
        csv_file = SimpleUploadedFile(
            "recipients.csv",
            b"receiver_email_ID,receiver_name,name\na@b.com,A,Alice\n",
            content_type="text/csv",
        )
        with _auth_as(self.user):
            response = self.client.post(
                "/api/dispatch/start/",
                {"template_id": str(template.id), "csv_file": csv_file},
                format="multipart",
            )
        self.assertEqual(response.status_code, 400)
        self.assertIn("app password", response.json()["error"].lower())
        self.assertEqual(DispatchJob.objects.count(), 0)

    def test_ensure_sender_email_is_immutable(self):
        ensure_sender_email(self.user, "other@example.com")
        credential = UserSmtpCredential.objects.get(user=self.user)
        self.assertEqual(credential.sender_email, "sender@example.com")
