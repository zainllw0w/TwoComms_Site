from django.db import migrations, models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


UGC_LIFECYCLE_JOB_TABLE = "management_igugcrewardlifecyclejob"


def ensure_ugc_lifecycle_job_innodb(apps, schema_editor):
    if schema_editor.connection.vendor not in {"mysql", "mariadb"}:
        return
    quote = schema_editor.quote_name
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "SELECT ENGINE FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s",
            [UGC_LIFECYCLE_JOB_TABLE],
        )
        row = cursor.fetchone()
    if row is None:
        raise RuntimeError(
            "required UGC lifecycle job table is missing: "
            f"{UGC_LIFECYCLE_JOB_TABLE}"
        )
    if str(row[0]).lower() != "innodb":
        schema_editor.execute(
            f"ALTER TABLE {quote(UGC_LIFECYCLE_JOB_TABLE)} ENGINE=InnoDB"
        )


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("management", "0165_alter_igugcevidenceassessment_decision"),
    ]

    operations = [
        migrations.CreateModel(
            name="IgUgcRewardLifecycleJob",
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
                (
                    "order_id",
                    models.PositiveBigIntegerField(
                        blank=True,
                        db_index=True,
                        null=True,
                    ),
                ),
                (
                    "client_id",
                    models.PositiveBigIntegerField(
                        blank=True,
                        db_index=True,
                        null=True,
                    ),
                ),
                ("source", models.CharField(blank=True, default="", max_length=32)),
                (
                    "due_at",
                    models.DateTimeField(db_index=True, default=timezone.now),
                ),
                ("attempts", models.PositiveSmallIntegerField(default=0)),
                (
                    "last_error_kind",
                    models.CharField(blank=True, default="", max_length=64),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["due_at", "id"]},
        ),
        migrations.AddConstraint(
            model_name="igugcrewardlifecyclejob",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(("order_id__isnull", False))
                    | models.Q(("client_id__isnull", False))
                ),
                name="ig_ugc_life_job_target",
            ),
        ),
        migrations.AddIndex(
            model_name="igugcrewardlifecyclejob",
            index=models.Index(
                fields=["due_at", "id"],
                name="ig_ugc_life_job_due",
            ),
        ),
        migrations.AddField(
            model_name="igugcreward",
            name="lifecycle_reason",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="igugcreward",
            name="lifecycle_state",
            field=models.CharField(
                choices=[
                    ("active", _("Активна")),
                    ("held", _("Тимчасово призупинена")),
                    ("revoked", _("Відкликана")),
                ],
                db_index=True,
                default="active",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="igugcreward",
            name="lifecycle_updated_at",
            field=models.DateTimeField(
                db_index=True,
                default=timezone.now,
            ),
        ),
        migrations.RunPython(
            ensure_ugc_lifecycle_job_innodb,
            migrations.RunPython.noop,
        ),
    ]
