from django.core.management.base import BaseCommand
from django.db import transaction

from management.models import ComponentReadiness, ManagementStatsConfig


DEFAULT_COMPONENTS = {
    "result": ComponentReadiness.Status.SHADOW,
    "source_fairness": ComponentReadiness.Status.SHADOW,
    "process": ComponentReadiness.Status.SHADOW,
    "follow_up": ComponentReadiness.Status.SHADOW,
    "data_quality": ComponentReadiness.Status.SHADOW,
    "verified_communication": ComponentReadiness.Status.DORMANT,
    "telephony": ComponentReadiness.Status.DORMANT,
    "dtf_bridge": ComponentReadiness.Status.DORMANT,
}


DEFAULT_FEATURE_FLAGS = {
    "mosaic_shadow_enabled": True,
    "telephony_shadow_enabled": False,
    "dtf_bridge_enabled": False,
}


DEFAULT_FORMULA_DEFAULTS = {
    "formula_version": "mosaic-v1",
    "defaults_version": "2026-03-13",
    "snapshot_schema_version": "v1",
    "payload_version": "v1",
    "rollout_state": "shadow",
}


class Command(BaseCommand):
    help = "Seeds singleton management analytics config and component readiness rows."

    @transaction.atomic
    def handle(self, *args, **options):
        config, _ = ManagementStatsConfig.objects.update_or_create(
            id=1,
            defaults={
                "formula_version": DEFAULT_FORMULA_DEFAULTS["formula_version"],
                "defaults_version": DEFAULT_FORMULA_DEFAULTS["defaults_version"],
                "snapshot_schema_version": DEFAULT_FORMULA_DEFAULTS["snapshot_schema_version"],
                "payload_version": DEFAULT_FORMULA_DEFAULTS["payload_version"],
                "rollout_state": DEFAULT_FORMULA_DEFAULTS["rollout_state"],
                "feature_flags": DEFAULT_FEATURE_FLAGS,
                "formula_defaults": DEFAULT_FORMULA_DEFAULTS,
            },
        )

        created_or_updated = 1
        for component, status in DEFAULT_COMPONENTS.items():
            _, created = ComponentReadiness.objects.update_or_create(
                component=component,
                defaults={"status": status},
            )
            created_or_updated += 1 if created else 0

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded config {config.id} and ensured {len(DEFAULT_COMPONENTS)} readiness rows."
            )
        )
