from django.db import migrations, models


class Migration(migrations.Migration):
    """Add the pending-verification status for public deletion requests.

    Only `choices` changes, so the DB column is untouched on MariaDB/MySQL
    (Django emits no ALTER for choice-only edits on CharField).
    """

    dependencies = [
        ("management", "0119_ig_order_assignments"),
    ]

    operations = [
        migrations.AlterField(
            model_name="botdatadeletionrequest",
            name="status",
            field=models.CharField(
                choices=[
                    ("completed", "Completed"),
                    ("no_match", "No matching records"),
                    ("received", "Received"),
                    ("pending_verification", "Pending ownership verification"),
                ],
                default="received",
                max_length=24,
            ),
        ),
    ]
