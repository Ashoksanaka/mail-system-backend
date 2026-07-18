# ──────────────────────────────────────────────────────────────
# Dispatch — WebSocket Consumer
# Django Channels consumer for real-time dispatch progress updates
# Authenticated via first-message Clerk session token.
# ──────────────────────────────────────────────────────────────
import asyncio
import json
import logging

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from apps.accounts.clerk import verify_clerk_bearer_token
from apps.accounts.services import get_or_create_user_from_clerk_payload

from .models import DispatchJob

logger = logging.getLogger(__name__)

AUTH_TIMEOUT_SECONDS = 10
# Close codes: 4001 unauthorized, 4003 forbidden, 4008 auth timeout
CLOSE_UNAUTHORIZED = 4001
CLOSE_FORBIDDEN = 4003
CLOSE_AUTH_TIMEOUT = 4008


class DispatchConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time dispatch progress.

    Protocol:
      1. Client connects to wss://host/ws/dispatch/<job_id>/
         (local development may use an insecure WebSocket to the ASGI host)
      2. Server accepts the socket but does not join the job group yet
      3. Client sends: {"type": "auth", "token": "<clerk_session_jwt>"}
      4. Server verifies token + job ownership, then joins the group
      5. Server replies: {"type": "auth.ok"} or {"type": "auth.error", ...}
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.job_id = None
        self.group_name = None
        self.user = None
        self.authenticated = False
        self._auth_timeout_task = None

    async def connect(self):
        self.job_id = self.scope["url_route"]["kwargs"]["job_id"]
        self.group_name = f"dispatch_{self.job_id}"
        self.authenticated = False
        await self.accept()
        self._auth_timeout_task = asyncio.create_task(self._auth_timeout())

    async def disconnect(self, close_code):
        if self._auth_timeout_task and not self._auth_timeout_task.done():
            self._auth_timeout_task.cancel()
        if self.authenticated and self.group_name:
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name,
            )

    async def receive(self, text_data=None, bytes_data=None):
        if self.authenticated:
            return

        try:
            payload = json.loads(text_data or "{}")
        except json.JSONDecodeError:
            await self._reject_auth("Invalid JSON payload.", CLOSE_UNAUTHORIZED)
            return

        if payload.get("type") != "auth" or not payload.get("token"):
            await self._reject_auth(
                "Expected auth message with token.", CLOSE_UNAUTHORIZED
            )
            return

        try:
            state = await database_sync_to_async(verify_clerk_bearer_token)(
                payload["token"]
            )
            if not state.is_signed_in:
                await self._reject_auth("Invalid or expired session.", CLOSE_UNAUTHORIZED)
                return

            user, _identity = await database_sync_to_async(
                get_or_create_user_from_clerk_payload
            )(state.payload or {})
            owns_job = await self._user_owns_job(user.id, self.job_id)
            if not owns_job:
                await self._reject_auth(
                    "Dispatch job not found or access denied.", CLOSE_FORBIDDEN
                )
                return

            self.user = user
            self.authenticated = True
            if self._auth_timeout_task and not self._auth_timeout_task.done():
                self._auth_timeout_task.cancel()

            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.send(text_data=json.dumps({"type": "auth.ok"}))
        except PermissionError as exc:
            await self._reject_auth(str(exc), CLOSE_UNAUTHORIZED)
        except Exception:
            logger.exception("WebSocket authentication failed")
            await self._reject_auth("Authentication failed.", CLOSE_UNAUTHORIZED)

    async def dispatch_update(self, event):
        if not self.authenticated:
            return
        await self.send(text_data=json.dumps(event))

    async def _auth_timeout(self):
        try:
            await asyncio.sleep(AUTH_TIMEOUT_SECONDS)
            if not self.authenticated:
                await self.send(
                    text_data=json.dumps(
                        {
                            "type": "auth.error",
                            "message": "Authentication timeout.",
                        }
                    )
                )
                await self.close(code=CLOSE_AUTH_TIMEOUT)
        except asyncio.CancelledError:
            return

    async def _reject_auth(self, message: str, code: int):
        try:
            await self.send(
                text_data=json.dumps({"type": "auth.error", "message": message})
            )
        finally:
            await self.close(code=code)

    @database_sync_to_async
    def _user_owns_job(self, user_id, job_id) -> bool:
        return DispatchJob.objects.filter(pk=job_id, owner_id=user_id).exists()
