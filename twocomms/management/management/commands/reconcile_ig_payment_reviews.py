import json

from django.core.management.base import BaseCommand, CommandError

from management.services.ig_payment_review import reconcile_legacy_payment_reviews


class Command(BaseCommand):
    help = "Preview or apply bounded, evidence-anchored Instagram payment-review deduplication."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Preview only (the default).")
        parser.add_argument("--apply", action="store_true", help="Persist superseded rows and resolve duplicate alerts.")
        parser.add_argument("--limit", type=int, default=100)
        parser.add_argument("--client-id", type=int, default=0)

    def handle(self, *args, **options):
        if options["dry_run"] and options["apply"]:
            raise CommandError("Використайте лише один з --dry-run або --apply.")
        result = reconcile_legacy_payment_reviews(
            client_id=options["client_id"] or None,
            limit=options["limit"],
            dry_run=not options["apply"],
        )
        self.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True))
