"""Persistent local worker for approval-gated AgentJob records."""

from django.utils import timezone

from .models import AgentJob
from .sandbox import run_sandboxed_code
from .security import scan_files


def execute_agent_job(job):
    if job.status in {"cancelled", "completed"}:
        return job
    job.status = "running"
    job.attempts += 1
    job.started_at = job.started_at or timezone.now()
    job.checkpoint = {**(job.checkpoint or {}), "stage": "safe_checks", "updated_at": timezone.now().isoformat()}
    logs = [*(job.logs or []), {"level": "info", "message": f"Worker attempt {job.attempts} started."}]
    code = (job.payload or {}).get("code", "")
    test_code = (job.payload or {}).get("test_code", "")
    if code:
        scan = scan_files([{"filename": "background-agent-buffer", "content": code}])
        logs.append({"level": "warning" if scan["findings"] else "info", "message": scan["summary"]})
    if test_code and job.status == "running":
        result = run_sandboxed_code("python", code + "\n\n" + test_code)
        logs.append({"level": "info" if result["success"] else "error", "message": "Guarded tests " + ("passed." if result["success"] else "failed.")})
        job.checkpoint["tests_passed"] = result["success"]
        if not result["success"]:
            job.status = "failed"
            job.last_error = result.get("stderr") or "Guarded tests failed."
    if job.status == "running":
        job.status = "completed"
        job.checkpoint["stage"] = "completed"
        job.finished_at = timezone.now()
        logs.append({"level": "info", "message": "Background job completed at a safe checkpoint."})
    job.logs = logs[-100:]
    job.save(update_fields=["status", "attempts", "started_at", "finished_at", "checkpoint", "logs", "last_error", "updated_at"])
    return job


def process_queued_jobs(owner=None, limit=5):
    queryset = AgentJob.objects.filter(status="queued").order_by("created_at", "id")
    if owner is not None:
        queryset = queryset.filter(owner=owner)
    processed = []
    for job in queryset.select_related("task")[:max(1, min(int(limit), 50))]:
        processed.append(execute_agent_job(job))
    return processed
