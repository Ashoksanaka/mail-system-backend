"""Temporary CORS debug middleware — logs Origin vs allowlist (debug session 262c30)."""
from django.conf import settings


class CorsDebugMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        origin = request.META.get("HTTP_ORIGIN", "")
        allowed = list(getattr(settings, "CORS_ALLOWED_ORIGINS", []) or [])
        matched = origin in allowed if origin else False

        # #region agent log
        try:
            import json
            import time

            payload = {
                "sessionId": "262c30",
                "runId": "cors-1",
                "hypothesisId": "A",
                "location": "CorsDebugMiddleware",
                "message": "Incoming Origin vs CORS allowlist",
                "data": {
                    "origin": origin or None,
                    "matched": matched,
                    "path": request.path,
                    "method": request.method,
                    "allowed_count": len(allowed),
                    "allowed_sample": allowed[:8],
                },
                "timestamp": int(time.time() * 1000),
            }
            print(f"[agent-cors-debug] {json.dumps(payload)}", flush=True)
        except Exception:
            pass
        # #endregion

        response = self.get_response(request)
        response["X-Debug-Request-Origin"] = origin or "(none)"
        response["X-Debug-Cors-Matched"] = "true" if matched else "false"
        return response
