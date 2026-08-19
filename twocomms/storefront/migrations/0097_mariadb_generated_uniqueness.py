import re

from django.db import migrations, models


def assert_no_generated_unique_duplicates(apps, schema_editor):
    ProductFitOption = apps.get_model("storefront", "ProductFitOption")
    WebPushDeviceSubscription = apps.get_model(
        "storefront", "WebPushDeviceSubscription"
    )
    default_duplicate = (
        ProductFitOption.objects.filter(is_default=True)
        .values("product_id")
        .annotate(row_count=models.Count("pk"))
        .filter(row_count__gt=1)
        .exists()
    )
    if default_duplicate:
        raise RuntimeError("duplicate default ProductFitOption")
    endpoint_duplicate = (
        WebPushDeviceSubscription.objects.values("endpoint")
        .annotate(row_count=models.Count("pk"))
        .filter(row_count__gt=1)
        .exists()
    )
    if endpoint_duplicate:
        raise RuntimeError("duplicate WebPushDeviceSubscription endpoint")


def _is_mariadb(schema_editor):
    connection = schema_editor.connection
    if connection.vendor != "mysql":
        return False
    if not getattr(connection, "mysql_is_mariadb", False):
        raise RuntimeError("ProductFitOption generated identity requires MariaDB")
    return True


def _normalize_expression(value):
    return re.sub(r"[\s`()]+", "", str(value).casefold())


def _assert_column(schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "SELECT DATA_TYPE, EXTRA, GENERATION_EXPRESSION "
            "FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() "
            "AND TABLE_NAME = 'storefront_productfitoption' "
            "AND COLUMN_NAME = 'default_product_identity'"
        )
        row = cursor.fetchone()
    if row is None:
        raise RuntimeError("ProductFitOption generated identity is missing")
    data_type, extra, expression = row
    if (
        str(data_type).casefold() != "bigint"
        or str(extra).casefold() != "stored generated"
        or _normalize_expression(expression)
        != "casewhenis_default=1thenproduct_idelsenullend"
    ):
        raise RuntimeError("ProductFitOption generated identity does not match")


def _assert_index(schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "SELECT NON_UNIQUE, "
            "GROUP_CONCAT(COLUMN_NAME ORDER BY SEQ_IN_INDEX SEPARATOR ',') "
            "FROM information_schema.STATISTICS "
            "WHERE TABLE_SCHEMA = DATABASE() "
            "AND TABLE_NAME = 'storefront_productfitoption' "
            "AND INDEX_NAME = 'uniq_default_fit_product' "
            "GROUP BY NON_UNIQUE"
        )
        rows = list(cursor.fetchall())
    if rows != [(0, "default_product_identity")]:
        raise RuntimeError("ProductFitOption generated unique index does not match")


def apply_product_fit_schema(apps, schema_editor):
    if not _is_mariadb(schema_editor):
        return
    statements = (
        (
            "ALTER TABLE `storefront_productfitoption` "
            "ADD COLUMN IF NOT EXISTS `default_product_identity` bigint "
            "GENERATED ALWAYS AS (CASE WHEN `is_default` = 1 "
            "THEN `product_id` ELSE NULL END) STORED",
            lambda: _assert_column(schema_editor),
        ),
        (
            "ALTER TABLE `storefront_productfitoption` "
            "ADD UNIQUE INDEX IF NOT EXISTS `uniq_default_fit_product` "
            "(`default_product_identity`)",
            lambda: _assert_index(schema_editor),
        ),
    )
    for statement, verify in statements:
        with schema_editor.connection.cursor() as cursor:
            cursor.execute(statement)
        verify()


def reverse_product_fit_schema(apps, schema_editor):
    if not _is_mariadb(schema_editor):
        return
    statements = (
        "ALTER TABLE `storefront_productfitoption` DROP INDEX IF EXISTS "
        "`uniq_default_fit_product`",
        "ALTER TABLE `storefront_productfitoption` DROP COLUMN IF EXISTS "
        "`default_product_identity`",
    )
    with schema_editor.connection.cursor() as cursor:
        for statement in statements:
            cursor.execute(statement)


class Migration(migrations.Migration):
    atomic = False
    dependencies = [("storefront", "0096_alter_catalogcolorseooverride_body_html_and_more")]

    operations = [
        migrations.RunPython(
            assert_no_generated_unique_duplicates,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    apply_product_fit_schema,
                    reverse_code=reverse_product_fit_schema,
                ),
            ],
            state_operations=[
                migrations.RemoveConstraint(
                    model_name="productfitoption",
                    name="uniq_default_fit_per_product",
                ),
                migrations.AddField(
                    model_name="productfitoption",
                    name="default_product_identity",
                    field=models.GeneratedField(
                        db_persist=True,
                        expression=models.Case(
                            models.When(
                                is_default=True,
                                then=models.F("product_id"),
                            ),
                            default=models.Value(None),
                            output_field=models.BigIntegerField(),
                        ),
                        output_field=models.BigIntegerField(),
                    ),
                ),
                migrations.AddConstraint(
                    model_name="productfitoption",
                    constraint=models.UniqueConstraint(
                        fields=("default_product_identity",),
                        name="uniq_default_fit_product",
                    ),
                ),
                migrations.AlterField(
                    model_name="webpushdevicesubscription",
                    name="endpoint",
                    field=models.URLField(
                        max_length=768,
                        unique=False,
                        verbose_name="Push endpoint",
                    ),
                ),
                migrations.AddConstraint(
                    model_name="webpushdevicesubscription",
                    constraint=models.UniqueConstraint(
                        fields=("endpoint",),
                        name="uniq_webpush_endpoint_state",
                    ),
                ),
            ],
        ),
    ]
