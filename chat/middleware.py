import json
import os

from django.core.cache import cache
from django.http import JsonResponse

from .models import AuditEvent, Workspace
from .security import redact_coding_response
from .deployment_mode import current_mode


class DeploymentModeMiddleware:
    """Enforce hosted-mode authentication and local capability boundaries."""

    capability_prefixes = {
        "local_runtime": (
            "/api/ask-code/",
            "/api/ollama/",
            "/api/models/",
            "/api/ocr/",
            "/api/speech/",
            "/api/screen/",
        ),
        "local_files": (
            "/api/project/",
            "/api/agent/worktrees/",
        ),
        "local_git": ("/api/git/",),
        "local_tools": (
            "/api/execute/",
            "/api/mcp/",
            "/api/tests/run",
            "/api/agent/job/",
            "/api/agent/task/",
            "/api/agent/team/",
            "/api/scheduler/",
        ),
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        mode = current_mode()
        path = request.path

        if mode == "hosted" and path.startswith("/api/") and path not in {
            "/api/deployment/mode/",
            "/api/privacy/",
        } and not getattr(request.user, "is_authenticated", False):
            return JsonResponse({
                "success": False,
                "error": "Hosted Mode requires sign-in before using workspace APIs.",
                "authentication_required": True,
            }, status=401)

        if mode == "hosted":
            for capability, prefixes in self.capability_prefixes.items():
                if any(path.startswith(prefix) for prefix in prefixes):
                    return JsonResponse({
                        "success": False,
                        "error": f"{capability.replace('_', ' ').title()} are disabled in Hosted Mode.",
                        "deployment_mode": mode,
                        "capability": capability,
                    }, status=403)

        return self.get_response(request)


class CodingSecurityMiddleware:
    """Apply one safety boundary to every authenticated coding API request."""

    max_body_bytes = 2_500_000
    window_seconds = 60

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        guarded = request.path.startswith("/api/coding/")
        if not guarded:
            return self.get_response(request)
        if int(request.META.get("CONTENT_LENGTH") or 0) > self.max_body_bytes:
            return JsonResponse({"success": False, "error": "Coding request is limited to 2.5 MB."}, status=413)
        if request.method in {"POST", "PUT", "PATCH"}:
            identity = getattr(request.user, "pk", None) or request.META.get("REMOTE_ADDR", "local")
            key = f"coding-rate:{identity}:{request.path}"
            count = cache.get(key, 0) + 1
            cache.set(key, count, self.window_seconds)
            limit = int(os.environ.get("LOCAL_CODING_RATE_LIMIT", "120"))
            if count > max(10, limit):
                return JsonResponse({"success": False, "error": "Coding API rate limit reached; retry shortly."}, status=429)
        response = self.get_response(request)
        if getattr(request.user, "is_authenticated", False) and request.method in {"POST", "PUT", "PATCH"}:
            workspace, _ = Workspace.objects.get_or_create(owner=request.user, name="Personal coding workspace")
            AuditEvent.objects.create(actor=request.user, workspace=workspace, event_type="coding.api_request", details={"path": request.path[:160], "method": request.method, "status": response.status_code})
        if hasattr(response, "streaming_content"):
            return response
        if response.get("Content-Type", "").startswith("application/json"):
            try:
                payload = json.loads(response.content.decode("utf-8"))
                masked = redact_coding_response(json.dumps(payload, ensure_ascii=False))
                response.content = masked.encode("utf-8")
                response.headers["Content-Length"] = str(len(response.content))
            except (TypeError, ValueError, UnicodeDecodeError):
                pass
        return response
