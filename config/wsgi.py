# ──────────────────────────────────────────────────────────────
# WSGI Configuration — Bulk Email Dispatch Platform
# Standard WSGI entry point (fallback — Daphne uses ASGI)
# ──────────────────────────────────────────────────────────────
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_wsgi_application()
