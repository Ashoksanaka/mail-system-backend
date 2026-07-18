from django.conf import settings
from rest_framework import authentication, exceptions

from .clerk import verify_clerk_request
from .services import get_or_create_user_from_clerk_payload


class ClerkAuthentication(authentication.BaseAuthentication):
    """
    Authenticate API requests using a Clerk session JWT from the
    Authorization: Bearer <token> header (or __session cookie).
    """

    def authenticate_header(self, request):
        # Ensures DRF returns 401 (not 403) for anonymous API callers.
        return "Bearer"

    def authenticate(self, request):
        state = verify_clerk_request(request)

        if not state.is_signed_in:
            # No credentials → allow DRF to treat as unauthenticated.
            # Missing/invalid bearer token still becomes 401 via IsAuthenticated.
            auth_header = request.headers.get("Authorization", "")
            has_cookie = bool(request.COOKIES.get("__session"))
            if not auth_header and not has_cookie:
                return None
            reason = getattr(state, "reason", None)
            detail = getattr(reason, "value", None) or getattr(reason, "name", None) or "Invalid Clerk session token."
            # #region agent log
            import json
            import time

            print(
                "[agent-auth-debug] "
                + json.dumps(
                    {
                        "sessionId": "262c30",
                        "runId": "auth-1",
                        "hypothesisId": "F",
                        "location": "ClerkAuthentication.authenticate",
                        "message": "Clerk token rejected",
                        "data": {
                            "detail": str(detail),
                            "origin": request.META.get("HTTP_ORIGIN"),
                            "has_bearer": auth_header.lower().startswith("bearer "),
                            "authorized_parties": list(
                                getattr(settings, "CLERK_AUTHORIZED_PARTIES", []) or []
                            ),
                        },
                        "timestamp": int(time.time() * 1000),
                    }
                ),
                flush=True,
            )
            # #endregion
            raise exceptions.AuthenticationFailed(detail)

        try:
            user, _identity = get_or_create_user_from_clerk_payload(state.payload or {})
        except PermissionError as exc:
            raise exceptions.AuthenticationFailed(str(exc)) from exc
        except ValueError as exc:
            raise exceptions.AuthenticationFailed(str(exc)) from exc

        return (user, state.payload)
