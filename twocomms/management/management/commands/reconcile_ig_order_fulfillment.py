from django.core.management.base import BaseCommand, CommandError

from management.services.ig_order_fulfillment import reconcile_order_customer_events


class Command(BaseCommand):
    help = "Materialize and deliver durable Instagram order fulfillment notifications."

    def add_arguments(self, parser):
        parser.add_argument("--order-id", type=int)
        parser.add_argument("--limit", type=int, default=100)
        parser.add_argument("--no-send", action="store_true", help="Only materialize events and release claims.")

    def handle(self, *args, **options):
        limit = max(1, min(int(options["limit"] or 100), 1000))
        try:
            stats = reconcile_order_customer_events(
                order_id=options.get("order_id"),
                limit=limit,
                send=not options["no_send"],
            )
        except Exception as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS("Instagram fulfillment: " + ", ".join(f"{key}={value}" for key, value in sorted(stats.items()))))
