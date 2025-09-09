#!/usr/bin/env python3
"""
Скрипт для диагностики 500 ошибки
"""
import os
import django
import requests
from django.test import RequestFactory
from django.core.handlers.wsgi import WSGIRequest

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'twocomms.production_settings')
django.setup()

from django.conf import settings
from storefront.views import index

print("=== Диагностика 500 ошибки ===")

# 1. Проверяем настройки
print(f"DEBUG: {settings.DEBUG}")
print(f"ALLOWED_HOSTS: {settings.ALLOWED_HOSTS}")
print(f"CSRF_TRUSTED_ORIGINS: {settings.CSRF_TRUSTED_ORIGINS}")

# 2. Проверяем основные view
print("\n=== Тестирование view ===")
try:
    factory = RequestFactory()
    request = factory.get('/', HTTP_HOST='www.twocomms.shop')
    response = index(request)
    print(f"Главная страница: {response.status_code}")
    if response.status_code != 200:
        print(f"Содержимое ответа: {response.content[:200]}...")
except Exception as e:
    print(f"Ошибка в главной странице: {e}")
    import traceback
    traceback.print_exc()

# 3. Проверяем middleware
print(f"\n=== Middleware ===")
for middleware in settings.MIDDLEWARE:
    print(f"- {middleware}")

# 4. Проверяем базу данных
print(f"\n=== База данных ===")
try:
    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        print(f"Подключение к БД: OK")
except Exception as e:
    print(f"Ошибка БД: {e}")

# 5. Проверяем статические файлы
print(f"\n=== Статические файлы ===")
print(f"STATIC_URL: {settings.STATIC_URL}")
print(f"STATIC_ROOT: {settings.STATIC_ROOT}")

# 6. Проверяем шаблоны
print(f"\n=== Шаблоны ===")
try:
    from django.template.loader import get_template
    template = get_template('pages/index.html')
    print("Шаблон index.html: OK")
except Exception as e:
    print(f"Ошибка шаблона: {e}")

print("\n=== Диагностика завершена ===")
