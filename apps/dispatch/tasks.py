# ──────────────────────────────────────────────────────────────
# Dispatch — Celery Tasks
# Async task for bulk email sending via Gmail SMTP
# ──────────────────────────────────────────────────────────────
import errno
import logging
import os
import shutil
import smtplib
import socket
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from django.core.files.storage import default_storage

from asgiref.sync import async_to_sync
from celery import shared_task
from channels.layers import get_channel_layer
from django.utils import timezone

from apps.accounts.credentials import load_smtp_login
from apps.accounts.crypto import CredentialsEncryptionError
from apps.core.utils import fill_template

from .models import DispatchJob, DispatchLog

logger = logging.getLogger(__name__)

GMAIL_SMTP_HOST = "smtp.gmail.com"
GMAIL_SMTP_PORT = 587
SMTP_CONNECT_TIMEOUT = 20

# Short messages safe to persist and send to browsers.
PUBLIC_AUTH_ERROR = "SMTP authentication failed. Check your email settings."
PUBLIC_NETWORK_ERROR = (
    "Email service is temporarily unavailable. Please try again."
)
PUBLIC_RECIPIENT_ERROR = "Email could not be sent."
PUBLIC_JOB_ERROR = "Dispatch failed. Please try again."


def _is_network_error(exc: BaseException) -> bool:
    """True for timeouts, DNS failures, and host/network unreachable errors."""
    msg = (str(exc) or "").lower()
    if isinstance(exc, (TimeoutError, socket.timeout)) or "timed out" in msg:
        return True
    if isinstance(exc, socket.gaierror) or "name resolution" in msg:
        return True
    if (
        isinstance(exc, OSError)
        and getattr(exc, "errno", None)
        in (errno.ENETUNREACH, errno.EHOSTUNREACH, errno.ECONNREFUSED)
    ) or "unreachable" in msg:
        return True
    return False


def _format_dispatch_error(exc: BaseException) -> tuple[str, str]:
    """
    Return (internal_detail, public_message).

    internal_detail: verbose text for server logs (same verbosity as before).
    public_message: short user-safe text for DB / WebSocket / API clients.
    """
    if isinstance(exc, smtplib.SMTPAuthenticationError):
        internal = (
            f"Gmail SMTP authentication failed: {exc}. "
            "Check the app password under Settings."
        )
        return internal, PUBLIC_AUTH_ERROR

    msg = str(exc) or exc.__class__.__name__
    if _is_network_error(exc):
        internal = (
            f"Cannot connect to Gmail SMTP "
            f"({GMAIL_SMTP_HOST}:{GMAIL_SMTP_PORT} — {msg}). "
            "This is a network/firewall issue, not an authentication failure."
        )
        return internal, PUBLIC_NETWORK_ERROR

    return msg, PUBLIC_JOB_ERROR


class _IPv4SMTP(smtplib.SMTP):
    """SMTP client that only dials IPv4 (avoids broken AAAA routes)."""

    def _get_socket(self, host, port, timeout):
        last_error = None
        for family, socktype, proto, _canon, sockaddr in socket.getaddrinfo(
            host, port, socket.AF_INET, socket.SOCK_STREAM
        ):
            sock = socket.socket(family, socktype, proto)
            if timeout is not None:
                sock.settimeout(timeout)
            try:
                sock.connect(sockaddr)
                return sock
            except OSError as exc:
                last_error = exc
                try:
                    sock.close()
                except OSError:
                    pass
        if last_error is not None:
            raise last_error
        raise OSError(f"No IPv4 address found for {host}")


def _open_gmail_smtp(timeout: int = SMTP_CONNECT_TIMEOUT) -> smtplib.SMTP:
    """
    Open an SMTP connection to Gmail, preferring IPv4.

    Uses a real hostname on the SMTP client so STARTTLS SNI / cert
    verification works (empty _host raises ValueError from ssl).
    """
    return _IPv4SMTP(GMAIL_SMTP_HOST, GMAIL_SMTP_PORT, timeout=timeout)


def cleanup_job_attachments(job_id: str) -> bool:
    """
    Remove the on-disk attachment directory for a dispatch job.

    Returns True if a directory was removed, False otherwise.
    """
    try:
        job_dir = default_storage.path(f"dispatch_attachments/{job_id}")
        if os.path.isdir(job_dir):
            shutil.rmtree(job_dir)
            logger.info("Cleaned up attachment directory for job %s", job_id)
            return True
    except Exception as exc:
        logger.error("Failed to cleanup attachments for job %s: %s", job_id, exc)
    return False


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
        job = DispatchJob.objects.select_related("template", "owner").get(pk=job_id)
        job.status = DispatchJob.Status.IN_PROGRESS
        job.save(update_fields=["status"])

        # ── 2. Fetch the email template through the owned job ─
        template = job.template
        if template is None or str(template.id) != str(template_id):
            raise ValueError(
                "Dispatch job template mismatch or missing template; refusing to send."
            )
        if template.owner_id != job.owner_id:
            raise ValueError(
                "Dispatch job and template owners do not match; refusing to send."
            )

        # ── 3. Load per-owner SMTP credentials from the DB ───
        try:
            sender_email, sender_app_password = load_smtp_login(job.owner)
        except (ValueError, CredentialsEncryptionError) as exc:
            raise ValueError(str(exc)) from exc

        # ── 4. Open a single SMTP connection for the batch ───
        smtp = _open_gmail_smtp()
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
                        smtp = _open_gmail_smtp()
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
                        internal_error = str(retry_e)
                        error_message = PUBLIC_RECIPIENT_ERROR
                        log_status = DispatchLog.Status.FAILED
                        logger.error(
                            "Failed to send email to %s after retry: %s",
                            receiver_email,
                            internal_error,
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
                    # Record failure — verbose detail stays in logs only
                    internal_error = str(e)
                    error_message = PUBLIC_RECIPIENT_ERROR
                    log_status = DispatchLog.Status.FAILED
                    logger.error(
                        "Failed to send email to %s: %s",
                        receiver_email,
                        internal_error,
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

    except Exception as e:
        # ── 9. Handle top-level exceptions ───────────────────
        internal_error, public_error = _format_dispatch_error(e)
        logger.exception(
            "Dispatch job %s failed with error: %s", job_id, internal_error
        )

        try:
            job = DispatchJob.objects.get(pk=job_id)
            remaining = max(
                0,
                job.total_recipients - job.sent_count - job.failed_count,
            )
            job.status = DispatchJob.Status.FAILED
            job.error_message = public_error
            job.failed_count = job.failed_count + remaining
            job.completed_at = timezone.now()
            job.save(
                update_fields=[
                    "status",
                    "error_message",
                    "failed_count",
                    "completed_at",
                ]
            )

            # Per-recipient logs for rows never processed in this run
            processed = job.logs.count()
            abort_logs = []
            for row in (csv_rows or [])[processed:]:
                abort_logs.append(
                    DispatchLog(
                        job=job,
                        recipient_email=(row.get("receiver_email_ID") or "").strip()
                        or "unknown@invalid",
                        recipient_name=(row.get("receiver_name") or "").strip(),
                        status=DispatchLog.Status.FAILED,
                        error_message=public_error,
                    )
                )
            if abort_logs:
                DispatchLog.objects.bulk_create(abort_logs)

            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    "type": "dispatch.update",
                    "job_id": str(job_id),
                    "total": job.total_recipients,
                    "sent": job.sent_count,
                    "failed": job.failed_count,
                    "pending": 0,
                    "aborted": remaining,
                    "last_recipient": None,
                    "job_status": "FAILED",
                    "error": public_error,
                },
            )
        except Exception:
            logger.exception("Failed to update job %s status to FAILED", job_id)

        # Re-raise for Celery to log
        raise
    finally:
        # ── 10. Always cleanup attachments (success or failure) ─
        cleanup_job_attachments(job_id)


@shared_task(ignore_result=True)
def cleanup_stale_dispatch_attachments(max_age_hours: int = 6):
    """
    Remove leftover attachment directories for finished or abandoned jobs.

    Deletes a job directory when:
    - the DispatchJob no longer exists, or
    - the job is COMPLETED / FAILED, or
    - the directory is older than max_age_hours (stuck PENDING / IN_PROGRESS).
    """
    try:
        root = default_storage.path("dispatch_attachments")
    except Exception as exc:
        logger.error("Cannot resolve dispatch_attachments path: %s", exc)
        return {"removed": 0, "skipped": 0}

    if not os.path.isdir(root):
        return {"removed": 0, "skipped": 0}

    cutoff = timezone.now() - timedelta(hours=max_age_hours)
    removed = 0
    skipped = 0
    terminal = {DispatchJob.Status.COMPLETED, DispatchJob.Status.FAILED}

    for name in os.listdir(root):
        job_dir = os.path.join(root, name)
        if not os.path.isdir(job_dir):
            continue

        should_remove = False
        try:
            job = DispatchJob.objects.filter(pk=name).only("status", "created_at").first()
            if job is None:
                should_remove = True
            elif job.status in terminal:
                should_remove = True
            else:
                dir_mtime = datetime.fromtimestamp(
                    os.path.getmtime(job_dir),
                    tz=timezone.get_current_timezone(),
                )
                if dir_mtime < cutoff:
                    should_remove = True
        except Exception as exc:
            logger.error("Error inspecting attachment dir %s: %s", name, exc)
            skipped += 1
            continue

        if should_remove and cleanup_job_attachments(name):
            removed += 1
        else:
            skipped += 1

    logger.info(
        "Stale attachment cleanup finished: removed=%s skipped=%s",
        removed,
        skipped,
    )
    return {"removed": removed, "skipped": skipped}
