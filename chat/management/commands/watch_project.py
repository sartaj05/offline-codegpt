import time
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User

from chat.views import MAX_FILE_BYTES, _extract_document_text, _safe_filename, _save_knowledge_document


WATCHABLE_EXTENSIONS = {".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".cs", ".php", ".sql", ".html", ".css", ".json", ".md", ".txt", ".pdf", ".docx"}


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

        state = {}

        def scan():
            for path in root.rglob("*"):
                if not path.is_file() or path.suffix.lower() not in WATCHABLE_EXTENSIONS:
                    continue
                try:
                    stat = path.stat()
                    marker = (stat.st_mtime_ns, stat.st_size)
                    if state.get(str(path)) == marker:
                        continue
                    if stat.st_size > MAX_FILE_BYTES:
                        self.stdout.write(self.style.WARNING(f"Skipped large file: {path.name}"))
                        state[str(path)] = marker
                        continue
                    relative_name = _safe_filename(path.relative_to(root).as_posix())
                    text = _extract_document_text(relative_name, path.read_bytes())
                    _save_knowledge_document(relative_name, text, "project", owner)
                    state[str(path)] = marker
                    self.stdout.write(f"Indexed {relative_name}")
                except (OSError, ValueError) as exc:
                    self.stdout.write(self.style.WARNING(f"Skipped {path.name}: {exc}"))

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
