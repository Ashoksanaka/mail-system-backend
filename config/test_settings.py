# Test settings — SQLite + in-memory channel layer / cache
from .settings import *  # noqa: F401,F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

CHANNEL_LAYERS = {
    "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"},
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "test-cache",
    }
}

from cryptography.fernet import Fernet

CLERK_SECRET_KEY = CLERK_SECRET_KEY or "sk_test_dummy"
CLERK_AUTHORIZED_PARTIES = CLERK_AUTHORIZED_PARTIES or ["http://localhost:3000"]
ALLOWED_HOSTS = ["localhost", "testserver", "*"]
WS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://mailblasto.vercel.app",
]
SECURE_SSL_REDIRECT = False
CREDENTIALS_ENCRYPTION_KEY = CREDENTIALS_ENCRYPTION_KEY or Fernet.generate_key().decode()

