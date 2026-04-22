# ──────────────────────────────────────────────────────────────
# Templates Manager — Models
# Database model for email templates with {{placeholder}} support
# ──────────────────────────────────────────────────────────────
import uuid

from django.db import models


class EmailTemplate(models.Model):
    """
    Stores email templates with plain-text bodies containing
    {{placeholder}} markers that get replaced with per-recipient data.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    name = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="Unique template name",
    )
    subject = models.CharField(
        max_length=255,
        default="No Subject",
        help_text="Email subject with {{placeholder}} support",
    )
    has_attachments = models.BooleanField(
        default=False,
        help_text="Does this template require attachments?",
    )
    has_global_attachment = models.BooleanField(
        default=False,
        help_text="Is the attachment identical for all recipients?",
    )
    attachment_names = models.JSONField(
        default=list,
        blank=True,
        help_text="List of attachment labels/names expected",
    )
    description = models.TextField(
        help_text="Brief description of the template's purpose",
    )
    body = models.TextField(
        help_text="Plain text body with {{placeholder}} markers",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Email Template"
        verbose_name_plural = "Email Templates"

    def __str__(self):
        return self.name
