from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("management", "0153_owned_ig_message_media")]

    operations = [
        migrations.AddField(
            model_name="instagrambotmessage",
            name="synthetic_event_key",
            field=models.CharField(
                blank=True, db_index=True, max_length=64, null=True, unique=True
            ),
        ),
    ]
