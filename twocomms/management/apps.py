from django.apps import AppConfig


class ManagementConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'management'

    def ready(self):
        from . import checks  # noqa: F401
        from .services import ig_order_truth  # noqa: F401
