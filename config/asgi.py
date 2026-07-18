# ──────────────────────────────────────────────────────────────
# ASGI Configuration — Django Channels
# Routes HTTP and WebSocket protocols
# ──────────────────────────────────────────────────────────────
import os

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import OriginValidator
from django.conf import settings
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# Initialize Django ASGI application early to ensure AppRegistry is populated
django_asgi_app = get_asgi_application()

# Import WebSocket URL patterns after Django setup
from apps.dispatch.routing import websocket_urlpatterns  # noqa: E402

_websocket_urls = URLRouter(websocket_urlpatterns)


class SettingsOriginValidator:
    """
    OriginValidator that reads settings.WS_ALLOWED_ORIGINS per connection.

    This keeps production allowlists environment-driven and lets tests override
    WS_ALLOWED_ORIGINS without re-importing the ASGI module.
    """

    def __init__(self, application):
        self.application = application

    async def __call__(self, scope, receive, send):
        allowed = getattr(settings, "WS_ALLOWED_ORIGINS", None) or [
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
        validator = OriginValidator(self.application, allowed)
        return await validator(scope, receive, send)


application = ProtocolTypeRouter(
    {
        # HTTP requests → standard Django ASGI handler
        "http": django_asgi_app,
        # WebSocket connections → Channels routing.
        # Clerk auth is handled inside DispatchConsumer (first-message token).
        "websocket": SettingsOriginValidator(_websocket_urls),
    }
)
