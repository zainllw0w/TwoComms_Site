from django.apps import AppConfig


class MigrationDriftProbeConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "test_support.migration_drift_probe"
    label = "migration_drift_probe"
