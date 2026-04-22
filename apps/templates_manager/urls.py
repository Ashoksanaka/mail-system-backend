# ──────────────────────────────────────────────────────────────
# Templates Manager — URL Configuration
# Routes for email template CRUD and placeholder extraction
# ──────────────────────────────────────────────────────────────
from django.urls import path

from . import views

app_name = "templates_manager"

urlpatterns = [
    # List all templates / Create a new template
    path(
        "",
        views.EmailTemplateListCreateView.as_view(),
        name="template-list-create",
    ),
    # Retrieve / Update / Delete a specific template
    path(
        "<uuid:pk>/",
        views.EmailTemplateDetailView.as_view(),
        name="template-detail",
    ),
    # Extract placeholders from a specific template
    path(
        "<uuid:pk>/extract-placeholders/",
        views.ExtractPlaceholdersView.as_view(),
        name="template-extract-placeholders",
    ),
]
