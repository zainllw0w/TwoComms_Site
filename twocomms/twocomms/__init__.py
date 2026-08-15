# -*- coding: utf-8 -*-

# Celery удалён: хостинг не может запускать воркеры, проект работает по модели
# cron + синхронные shim-задачи (см. storefront/tasks.py). Импорт оставлен
# защищённым на случай, если пакет celery снова появится в окружении.
try:
    from .celery import app as celery_app  # noqa: F401
    __all__ = ("celery_app",)
except Exception:
    __all__ = ()
