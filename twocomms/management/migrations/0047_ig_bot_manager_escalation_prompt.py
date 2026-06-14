"""Додати правило ескалації на менеджера ([MANAGER]) у системний промпт
існуючого налаштування — лише якщо промпт не кастомізований користувачем."""
from django.db import migrations

PREV_MARKER = "Ти — офіційний віртуальний помічник українського бренду одягу TwoComms"


def forward(apps, schema_editor):
    Settings = apps.get_model("management", "InstagramBotSettings")
    try:
        from management.models import DEFAULT_BOT_SYSTEM_PROMPT
    except Exception:
        return
    for s in Settings.objects.all():
        prompt = (s.system_prompt or "").strip()
        # Оновлюємо лише якщо це попередній дефолт без правила менеджера.
        if prompt.startswith(PREV_MARKER) and "[MANAGER]" not in prompt:
            s.system_prompt = DEFAULT_BOT_SYSTEM_PROMPT
            s.save(update_fields=["system_prompt"])


def backward(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("management", "0046_alter_instagrambotsettings_receive_via_poll"),
    ]
    operations = [migrations.RunPython(forward, backward)]
