"""Report and guardedly remove an unsupported imported 50+ wash claim."""

from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from storefront.models import Product


STANDARD_CATEGORY_SLUGS = ("tshirts", "hoodie", "long-sleeve")
STANDARD_PRODUCT_STATUS = "published"
COPY_FIELDS = (
    "full_description",
    "full_description_uk",
    "full_description_ru",
    "full_description_en",
)
FIELD_LOCALES = {
    "full_description": "uk",
    "full_description_uk": "uk",
    "full_description_ru": "ru",
    "full_description_en": "en",
}
LEGACY_SENTENCES = {
    "uk": (
        "Принт нанесено методом DTF-друку — насичені кольори, тонкі деталі "
        "та стійкість до 50+ циклів прання при дотриманні правил догляду."
    ),
    "ru": (
        "Принт нанесён методом DTF-печати — насыщенные цвета, тонкие детали "
        "и стойкость к 50+ циклам стирки при соблюдении правил ухода."
    ),
    "en": (
        "The print is applied by DTF printing — saturated colours, fine detail "
        "and a lifespan of 50+ wash cycles when care instructions are followed."
    ),
}
NEUTRAL_SENTENCES = {
    "uk": "Принт нанесено методом DTF-друку — насичені кольори та тонкі деталі.",
    "ru": "Принт нанесён методом DTF-печати — насыщенные цвета и тонкие детали.",
    "en": "The print is applied by DTF printing — saturated colours and fine detail.",
}


@contextmanager
def _mysql_table_lock(cursor):
    cursor.execute(
        "LOCK TABLES storefront_product WRITE, storefront_category READ"
    )
    try:
        yield
    finally:
        cursor.execute("UNLOCK TABLES")


def _candidate_updates(row):
    """Return only exact imported sentences, never broad 50+ text matches."""
    updates = {}
    for field in COPY_FIELDS:
        current = getattr(row, field, "") or ""
        locale = FIELD_LOCALES[field]
        legacy = LEGACY_SENTENCES[locale]
        if current.count(legacy) == 1:
            updates[field] = {
                "before": current,
                "after": current.replace(legacy, NEUTRAL_SENTENCES[locale]),
            }
    return updates


def _fingerprint(row):
    return (
        row.id,
        row.category_id,
        row.status,
        *(getattr(row, field, "") or "" for field in COPY_FIELDS),
    )


def _scan(rows):
    candidates = {
        row.id: _candidate_updates(row)
        for row in rows
        if _candidate_updates(row)
    }
    return {
        "candidate_ids": sorted(candidates),
        "updates": candidates,
        "fingerprints": {row.id: _fingerprint(row) for row in rows},
    }


def _scoped_queryset(slug=None):
    queryset = (
        Product.objects.filter(
            status=STANDARD_PRODUCT_STATUS,
            category__slug__in=STANDARD_CATEGORY_SLUGS,
        )
        .select_related("category")
        .order_by("id")
    )
    return queryset.filter(slug=slug) if slug else queryset


def _backup_rows(rows, report):
    rows_by_id = {row.id: row for row in rows}
    payload_rows = []
    for product_id in report["candidate_ids"]:
        row = rows_by_id[product_id]
        updates = report["updates"][product_id]
        payload_rows.append(
            {
                "id": row.id,
                "slug": row.slug,
                "category_slug": row.category.slug,
                "fields": {
                    field: updates[field]["before"] for field in updates
                },
            }
        )
    return {
        "candidate_ids": report["candidate_ids"],
        "rows": payload_rows,
    }


def _update_exact(cursor, product_id, field, before, after):
    """Use physical columns so modeltranslation cannot alias default/UK fields."""
    # Field names come from COPY_FIELDS, never user input.
    table = connection.ops.quote_name(Product._meta.db_table)
    column = connection.ops.quote_name(field)
    cursor.execute(
        f"UPDATE {table} SET {column} = %s WHERE id = %s AND {column} = %s",
        [after, product_id, before],
    )
    return cursor.rowcount


def _apply_updates(rows, report, cursor):
    changed_fields = 0
    for product_id in report["candidate_ids"]:
        for field, update in report["updates"][product_id].items():
            updated = _update_exact(
                cursor,
                product_id,
                field,
                update["before"],
                update["after"],
            )
            if updated != 1:
                raise CommandError(
                    "A product description changed after the scan; no further "
                    "updates were applied. Restore the JSON backup before retrying."
                )
            changed_fields += 1
    return changed_fields


class Command(BaseCommand):
    help = "Report exact imported 50+ wash copy; apply only with --apply --confirm."

    def add_arguments(self, parser):
        parser.add_argument("--slug")
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--confirm", action="store_true")
        parser.add_argument("--backup-path")

    def handle(self, *args, **options):
        if options["confirm"] and not options["apply"]:
            raise CommandError("--confirm requires --apply")
        if options["apply"] and not options["confirm"]:
            raise CommandError("Refusing to modify product copy without --confirm")
        if options["apply"] and not options["backup_path"]:
            raise CommandError("--apply requires --backup-path")

        rows = list(_scoped_queryset(options["slug"]))
        report = _scan(rows)
        candidate_fields = sum(
            len(updates) for updates in report["updates"].values()
        )
        self.stdout.write(f"dry-run candidate products: {len(report['candidate_ids'])}")
        self.stdout.write(f"dry-run candidate fields: {candidate_fields}")
        if report["candidate_ids"]:
            self.stdout.write(f"candidate ids: {report['candidate_ids']}")
        if not options["apply"] or not report["candidate_ids"]:
            return

        def apply_cleanup(locked_rows, cursor):
            current = _scan(locked_rows)
            if current != report:
                raise CommandError(
                    "Product copy changed after the initial scan; no fields were updated"
                )
            backup = _backup_rows(locked_rows, report)
            path = Path(options["backup_path"])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(backup, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            return _apply_updates(locked_rows, report, cursor=cursor)

        if connection.vendor == "mysql":
            with connection.cursor() as cursor:
                with _mysql_table_lock(cursor):
                    changed_fields = apply_cleanup(
                        list(_scoped_queryset(options["slug"])), cursor=cursor
                    )
        else:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    changed_fields = apply_cleanup(
                        list(_scoped_queryset(options["slug"]).select_for_update()),
                        cursor=cursor,
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f"replaced products: {len(report['candidate_ids'])}; "
                f"replaced fields: {changed_fields}"
            )
        )
