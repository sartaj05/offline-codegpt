from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):
    dependencies = [("chat", "0042_syncpeer"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="CodingWorkflowArtifact",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(choices=[("plan", "Plan"), ("replay", "Replay"), ("risk", "Risk report"), ("dependency", "Dependency report"), ("environment", "Environment report"), ("git", "Git archaeology"), ("result", "Feature result")], default="result", max_length=30)),
                ("title", models.CharField(max_length=200)),
                ("payload", models.JSONField(default=dict)),
                ("fingerprint", models.CharField(db_index=True, max_length=64)),
                ("status", models.CharField(default="saved", max_length=30)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="coding_workflow_artifacts", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-updated_at", "-id"]},
        ),
    ]
