# ──────────────────────────────────────────────────────────────
# Celery Application Configuration
# App name: 'bulkmail'
# ──────────────────────────────────────────────────────────────
import os

from celery import Celery

# Set the default Django settings module for the 'celery' program
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# Create the Celery application instance
app = Celery("bulkmail")

# Load configuration from Django settings
# All Celery-related settings should be prefixed with CELERY_ in settings.py
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks from all installed Django apps
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task to verify Celery is working."""
    print(f"Request: {self.request!r}")
