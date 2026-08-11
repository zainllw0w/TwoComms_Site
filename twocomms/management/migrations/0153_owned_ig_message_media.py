import json

from django.db import migrations, models


def mark_existing_attachments_metadata_only(apps, schema_editor):
    Message = apps.get_model("management", "InstagramBotMessage")
    rows = Message.objects.exclude(attachments="").only("pk", "attachments")
    for row in rows.iterator(chunk_size=200):
        try:
            urls = json.loads(row.attachments or "[]")
        except (TypeError, ValueError):
            urls = []
        if not isinstance(urls, list):
            urls = []
        media = []
        seen_urls = set()
        for raw in urls:
            url = str(raw or "").strip()
            if (
                not url.startswith(("https://", "http://"))
                or url in seen_urls
            ):
                continue
            seen_urls.add(url)
            media.append({
                "url": url[:1200],
                "provenance": "historical_import",
                "status": "metadata_only",
            })
            if len(media) >= 8:
                break
        if media:
            Message.objects.filter(pk=row.pk).update(attachment_media=media)


class Migration(migrations.Migration):
    dependencies = [("management", "0152_harden_ig_stage_prompt")]

    operations = [
        migrations.AddField(
            model_name="instagrambotmessage",
            name="attachment_media",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="instagrambotmessage",
            name="media_capture_eligible",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="igconversationanalysisjob",
            name="media_phase",
            field=models.CharField(
                choices=[
                    ("not_started", "Медіа не розпочато"),
                    ("acquiring", "Медіа обробляється"),
                    ("ready", "Медіа готове"),
                    ("metadata_only", "Лише метадані"),
                    ("failed", "Помилка медіа"),
                ],
                db_index=True,
                default="not_started",
                max_length=24,
            ),
        ),
        migrations.AddField(
            model_name="igconversationanalysisjob",
            name="media_error_kind",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="igconversationanalysisjob",
            name="media_started_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="igconversationanalysisjob",
            name="media_completed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="igconversationanalysisjob",
            name="media_item_count",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.RunPython(
            mark_existing_attachments_metadata_only,
            migrations.RunPython.noop,
        ),
    ]
