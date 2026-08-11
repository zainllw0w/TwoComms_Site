import django.db.models.deletion
from django.db import migrations, models


POLICY_TABLE = "product_catalog_productinventorypolicy"


def ensure_inventory_policy_innodb(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor not in {"mysql", "mariadb"}:
        return
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT ENGINE FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s",
            [POLICY_TABLE],
        )
        row = cursor.fetchone()
    if row is None:
        raise RuntimeError(f"required inventory policy table is missing: {POLICY_TABLE}")
    if str(row[0]).lower() != "innodb":
        table = connection.ops.quote_name(POLICY_TABLE)
        schema_editor.execute(f"ALTER TABLE {table} ENGINE=InnoDB")


def backfill_product_inventory_policies(apps, schema_editor):
    Product = apps.get_model("storefront", "Product")
    ProductInventoryPolicy = apps.get_model("product_catalog", "ProductInventoryPolicy")
    VariantBlankLink = apps.get_model("product_catalog", "VariantBlankLink")

    warehouse_product_ids = set(
        VariantBlankLink.objects.values_list("variant__product_id", flat=True).distinct()
    )
    ProductInventoryPolicy.objects.bulk_create(
        [
            ProductInventoryPolicy(
                product_id=product_id,
                source="warehouse" if product_id in warehouse_product_ids else "untracked",
            )
            for product_id in Product.objects.values_list("id", flat=True).iterator(chunk_size=500)
        ],
        batch_size=500,
    )


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("product_catalog", "0007_product_option_axis_presentation"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProductInventoryPolicy",
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
                    "source",
                    models.CharField(
                        choices=[
                            ("warehouse", "Склад"),
                            ("catalog_variant", "Залишок варіанта каталогу"),
                            ("untracked", "Не відстежується"),
                        ],
                        max_length=24,
                    ),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "product",
                    models.OneToOneField(
                        db_constraint=False,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="product_catalog_inventory_policy",
                        to="storefront.product",
                    ),
                ),
            ],
        ),
        migrations.RunPython(
            ensure_inventory_policy_innodb,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.RunPython(
            backfill_product_inventory_policies,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
