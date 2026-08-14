"""Report and guardedly remove the retired generated 50+ wash FAQ."""

from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from storefront.models import ProductFAQ


STANDARD_CATEGORY_SLUGS = ("tshirts", "hoodie", "long-sleeve")
STANDARD_PRODUCT_STATUS = "published"
STANDARD_FAQ_ORDER = 1
LOCALE_FIELDS = (
    "question", "answer", "question_uk", "answer_uk",
    "question_ru", "answer_ru", "question_en", "answer_en",
)

LEGACY_SIGNATURES = (
    {
        "question": "Як прати футболку, щоб принт не зіпсувався?",
        "answer": "Виверніть навиворіт, періть при 30 °C у режимі для бавовни без відбілювачів. Сушіть на повітрі. Прасувати можна з вивороту або через марлю. DTF-принт витримує 50+ циклів такого прання.",
        "question_uk": "Як прати футболку, щоб принт не зіпсувався?",
        "answer_uk": "Виверніть навиворіт, періть при 30 °C у режимі для бавовни без відбілювачів. Сушіть на повітрі. Прасувати можна з вивороту або через марлю. DTF-принт витримує 50+ циклів такого прання.",
        "question_ru": "Как стирать футболку, чтобы принт не испортился?",
        "answer_ru": "Выверните наизнанку, стирайте при 30 °C в режиме для хлопка без отбеливателей. Сушите на воздухе. Гладить можно с изнанки или через марлю. DTF-принт выдерживает 50+ циклов такой стирки.",
        "question_en": "How do I wash the tee without damaging the print?",
        "answer_en": "Turn inside out, wash at 30 °C on a cotton cycle without bleach. Air-dry only. Iron inside out or through cheesecloth. The DTF print easily survives 50+ wash cycles.",
    },
)
LEGACY_SIGNATURES += (
    {
        **LEGACY_SIGNATURES[0],
        "question_en": "How should I wash the tee so the print stays intact?",
    },
)


@contextmanager
def _mysql_table_lock(cursor):
    cursor.execute(
        "LOCK TABLES storefront_productfaq WRITE, "
        "storefront_product READ, storefront_category READ"
    )
    try:
        yield
    finally:
        cursor.execute("UNLOCK TABLES")


def _delete_mysql_candidates(cursor, candidate_ids):
    """Delete only the already-scanned active rows while tables are locked."""
    if not candidate_ids:
        return 0
    placeholders = ", ".join(["%s"] * len(candidate_ids))
    cursor.execute(
        "DELETE FROM storefront_productfaq "
        f"WHERE id IN ({placeholders}) AND is_active = %s",
        [*candidate_ids, True],
    )
    return cursor.rowcount


def _signature_key(row):
    return tuple(getattr(row, field, None) for field in LOCALE_FIELDS)


def _fingerprint(row):
    return tuple(
        getattr(row, field, None)
        for field in ("id", "product_id", "order", "is_active", *LOCALE_FIELDS)
    )


def _row_payload(row):
    fields = ("id", "product_id", "order", "is_active", "created_at", "updated_at", *LOCALE_FIELDS)
    payload = {}
    for field in fields:
        value = getattr(row, field, None)
        payload[field] = value.isoformat() if hasattr(value, "isoformat") else value
    return payload


def _scan_rows(rows):
    signatures = {
        tuple(signature[field] for field in LOCALE_FIELDS)
        for signature in LEGACY_SIGNATURES
    }
    candidates = [
        row for row in rows
        if (
            row.product.status == STANDARD_PRODUCT_STATUS
            and row.product.category.slug in STANDARD_CATEGORY_SLUGS
            and row.order == STANDARD_FAQ_ORDER
            and row.is_active
            and _signature_key(row) in signatures
        )
    ]
    return {
        "candidate_ids": sorted(row.id for row in candidates),
        "fingerprints": {row.id: _fingerprint(row) for row in rows},
    }


def _scoped_queryset(slug=None):
    queryset = (
        ProductFAQ.objects.filter(
            is_active=True,
            order=STANDARD_FAQ_ORDER,
            product__status=STANDARD_PRODUCT_STATUS,
            product__category__slug__in=STANDARD_CATEGORY_SLUGS,
        )
        .select_related("product", "product__category")
        .order_by("id")
    )
    return queryset.filter(product__slug=slug) if slug else queryset


class Command(BaseCommand):
    help = "Report exact legacy 50+ wash FAQs; apply only with --apply --confirm."

    def add_arguments(self, parser):
        parser.add_argument("--slug")
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--confirm", action="store_true")
        parser.add_argument("--backup-path")

    def handle(self, *args, **options):
        if options["confirm"] and not options["apply"]:
            raise CommandError("--confirm requires --apply")
        if options["apply"] and not options["confirm"]:
            raise CommandError("Refusing to modify FAQ rows without --confirm")
        if options["apply"] and not options["backup_path"]:
            raise CommandError("--apply requires --backup-path")

        rows = list(_scoped_queryset(options["slug"]))
        report = _scan_rows(rows)
        self.stdout.write(f"dry-run candidate rows: {len(report['candidate_ids'])}")
        if report["candidate_ids"]:
            self.stdout.write(f"candidate ids: {report['candidate_ids']}")
        if not options["apply"] or not report["candidate_ids"]:
            return

        def apply_cleanup(locked, mysql_cursor=None):
            current = _scan_rows(locked)
            if current != report:
                raise CommandError("FAQ rows changed after the initial scan; no rows were deleted")
            candidates = [row for row in locked if row.id in report["candidate_ids"]]
            backup = {
                "candidate_ids": report["candidate_ids"],
                "rows": [_row_payload(row) for row in candidates],
            }
            path = Path(options["backup_path"])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(backup, ensure_ascii=False, indent=2), encoding="utf-8")
            if mysql_cursor is not None:
                deleted_count = _delete_mysql_candidates(
                    mysql_cursor, report["candidate_ids"]
                )
            else:
                deleted_count, _ = ProductFAQ.objects.filter(
                    pk__in=report["candidate_ids"], is_active=True
                ).delete()
            if deleted_count != len(report["candidate_ids"]):
                raise CommandError(
                    "The delete count did not match the scanned candidate count; "
                    "restore the JSON backup before retrying"
                )
            return deleted_count

        if connection.vendor == "mysql":
            with connection.cursor() as cursor:
                with _mysql_table_lock(cursor):
                    deleted_count = apply_cleanup(
                        list(_scoped_queryset(options["slug"])), cursor
                    )
        else:
            with transaction.atomic():
                deleted_count = apply_cleanup(
                    list(_scoped_queryset(options["slug"]).select_for_update())
                )

        self.stdout.write(self.style.SUCCESS(f"deleted rows: {deleted_count}"))
