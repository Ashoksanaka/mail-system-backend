# ──────────────────────────────────────────────────────────────
# Dispatch — WebSocket Consumer
# Django Channels consumer for real-time dispatch progress updates
# ──────────────────────────────────────────────────────────────
import json

from channels.generic.websocket import AsyncWebsocketConsumer


class DispatchConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time dispatch progress.
    Each client subscribes to updates for a specific job_id.

    Connect to: ws://host/ws/dispatch/<job_id>/
    """

    async def connect(self):
        """
        Handle WebSocket connection.
        Extracts job_id from the URL route and joins the
        corresponding channel group.
        """
        # Extract job_id from URL route kwargs
        self.job_id = self.scope["url_route"]["kwargs"]["job_id"]
        self.group_name = f"dispatch_{self.job_id}"

        # Add this channel to the job-specific group
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name,
        )

        # Accept the WebSocket connection
        await self.accept()

    async def disconnect(self, close_code):
        """
        Handle WebSocket disconnection.
        Removes the channel from the job group.
        """
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name,
        )

    async def receive(self, text_data):
        """
        Handle incoming WebSocket messages from the client.
        Not used — client only listens, does not send.
        """
        pass

    async def dispatch_update(self, event):
        """
        Called by Celery task via group_send.
        Forwards the dispatch progress data to the connected WebSocket client.
        """
        # Send the event data as JSON to the client
        await self.send(text_data=json.dumps(event))
