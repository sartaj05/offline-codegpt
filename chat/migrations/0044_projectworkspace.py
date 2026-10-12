from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("chat", "0043_codingworkflowartifact")]

    operations = [
        migrations.CreateModel(
            name="ProjectWorkspace",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=160)),
                ("root_path", models.TextField()),
                ("status", models.CharField(choices=[("idle", "Idle"), ("scanning", "Scanning"), ("ready", "Ready"), ("error", "Error")], default="idle", max_length=20)),
                ("files_seen", models.PositiveIntegerField(default=0)),
                ("indexed_count", models.PositiveIntegerField(default=0)),
                ("skipped_count", models.PositiveIntegerField(default=0)),
                ("error_count", models.PositiveIntegerField(default=0)),
                ("errors", models.JSONField(blank=True, default=list)),
                ("last_scan_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="project_workspaces", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-updated_at", "-id"]},
        ),
        migrations.AddConstraint(
            model_name="projectworkspace",
            constraint=models.UniqueConstraint(fields=("owner", "root_path"), name="unique_owner_project_root"),
        ),
    ]
