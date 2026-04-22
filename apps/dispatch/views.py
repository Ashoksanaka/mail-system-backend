# ──────────────────────────────────────────────────────────────
# Dispatch — Views
# API views for CSV generation, upload/validation, and dispatch
# ──────────────────────────────────────────────────────────────
import csv
import io
import uuid

from django.http import HttpResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.utils import extract_placeholders, generate_csv_content
from apps.templates_manager.models import EmailTemplate

from .models import DispatchJob
from .serializers import DispatchJobSerializer, DispatchLogSerializer
from .tasks import send_bulk_emails


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

        # Fetch the email template
        try:
            template = EmailTemplate.objects.get(pk=template_id)
        except EmailTemplate.DoesNotExist:
            return Response(
                {"error": "Template not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Extract placeholders and generate CSV content
        placeholders = extract_placeholders(f"{template.subject} {template.body}")
        csv_content = generate_csv_content(placeholders)

        # Build file response
        # Sanitize template name for filename
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

        # ── Input validation ─────────────────────────────────
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

        # Fetch template
        try:
            template = EmailTemplate.objects.get(pk=template_id)
        except EmailTemplate.DoesNotExist:
            return Response(
                {"error": "Template not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # ── Parse and validate CSV ───────────────────────────
        expected_placeholders = extract_placeholders(f"{template.subject} {template.body}")
        validation_errors = []

        try:
            # Read the CSV file content
            decoded = csv_file.read().decode("utf-8-sig")
            reader = csv.DictReader(io.StringIO(decoded))

            # Check headers exist
            if reader.fieldnames is None:
                return Response(
                    {"error": "CSV file is empty or has no headers."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            headers = [h.strip() for h in reader.fieldnames]

            # Validate required columns
            if "receiver_email_ID" not in headers:
                validation_errors.append(
                    "Missing required column: 'receiver_email_ID'"
                )
            if "receiver_name" not in headers:
                validation_errors.append(
                    "Missing required column: 'receiver_name'"
                )

            # Validate placeholder columns
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

            # Read all rows
            rows = []
            for row in reader:
                # Strip whitespace from keys
                cleaned = {k.strip(): v for k, v in row.items()}
                rows.append(cleaned)

            # Validate at least 1 data row
            if len(rows) == 0:
                return Response(
                    {
                        "error": "CSV validation failed.",
                        "details": ["CSV must have at least 1 data row."],
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Validate receiver_email_ID values are non-empty
            empty_email_rows = []
            for i, row in enumerate(rows, start=2):  # start=2 (header is row 1)
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

            # ── Success response ─────────────────────────────
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

        # ── Input validation (cheap checks first) ───────────
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

        # ── Rate limiting / Active Job Check (DB query) ──────
        if DispatchJob.objects.filter(status=DispatchJob.Status.IN_PROGRESS).exists():
            return Response(
                {"error": "A dispatch job is already in progress. Please wait."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        # Fetch template
        try:
            template = EmailTemplate.objects.get(pk=template_id)
        except EmailTemplate.DoesNotExist:
            return Response(
                {"error": "Template not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # ── Parse CSV ────────────────────────────────────────
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

        # ── Create DispatchJob ───────────────────────────────
        job = DispatchJob.objects.create(
            template=template,
            total_recipients=len(rows),
            status=DispatchJob.Status.PENDING,
        )

        # ── Handle Attachments ───────────────────────────────
        from django.core.files.storage import default_storage
        file_mapping = {}

        if template.has_attachments:
            job_dir = f"dispatch_attachments/{job.id}"
            
            for key, file in request.FILES.items():
                # Skip the primary csv_file
                if key == "csv_file":
                    continue
                
                # Check if it matches our attachment keys format
                if key.startswith("global_") or key.startswith("row_"):
                    # Save the file temporarily
                    file_path = default_storage.save(f"{job_dir}/{file.name}", file)
                    file_mapping[key] = {
                        "path": file_path,
                        "original_name": file.name,
                        "content_type": file.content_type,
                    }

        # ── Trigger Celery task ──────────────────────────────
        send_bulk_emails.delay(
            str(job.id),
            str(template.id),
            rows,
            file_mapping,
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
            job = DispatchJob.objects.select_related('template').get(pk=job_id)
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
