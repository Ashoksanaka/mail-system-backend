# ──────────────────────────────────────────────────────────────
# ASGI Configuration — Django Channels
# Routes HTTP and WebSocket protocols
# ──────────────────────────────────────────────────────────────
import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# Initialize Django ASGI application early to ensure AppRegistry is populated
django_asgi_app = get_asgi_application()

# Import WebSocket URL patterns after Django setup
from apps.dispatch.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter(
    {
        # HTTP requests → standard Django ASGI handler
        "http": django_asgi_app,
        # WebSocket connections → Channels routing with auth
        "websocket": AuthMiddlewareStack(
            URLRouter(websocket_urlpatterns)
        ),
    }
)
