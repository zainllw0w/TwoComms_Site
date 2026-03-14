from django.core.management.base import BaseCommand
from django.db import transaction

from management.models import ComponentReadiness, ManagementStatsConfig
from management.services.config_versions import (
    DEFAULT_FEATURE_FLAGS,
    DEFAULT_FORECAST_CONFIG,
    DEFAULT_FORMULA_DEFAULTS,
    DEFAULT_MOSAIC_CONFIG,
    DEFAULT_PAYROLL_CONFIG,
    DEFAULT_TELEPHONY_CONFIG,
    DEFAULT_UI_CONFIG,
    DEFAULT_VALIDATION_STATE,
)


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


class Command(BaseCommand):
    help = "Seeds singleton management analytics config and component readiness rows."

    @transaction.atomic
    def handle(self, *args, **options):
        config, _ = ManagementStatsConfig.objects.update_or_create(
            id=1,
            defaults={
                "formula_version": DEFAULT_FORMULA_DEFAULTS["formula_version"],
                "legacy_kpd_formula_version": "kpd-v1",
                "shadow_mosaic_formula_version": DEFAULT_FORMULA_DEFAULTS["formula_version"],
                "defaults_version": DEFAULT_FORMULA_DEFAULTS["defaults_version"],
                "snapshot_schema_version": DEFAULT_FORMULA_DEFAULTS["snapshot_schema_version"],
                "payload_version": DEFAULT_FORMULA_DEFAULTS["payload_version"],
                "rollout_state": DEFAULT_FORMULA_DEFAULTS["rollout_state"],
                "feature_flags": DEFAULT_FEATURE_FLAGS,
                "formula_defaults": DEFAULT_FORMULA_DEFAULTS,
                "mosaic_config": DEFAULT_MOSAIC_CONFIG,
                "payroll_config": DEFAULT_PAYROLL_CONFIG,
                "forecast_config": DEFAULT_FORECAST_CONFIG,
                "telephony_config": DEFAULT_TELEPHONY_CONFIG,
                "ui_config": DEFAULT_UI_CONFIG,
                "validation_state": DEFAULT_VALIDATION_STATE,
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
