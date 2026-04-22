# ──────────────────────────────────────────────────────────────
# Dispatch — URL Configuration
# Routes for CSV generation, upload, dispatch, and job status
# ──────────────────────────────────────────────────────────────
from django.urls import path

from . import views

app_name = "dispatch"

urlpatterns = [
    # Generate a CSV template with correct headers
    path(
        "generate-csv/",
        views.GenerateCSVView.as_view(),
        name="generate-csv",
    ),
    # Upload and validate a CSV file
    path(
        "upload-csv/",
        views.UploadCSVView.as_view(),
        name="upload-csv",
    ),
    # Start a bulk email dispatch
    path(
        "start/",
        views.StartDispatchView.as_view(),
        name="start-dispatch",
    ),
    # Get dispatch job status and logs
    path(
        "jobs/<uuid:job_id>/",
        views.DispatchJobDetailView.as_view(),
        name="job-detail",
    ),
]
