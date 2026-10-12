import time
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User

from chat.models import ProjectWorkspace
from chat.workspace_indexer import scan_workspace


class Command(BaseCommand):
    help = "Watch a local folder and incrementally index changed project files."

    def add_arguments(self, parser):
        parser.add_argument("path", type=str)
        parser.add_argument("--username", required=True)
        parser.add_argument("--once", action="store_true", help="Scan once and exit.")
        parser.add_argument("--interval", type=float, default=2.0)

    def handle(self, *args, **options):
        root = Path(options["path"]).expanduser().resolve()
        if not root.is_dir():
            raise CommandError(f"Folder does not exist: {root}")
        try:
            owner = User.objects.get(username=options["username"])
        except User.DoesNotExist as exc:
            raise CommandError("Choose an existing local user with --username.") from exc

        def scan():
            workspace, _ = ProjectWorkspace.objects.get_or_create(owner=owner, root_path=str(root), defaults={"name": root.name or str(root)})
            result = scan_workspace(workspace)
            self.stdout.write(f"Scan {result.status}: {result.indexed_count} indexed, {result.skipped_count} unchanged/skipped.")

        scan()
        if options["once"]:
            return
        self.stdout.write(self.style.SUCCESS(f"Watching {root} for changes. Press Ctrl+C to stop."))
        try:
            while True:
                scan()
                time.sleep(max(0.5, options["interval"]))
        except KeyboardInterrupt:
            self.stdout.write("Watcher stopped.")
