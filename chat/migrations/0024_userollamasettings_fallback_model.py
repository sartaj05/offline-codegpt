from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chat", "0023_extensionpackage_extensioninstall"),
    ]

    operations = [
        migrations.AddField(
            model_name="userollamasettings",
            name="fallback_model",
            field=models.CharField(default="phi3:mini", blank=True, max_length=100),
        ),
    ]