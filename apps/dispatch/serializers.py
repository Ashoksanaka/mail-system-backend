# ──────────────────────────────────────────────────────────────
# Dispatch — Serializers
# DRF serializers for dispatch jobs and logs
# ──────────────────────────────────────────────────────────────
from rest_framework import serializers

from .models import DispatchJob, DispatchLog


class DispatchJobSerializer(serializers.ModelSerializer):
    """
    Serializer for DispatchJob model.
    Includes a read-only template_name field derived from the FK relationship.
    """

    template_name = serializers.SerializerMethodField()

    def get_template_name(self, obj):
        return obj.template.name if obj.template else "Deleted Template"

    class Meta:
        model = DispatchJob
        fields = [
            "id",
            "template",
            "template_name",
            "total_recipients",
            "sent_count",
            "failed_count",
            "status",
            "created_at",
            "completed_at",
        ]
        read_only_fields = [
            "id",
            "template_name",
            "total_recipients",
            "sent_count",
            "failed_count",
            "status",
            "created_at",
            "completed_at",
        ]


class DispatchLogSerializer(serializers.ModelSerializer):
    """
    Serializer for individual dispatch log entries.
    Records the result of each email send attempt.
    """

    class Meta:
        model = DispatchLog
        fields = [
            "id",
            "job",
            "recipient_email",
            "recipient_name",
            "status",
            "error_message",
            "sent_at",
        ]
        read_only_fields = [
            "id",
            "job",
            "recipient_email",
            "recipient_name",
            "status",
            "error_message",
            "sent_at",
        ]
