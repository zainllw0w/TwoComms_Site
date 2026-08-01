"""Restore explicit Nova Poshta point type/number on legacy orders."""

import time

from django.core.management.base import BaseCommand

from orders.models import Order
from orders.nova_poshta_lookup import NovaPoshtaDirectoryService


class Command(BaseCommand):
    help = "Backfill canonical Nova Poshta branch/postomat labels for orders with a saved warehouse Ref."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=1000)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--delay", type=float, default=1.1)

    def handle(self, *args, **options):
        limit = max(1, int(options.get("limit") or 1000))
        dry_run = bool(options.get("dry_run"))
        delay = max(0.0, float(options.get("delay") or 0.0))
        orders = list(
            Order.objects.exclude(np_warehouse_ref="")
            .exclude(np_warehouse_ref__isnull=True)
            .order_by("id")[:limit]
        )
        if not orders:
            self.stdout.write("No orders with Nova Poshta warehouse refs found.")
            return

        service = NovaPoshtaDirectoryService()
        labels_by_ref = {}
        updated = 0
        unresolved = 0
        for order in orders:
            warehouse_ref = (order.np_warehouse_ref or "").strip()
            if warehouse_ref not in labels_by_ref:
                if labels_by_ref and delay:
                    time.sleep(delay)
                record = None
                for attempt in range(3):
                    try:
                        record = service.get_warehouse_by_ref(warehouse_ref)
                        break
                    except Exception as exc:  # API outages must not abort other refs.
                        if attempt < 2:
                            time.sleep(max(delay, 1.5) * (attempt + 1))
                            continue
                        self.stderr.write(
                            f"Could not resolve ref for order {order.order_number}: {exc.__class__.__name__}"
                        )
                labels_by_ref[warehouse_ref] = (record or {}).get("label", "")

            canonical_label = labels_by_ref[warehouse_ref]
            if not canonical_label:
                unresolved += 1
                continue
            if canonical_label == (order.np_office or "").strip():
                continue
            self.stdout.write(
                f"{order.order_number}: {(order.np_office or '—')} -> {canonical_label}"
            )
            if not dry_run:
                order.np_office = canonical_label[:200]
                order.save(update_fields=["np_office", "updated"])
            updated += 1

        mode = "Would update" if dry_run else "Updated"
        self.stdout.write(f"{mode} {updated} orders; unresolved refs: {unresolved}; checked: {len(orders)}.")
