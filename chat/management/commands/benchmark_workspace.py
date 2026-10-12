import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from chat.performance import benchmark_repository


class Command(BaseCommand):
    help = "Measure read-only indexing throughput for a local repository."

    def add_arguments(self, parser):
        parser.add_argument("path", type=str)
        parser.add_argument("--max-files", type=int, default=10000)
        parser.add_argument("--json", action="store_true", dest="as_json")

    def handle(self, *args, **options):
        root = Path(options["path"]).expanduser().resolve()
        if not root.is_dir():
            raise CommandError(f"Folder does not exist: {root}")
        report = benchmark_repository(root, options["max_files"])
        if options["as_json"]:
            self.stdout.write(json.dumps(report, indent=2))
        else:
            self.stdout.write(f"{report['files_seen']} files in {report['duration_ms']} ms; {report['mb_per_second']} MB/s; peak memory {report['peak_memory_bytes']} bytes")
