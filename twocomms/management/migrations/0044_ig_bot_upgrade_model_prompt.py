"""Оновлення існуючого singleton-налаштування бота: модель -> gemini-3.5-flash
і guardrail-промпт за замовчуванням (лише якщо промпт не кастомізований)."""
from django.db import migrations

NEW_PROMPT_MARKER = "Ти — офіційний віртуальний помічник українського бренду одягу TwoComms"
OLD_PROMPT_MARKERS = (
    "Ты — дружелюбный ассистент бренда TwoComms",
)


def forward(apps, schema_editor):
    Settings = apps.get_model("management", "InstagramBotSettings")
    try:
        from management.models import DEFAULT_BOT_SYSTEM_PROMPT
    except Exception:
        DEFAULT_BOT_SYSTEM_PROMPT = None

    for s in Settings.objects.all():
        changed = []
        if (s.gemini_model or "").startswith("gemini-2"):
            s.gemini_model = "gemini-3.5-flash"
            changed.append("gemini_model")
        prompt = (s.system_prompt or "").strip()
        is_old_default = (not prompt) or any(prompt.startswith(m) for m in OLD_PROMPT_MARKERS)
        if DEFAULT_BOT_SYSTEM_PROMPT and is_old_default and not prompt.startswith(NEW_PROMPT_MARKER):
            s.system_prompt = DEFAULT_BOT_SYSTEM_PROMPT
            changed.append("system_prompt")
        if changed:
            s.save(update_fields=changed)


def backward(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("management", "0043_instagrambotmessage_attachments_and_more"),
    ]
    operations = [migrations.RunPython(forward, backward)]
