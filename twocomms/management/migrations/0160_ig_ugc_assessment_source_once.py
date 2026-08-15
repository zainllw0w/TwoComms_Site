from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("management", "0159_ig_lifecycle_final_text"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="igugcevidenceassessment",
            constraint=models.UniqueConstraint(
                fields=("client", "source_message_id"),
                name="ig_ugc_assess_source_once",
            ),
        ),
    ]
