import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from chat.security_audit import audit_project


class Command(BaseCommand):
    help = "Run a read-only local security audit for coding and tool boundaries."

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true", dest="as_json")
        parser.add_argument("--fail-on-high", action="store_true")

    def handle(self, *args, **options):
        report = audit_project(Path(settings.BASE_DIR))
        if options["as_json"]:
            self.stdout.write(json.dumps(report, indent=2))
        else:
            self.stdout.write(f"Scanned {report['scanned_files']} files: {report['summary']}")
            for finding in report["findings"]:
                self.stdout.write(f"[{finding['severity']}] {finding['category']}: {finding['message']}")
        if options["fail_on_high"] and not report["success"]:
            raise CommandError("Security audit found high-severity findings.")
