import time

from django.core.management.base import BaseCommand

from chat.job_runner import process_queued_jobs
from chat.management.commands.run_scheduler import Command as SchedulerCommand


class Command(BaseCommand):
    help = "Run the local agent queue and scheduled offline tasks."

    def add_arguments(self, parser):
        parser.add_argument("--loop", action="store_true", help="Keep polling until stopped.")
        parser.add_argument("--interval", type=float, default=5.0, help="Polling interval in seconds.")
        parser.add_argument("--limit", type=int, default=5, help="Maximum queued agent jobs per cycle.")

    def run_cycle(self, limit):
        jobs = process_queued_jobs(limit=limit)
        for job in jobs:
            self.stdout.write(self.style.SUCCESS(f"Agent job {job.id}: {job.status}"))
        SchedulerCommand().run_due_tasks()
        return len(jobs)

    def handle(self, *args, **options):
        while True:
            self.run_cycle(max(1, min(int(options["limit"]), 50)))
            if not options["loop"]:
                return
            time.sleep(max(1.0, min(300.0, float(options["interval"]))))
