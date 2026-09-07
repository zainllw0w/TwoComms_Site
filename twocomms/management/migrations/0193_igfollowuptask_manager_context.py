from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("management", "0192_bot_prompt_revision_system_prompt"),
    ]

    operations = [
        migrations.AddField(
            model_name="igfollowuptask",
            name="manager_context",
            field=models.JSONField(blank=True, default=None, null=True),
        ),
    ]
