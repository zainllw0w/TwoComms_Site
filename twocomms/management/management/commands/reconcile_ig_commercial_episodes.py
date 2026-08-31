from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Converge Instagram commercial episodes after deploy or interrupted backfill."

    def add_arguments(self, parser):
        parser.add_argument("--passes", type=int, default=3)

    def handle(self, *args, **options):
        passes = max(1, min(int(options["passes"]), 10))
        from management.services.ig_commercial_episodes import (
            reconcile_missing_commercial_episode_sources,
        )

        try:
            result = reconcile_missing_commercial_episode_sources(
                passes=passes,
            )
        except Exception as exc:
            raise CommandError(str(exc)) from exc
        remaining = result["remaining"]
        self.stdout.write(self.style.SUCCESS(
            "Instagram missing commercial episodes reconciled; "
            + ", ".join(
                f"processed_{key}={result[key]}"
                for key in ("deals", "reviews", "attributions")
            )
            + "; remaining "
            + ", ".join(f"{key}={value}" for key, value in remaining.items())
        ))
