from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("management", "0110_ig_post_sale_cases"),
    ]

    operations = [
        migrations.AddField(
            model_name="igclient",
            name="profile_sync_attempted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="igclient",
            name="profile_sync_error_kind",
            field=models.CharField(blank=True, default="", max_length=32),
        ),
        migrations.AddField(
            model_name="igclient",
            name="profile_sync_failures",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="igclient",
            name="profile_sync_next_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="instagrambotmessage",
            name="provider_created_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
    ]
