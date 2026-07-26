from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from importlib import import_module


class Command(BaseCommand):
    help = "Converge Instagram commercial episodes after deploy or interrupted backfill."

    def add_arguments(self, parser):
        parser.add_argument("--passes", type=int, default=3)

    def handle(self, *args, **options):
        migration = import_module("management.migrations.0106_ig_commercial_episodes")

        passes = max(1, min(int(options["passes"]), 10))
        # Use the live app registry: this command runs after migrations and may
        # repair rows written by an older worker during the release window.
        from django.apps import apps

        try:
            schema_context = type("SchemaContext", (), {"connection": connection})()
            remaining = migration.backfill_until_quiescent(
                apps, schema_context, max_passes=passes
            )
        except Exception as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(
            "Instagram commercial episodes reconciled; "
            + ", ".join(f"{key}={value}" for key, value in remaining.items())
        ))
