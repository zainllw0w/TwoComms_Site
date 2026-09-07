from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("management", "0199_deletion_request_erasure_lease")]

    operations = [
        migrations.AddField(
            model_name="igrevisiondeliveryeffect",
            name="projection_metadata",
            field=models.JSONField(blank=True, default=dict, db_default={}),
        ),
        migrations.AddField(
            model_name="igrevisiondeliveryeffect",
            name="projection_digest",
            field=models.CharField(blank=True, default="", db_default="", max_length=64),
        ),
    ]
