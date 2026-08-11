import django.db.models.deletion
from django.db import migrations, models


POLICY_TABLE = "product_catalog_productinventorypolicy"


def _table_names(schema_editor):
    return set(schema_editor.connection.introspection.table_names())


def _columns(schema_editor, table_name):
    with schema_editor.connection.cursor() as cursor:
        description = schema_editor.connection.introspection.get_table_description(
            cursor,
            table_name,
        )
    return {column.name: column for column in description}


def ensure_inventory_policy_table(apps, schema_editor):
    """Create or complete the policy table after an interrupted non-atomic run."""

    model = apps.get_model("product_catalog", "ProductInventoryPolicy")
    table_name = model._meta.db_table
    if table_name not in _table_names(schema_editor):
        schema_editor.create_model(model)
        return

    existing_columns = _columns(schema_editor, table_name)
    for field in model._meta.local_fields:
        if field.column in existing_columns:
            continue
        schema_editor.add_field(model, field)
        existing_columns[field.column] = None


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
        ignore_conflicts=True,
    )


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("product_catalog", "0007_product_option_axis_presentation"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
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
            ],
        ),
        migrations.RunPython(
            ensure_inventory_policy_table,
            reverse_code=migrations.RunPython.noop,
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
