from django.apps import AppConfig
class StorefrontConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'storefront'

    def ready(self):
        # Импорт и инициализация трекинга (ленивый import)
        try:
            from . import tracking  # noqa: F401
        except Exception:
            pass
