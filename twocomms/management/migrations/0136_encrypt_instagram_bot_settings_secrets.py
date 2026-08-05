from django.conf import settings
from django.db import migrations, models


SECRET_PREFIX = "fernet:v1:"
SECRET_FIELDS = ("custom_direct_token_encrypted", "custom_gemini_key_encrypted")


def _fernet():
    key = getattr(settings, "FIELD_ENCRYPTION_KEY", "") or ""
    if not key:
        raise RuntimeError(
            "FIELD_ENCRYPTION_KEY must be configured before encrypting Instagram bot credentials"
        )
    from cryptography.fernet import Fernet

    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_legacy_credentials(apps, schema_editor):
    Settings = apps.get_model("management", "InstagramBotSettings")
    rows = list(Settings.objects.all())
    if not any(str(getattr(row, field) or "") for row in rows for field in SECRET_FIELDS):
        return
    fernet = _fernet()
    for row in rows:
        changed = []
        for field in SECRET_FIELDS:
            value = str(getattr(row, field) or "")
            if value and not value.startswith(SECRET_PREFIX):
                setattr(
                    row,
                    field,
                    SECRET_PREFIX + fernet.encrypt(value.encode("utf-8")).decode("ascii"),
                )
                changed.append(field)
        if changed:
            row.save(update_fields=changed)


def restore_legacy_credentials(apps, schema_editor):
    Settings = apps.get_model("management", "InstagramBotSettings")
    rows = list(Settings.objects.all())
    if not any(
        str(getattr(row, field) or "").startswith(SECRET_PREFIX)
        for row in rows
        for field in SECRET_FIELDS
    ):
        return
    fernet = _fernet()
    for row in rows:
        changed = []
        for field in SECRET_FIELDS:
            value = str(getattr(row, field) or "")
            if value.startswith(SECRET_PREFIX):
                setattr(
                    row,
                    field,
                    fernet.decrypt(value[len(SECRET_PREFIX):].encode("ascii")).decode("utf-8"),
                )
                changed.append(field)
        if changed:
            row.save(update_fields=changed)


class Migration(migrations.Migration):
    dependencies = [
        ("management", "0135_instagrambottaskheartbeat"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.RenameField(
                    model_name="instagrambotsettings",
                    old_name="custom_direct_token",
                    new_name="custom_direct_token_encrypted",
                ),
                migrations.AlterField(
                    model_name="instagrambotsettings",
                    name="custom_direct_token_encrypted",
                    field=models.TextField(blank=True, db_column="custom_direct_token", default=""),
                ),
                migrations.RenameField(
                    model_name="instagrambotsettings",
                    old_name="custom_gemini_key",
                    new_name="custom_gemini_key_encrypted",
                ),
                migrations.AlterField(
                    model_name="instagrambotsettings",
                    name="custom_gemini_key_encrypted",
                    field=models.TextField(blank=True, db_column="custom_gemini_key", default=""),
                ),
            ],
        ),
        migrations.RunPython(encrypt_legacy_credentials, restore_legacy_credentials),
    ]
