from django.db import migrations, models


PRIMARY_MODEL = "gemini-3.7-flash"
PREVIOUS_PRIMARY_MODEL = "gemini-3.6-flash"
LEGACY_PRIMARY_MODELS = (PREVIOUS_PRIMARY_MODEL, "gemini-3-flash-preview", "")


def use_gemini_37_for_existing_bot_settings(apps, schema_editor):
    Settings = apps.get_model("management", "InstagramBotSettings")
    Settings.objects.filter(gemini_model__in=LEGACY_PRIMARY_MODELS).update(
        gemini_model=PRIMARY_MODEL
    )


def restore_previous_primary_for_bot_settings(apps, schema_editor):
    Settings = apps.get_model("management", "InstagramBotSettings")
    Settings.objects.filter(gemini_model=PRIMARY_MODEL).update(
        gemini_model=PREVIOUS_PRIMARY_MODEL
    )


class Migration(migrations.Migration):
    dependencies = [("management", "0154_synthetic_inbound_event_key")]

    operations = [
        migrations.AddField(
            model_name="instagrambotmessage",
            name="gemini_model",
            field=models.CharField(blank=True, default="", max_length=80),
        ),
        migrations.AlterField(
            model_name="instagrambotsettings",
            name="gemini_model",
            field=models.CharField(default=PRIMARY_MODEL, max_length=80),
        ),
        migrations.RunPython(
            use_gemini_37_for_existing_bot_settings,
            restore_previous_primary_for_bot_settings,
        ),
    ]
