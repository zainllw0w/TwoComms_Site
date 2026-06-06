from django.apps import AppConfig


class OrdersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'orders'

    def ready(self):
        # Підключаємо ТІЛЬКИ сигнали оптових накладних (нарахування комісії
        # при оплаті). Order-нотифікації з orders/signals.py навмисно не
        # активуємо тут — вони шлються вручну з view.
        try:
            from . import wholesale_signals  # noqa: F401
        except Exception:
            pass
