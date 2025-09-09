#!/usr/bin/env python3
"""
Прямой тест Django приложения
"""
import os
import django
from django.core.wsgi import get_wsgi_application

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'twocomms.production_settings')
django.setup()

from django.test import Client
from django.urls import reverse

print("=== Прямой тест Django приложения ===")

# Создаем тестовый клиент
client = Client(HTTP_HOST='www.twocomms.shop')

try:
    # Тестируем главную страницу
    response = client.get('/')
    print(f"Главная страница: {response.status_code}")
    if response.status_code == 200:
        print("✅ Главная страница работает!")
        print(f"Размер ответа: {len(response.content)} байт")
    else:
        print(f"❌ Ошибка: {response.status_code}")
        print(f"Содержимое: {response.content[:200]}...")
        
except Exception as e:
    print(f"❌ Исключение: {e}")
    import traceback
    traceback.print_exc()

try:
    # Тестируем каталог
    response = client.get('/catalog/')
    print(f"Каталог: {response.status_code}")
    if response.status_code == 200:
        print("✅ Каталог работает!")
    else:
        print(f"❌ Ошибка каталога: {response.status_code}")
        
except Exception as e:
    print(f"❌ Исключение в каталоге: {e}")

print("\n=== Тест завершен ===")
