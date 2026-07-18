from types import SimpleNamespace
from unittest.mock import patch

from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.test import TransactionTestCase, override_settings

from apps.accounts.models import ClerkIdentity
from apps.dispatch.models import DispatchJob
from apps.templates_manager.models import EmailTemplate
from config.asgi import application

User = get_user_model()


@override_settings(
    CHANNEL_LAYERS={
        "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"},
    },
    ALLOWED_HOSTS=["localhost", "testserver", "*"],
    WS_ALLOWED_ORIGINS=[
        "http://localhost:3000",
        "https://mailblasto.vercel.app",
    ],
    CLERK_SECRET_KEY="sk_test_dummy",
    CLERK_JWT_KEY="",
    CLERK_AUTHORIZED_PARTIES=["http://localhost:3000"],
)
class DispatchWebSocketAuthTests(TransactionTestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="ws_owner", password="x")
        self.owner.set_unusable_password()
        self.owner.save()
        ClerkIdentity.objects.create(
            user=self.owner, clerk_user_id="user_ws_owner", email="ws@example.com"
        )
        self.other = User.objects.create_user(username="ws_other", password="x")
        self.other.set_unusable_password()
        self.other.save()
        ClerkIdentity.objects.create(
            user=self.other, clerk_user_id="user_ws_other", email="other@example.com"
        )
        self.template = EmailTemplate.objects.create(
            owner=self.owner,
            name="WS",
            subject="Hi {{name}}",
            description="WS",
            body="Hello {{name}}",
        )
        self.job = DispatchJob.objects.create(
            owner=self.owner,
            template=self.template,
            total_recipients=1,
        )

    def _communicator(self, origin=b"http://localhost:3000"):
        return WebsocketCommunicator(
            application,
            f"/ws/dispatch/{self.job.id}/",
            headers=[(b"origin", origin)],
        )

    async def test_rejects_missing_auth_message(self):
        communicator = self._communicator()
        connected, _ = await communicator.connect()
        self.assertTrue(connected)
        await communicator.send_json_to({"type": "ping"})
        response = await communicator.receive_json_from()
        self.assertEqual(response["type"], "auth.error")
        await communicator.disconnect()

    async def test_accepts_owner_token(self):
        state = SimpleNamespace(
            is_signed_in=True,
            payload={"sub": "user_ws_owner", "email": "ws@example.com"},
            reason=None,
        )
        with patch(
            "apps.dispatch.consumers.verify_clerk_bearer_token",
            return_value=state,
        ):
            communicator = self._communicator()
            connected, _ = await communicator.connect()
            self.assertTrue(connected)
            await communicator.send_json_to({"type": "auth", "token": "good"})
            response = await communicator.receive_json_from()
            self.assertEqual(response["type"], "auth.ok")
            await communicator.disconnect()

    async def test_rejects_cross_user_job(self):
        state = SimpleNamespace(
            is_signed_in=True,
            payload={"sub": "user_ws_other", "email": "other@example.com"},
            reason=None,
        )
        with patch(
            "apps.dispatch.consumers.verify_clerk_bearer_token",
            return_value=state,
        ):
            communicator = self._communicator()
            connected, _ = await communicator.connect()
            self.assertTrue(connected)
            await communicator.send_json_to({"type": "auth", "token": "good"})
            response = await communicator.receive_json_from()
            self.assertEqual(response["type"], "auth.error")
            await communicator.disconnect()

    async def test_rejects_disallowed_origin(self):
        communicator = self._communicator(origin=b"https://evil.example")
        connected, _ = await communicator.connect()
        self.assertFalse(connected)
