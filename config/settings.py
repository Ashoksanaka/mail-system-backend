# ──────────────────────────────────────────────────────────────
# Django Settings — Bulk Email Dispatch Platform
# All sensitive values are read from environment variables
# ──────────────────────────────────────────────────────────────
import os
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def _split_csv(value: str) -> list[str]:
    """Split a comma-separated env value into a stripped, non-empty list."""
    return [item.strip() for item in value.split(",") if item.strip()]


# ─── Base Directory ──────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent

# ─── Security ────────────────────────────────────────────────
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY", "django-insecure-fallback-key-change-in-production"
)
DEBUG = os.environ.get("DJANGO_DEBUG", "True").lower() in ("true", "1", "yes")
ALLOWED_HOSTS = _split_csv(
    os.environ.get(
        "DJANGO_ALLOWED_HOSTS",
        "localhost,127.0.0.1,13-60-91-88.nip.io",
    )
)

# Trust Caddy's forwarded scheme so request.is_secure() is correct behind TLS.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = os.environ.get("SECURE_SSL_REDIRECT", "False").lower() in (
        "true",
        "1",
        "yes",
    )

# ─── Upload Limits ───────────────────────────────────────────
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10 MB

# ─── CSRF ────────────────────────────────────────────────────
CSRF_TRUSTED_ORIGINS = _split_csv(
    os.environ.get(
        "CSRF_TRUSTED_ORIGINS",
        (
            "http://localhost:3000,http://127.0.0.1:3000,"
            "http://localhost:5173,http://127.0.0.1:5173,"
            "https://mailblasto.vercel.app"
        ),
    )
)

# ─── Clerk Authentication ────────────────────────────────────
CLERK_SECRET_KEY = os.environ.get("CLERK_SECRET_KEY", "")
CLERK_JWT_KEY = os.environ.get("CLERK_JWT_KEY", "").replace("\\n", "\n")
CLERK_AUTHORIZED_PARTIES = _split_csv(
    os.environ.get(
        "CLERK_AUTHORIZED_PARTIES",
        (
            "http://localhost:3000,http://localhost:5173,http://127.0.0.1:5173,"
            "https://mailblasto.vercel.app"
        ),
    )
)

# Fernet key for encrypting per-user Gmail app passwords at rest.
# Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
CREDENTIALS_ENCRYPTION_KEY = os.environ.get("CREDENTIALS_ENCRYPTION_KEY", "")

# ─── Installed Apps ──────────────────────────────────────────
INSTALLED_APPS = [
    # Django built-in apps
    "daphne",  # Must be listed before django.contrib.staticfiles
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party apps
    "rest_framework",
    "channels",
    "corsheaders",
    # Project apps
    "apps.accounts",
    "apps.templates_manager",
    "apps.dispatch",
    "apps.core",
]

# ─── Middleware ───────────────────────────────────────────────
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",  # Must be as high as possible
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# ─── URL Configuration ───────────────────────────────────────
ROOT_URLCONF = "config.urls"

# ─── Templates ────────────────────────────────────────────────
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ─── ASGI Application ────────────────────────────────────────
ASGI_APPLICATION = "config.asgi.application"

# ─── Database (PostgreSQL) ───────────────────────────────────
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DB_NAME", "bulkmail_db"),
        "USER": os.environ.get("DB_USER", "bulkmail_user"),
        "PASSWORD": os.environ.get("DB_PASSWORD", "bulkmail_password"),
        "HOST": os.environ.get("DB_HOST", "db"),
        "PORT": os.environ.get("DB_PORT", "5432"),
    }
}

# ─── Password Validators ─────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ─── Internationalization ────────────────────────────────────
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ─── Static Files ────────────────────────────────────────────
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# ─── Default Primary Key ─────────────────────────────────────
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ─── Django Channels (WebSocket Layer) ───────────────────────
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [os.environ.get("REDIS_URL", "redis://redis:6379/0")],
        },
    },
}

# ─── Celery Configuration ────────────────────────────────────
CELERY_BROKER_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("REDIS_URL", "redis://redis:6379/0")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "UTC"
CELERY_BEAT_SCHEDULE = {
    "cleanup-stale-dispatch-attachments": {
        "task": "apps.dispatch.tasks.cleanup_stale_dispatch_attachments",
        "schedule": 3600.0,  # every hour
        "kwargs": {"max_age_hours": 6},
    },
}

# ─── Cache (DRF throttling + shared counters) ────────────────
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": os.environ.get("REDIS_URL", "redis://redis:6379/0"),
    },
}

# ─── CORS Configuration ──────────────────────────────────────
# Browser HTTPS pages (Vercel) may only call an HTTPS API origin.
CORS_ALLOWED_ORIGINS = _split_csv(
    os.environ.get(
        "CORS_ALLOWED_ORIGINS",
        (
            "http://localhost:3000,http://localhost:5173,http://127.0.0.1:5173,"
            "https://mailblasto.vercel.app"
        ),
    )
)
CORS_ALLOW_CREDENTIALS = True

# WebSocket Origin allowlist (scheme + host). Used by Channels OriginValidator
# so WSS from the Vercel frontend is accepted without wildcard ALLOWED_HOSTS.
WS_ALLOWED_ORIGINS = _split_csv(
    os.environ.get(
        "WS_ALLOWED_ORIGINS",
        (
            "http://localhost:3000,http://localhost:5173,http://127.0.0.1:5173,"
            "https://mailblasto.vercel.app"
        ),
    )
)

# ─── Django REST Framework ───────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.accounts.authentication.ClerkAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",  # Required for file uploads
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "30/minute",
        "user": "200/minute",
    },
}

# ─── Email Configuration (Gmail SMTP transport defaults) ─────
# Per-user sender email + app password are stored in the database.
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
