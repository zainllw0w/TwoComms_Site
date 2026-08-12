"""Report and, with explicit confirmation, remove exact ProductFAQ duplicates."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from storefront.models import ProductFAQ


LOCALES = ("", "_uk", "_ru", "_en")


def _norm(value):
    return " ".join(str(value or "").split()).casefold()


def _pair(row, suffix):
    return (_norm(getattr(row, f"question{suffix}", "")), _norm(getattr(row, f"answer{suffix}", "")))


def _fingerprint(row):
    fields = ["id", "product_id", "question", "answer", "order", "is_active"]
    fields.extend(f"{field}{suffix}" for suffix in LOCALES[1:] for field in ("question", "answer"))
    return tuple(getattr(row, field, None) for field in fields)


def _scan_rows(rows):
    by_product = defaultdict(list)
    for row in rows:
        if getattr(row, "is_active", False):
            by_product[row.product_id].append(row)

    clusters = []
    conflicts = []
    candidate_ids = []
    for product_id, product_rows in by_product.items():
        grouped = defaultdict(list)
        questions = defaultdict(list)
        for row in sorted(product_rows, key=lambda item: (item.order, item.id)):
            key = tuple(_pair(row, suffix) for suffix in LOCALES)
            grouped[key].append(row)
            for suffix in LOCALES:
                question, answer = _pair(row, suffix)
                if question and answer:
                    questions[(suffix, question)].append((answer, row))

        conflict_keys = {
            (suffix, question)
            for (suffix, question), values in questions.items()
            if len({answer for answer, _ in values}) > 1
        }

        for key, members in grouped.items():
            if len(members) < 2 or not all(question and answer for question, answer in key):
                continue
            if any(
                (suffix, question) in conflict_keys
                for suffix, (question, _answer) in zip(LOCALES, key)
            ):
                continue
            keeper = members[0]
            duplicates = members[1:]
            clusters.append({
                "product_id": product_id,
                "keeper_id": keeper.id,
                "duplicate_ids": [row.id for row in duplicates],
            })
            candidate_ids.extend(row.id for row in duplicates)

        for (suffix, question), values in questions.items():
            if len({answer for answer, _ in values}) > 1:
                conflicts.append({
                    "product_id": product_id,
                    "locale": suffix.lstrip("_") or "base",
                    "question": question,
                    "row_ids": [row.id for _, row in values],
                })

    return {
        "clusters": clusters,
        "candidate_ids": sorted(set(candidate_ids)),
        "conflicts": conflicts,
        "fingerprints": {row.id: _fingerprint(row) for row in rows if getattr(row, "is_active", False)},
    }


def _row_payload(row):
    fields = ["id", "product_id", "question", "answer", "order", "is_active", "created_at", "updated_at"]
    fields.extend(f"{field}{suffix}" for suffix in LOCALES[1:] for field in ("question", "answer"))
    payload = {}
    for field in fields:
        value = getattr(row, field, None)
        payload[field] = value.isoformat() if hasattr(value, "isoformat") else value
    return payload


class Command(BaseCommand):
    help = "Report exact intra-product ProductFAQ duplicates; apply only with --apply --confirm."

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

        queryset = ProductFAQ.objects.filter(is_active=True).select_related("product").order_by("product_id", "order", "id")
        if options["slug"]:
            queryset = queryset.filter(product__slug=options["slug"])
        rows = list(queryset)
        report = _scan_rows(rows)
        if report["conflicts"]:
            self.stdout.write(self.style.WARNING(f"conflicts: {len(report['conflicts'])}"))
            for conflict in report["conflicts"]:
                self.stdout.write(f"conflict product={conflict['product_id']} {conflict['locale']} rows={conflict['row_ids']}")
        self.stdout.write(f"dry-run candidate rows: {len(report['candidate_ids'])}")
        for cluster in report["clusters"]:
            self.stdout.write(f"product={cluster['product_id']} keeper={cluster['keeper_id']} duplicates={cluster['duplicate_ids']}")

        if not options["apply"] or not report["candidate_ids"] or report["conflicts"]:
            return

        with transaction.atomic():
            locked = list(
                ProductFAQ.objects.select_for_update()
                .filter(is_active=True, pk__in=report["fingerprints"])
                .order_by("product_id", "order", "id")
            )
            current = _scan_rows(locked)
            if current["candidate_ids"] != report["candidate_ids"] or current["conflicts"] or current["fingerprints"] != report["fingerprints"]:
                raise CommandError("FAQ rows changed after the initial scan; no rows were deleted")
            candidates = [row for row in locked if row.id in report["candidate_ids"]]
            backup = {
                "candidate_ids": report["candidate_ids"],
                "clusters": report["clusters"],
                "rows": [_row_payload(row) for row in candidates],
            }
            path = Path(options["backup_path"])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(backup, ensure_ascii=False, indent=2), encoding="utf-8")
            ProductFAQ.objects.filter(pk__in=report["candidate_ids"], is_active=True).delete()
        self.stdout.write(self.style.SUCCESS(f"deleted rows: {len(report['candidate_ids'])}"))
