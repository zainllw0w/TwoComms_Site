"""Оновлює системний промпт IG-бота на playbook продавця — лише якщо адмін не
змінював його вручну (тобто він дорівнює старому дефолту або порожній).
"""
from django.db import migrations

OLD_PREFIX = "Ти — офіційний віртуальний помічник українського бренду одягу TwoComms"


def update_prompt(apps, schema_editor):
    Settings = apps.get_model("management", "InstagramBotSettings")
    from management.models import DEFAULT_BOT_SYSTEM_PROMPT

    for s in Settings.objects.all():
        cur = (s.system_prompt or "").strip()
        if not cur or cur.startswith(OLD_PREFIX):
            s.system_prompt = DEFAULT_BOT_SYSTEM_PROMPT
            s.save(update_fields=["system_prompt"])


class Migration(migrations.Migration):

    dependencies = [
        ("management", "0065_alter_instagrambotsettings_system_prompt"),
    ]

    operations = [
        migrations.RunPython(update_prompt, migrations.RunPython.noop),
    ]
