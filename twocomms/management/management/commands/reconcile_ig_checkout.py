from django.core.management.base import BaseCommand

from management.services.ig_checkout_reconciliation import reconcile_ig_checkout


class Command(BaseCommand):
    help = "Repair interrupted Instagram assisted-checkout state and lifecycle events."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)
        parser.add_argument("--no-provider-pull", action="store_true")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report bounded candidates without writes or provider calls.",
        )

    def handle(self, *args, **options):
        result = reconcile_ig_checkout(
            limit=options["limit"],
            pull_ambiguous=not options["no_provider_pull"],
            dry_run=options["dry_run"],
        )
        self.stdout.write(self.style.SUCCESS(
            "IG checkout reconciled: "
            + ", ".join(f"{key}={value}" for key, value in result.items())
        ))
