# ──────────────────────────────────────────────────────────────
# Accounts — serializers
# ──────────────────────────────────────────────────────────────
from rest_framework import serializers


class SmtpCredentialUpdateSerializer(serializers.Serializer):
    app_password = serializers.CharField(
        write_only=True,
        allow_blank=False,
        trim_whitespace=True,
        min_length=8,
        max_length=128,
        help_text="Gmail App Password (not the Google account password)",
    )

    def validate_app_password(self, value):
        cleaned = value.replace(" ", "")
        if not cleaned:
            raise serializers.ValidationError("App password cannot be empty.")
        if len(cleaned) < 8:
            raise serializers.ValidationError("App password is too short.")
        return cleaned
