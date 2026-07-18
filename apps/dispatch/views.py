# ──────────────────────────────────────────────────────────────
# Dispatch — Views
# API views for CSV generation, upload/validation, and dispatch
# ──────────────────────────────────────────────────────────────
import csv
import io
import uuid

from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.credentials import user_has_configured_smtp
from apps.core.utils import extract_placeholders, generate_csv_content
from apps.templates_manager.models import EmailTemplate

from .models import DispatchJob
from .serializers import DispatchJobSerializer, DispatchLogSerializer
from .tasks import cleanup_job_attachments, send_bulk_emails


class GenerateCSVView(APIView):
    """
    POST /api/dispatch/generate-csv/
    Generates a downloadable CSV template with the correct headers
    based on a template's placeholders.
    """

    def post(self, request):
        """Generate and return a CSV file with headers only."""
        template_id = request.data.get("template_id")
        if not template_id:
            return Response(
                {"error": "template_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            uuid.UUID(str(template_id))
        except ValueError:
            return Response(
                {"error": "Invalid template_id format."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            template = EmailTemplate.objects.get(pk=template_id, owner=request.user)
        except EmailTemplate.DoesNotExist:
            return Response(
                {"error": "Template not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        placeholders = extract_placeholders(f"{template.subject} {template.body}")
        csv_content = generate_csv_content(placeholders)

        safe_name = template.name.replace(" ", "_").lower()
        filename = f"recipients_{safe_name}.csv"

        response = HttpResponse(csv_content, content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


class UploadCSVView(APIView):
    """
    POST /api/dispatch/upload-csv/
    Validates an uploaded CSV file against a template's placeholders.
    Returns validation result and a preview of the data.
    """

    def post(self, request):
        """Upload and validate a CSV file."""
        template_id = request.data.get("template_id")
        csv_file = request.FILES.get("csv_file")

        if not template_id:
            return Response(
                {"error": "template_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            uuid.UUID(str(template_id))
        except ValueError:
            return Response(
                {"error": "Invalid template_id format."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not csv_file:
            return Response(
                {"error": "csv_file is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            template = EmailTemplate.objects.get(pk=template_id, owner=request.user)
        except EmailTemplate.DoesNotExist:
            return Response(
                {"error": "Template not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        expected_placeholders = extract_placeholders(
            f"{template.subject} {template.body}"
        )
        validation_errors = []

        try:
            decoded = csv_file.read().decode("utf-8-sig")
            reader = csv.DictReader(io.StringIO(decoded))

            if reader.fieldnames is None:
                return Response(
                    {"error": "CSV file is empty or has no headers."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            headers = [h.strip() for h in reader.fieldnames]

            if "receiver_email_ID" not in headers:
                validation_errors.append(
                    "Missing required column: 'receiver_email_ID'"
                )
            if "receiver_name" not in headers:
                validation_errors.append(
                    "Missing required column: 'receiver_name'"
                )

            for placeholder in expected_placeholders:
                if placeholder not in headers:
                    validation_errors.append(
                        f"Missing placeholder column: '{placeholder}'"
                    )

            if validation_errors:
                return Response(
                    {"error": "CSV validation failed.", "details": validation_errors},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            rows = []
            for row in reader:
                cleaned = {k.strip(): v for k, v in row.items()}
                rows.append(cleaned)

            if len(rows) == 0:
                return Response(
                    {
                        "error": "CSV validation failed.",
                        "details": ["CSV must have at least 1 data row."],
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            empty_email_rows = []
            for i, row in enumerate(rows, start=2):
                email = row.get("receiver_email_ID", "").strip()
                if not email:
                    empty_email_rows.append(f"Row {i}")

            if empty_email_rows:
                return Response(
                    {
                        "error": "CSV validation failed.",
                        "details": [
                            f"Empty receiver_email_ID in: {', '.join(empty_email_rows[:10])}"
                        ],
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            return Response(
                {
                    "valid": True,
                    "total_rows": len(rows),
                    "headers": headers,
                    "preview_rows": rows[:100],
                    "template_id": str(template.id),
                    "template_name": template.name,
                }
            )

        except UnicodeDecodeError:
            return Response(
                {"error": "CSV file encoding is not valid UTF-8."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except csv.Error as e:
            return Response(
                {"error": f"CSV parsing error: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )


class StartDispatchView(APIView):
    """
    POST /api/dispatch/start/
    Parses the CSV, creates a DispatchJob, and triggers the
    Celery task for bulk email sending.
    """

    def post(self, request):
        """Start a bulk email dispatch."""
        template_id = request.data.get("template_id")
        csv_file = request.FILES.get("csv_file")

        if not template_id:
            return Response(
                {"error": "template_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            uuid.UUID(str(template_id))
        except ValueError:
            return Response(
                {"error": "Invalid template_id format."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not csv_file:
            return Response(
                {"error": "csv_file is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if DispatchJob.objects.filter(
            owner=request.user,
            status__in=[
                DispatchJob.Status.PENDING,
                DispatchJob.Status.IN_PROGRESS,
            ],
        ).exists():
            existing = (
                DispatchJob.objects.filter(
                    owner=request.user,
                    status__in=[
                        DispatchJob.Status.PENDING,
                        DispatchJob.Status.IN_PROGRESS,
                    ],
                )
                .order_by("-created_at")
                .first()
            )
            return Response(
                {
                    "error": "A dispatch job is already in progress. Please wait.",
                    "job_id": str(existing.id),
                    "total_recipients": existing.total_recipients,
                    "status": existing.status,
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        if not user_has_configured_smtp(request.user):
            return Response(
                {
                    "error": (
                        "Gmail app password is not configured. "
                        "Add it under Settings before starting a dispatch."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            template = EmailTemplate.objects.get(pk=template_id, owner=request.user)
        except EmailTemplate.DoesNotExist:
            return Response(
                {"error": "Template not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            decoded = csv_file.read().decode("utf-8-sig")
            reader = csv.DictReader(io.StringIO(decoded))

            rows = []
            for row in reader:
                cleaned = {k.strip(): v for k, v in row.items()}
                rows.append(cleaned)

            if len(rows) == 0:
                return Response(
                    {"error": "CSV must have at least 1 data row."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        except (UnicodeDecodeError, csv.Error) as e:
            return Response(
                {"error": f"CSV parsing error: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        job = DispatchJob.objects.create(
            owner=request.user,
            template=template,
            total_recipients=len(rows),
            status=DispatchJob.Status.PENDING,
        )

        from django.core.files.storage import default_storage

        file_mapping = {}

        if template.has_attachments:
            job_dir = f"dispatch_attachments/{job.id}"

            for key, file in request.FILES.items():
                if key == "csv_file":
                    continue

                if key.startswith("global_") or key.startswith("row_"):
                    file_path = default_storage.save(f"{job_dir}/{file.name}", file)
                    file_mapping[key] = {
                        "path": file_path,
                        "original_name": file.name,
                        "content_type": file.content_type,
                    }

        try:
            send_bulk_emails.delay(
                str(job.id),
                str(template.id),
                rows,
                file_mapping,
            )
        except Exception:
            cleanup_job_attachments(str(job.id))
            job.status = DispatchJob.Status.FAILED
            job.error_message = "Failed to queue dispatch task."
            job.completed_at = timezone.now()
            job.save(
                update_fields=["status", "error_message", "completed_at"]
            )
            return Response(
                {"error": "Failed to queue dispatch task. Please try again."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            {
                "job_id": str(job.id),
                "total_recipients": job.total_recipients,
                "status": job.status,
            },
            status=status.HTTP_201_CREATED,
        )


class DispatchJobDetailView(APIView):
    """
    GET /api/dispatch/jobs/:job_id/
    Returns job details and all associated dispatch logs.
    """

    def get(self, request, job_id):
        """Retrieve dispatch job status and logs."""
        try:
            job = DispatchJob.objects.select_related("template").get(
                pk=job_id, owner=request.user
            )
        except DispatchJob.DoesNotExist:
            return Response(
                {"error": "Dispatch job not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        logs = job.logs.all()

        return Response(
            {
                "job": DispatchJobSerializer(job).data,
                "logs": DispatchLogSerializer(logs, many=True).data,
            }
        )
