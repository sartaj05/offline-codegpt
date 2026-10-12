from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("chat", "0044_projectworkspace")]

    operations = [
        migrations.CreateModel(
            name="PatchRevision",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("filename", models.CharField(default="editor-buffer", max_length=300)),
                ("original", models.TextField()),
                ("updated", models.TextField()),
                ("diff", models.TextField(blank=True, default="")),
                ("status", models.CharField(choices=[("preview", "Preview"), ("applied", "Applied"), ("rejected", "Rejected"), ("reverted", "Reverted")], default="preview", max_length=20)),
                ("test_result", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("document", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="patch_revisions", to="chat.knowledgedocument")),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="patch_revisions", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-updated_at", "-id"]},
        ),
    ]
