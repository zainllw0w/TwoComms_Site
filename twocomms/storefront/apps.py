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
        
        # Сигналы для автоматического обновления Google Merchant feed
        try:
            from . import signals  # noqa: F401
        except Exception:
            pass

        # Перезагружаем монолітні в'юхи для сумісності після ініціалізації Django
        try:
            from . import views as new_views

            if hasattr(new_views, '_load_legacy_views'):
                new_views._load_legacy_views(force=True)
        except Exception:
            pass
