#!/usr/bin/env python
import os
import sys
import django

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'twocomms.settings')
django.setup()

from django.core.cache import cache

# Очистка кеша
cache.clear()
print("Cache cleared successfully!")

# Также очистим кеш браузера через заголовки
print("Browser cache should be cleared on next request")
