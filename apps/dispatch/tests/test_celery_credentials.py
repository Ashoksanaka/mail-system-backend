from unittest.mock import AsyncMock, MagicMock, patch

from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.accounts.credentials import set_app_password
from apps.accounts.models import ClerkIdentity, UserSmtpCredential
from apps.dispatch.models import DispatchJob, DispatchLog
from apps.dispatch.tasks import (
    GMAIL_SMTP_HOST,
    PUBLIC_NETWORK_ERROR,
    _IPv4SMTP,
    send_bulk_emails,
)
from apps.templates_manager.models import EmailTemplate

User = get_user_model()
TEST_FERNET_KEY = Fernet.generate_key().decode()


@override_settings(
    CREDENTIALS_ENCRYPTION_KEY=TEST_FERNET_KEY,
    CLERK_SECRET_KEY="sk_test_dummy",
)
class CelerySmtpCredentialTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="celery_user", password="x")
        self.user.set_unusable_password()
        self.user.save()
        ClerkIdentity.objects.create(
            user=self.user,
            clerk_user_id="user_celery",
            email="owner@example.com",
        )
        UserSmtpCredential.objects.create(
            user=self.user,
            sender_email="owner@example.com",
        )
        set_app_password(self.user, "abcd-efgh-ijkl-mnop")
        self.template = EmailTemplate.objects.create(
            owner=self.user,
            name="CeleryTemplate",
            subject="Hi {{name}}",
            description="d",
            body="Hello {{name}}",
        )
        self.job = DispatchJob.objects.create(
            owner=self.user,
            template=self.template,
            total_recipients=1,
        )

    @patch("apps.dispatch.tasks.get_channel_layer")
    @patch("apps.dispatch.tasks._open_gmail_smtp")
    def test_celery_uses_owner_credentials(self, open_smtp, channel_layer_get):
        smtp = MagicMock()
        open_smtp.return_value = smtp
        channel_layer = MagicMock()
        channel_layer.group_send = AsyncMock(return_value=None)
        channel_layer_get.return_value = channel_layer

        send_bulk_emails(
            str(self.job.id),
            str(self.template.id),
            [{"receiver_email_ID": "a@b.com", "receiver_name": "A", "name": "Alice"}],
            {},
        )

        smtp.login.assert_called_with("owner@example.com", "abcd-efgh-ijkl-mnop")
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, DispatchJob.Status.COMPLETED)

    @patch("apps.dispatch.tasks.get_channel_layer")
    @patch("apps.dispatch.tasks._open_gmail_smtp")
    def test_celery_persists_top_level_error(self, open_smtp, channel_layer_get):
        open_smtp.side_effect = OSError("Network is unreachable")
        channel_layer = MagicMock()
        channel_layer.group_send = AsyncMock(return_value=None)
        channel_layer_get.return_value = channel_layer

        with self.assertLogs("apps.dispatch.tasks", level="ERROR") as log_cm:
            with self.assertRaises(OSError):
                send_bulk_emails(
                    str(self.job.id),
                    str(self.template.id),
                    [
                        {
                            "receiver_email_ID": "a@b.com",
                            "receiver_name": "A",
                            "name": "Alice",
                        }
                    ],
                    {},
                )

        # Verbose detail stays in server logs
        joined_logs = "\n".join(log_cm.output)
        self.assertIn("Network is unreachable", joined_logs)
        self.assertIn("not an authentication failure", joined_logs)

        # Client-facing surfaces get only the short public message
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, DispatchJob.Status.FAILED)
        self.assertEqual(self.job.failed_count, 1)
        self.assertEqual(self.job.error_message, PUBLIC_NETWORK_ERROR)
        self.assertNotIn("Network is unreachable", self.job.error_message)
        self.assertEqual(
            DispatchLog.objects.filter(
                job=self.job, status=DispatchLog.Status.FAILED
            ).count(),
            1,
        )
        abort_log = DispatchLog.objects.get(
            job=self.job, status=DispatchLog.Status.FAILED
        )
        self.assertEqual(abort_log.error_message, PUBLIC_NETWORK_ERROR)
        channel_layer.group_send.assert_called()
        ws_payload = channel_layer.group_send.call_args[0][1]
        self.assertEqual(ws_payload["job_status"], "FAILED")
        self.assertEqual(ws_payload["pending"], 0)
        self.assertEqual(ws_payload["failed"], 1)
        self.assertEqual(ws_payload["error"], PUBLIC_NETWORK_ERROR)
        self.assertNotIn("Network is unreachable", ws_payload["error"])

    @patch("apps.dispatch.tasks.cleanup_job_attachments")
    @patch("apps.dispatch.tasks.get_channel_layer")
    @patch("apps.dispatch.tasks._open_gmail_smtp")
    def test_celery_cleans_attachments_on_top_level_failure(
        self, open_smtp, channel_layer_get, cleanup_attachments
    ):
        """Attachments must be removed even when SMTP fails before the send loop."""
        open_smtp.side_effect = OSError("Network is unreachable")
        channel_layer = MagicMock()
        channel_layer.group_send = AsyncMock(return_value=None)
        channel_layer_get.return_value = channel_layer

        with self.assertRaises(OSError):
            send_bulk_emails(
                str(self.job.id),
                str(self.template.id),
                [{"receiver_email_ID": "a@b.com", "receiver_name": "A", "name": "Alice"}],
                {"global_0": {"path": "dispatch_attachments/x/a.pdf"}},
            )

        cleanup_attachments.assert_called_once_with(str(self.job.id))

    @patch("apps.dispatch.tasks._IPv4SMTP")
    def test_open_gmail_smtp_uses_hostname_for_starttls(self, smtp_cls):
        """STARTTLS needs a non-empty SMTP _host (SNI); connect via hostname."""
        from apps.dispatch.tasks import _open_gmail_smtp

        instance = MagicMock()
        smtp_cls.return_value = instance
        result = _open_gmail_smtp(timeout=5)
        smtp_cls.assert_called_once_with(GMAIL_SMTP_HOST, 587, timeout=5)
        self.assertIs(result, instance)
