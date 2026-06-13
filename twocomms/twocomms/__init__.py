# -*- coding: utf-8 -*-
import os

# Использовать PyMySQL только если явно указано в переменной окружения
if os.environ.get("MYSQL_USE_PYMYSQL") == "1":
    try:
        import pymysql
        pymysql.install_as_MySQLdb()
    except Exception:
        pass

# Celery удалён: хостинг не может запускать воркеры, проект работает по модели
# cron + синхронные shim-задачи (см. storefront/tasks.py). Импорт оставлен
# защищённым на случай, если пакет celery снова появится в окружении.
try:
    from .celery import app as celery_app  # noqa: F401
    __all__ = ("celery_app",)
except Exception:
    __all__ = ()
