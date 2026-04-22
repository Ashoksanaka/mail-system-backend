# ──────────────────────────────────────────────────────────────
# Templates Manager — Views
# API views for email template CRUD + placeholder extraction
# ──────────────────────────────────────────────────────────────
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.utils import extract_placeholders

from .models import EmailTemplate
from .serializers import EmailTemplateListSerializer, EmailTemplateSerializer


class EmailTemplateListCreateView(APIView):
    """
    GET  /api/templates/       → List all templates (lightweight)
    POST /api/templates/       → Create a new template
    """

    def get(self, request):
        """Return list of all templates ordered by -created_at."""
        templates = EmailTemplate.objects.all()
        serializer = EmailTemplateListSerializer(templates, many=True)
        return Response(serializer.data)

    def post(self, request):
        """Create a new email template."""
        serializer = EmailTemplateSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class EmailTemplateDetailView(APIView):
    """
    GET    /api/templates/:id/    → Retrieve full template details
    PUT    /api/templates/:id/    → Update template
    DELETE /api/templates/:id/    → Delete template
    """

    def _get_template(self, pk):
        """Fetch template by primary key or return None."""
        try:
            return EmailTemplate.objects.get(pk=pk)
        except EmailTemplate.DoesNotExist:
            return None

    def get(self, request, pk):
        """Return full template details."""
        template = self._get_template(pk)
        if template is None:
            return Response(
                {"error": "Template not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = EmailTemplateSerializer(template)
        return Response(serializer.data)

    def put(self, request, pk):
        """Update an existing template (all fields)."""
        template = self._get_template(pk)
        if template is None:
            return Response(
                {"error": "Template not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = EmailTemplateSerializer(template, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        """Delete an email template."""
        template = self._get_template(pk)
        if template is None:
            return Response(
                {"error": "Template not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        
        template.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ExtractPlaceholdersView(APIView):
    """
    GET /api/templates/:id/extract-placeholders/
    Extracts and returns all {{placeholder}} names from a template's body.
    """

    def get(self, request, pk):
        """Extract placeholders from the template body."""
        try:
            template = EmailTemplate.objects.get(pk=pk)
        except EmailTemplate.DoesNotExist:
            return Response(
                {"error": "Template not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        placeholders = extract_placeholders(template.body)

        return Response(
            {
                "template_id": str(template.id),
                "placeholders": placeholders,
            }
        )
