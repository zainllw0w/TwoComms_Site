from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("management", "0130_igfollowuptask_fulfillment_kind")]

    operations = [
        migrations.AddField(
            model_name="igfollowuptask",
            name="event_key",
            field=models.CharField(
                blank=True, max_length=180, null=True, unique=True
            ),
        ),
        migrations.AddField(
            model_name="igfollowuptask",
            name="claim_token",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="igfollowuptask",
            name="claim_until",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="igfollowuptask",
            name="provider_message_id",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
    ]
