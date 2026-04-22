# ──────────────────────────────────────────────────────────────
# Dispatch — WebSocket URL Routing
# Maps WebSocket URL patterns to consumers
# ──────────────────────────────────────────────────────────────
from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(
        r"ws/dispatch/(?P<job_id>[0-9a-f-]+)/$",
        consumers.DispatchConsumer.as_asgi(),
    ),
]
