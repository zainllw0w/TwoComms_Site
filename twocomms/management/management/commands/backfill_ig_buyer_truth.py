"""Recompute Instagram client purchase aggregates from confirmed purchase truth.

Why a backfill exists at all: ``purchases_count`` and ``total_spent`` were
projected from ``IgPaymentProjection`` only, and that table holds a single row
against 289 clients on production, because payments were confirmed by managers
rather than by the provider (F-DATA-005). Every client therefore read as
"never bought anything", including one with a paid order and a size exchange
already in transit.

Default mode is a report. ``--apply`` is required to write, so the command can
be run on production to measure the blast radius before changing anything.
"""
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from management.models import IgClient
from management.services.bot_payment_truth import (
    annotate_confirmed_purchase,
    confirmed_purchase_units,
    recalculate_client_payment_aggregates,
)


class Command(BaseCommand):
    help = "Recompute IgClient purchase aggregates from confirmed purchase truth."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Write the recomputed aggregates. Without it nothing is written.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Explicit no-write mode (the default; kept for readable runbooks).",
        )
        parser.add_argument(
            "--client-id",
            type=int,
            default=None,
            help="Restrict to a single client, for a targeted check.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Stop after N changed rows (0 = no limit).",
        )

    def handle(self, *args, **options):
        apply_changes = bool(options["apply"])
        if apply_changes and options["dry_run"]:
            raise CommandError("--apply and --dry-run are mutually exclusive.")
        limit = max(0, int(options["limit"] or 0))

        queryset = annotate_confirmed_purchase(IgClient.objects.all()).order_by("pk")
        if options["client_id"]:
            queryset = queryset.filter(pk=options["client_id"])

        mode = "apply" if apply_changes else "dry-run"
        self.stdout.write(f"mode={mode}")

        scanned = 0
        changed = 0
        buyers = 0
        unknown_amount = 0
        for client in queryset.iterator(chunk_size=200):
            scanned += 1
            units = confirmed_purchase_units(client)
            purchases = len(units)
            total = sum(
                (row["amount"] for row in units if row["amount"] is not None),
                Decimal("0.00"),
            )
            if purchases:
                buyers += 1
            if any(row["amount"] is None for row in units):
                unknown_amount += 1
            before = (int(client.purchases_count or 0), client.total_spent)
            after = (purchases, total)
            if before == after:
                continue
            changed += 1
            sources = sorted({
                source for row in units for source in row["sources"]
            })
            self.stdout.write(
                f"client={client.pk} purchases {before[0]}->{after[0]} "
                f"total {before[1]}->{after[1]} sources={','.join(sources) or 'none'}"
            )
            if apply_changes:
                with transaction.atomic():
                    recalculate_client_payment_aggregates(client)
            if limit and changed >= limit:
                self.stdout.write(f"stopped at limit={limit}")
                break

        self.stdout.write(
            f"scanned={scanned} changed={changed} buyers={buyers} "
            f"amount_unknown={unknown_amount} mode={mode}"
        )
