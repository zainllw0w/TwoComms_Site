from django.apps import AppConfig


class WarehouseConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "warehouse"
    verbose_name = "Склад / Warehouse"

    def ready(self):
        # Late import keeps app loading cheap; signals attach here when implemented.
        try:
            from . import signals  # noqa: F401
        except Exception:
            pass
