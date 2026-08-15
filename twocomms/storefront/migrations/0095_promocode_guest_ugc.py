from django.db import migrations, models
import django.db.models.deletion


GUEST_TABLE = "storefront_promocodeguestusage"


def ensure_guest_table_innodb(apps, schema_editor):
    if schema_editor.connection.vendor not in {"mysql", "mariadb"}:
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "SELECT ENGINE FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s",
            [GUEST_TABLE],
        )
        row = cursor.fetchone()
    if row is None:
        raise RuntimeError(f"required guest promo table is missing: {GUEST_TABLE}")
    if str(row[0]).lower() != "innodb":
        schema_editor.execute(
            f"ALTER TABLE {schema_editor.quote_name(GUEST_TABLE)} ENGINE=InnoDB"
        )


class Migration(migrations.Migration):
    atomic = False

    dependencies = [("storefront", "0094_utm_click_ids")]

    operations = [
        migrations.AddField(
            model_name="promocode",
            name="guest_redeemable",
            field=models.BooleanField(
                default=False,
                verbose_name="Дозволити гостьове використання",
            ),
        ),
        migrations.CreateModel(
            name="PromoCodeGuestUsage",
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
                    "reservation_key",
                    models.CharField(max_length=96, unique=True),
                ),
                (
                    "state",
                    models.CharField(
                        choices=[
                            ("reserved", "Reserved"),
                            ("consumed", "Consumed"),
                            ("released", "Released"),
                        ],
                        db_index=True,
                        default="reserved",
                        max_length=16,
                    ),
                ),
                ("reserved_at", models.DateTimeField(auto_now_add=True)),
                ("consumed_at", models.DateTimeField(blank=True, null=True)),
                ("released_at", models.DateTimeField(blank=True, null=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                (
                    "order",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        db_constraint=False,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="guest_promo_usages",
                        to="orders.order",
                    ),
                ),
                (
                    "promo_code",
                    models.OneToOneField(
                        db_constraint=False,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="guest_usage",
                        to="storefront.promocode",
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=["state", "reserved_at"],
                        name="promo_guest_state_dt",
                    )
                ],
            },
        ),
        migrations.RunPython(ensure_guest_table_innodb, migrations.RunPython.noop),
    ]
