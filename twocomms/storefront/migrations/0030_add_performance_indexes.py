"""Add the second performance-index batch without MySQL name collisions."""

from django.db import migrations, models


_INDEXES = (
    ("Category", "idx_category_active", ("is_active",)),
    ("Category", "idx_category_featured", ("is_featured",)),
    ("Category", "idx_category_order", ("order",)),
    ("Product", "idx_product_featured", ("featured",)),
    ("Product", "idx_product_dropship", ("is_dropship_available",)),
    ("Product", "idx_product_category_id", ("category", "-id")),
    ("PromoCode", "idx_promo_active_created", ("is_active", "-created_at")),
    ("OfflineStore", "idx_store_active_order", ("is_active", "order")),
    ("SiteSession", "idx_session_bot_seen", ("is_bot", "-last_seen")),
    ("PageView", "idx_pageview_bot_when", ("is_bot", "-when")),
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
        # Migration 0018 predates this batch and used three of these names.
        # Keep the already-created index rather than failing the whole graph.
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

    # MySQL cannot roll back DDL. The helper is safe to resume after
    # an interruption because every index is checked before it is created.
    atomic = False

    dependencies = [
        ("storefront", "0029_product_idx_product_id_desc"),
    ]

    operations = [
        migrations.RunPython(_ensure_indexes, _remove_indexes),
    ]
