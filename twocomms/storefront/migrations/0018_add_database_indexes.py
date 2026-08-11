"""Add the legacy performance indexes on every supported SQL backend.

The former raw SQL used ``CREATE INDEX IF NOT EXISTS``. MySQL does not
support that clause, so a fresh production-like database could not complete
the migration.  Django's schema editor gives us portable, introspection-based
idempotence while retaining the historical index names.
"""

from django.db import migrations, models


_INDEXES = (
    ("Product", "idx_product_featured", ("featured",)),
    ("Product", "idx_product_category", ("category_id",)),
    ("Product", "idx_product_created", ("-id",)),
    ("Product", "idx_product_price", ("price",)),
    ("Category", "idx_category_order", ("order", "name")),
    ("Category", "idx_category_active", ("is_active",)),
    ("PromoCode", "idx_promocode_code", ("code",)),
    ("PromoCode", "idx_promocode_active", ("is_active",)),
    ("PromoCode", "idx_promocode_created", ("-created_at",)),
)


def _has_index(schema_editor, model, name):
    with schema_editor.connection.cursor() as cursor:
        constraints = schema_editor.connection.introspection.get_constraints(
            cursor, model._meta.db_table
        )
    return name in constraints


def _ensure_indexes(apps, schema_editor):
    for model_name, name, fields in _INDEXES:
        model = apps.get_model("storefront", model_name)
        if not _has_index(schema_editor, model, name):
            schema_editor.add_index(
                model,
                models.Index(fields=list(fields), name=name),
            )


def _remove_indexes(apps, schema_editor):
    for model_name, name, fields in reversed(_INDEXES):
        model = apps.get_model("storefront", model_name)
        if _has_index(schema_editor, model, name):
            schema_editor.remove_index(
                model,
                models.Index(fields=list(fields), name=name),
            )


class Migration(migrations.Migration):

    # MySQL cannot roll back DDL; the helper is introspection-based and
    # safe to resume one index at a time when the process is interrupted.
    atomic = False

    dependencies = [
        ("storefront", "0011_category_description_category_is_active_and_more"),
    ]

    operations = [
        migrations.RunPython(_ensure_indexes, _remove_indexes),
    ]
