# ──────────────────────────────────────────────────────────────
# Accounts — API views
# ──────────────────────────────────────────────────────────────
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .credentials import set_app_password, smtp_status
from .serializers import SmtpCredentialUpdateSerializer


class SmtpCredentialView(APIView):
    """
    GET  /api/account/smtp/  → sender_email + has_app_password
    PUT  /api/account/smtp/  → set/update Gmail app password
    """

    def get(self, request):
        return Response(smtp_status(request.user))

    def put(self, request):
        if "sender_email" in request.data:
            return Response(
                {"error": "sender_email cannot be changed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = SmtpCredentialUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            set_app_password(request.user, serializer.validated_data["app_password"])
        except ValueError as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(smtp_status(request.user))
