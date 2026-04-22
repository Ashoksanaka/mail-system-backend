# ──────────────────────────────────────────────────────────────
# Dispatch — Models
# Database models for dispatch jobs and per-recipient logs
# ──────────────────────────────────────────────────────────────
import uuid

from django.db import models

from apps.templates_manager.models import EmailTemplate


class DispatchJob(models.Model):
    """
    Represents a single bulk email dispatch operation.
    Tracks overall progress: total, sent, and failed counts.
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    template = models.ForeignKey(
        EmailTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dispatch_jobs",
        help_text="The email template used for this dispatch",
    )
    total_recipients = models.IntegerField(
        default=0,
        help_text="Total number of recipients in the CSV",
    )
    sent_count = models.IntegerField(
        default=0,
        help_text="Number of emails successfully sent",
    )
    failed_count = models.IntegerField(
        default=0,
        help_text="Number of emails that failed to send",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Dispatch Job"
        verbose_name_plural = "Dispatch Jobs"

    def __str__(self):
        return f"Job {self.id} — {self.status} ({self.sent_count}/{self.total_recipients})"


class DispatchLog(models.Model):
    """
    Per-recipient log entry within a dispatch job.
    Records whether each individual email was sent successfully or failed.
    """

    class Status(models.TextChoices):
        SUCCESS = "SUCCESS", "Success"
        FAILED = "FAILED", "Failed"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    job = models.ForeignKey(
        DispatchJob,
        on_delete=models.CASCADE,
        related_name="logs",
    )
    recipient_email = models.EmailField(
        help_text="Recipient's email address",
    )
    recipient_name = models.CharField(
        max_length=255,
        help_text="Recipient's display name",
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
    )
    error_message = models.TextField(
        null=True,
        blank=True,
        help_text="Error details if the email failed to send",
    )
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sent_at"]
        verbose_name = "Dispatch Log"
        verbose_name_plural = "Dispatch Logs"
        indexes = [
            models.Index(fields=["job", "status"]),
        ]

    def __str__(self):
        return f"{self.recipient_email} — {self.status}"
