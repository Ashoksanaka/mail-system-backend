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
    GET  /api/templates/       → List the caller's templates
    POST /api/templates/       → Create a new template for the caller
    """

    def get(self, request):
        templates = EmailTemplate.objects.filter(owner=request.user)
        serializer = EmailTemplateListSerializer(templates, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = EmailTemplateSerializer(
            data=request.data, context={"request": request}
        )
        if serializer.is_valid():
            serializer.save(owner=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class EmailTemplateDetailView(APIView):
    """
    GET    /api/templates/:id/    → Retrieve full template details
    PUT    /api/templates/:id/    → Update template
    DELETE /api/templates/:id/    → Delete template
    """

    def _get_template(self, request, pk):
        try:
            return EmailTemplate.objects.get(pk=pk, owner=request.user)
        except EmailTemplate.DoesNotExist:
            return None

    def get(self, request, pk):
        template = self._get_template(request, pk)
        if template is None:
            return Response(
                {"error": "Template not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = EmailTemplateSerializer(template, context={"request": request})
        return Response(serializer.data)

    def put(self, request, pk):
        template = self._get_template(request, pk)
        if template is None:
            return Response(
                {"error": "Template not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = EmailTemplateSerializer(
            template, data=request.data, context={"request": request}
        )
        if serializer.is_valid():
            serializer.save(owner=request.user)
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        template = self._get_template(request, pk)
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
    Extracts and returns all {{placeholder}} names from subject + body
    (same source text as CSV generation).
    """

    def get(self, request, pk):
        try:
            template = EmailTemplate.objects.get(pk=pk, owner=request.user)
        except EmailTemplate.DoesNotExist:
            return Response(
                {"error": "Template not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        placeholders = extract_placeholders(
            f"{template.subject} {template.body}"
        )

        return Response(
            {
                "template_id": str(template.id),
                "placeholders": placeholders,
            }
        )
