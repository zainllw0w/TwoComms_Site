from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("management", "0166_ig_ugc_reward_lifecycle")]

    operations = [
        migrations.AddField(
            model_name="instagrambotsettings",
            name="binotel_ai_enabled",
            field=models.BooleanField(default=False),
        ),
    ]
