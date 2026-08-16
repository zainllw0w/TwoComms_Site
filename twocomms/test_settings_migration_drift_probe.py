"""Synthetic model drift proving that the non-DTF migration gate fails closed."""

from test_settings_migrations_non_dtf import *  # noqa: F401,F403


INSTALLED_APPS = [
    *INSTALLED_APPS,
    "test_support.migration_drift_probe.apps.MigrationDriftProbeConfig",
]
