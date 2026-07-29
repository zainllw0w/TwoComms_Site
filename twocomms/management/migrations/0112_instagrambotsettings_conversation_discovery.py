from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("management", "0111_instagrambotmessage_provider_created_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="instagrambotsettings",
            name="conversation_discovery_ids",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="instagrambotsettings",
            name="conversation_discovery_cursor",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="instagrambotsettings",
            name="conversation_discovery_page_id",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="instagrambotsettings",
            name="conversation_discovery_scan_ids",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="instagrambotsettings",
            name="conversation_discovery_cursor_hashes",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="instagrambotsettings",
            name="conversation_discovery_pages_seen",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="instagrambotsettings",
            name="conversation_discovery_updated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="instagrambotsettings",
            name="conversation_discovery_completed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="instagrambotsettings",
            name="conversation_discovery_lease_token",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="instagrambotsettings",
            name="conversation_discovery_lease_expires_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
