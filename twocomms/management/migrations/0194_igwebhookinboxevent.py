from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("management", "0193_igfollowuptask_manager_context")]

    operations = [
        migrations.CreateModel(
            name="IgWebhookInboxEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("namespace", models.CharField(max_length=128)),
                ("event_key", models.CharField(max_length=255)),
                ("owner_id", models.CharField(blank=True, default="", max_length=64)),
                ("customer_igsid", models.CharField(blank=True, db_index=True, default="", max_length=64)),
                ("decision", models.CharField(choices=[("accepted", "Accepted"), ("rejected", "Rejected"), ("blocked", "Blocked")], db_index=True, max_length=16)),
                ("reason", models.CharField(blank=True, default="", max_length=64)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("payload_digest", models.CharField(max_length=64)),
                ("received_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("processed_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("last_error", models.CharField(blank=True, default="", max_length=64)),
                ("next_attempt_at", models.DateTimeField(blank=True, db_index=True, null=True)),
            ],
            options={"ordering": ["id"]},
        ),
        migrations.AddConstraint(
            model_name="igwebhookinboxevent",
            constraint=models.UniqueConstraint(fields=("namespace", "event_key"), name="ig_webhook_inbox_namespace_event_uniq"),
        ),
        migrations.AddIndex(
            model_name="igwebhookinboxevent",
            index=models.Index(fields=["decision", "processed_at", "id"], name="ig_webhook_inbox_drain_idx"),
        ),
        migrations.AddField(
            model_name="instagrambotmessage",
            name="provider_namespace",
            field=models.CharField(blank=True, db_index=True, default="", db_default="", max_length=128),
        ),
    ]
