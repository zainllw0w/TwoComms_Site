import os
import sys

# Добавляем корень приложения в PYTHONPATH
sys.path.insert(0, os.path.dirname(__file__))

# Указываем модуль настроек для продакшена
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "twocomms.production_settings")

# WSGI-приложение для Passenger/uWSGI/Gunicorn
from twocomms.wsgi import application


