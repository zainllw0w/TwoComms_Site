from django.core.management.base import BaseCommand, CommandError

from management.services.ig_core_policy import (
    CorePolicyPublicationError,
    publish_canonical_core,
)


class Command(BaseCommand):
    help = "Validate or atomically publish the canonical Instagram bot core policy."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Apply the publication. The default is a read-only dry run.",
        )
        parser.add_argument(
            "--expected-current-hash",
            default="",
            help="Required SHA-256 CAS value for --apply.",
        )

    def handle(self, *args, **options):
        try:
            result = publish_canonical_core(
                apply=bool(options["apply"]),
                expected_current_hash=options["expected_current_hash"],
            )
        except CorePolicyPublicationError as exc:
            raise CommandError(f"{exc.code}: {exc}") from exc

        mode = "applied" if result.applied else "dry-run"
        self.stdout.write(
            " ".join((
                f"mode={mode}",
                f"version={result.version}",
                f"current_hash={result.current_hash}",
                f"target_hash={result.target_hash}",
                f"changed={str(result.changed).lower()}",
                f"history_created={str(result.history_created).lower()}",
                f"readiness={result.readiness}",
            ))
        )
