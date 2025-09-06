import os
import sys

# Добавляем корень приложения в PYTHONPATH
sys.path.insert(0, os.path.dirname(__file__))

# Указываем модуль настроек для продакшена
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "twocomms.production_settings")

# Импортируем Django WSGI приложение
import django
from django.core.wsgi import get_wsgi_application

# Инициализируем Django
django.setup()

# Создаем WSGI приложение
application = get_wsgi_application()
