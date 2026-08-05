"""Explicit, dry-run-first closure of legacy Instagram sales."""
from __future__ import annotations

import json

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from management.ig_bot_models import IgPaymentConfirmationReview
from management.services.ig_payment_review import resolve_historical_paid_review


def _amount_mappings(values: list[str]) -> dict[int, str]:
    mappings = {}
    for raw_value in values or []:
        value = str(raw_value or "").strip()
        review_id, separator, amount = value.partition("=")
        if not separator or not review_id.isdigit() or not amount.strip():
            raise CommandError("--paid-amount має формат REVIEW_ID=AMOUNT.")
        key = int(review_id)
        if key in mappings:
            raise CommandError("--paid-amount не може містити один review ID двічі.")
        mappings[key] = amount.strip()
    return mappings


class Command(BaseCommand):
    help = "Dry-run or explicitly archive completed legacy Instagram sales without creating orders."

    def add_arguments(self, parser):
        parser.add_argument("--review-id", type=int, action="append", default=[])
        parser.add_argument("--actor-id", type=int, required=True)
        parser.add_argument(
            "--outcome",
            required=True,
            choices=[
                "already_received",
                "already_delivered",
                "completed_unknown",
            ],
        )
        parser.add_argument("--reason", required=True)
        parser.add_argument("--paid-amount", action="append", default=[])
        parser.add_argument("--amount-unrecoverable", type=int, action="append", default=[])
        parser.add_argument("--apply", action="store_true", help="Persist the explicitly selected reviews.")

    def handle(self, *args, **options):
        review_ids = list(dict.fromkeys(int(value) for value in options["review_id"] if value))
        if not review_ids:
            raise CommandError("Надайте щонайменше один --review-id.")
        paid_amounts = _amount_mappings(options["paid_amount"])
        unrecoverable_ids = set(options["amount_unrecoverable"] or [])
        selected_ids = set(review_ids)
        unexpected_ids = (set(paid_amounts) | unrecoverable_ids) - selected_ids
        if unexpected_ids:
            raise CommandError("Суми можна задавати лише для переданих --review-id.")
        conflicting_ids = set(paid_amounts) & unrecoverable_ids
        if conflicting_ids:
            raise CommandError("Один review не може мати і точну, і невідновлювану суму.")

        actor = get_user_model().objects.filter(pk=options["actor_id"]).first()
        if not actor or not (getattr(actor, "is_staff", False) or getattr(actor, "is_superuser", False)):
            raise CommandError("--actor-id має посилатися на staff-користувача.")

        apply_changes = bool(options["apply"])
        results = []
        for review_id in review_ids:
            review = IgPaymentConfirmationReview.objects.filter(pk=review_id).first()
            if review is None:
                results.append({"review_id": review_id, "status": "skipped", "reason": "review_not_found"})
                continue
            was_resolved = bool(
                review.resolution_kind
                == IgPaymentConfirmationReview.ResolutionKind.HISTORICAL_PAID_ARCHIVED
            )
            try:
                with transaction.atomic():
                    resolve_historical_paid_review(
                        review,
                        actor=actor,
                        outcome=options["outcome"],
                        reason=options["reason"],
                        confirmed_amount=paid_amounts.get(review_id),
                        amount_unrecoverable=review_id in unrecoverable_ids,
                    )
                    if not apply_changes:
                        transaction.set_rollback(True)
            except ValueError as exc:
                results.append({"review_id": review_id, "status": "skipped", "reason": str(exc)})
                continue
            results.append({
                "review_id": review_id,
                "status": "skipped" if was_resolved else "applied" if apply_changes else "eligible",
                "reason": "already_resolved" if was_resolved else "",
            })

        self.stdout.write(json.dumps({
            "dry_run": not apply_changes,
            "results": results,
        }, ensure_ascii=False, sort_keys=True))
