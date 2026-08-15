from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("management", "0161_optional_follow_cta_prompt"),
    ]

    operations = [
        migrations.AddField(
            model_name="igfollowstate",
            name="cta_refused_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="igfollowstate",
            name="cta_refusal_message_id",
            field=models.PositiveBigIntegerField(default=0),
        ),
    ]
