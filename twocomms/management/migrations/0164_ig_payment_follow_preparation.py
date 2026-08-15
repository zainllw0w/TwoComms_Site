import django.db.models.deletion
from django.db import migrations, models


PAYMENT_FOLLOW_PREPARATION_TABLE = "management_igpaymentfollowpreparation"


def ensure_payment_follow_preparation_table_innodb(apps, schema_editor):
    if schema_editor.connection.vendor not in {"mysql", "mariadb"}:
        return
    quote = schema_editor.quote_name
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "SELECT ENGINE FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s",
            [PAYMENT_FOLLOW_PREPARATION_TABLE],
        )
        row = cursor.fetchone()
    if row is None:
        raise RuntimeError(
            "required payment follow preparation table is missing: "
            f"{PAYMENT_FOLLOW_PREPARATION_TABLE}"
        )
    if str(row[0]).lower() != "innodb":
        schema_editor.execute(
            f"ALTER TABLE {quote(PAYMENT_FOLLOW_PREPARATION_TABLE)} ENGINE=InnoDB"
        )


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("management", "0163_ig_ugc_reward_evidence_snapshot"),
    ]

    operations = [
        migrations.CreateModel(
            name="IgPaymentFollowPreparation",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("deadline_at", models.DateTimeField(db_index=True)),
                (
                    "state",
                    models.CharField(
                        choices=[
                            ("pending", "Очікує підготовки"),
                            ("waiting_follow", "Очікує перевірки підписки"),
                            ("processing", "Готується"),
                            ("prepared", "Підготовлено"),
                            ("suppressed", "Не додавати CTA"),
                            ("expired", "Час підготовки минув"),
                            ("failed", "Помилка підготовки"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=24,
                    ),
                ),
                ("attempts", models.PositiveSmallIntegerField(default=0)),
                ("lease_token", models.CharField(blank=True, default="", max_length=64)),
                (
                    "lease_expires_at",
                    models.DateTimeField(blank=True, db_index=True, null=True),
                ),
                (
                    "last_error_kind",
                    models.CharField(blank=True, default="", max_length=32),
                ),
                (
                    "last_error_code",
                    models.CharField(blank=True, default="", max_length=64),
                ),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.AlterModelOptions(
            name="igugcevidenceassessment",
            options={"ordering": ["-id"]},
        ),
        migrations.AlterField(
            model_name="igugcreward",
            name="evidence_type",
            field=models.CharField(
                choices=[
                    ("direct_message", "Повідомлення Direct"),
                    ("instagram_url", "Посилання Instagram"),
                    ("story_mention", "Відмітка в story"),
                ],
                max_length=24,
            ),
        ),
        migrations.AddIndex(
            model_name="igugcreward",
            index=models.Index(
                fields=["reward_path", "-issued_at"],
                name="ig_ugc_path_issued",
            ),
        ),
        migrations.AddField(
            model_name="igpaymentfollowpreparation",
            name="client",
            field=models.ForeignKey(
                db_constraint=False,
                on_delete=django.db.models.deletion.DO_NOTHING,
                related_name="payment_follow_preparations",
                to="management.igclient",
            ),
        ),
        migrations.AddField(
            model_name="igpaymentfollowpreparation",
            name="lifecycle_event",
            field=models.OneToOneField(
                db_constraint=False,
                on_delete=django.db.models.deletion.DO_NOTHING,
                related_name="follow_preparation",
                to="management.iglifecycleevent",
            ),
        ),
        migrations.AddIndex(
            model_name="igpaymentfollowpreparation",
            index=models.Index(
                fields=["state", "deadline_at", "id"],
                name="ig_pay_follow_prep_due",
            ),
        ),
        migrations.AddIndex(
            model_name="igpaymentfollowpreparation",
            index=models.Index(
                fields=["client", "state"],
                name="ig_pay_follow_prep_client",
            ),
        ),
        migrations.RunPython(
            ensure_payment_follow_preparation_table_innodb,
            migrations.RunPython.noop,
        ),
    ]
