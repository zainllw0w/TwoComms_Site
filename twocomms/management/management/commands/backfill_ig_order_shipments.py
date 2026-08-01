"""Seed the shipment journal from the tracking numbers orders already carry.

Without this the journal starts empty, so an order that was shipped before the
journal existed would show its exchange replacement as the *first* parcel and
lose the original one — exactly the loss the journal was built to prevent.

Only Instagram-linked orders are touched: the journal answers a question about
the Instagram post-sale flow, and filling it for every web order would add rows
nobody reads. Use ``--all`` to override.

Default mode is a report; ``--apply`` is required to write.
"""
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from orders.models import Order


class Command(BaseCommand):
    help = "Record the current tracking number of each order as its first shipment."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Write the rows.")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Explicit no-write mode (the default).",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Include orders with no Instagram link.",
        )
        parser.add_argument("--limit", type=int, default=0)

    def handle(self, *args, **options):
        apply_changes = bool(options["apply"])
        if apply_changes and options["dry_run"]:
            raise CommandError("--apply and --dry-run are mutually exclusive.")
        limit = max(0, int(options["limit"] or 0))
        mode = "apply" if apply_changes else "dry-run"
        self.stdout.write(f"mode={mode}")

        from management.ig_bot_models import IgOrderShipment
        from management.services.ig_shipments import normalize_tracking

        queryset = Order.objects.exclude(tracking_number__isnull=True).exclude(
            tracking_number=""
        )
        if not options["all"]:
            queryset = queryset.filter(
                Q(instagram_assignment__isnull=False)
                | Q(instagram_attribution__isnull=False)
                | Q(ig_deals__isnull=False)
                | Q(instagram_post_sale_cases__isnull=False)
            ).distinct()

        scanned = 0
        created = 0
        skipped_invalid = 0
        for order in queryset.order_by("pk").iterator(chunk_size=200):
            scanned += 1
            number = normalize_tracking(order.tracking_number)
            if not number:
                skipped_invalid += 1
                self.stdout.write(
                    f"order={order.pk} skip invalid tracking={order.tracking_number!r}"
                )
                continue
            if IgOrderShipment.objects.filter(order_id=order.pk).exists():
                continue
            created += 1
            self.stdout.write(
                f"order={order.pk} {order.order_number or ''} "
                f"initial tracking={number}"
            )
            if apply_changes:
                IgOrderShipment.objects.create(
                    order_id=order.pk,
                    tracking_number=number,
                    direction=IgOrderShipment.Direction.OUTBOUND,
                    purpose=IgOrderShipment.Purpose.INITIAL,
                    source=IgOrderShipment.Source.ORDER_FIELD,
                    note="backfilled from Order.tracking_number",
                )
            if limit and created >= limit:
                self.stdout.write(f"stopped at limit={limit}")
                break

        self.stdout.write(
            f"scanned={scanned} created={created} "
            f"invalid={skipped_invalid} mode={mode}"
        )
