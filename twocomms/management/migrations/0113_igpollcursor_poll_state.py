from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("management", "0112_instagrambotsettings_conversation_discovery"),
    ]

    operations = [
        migrations.AddField(
            model_name="igpollcursor",
            name="participant_igsid",
            field=models.CharField(blank=True, db_index=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="igpollcursor",
            name="provider_updated_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="igpollcursor",
            name="synced_provider_updated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="igpollcursor",
            name="excluded_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="igpollcursor",
            name="excluded_reason",
            field=models.CharField(blank=True, default="", max_length=32),
        ),
        migrations.AddField(
            model_name="igpollcursor",
            name="failure_count",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="igpollcursor",
            name="next_attempt_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="igpollcursor",
            name="last_error",
            field=models.CharField(blank=True, default="", max_length=80),
        ),
    ]
