import time

from django.core.management.base import BaseCommand

from chat.job_runner import process_queued_jobs


class Command(BaseCommand):
    help = "Process queued local AgentJob records once or keep polling."

    def add_arguments(self, parser):
        parser.add_argument("--loop", action="store_true")
        parser.add_argument("--interval", type=float, default=2.0)
        parser.add_argument("--limit", type=int, default=5)

    def handle(self, *args, **options):
        while True:
            jobs = process_queued_jobs(limit=options["limit"])
            for job in jobs:
                self.stdout.write(self.style.SUCCESS(f"Job {job.id}: {job.status}"))
            if not options["loop"]:
                return
            time.sleep(max(0.5, min(60.0, options["interval"])))
