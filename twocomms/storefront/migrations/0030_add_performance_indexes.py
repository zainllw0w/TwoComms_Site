"""Add the second performance-index batch without MySQL name collisions."""

from django.db import migrations, models


_INDEXES = (
    ("Category", "idx_category_active", ("is_active",)),
    ("Category", "idx_category_featured", ("is_featured",)),
    ("Category", "idx_category_order", ("order", "name")),
    ("Product", "idx_product_featured", ("featured",)),
    ("Product", "idx_product_dropship", ("is_dropship_available",)),
    ("Product", "idx_product_category_id", ("category", "-id")),
    ("PromoCode", "idx_promo_active_created", ("is_active", "-created_at")),
    ("OfflineStore", "idx_store_active_order", ("is_active", "order")),
    ("SiteSession", "idx_session_bot_seen", ("is_bot", "-last_seen")),
    ("PageView", "idx_pageview_bot_when", ("is_bot", "-when")),
)


_REUSED_INDEXES = {
    ("Category", "idx_category_active"),
    ("Category", "idx_category_order"),
    ("Product", "idx_product_featured"),
}


def _expected_index_columns(model, fields):
    return tuple(
        model._meta.get_field(field_name.lstrip("-")).column
        for field_name in fields
    )


def _index_columns(schema_editor, model, name):
    with schema_editor.connection.cursor() as cursor:
        constraints = schema_editor.connection.introspection.get_constraints(
            cursor, model._meta.db_table
        )
    row = constraints.get(name)
    if row is None:
        return None
    return tuple(row.get("columns") or ())


def _ensure_indexes(apps, schema_editor):
    for model_name, name, fields in _INDEXES:
        model = apps.get_model("storefront", model_name)
        expected_columns = _expected_index_columns(model, fields)
        actual_columns = _index_columns(schema_editor, model, name)
        if actual_columns is not None:
            if actual_columns != expected_columns:
                raise RuntimeError(
                    f"index definition mismatch for {name}: "
                    f"expected {expected_columns}, got {actual_columns}"
                )
            continue
        schema_editor.add_index(
            model,
            models.Index(fields=list(fields), name=name),
        )


def _remove_indexes(apps, schema_editor):
    for model_name, name, fields in reversed(_INDEXES):
        if (model_name, name) in _REUSED_INDEXES:
            continue
        model = apps.get_model("storefront", model_name)
        expected_columns = _expected_index_columns(model, fields)
        actual_columns = _index_columns(schema_editor, model, name)
        if actual_columns is None:
            continue
        if actual_columns != expected_columns:
            raise RuntimeError(
                f"index definition mismatch for {name}: "
                f"expected {expected_columns}, got {actual_columns}"
            )
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
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(_ensure_indexes, _remove_indexes),
            ],
            state_operations=[
                migrations.AddIndex(
                    model_name=model_name.lower(),
                    index=models.Index(fields=list(fields), name=name),
                )
                for model_name, name, fields in _INDEXES
            ],
        ),
    ]
