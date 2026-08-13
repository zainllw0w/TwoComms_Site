"""Report and guardedly remove the three retired generated delivery FAQs."""

from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from storefront.models import ProductFAQ


LOCALE_FIELDS = (
    "question",
    "answer",
    "question_uk",
    "answer_uk",
    "question_ru",
    "answer_ru",
    "question_en",
    "answer_en",
)

# Exact strings captured from the production generator. A row is removable
# only when every base/RU/EN value matches one complete signature.
LEGACY_SIGNATURES = (
    {
        "question": "Як швидко доставимо футболку?",
        "answer": "Новою Поштою — 1–3 робочі дні по всій Україні. Відділення/поштомат від 85 ₴, кур'єр від 180 ₴. Замовлення до 14:00 відправляємо того ж дня.",
        "question_uk": "Як швидко доставимо футболку?",
        "answer_uk": "Новою Поштою — 1–3 робочі дні по всій Україні. Відділення/поштомат від 85 ₴, кур'єр від 180 ₴. Замовлення до 14:00 відправляємо того ж дня.",
        "question_ru": "Как быстро доставим футболку?",
        "answer_ru": "Новой Почтой — 1–3 рабочих дня по всей Украине. Отделение/почтомат от 85 ₴, курьер от 180 ₴. Заказы до 14:00 отправляем в тот же день.",
        "question_en": "How fast will the tee arrive?",
        "answer_en": "Nova Poshta covers all of Ukraine in 1–3 business days. Branch/parcel locker from 85 UAH, courier from 180 UAH. Orders placed before 2 PM ship the same day.",
    },
    {
        "question": "Як швидко доставимо худі?",
        "answer": "Новою Поштою — 1–3 робочі дні. Відділення/поштомат від 85 ₴, адресна кур'єрська доставка від 180 ₴. Замовлення до 14:00 йдуть того ж дня.",
        "question_uk": "Як швидко доставимо худі?",
        "answer_uk": "Новою Поштою — 1–3 робочі дні. Відділення/поштомат від 85 ₴, адресна кур'єрська доставка від 180 ₴. Замовлення до 14:00 йдуть того ж дня.",
        "question_ru": "Как быстро доставим худи?",
        "answer_ru": "Новой Почтой — 1–3 рабочих дня. Отделение/почтомат от 85 ₴, адресная курьерская доставка от 180 ₴. Заказы до 14:00 уходят в тот же день.",
        "question_en": "How fast will the hoodie arrive?",
        "answer_en": "Nova Poshta — 1–3 business days. Branch/parcel locker from 85 UAH, courier-to-door from 180 UAH. Orders placed before 2 PM ship the same day.",
    },
    {
        "question": "Як довго їде доставка?",
        "answer": "Новою Поштою — 1–3 робочі дні. Відділення/поштомат від 85 ₴, адресна кур'єрська від 180 ₴. Оформлюйте до 14:00 — відправимо сьогодні.",
        "question_uk": "Як довго їде доставка?",
        "answer_uk": "Новою Поштою — 1–3 робочі дні. Відділення/поштомат від 85 ₴, адресна кур'єрська від 180 ₴. Оформлюйте до 14:00 — відправимо сьогодні.",
        "question_ru": "Сколько идёт доставка?",
        "answer_ru": "Новой Почтой — 1–3 рабочих дня. Отделение/почтомат от 85 ₴, адресная курьерская от 180 ₴. Оформляйте до 14:00 — отправим сегодня.",
        "question_en": "How long does shipping take?",
        "answer_en": "Nova Poshta delivery takes 1–3 business days. Branch/parcel locker from 85 UAH, courier-to-door from 180 UAH. Order by 2 PM and we ship the same day.",
    },
)


def _fingerprint(row):
    return tuple(getattr(row, field, None) for field in ("id", "product_id", *LOCALE_FIELDS))


def _row_payload(row):
    fields = ("id", "product_id", "order", "is_active", "created_at", "updated_at", *LOCALE_FIELDS)
    payload = {}
    for field in fields:
        value = getattr(row, field, None)
        payload[field] = value.isoformat() if hasattr(value, "isoformat") else value
    return payload


def _signature_key(row):
    return tuple(getattr(row, field, None) for field in LOCALE_FIELDS)


def _scan_rows(rows):
    signatures = {
        tuple(signature[field] for field in LOCALE_FIELDS): signature
        for signature in LEGACY_SIGNATURES
    }
    candidates = [row for row in rows if _signature_key(row) in signatures]
    return {
        "candidate_ids": sorted(row.id for row in candidates),
        "fingerprints": {row.id: _fingerprint(row) for row in rows},
        "rows": candidates,
    }


class Command(BaseCommand):
    help = "Report exact legacy generated delivery FAQs; apply only with --apply --confirm."

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

        queryset = ProductFAQ.objects.filter(is_active=True).order_by("id")
        if options["slug"]:
            queryset = queryset.filter(product__slug=options["slug"])
        rows = list(queryset)
        report = _scan_rows(rows)
        self.stdout.write(f"dry-run candidate rows: {len(report['candidate_ids'])}")
        if report["candidate_ids"]:
            self.stdout.write(f"candidate ids: {report['candidate_ids']}")

        if not options["apply"] or not report["candidate_ids"]:
            return

        with transaction.atomic():
            locked = list(
                ProductFAQ.objects.select_for_update()
                .filter(is_active=True, pk__in=report["fingerprints"])
                .order_by("id")
            )
            current = _scan_rows(locked)
            if (
                current["candidate_ids"] != report["candidate_ids"]
                or current["fingerprints"] != report["fingerprints"]
            ):
                raise CommandError("FAQ rows changed after the initial scan; no rows were deleted")
            candidates = [row for row in locked if row.id in report["candidate_ids"]]
            backup = {
                "candidate_ids": report["candidate_ids"],
                "rows": [_row_payload(row) for row in candidates],
            }
            path = Path(options["backup_path"])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(backup, ensure_ascii=False, indent=2), encoding="utf-8")
            ProductFAQ.objects.filter(pk__in=report["candidate_ids"], is_active=True).delete()

        self.stdout.write(self.style.SUCCESS(f"deleted rows: {len(report['candidate_ids'])}"))
