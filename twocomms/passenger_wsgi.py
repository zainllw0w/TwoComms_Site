import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

# Используем production_settings если доступен, иначе обычные settings
try:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "twocomms.production_settings")
except:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "twocomms.settings")

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
