import os
import subprocess
import sys
import time
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from chat.models import KnowledgeDocument, ScheduledTask
from chat.runtimes import get_runtime_adapter
from chat.views import _index_knowledge_document, _user_ollama_settings


class Command(BaseCommand):
    help = "Run due offline automation tasks once, or keep polling with --loop."

    def add_arguments(self, parser):
        parser.add_argument("--loop", action="store_true", help="Keep polling for due tasks.")
        parser.add_argument("--interval", type=int, default=30, help="Polling interval in seconds when --loop is used.")

    def handle(self, *args, **options):
        if options["loop"]:
            while True:
                self.run_due_tasks()
                time.sleep(max(5, min(300, options["interval"])))
        else:
            self.run_due_tasks()

    def run_due_tasks(self):
        now = timezone.now()
        tasks = ScheduledTask.objects.filter(enabled=True, next_run_at__lte=now).select_related("owner")
        for task in tasks:
            try:
                result = self.execute_task(task)
                task.last_result = result[:2000]
                self.stdout.write(self.style.SUCCESS(f"{task.name}: {result}"))
            except Exception as exc:
                task.last_result = "Failed: " + str(exc)[:1900]
                self.stderr.write(self.style.ERROR(f"{task.name}: {exc}"))
            task.last_run_at = now
            task.next_run_at = now + timedelta(minutes=max(5, task.interval_minutes))
            task.save(update_fields=["last_result", "last_run_at", "next_run_at", "updated_at"])

    def execute_task(self, task):
        if task.task_type == "reindex":
            documents = KnowledgeDocument.objects.filter(owner=task.owner, is_active=True)
            count = 0
            for document in documents:
                _index_knowledge_document(document, task.owner)
                count += 1
            return f"Re-indexed {count} local document(s)."

        settings = _user_ollama_settings(task.owner)
        if task.task_type == "health":
            models = get_runtime_adapter(settings.runtime, settings.server_url).models()
            return f"{settings.runtime} is reachable with {len(models)} model(s)."

        if task.task_type == "benchmark":
            model = (task.payload or {}).get("model") or settings.default_model
            ok, protocol, detail = get_runtime_adapter(settings.runtime, settings.server_url).warmup(model)
            return f"Warm-up {'passed' if ok else 'failed'} for {model} ({protocol}): {detail}"

        if task.task_type == "tests":
            root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            completed = subprocess.run(
                [sys.executable, "manage.py", "test", "chat"],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=600,
            )
            output = (completed.stdout or completed.stderr or "").strip().splitlines()
            return f"Project tests {'passed' if completed.returncode == 0 else 'failed'}: " + (output[-1] if output else "no output")

        if task.task_type == "backup":
            return "Backup reminder reached; use the local Backup panel to create an encrypted backup."

        return "No action was registered for this task type."
