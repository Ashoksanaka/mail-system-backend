# ──────────────────────────────────────────────────────────────
# Dispatch — Celery Tasks
# Async task for bulk email sending via Gmail SMTP
# ──────────────────────────────────────────────────────────────
import logging
import os
import shutil
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from django.core.files.storage import default_storage

from asgiref.sync import async_to_sync
from celery import shared_task
from channels.layers import get_channel_layer
from django.utils import timezone

from apps.core.utils import fill_template
from apps.templates_manager.models import EmailTemplate

from .models import DispatchJob, DispatchLog

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=0, time_limit=3660, soft_time_limit=3600)
def send_bulk_emails(self, job_id: str, template_id: str, csv_rows: list, file_mapping: dict = None):
    """
    Celery task that dispatches personalized emails to all recipients.
    Runs entirely in background. Pushes real-time WebSocket updates
    after each email attempt.

    Args:
        job_id: UUID string of the DispatchJob
        template_id: UUID string of the EmailTemplate
        csv_rows: List of dicts, each containing recipient data
    """
    channel_layer = get_channel_layer()
    group_name = f"dispatch_{job_id}"

    try:
        # ── 1. Fetch job and mark as in progress ─────────────
        job = DispatchJob.objects.get(pk=job_id)
        job.status = DispatchJob.Status.IN_PROGRESS
        job.save()

        # ── 2. Fetch the email template ──────────────────────
        template = EmailTemplate.objects.get(pk=template_id)

        # ── 3. Read SMTP credentials from environment ────────
        sender_email = os.environ.get("SENDER_EMAIL", "")
        sender_app_password = os.environ.get("SENDER_APP_PASSWORD", "")

        if not sender_email or not sender_app_password:
            raise ValueError(
                "SENDER_EMAIL and SENDER_APP_PASSWORD must be set in environment."
            )

        # ── 4. Open a single SMTP connection for the batch ───
        smtp = smtplib.SMTP("smtp.gmail.com", 587, timeout=60)
        smtp.starttls()
        smtp.login(sender_email, sender_app_password)

        try:
            # ── 5. Process each recipient row ────────────────
            logs_to_create = []

            for index, row in enumerate(csv_rows):
                receiver_email = row.get("receiver_email_ID", "").strip()
                receiver_name = row.get("receiver_name", "").strip()
                error_message = None
                log_status = DispatchLog.Status.SUCCESS
                # Initialize msg to None so the retry block can safely
                # check whether MIMEText was successfully constructed
                msg = None

                try:
                    # Build replacements dict from all columns
                    # (excluding the fixed receiver columns)
                    replacements = {
                        k: v
                        for k, v in row.items()
                        if k not in ("receiver_email_ID", "receiver_name")
                    }

                    # Fill the template with per-recipient data
                    filled_body = fill_template(template.body, replacements)

                    # Build email message
                    msg = MIMEMultipart()
                    msg["From"] = sender_email
                    msg["To"] = receiver_email
                    msg["Subject"] = fill_template(template.subject, replacements)
                    
                    # Attach the text body
                    msg.attach(MIMEText(filled_body, "plain"))

                    # Attach files if any
                    if template.has_attachments and file_mapping:
                        for att_idx, att_name in enumerate(template.attachment_names):
                            # Determine the file mapping key
                            if template.has_global_attachment:
                                key = f"global_{att_idx}"
                            else:
                                key = f"row_{index}_att_{att_idx}"

                            if key in file_mapping:
                                file_info = file_mapping[key]
                                try:
                                    with default_storage.open(file_info["path"], "rb") as f:
                                        part = MIMEApplication(f.read(), Name=file_info["original_name"])
                                    part["Content-Disposition"] = f'attachment; filename="{file_info["original_name"]}"'
                                    msg.attach(part)
                                except Exception as att_e:
                                    logger.error(f"Failed to attach {file_info['original_name']}: {att_e}")

                    # Send the email
                    smtp.sendmail(sender_email, receiver_email, msg.as_string())

                    # Record success
                    logs_to_create.append(
                        DispatchLog(
                            job=job,
                            recipient_email=receiver_email,
                            recipient_name=receiver_name,
                            status=DispatchLog.Status.SUCCESS,
                        )
                    )
                    job.sent_count += 1

                except smtplib.SMTPException as e:
                    # On SMTP connection error mid-batch: attempt smtp reconnect once
                    try:
                        smtp.quit()
                    except Exception:
                        pass

                    try:
                        smtp = smtplib.SMTP("smtp.gmail.com", 587, timeout=60)
                        smtp.starttls()
                        smtp.login(sender_email, sender_app_password)

                        # Only retry the send if msg was successfully built.
                        # If SMTPException fired before MIMEText was constructed
                        # (e.g. during fill_template), msg is None and we cannot
                        # retry — fall straight through to the failure branch.
                        if msg is not None:
                            smtp.sendmail(sender_email, receiver_email, msg.as_string())
                            logs_to_create.append(
                                DispatchLog(
                                    job=job,
                                    recipient_email=receiver_email,
                                    recipient_name=receiver_name,
                                    status=DispatchLog.Status.SUCCESS,
                                )
                            )
                            job.sent_count += 1
                        else:
                            raise RuntimeError(
                                "Email message was never constructed; cannot retry."
                            )
                    except Exception as retry_e:
                        error_message = str(retry_e)
                        log_status = DispatchLog.Status.FAILED
                        logger.error(
                            f"Failed to send email to {receiver_email} after retry: {error_message}"
                        )
                        logs_to_create.append(
                            DispatchLog(
                                job=job,
                                recipient_email=receiver_email,
                                recipient_name=receiver_name,
                                status=DispatchLog.Status.FAILED,
                                error_message=error_message,
                            )
                        )
                        job.failed_count += 1

                except Exception as e:
                    # Record failure
                    error_message = str(e)
                    log_status = DispatchLog.Status.FAILED
                    logger.error(
                        f"Failed to send email to {receiver_email}: {error_message}"
                    )
                    logs_to_create.append(
                        DispatchLog(
                            job=job,
                            recipient_email=receiver_email,
                            recipient_name=receiver_name,
                            status=DispatchLog.Status.FAILED,
                            error_message=error_message,
                        )
                    )
                    job.failed_count += 1

                # Save job and logs in batches of 10 or at the end
                if len(logs_to_create) >= 10 or index == len(csv_rows) - 1:
                    DispatchLog.objects.bulk_create(logs_to_create)
                    logs_to_create = []
                    job.save()

                # ── 6. Push WebSocket update ─────────────────
                async_to_sync(channel_layer.group_send)(
                    group_name,
                    {
                        "type": "dispatch.update",
                        "job_id": str(job_id),
                        "total": job.total_recipients,
                        "sent": job.sent_count,
                        "failed": job.failed_count,
                        "pending": (
                            job.total_recipients - job.sent_count - job.failed_count
                        ),
                        "last_recipient": {
                            "name": receiver_name,
                            "email": receiver_email,
                            "status": log_status,
                            "error": error_message,
                        },
                        "job_status": "IN_PROGRESS",
                    },
                )

            # ── 7. Mark job as completed ─────────────────────
            job.status = DispatchJob.Status.COMPLETED
            job.completed_at = timezone.now()
            job.save()

            # Push final WebSocket message
            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    "type": "dispatch.update",
                    "job_id": str(job_id),
                    "total": job.total_recipients,
                    "sent": job.sent_count,
                    "failed": job.failed_count,
                    "pending": 0,
                    "last_recipient": None,
                    "job_status": "COMPLETED",
                },
            )

        finally:
            # ── 8. Close SMTP connection ─────────────────────
            try:
                smtp.quit()
            except Exception:
                pass

            # ── 9. Cleanup Attachments ───────────────────────
            if file_mapping:
                try:
                    job_dir = default_storage.path(f"dispatch_attachments/{job_id}")
                    if os.path.exists(job_dir):
                        shutil.rmtree(job_dir)
                        logger.info(f"Cleaned up attachment directory for job {job_id}")
                except Exception as e:
                    logger.error(f"Failed to cleanup attachments for job {job_id}: {e}")

    except Exception as e:
        # ── 9. Handle top-level exceptions ───────────────────
        logger.exception(f"Dispatch job {job_id} failed with error: {str(e)}")

        try:
            job = DispatchJob.objects.get(pk=job_id)
            job.status = DispatchJob.Status.FAILED
            job.completed_at = timezone.now()
            job.save()

            # Push failure WebSocket message
            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    "type": "dispatch.update",
                    "job_id": str(job_id),
                    "total": job.total_recipients,
                    "sent": job.sent_count,
                    "failed": job.failed_count,
                    "pending": (
                        job.total_recipients - job.sent_count - job.failed_count
                    ),
                    "last_recipient": None,
                    "job_status": "FAILED",
                },
            )
        except Exception:
            logger.exception(f"Failed to update job {job_id} status to FAILED")

        # Re-raise for Celery to log
        raise
