# Generated for the Django 6.1 durable task runtime.

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name="DurableTask",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("task_name", models.CharField(db_index=True, max_length=255)),
                ("payload", models.JSONField(default=dict)),
                ("idempotency_key", models.CharField(max_length=180, unique=True)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("running", "Running"), ("done", "Done"), ("failed", "Failed")], db_index=True, default="pending", max_length=16)),
                ("available_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("lease_token", models.CharField(blank=True, default="", max_length=64)),
                ("lease_expires_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("worker_id", models.CharField(blank=True, default="", max_length=128)),
                ("last_error", models.CharField(blank=True, default="", max_length=1000)),
                ("result", models.JSONField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "indexes": [
                    models.Index(fields=["status", "available_at", "id"], name="task_runtime_due"),
                    models.Index(fields=["lease_expires_at", "id"], name="task_runtime_lease"),
                ],
            },
        ),
    ]
