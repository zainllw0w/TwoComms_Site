from django.apps import AppConfig

class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'

    def ready(self):
        # импорт сигналов, чтобы отработало авто‑создание профиля
        from . import models  # noqa
