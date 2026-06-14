"""Перехід на event-driven: вимкнути резервний поллінг у існуючого
singleton-налаштування (ми Live, webhook доставляє messages миттєво)."""
from django.db import migrations


def forward(apps, schema_editor):
    Settings = apps.get_model("management", "InstagramBotSettings")
    Settings.objects.all().update(receive_via_poll=False)


def backward(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("management", "0044_ig_bot_upgrade_model_prompt"),
    ]
    operations = [migrations.RunPython(forward, backward)]
