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
        
        # Импорт AI сигналов для автоматической генерации контента
        try:
            from . import ai_signals  # noqa: F401
        except Exception:
            pass
        
        # Сигналы для инвалидации кеша
        try:
            from . import cache_signals  # noqa: F401
        except Exception:
            pass
