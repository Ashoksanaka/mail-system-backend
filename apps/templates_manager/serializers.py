# ──────────────────────────────────────────────────────────────
# Templates Manager — Serializers
# DRF serializers for email template CRUD operations
# ──────────────────────────────────────────────────────────────
from rest_framework import serializers

from apps.core.utils import PLACEHOLDER_PATTERN, extract_placeholders

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
        """Name must be non-empty, unique per owner."""
        stripped = value.strip()
        if not stripped:
            raise serializers.ValidationError("Template name cannot be empty.")

        request = self.context.get("request")
        owner = getattr(request, "user", None) if request else None
        if owner and owner.is_authenticated:
            qs = EmailTemplate.objects.filter(owner=owner, name=stripped)
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    "You already have a template with this name."
                )
        return stripped

    def validate_subject(self, value):
        """Subject must be non-empty and stripped of whitespace."""
        stripped = value.strip()
        if not stripped:
            raise serializers.ValidationError("Template subject cannot be empty.")
        return stripped

    def validate_body(self, value):
        """Body must contain at least one underscore-style {{placeholder}}."""
        if not PLACEHOLDER_PATTERN.search(value) or not extract_placeholders(value):
            raise serializers.ValidationError(
                "Template body must contain at least one {{placeholder}} "
                "(use underscore-separated names like {{Your_Contact_Info}})."
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
