"""Э0.1 — физически создать generated-колонку на не-MariaDB backend.

`0097_mariadb_generated_uniqueness` объявляет `default_product_identity` в
Django model state для **всех** backend через `SeparateDatabaseAndState`, но
физическую колонку создаёт только на MariaDB (`_is_mariadb` возвращает False и
`apply_product_fit_schema` выходит сразу). На SQLite состояние модели утверждало,
что колонка есть, а базы данных её не имела: любой запрос по `ProductFitOption`
падал с `no such column: storefront_productfitoption.default_product_identity`.
Из-за этого весь commerce-слой (`management.tests_ig_checkout_service`) не имел
регрессионного покрытия — 26 ошибок схемы.

Правило, которое здесь соблюдается: **model field не должен объявляться
существующим на backend, где миграция намеренно его не создаёт.** Раз поле
объявлено в state для всех backend, оно должно быть физически создано на всех.

Почему отдельная миграция, а не правка 0097: 0097 уже применена на production.
Эта миграция — expand-only, на MariaDB строго no-op (колонка и индекс там уже
созданы вручную с проверкой через information_schema, и переделывать это не
нужно), на остальных backend создаёт то же самое штатным schema editor.

Четыре вопроса из плана, разделённые:
  1. в state — GeneratedField объявлен (без изменений, из 0097);
  2. на SQLite — создаётся штатным schema editor (этой миграцией);
  3. на MariaDB — создано вручную в 0097 с проверкой выражения и индекса;
  4. маршрутизация тестов — не требуется: колонка есть на обоих backend,
     ни один тест больше не пропускается из-за неудобного backend.
"""
from django.db import migrations, models


CONSTRAINT_NAME = "uniq_default_fit_product"


def _is_mariadb(schema_editor) -> bool:
    connection = schema_editor.connection
    return connection.vendor == "mysql" and bool(
        getattr(connection, "mysql_is_mariadb", False)
    )


def _generated_field():
    field = models.GeneratedField(
        db_persist=True,
        expression=models.Case(
            models.When(is_default=True, then=models.F("product_id")),
            default=models.Value(None),
            output_field=models.BigIntegerField(),
        ),
        output_field=models.BigIntegerField(),
    )
    field.set_attributes_from_name("default_product_identity")
    return field


def create_generated_column(apps, schema_editor):
    if _is_mariadb(schema_editor):
        return
    model = apps.get_model("storefront", "ProductFitOption")
    table = model._meta.db_table
    with schema_editor.connection.cursor() as cursor:
        existing = {
            column.name
            for column in schema_editor.connection.introspection.get_table_description(
                cursor, table
            )
        }
    if "default_product_identity" in existing:
        return
    field = _generated_field()
    field.model = model
    schema_editor.add_field(model, field)
    schema_editor.add_constraint(
        model,
        models.UniqueConstraint(
            fields=("default_product_identity",), name=CONSTRAINT_NAME
        ),
    )


def drop_generated_column(apps, schema_editor):
    if _is_mariadb(schema_editor):
        return
    model = apps.get_model("storefront", "ProductFitOption")
    try:
        schema_editor.remove_constraint(
            model,
            models.UniqueConstraint(
                fields=("default_product_identity",), name=CONSTRAINT_NAME
            ),
        )
    except Exception:
        pass
    field = _generated_field()
    field.model = model
    try:
        schema_editor.remove_field(model, field)
    except Exception:
        pass


class Migration(migrations.Migration):
    atomic = False
    dependencies = [("storefront", "0097_mariadb_generated_uniqueness")]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    create_generated_column,
                    reverse_code=drop_generated_column,
                ),
            ],
            state_operations=[],
        ),
    ]
