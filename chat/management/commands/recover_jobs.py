from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

from chat.views import _recover_agent_jobs


class Command(BaseCommand):
    help = "Recover interrupted local agent jobs by returning them to their last queued checkpoint."

    def add_arguments(self, parser):
        parser.add_argument("--username", default="", help="Recover jobs for one username only.")

    def handle(self, *args, **options):
        username = options.get("username", "").strip()
        users = User.objects.filter(username=username) if username else User.objects.all()
        recovered = 0
        for user in users:
            recovered += len(_recover_agent_jobs(user))
        self.stdout.write(self.style.SUCCESS(f"Recovered {recovered} interrupted job(s)."))
