from django.db import migrations, models


class Migration(migrations.Migration):
    """Keep replaced Monobank invoice ids so a late payment still finds its deal."""

    dependencies = [
        ("management", "0120_bot_deletion_pending_verification"),
    ]

    operations = [
        migrations.AddField(
            model_name="igdeal",
            name="superseded_invoice_ids",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
