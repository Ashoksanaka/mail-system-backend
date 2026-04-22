# ──────────────────────────────────────────────────────────────
# Templates Manager — Serializers
# DRF serializers for email template CRUD operations
# ──────────────────────────────────────────────────────────────
import re

from rest_framework import serializers

from .models import EmailTemplate


class EmailTemplateSerializer(serializers.ModelSerializer):
    """
    Full serializer for email template detail/create/update views.
    Includes all fields and custom validation.
    """

    class Meta:
        model = EmailTemplate
        fields = [
            "id",
            "name",
            "subject",
            "has_attachments",
            "has_global_attachment",
            "attachment_names",
            "description",
            "body",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_name(self, value):
        """Name must be non-empty and stripped of whitespace."""
        stripped = value.strip()
        if not stripped:
            raise serializers.ValidationError("Template name cannot be empty.")
        return stripped

    def validate_subject(self, value):
        """Subject must be non-empty and stripped of whitespace."""
        stripped = value.strip()
        if not stripped:
            raise serializers.ValidationError("Template subject cannot be empty.")
        return stripped

    def validate_body(self, value):
        """Body must contain at least one {{placeholder}}."""
        if not re.search(r"\{\{\s*\w+\s*\}\}", value):
            raise serializers.ValidationError(
                "Template body must contain at least one {{placeholder}}."
            )
        return value


class EmailTemplateListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for template list views.
    Excludes body to keep list responses small.
    """

    class Meta:
        model = EmailTemplate
        fields = [
            "id",
            "name",
            "subject",
            "has_attachments",
            "has_global_attachment",
            "attachment_names",
            "description",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]
