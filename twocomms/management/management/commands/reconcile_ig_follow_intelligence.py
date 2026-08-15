from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Reconcile demand-driven Instagram follow work and UGC reward outbox."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=50)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        limit = max(1, min(500, int(options.get("limit") or 50)))
        dry_run = bool(options.get("dry_run"))
        from management.services.ig_follow_reconcile import (
            reconcile_follow_intelligence_once,
        )

        counts = reconcile_follow_intelligence_once(limit=limit, dry_run=dry_run)
        self.stdout.write(
            self.style.SUCCESS(
                "IG follow intelligence reconciliation: "
                + " ".join(f"{key}={value}" for key, value in counts.items())
            )
        )
