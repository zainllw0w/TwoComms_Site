from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("management", "0167_binotel_ai_enabled")]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.RenameField(
                    model_name="instagrambotsettings",
                    old_name="binotel_ai_enabled",
                    new_name="call_auto_analysis_enabled",
                ),
                migrations.AlterField(
                    model_name="instagrambotsettings",
                    name="call_auto_analysis_enabled",
                    field=models.BooleanField(
                        db_column="binotel_ai_enabled", default=False
                    ),
                ),
            ],
        ),
    ]
