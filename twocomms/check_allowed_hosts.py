#!/usr/bin/env python3
"""
Скрипт для проверки настроек ALLOWED_HOSTS
"""
import os
import django

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'twocomms.production_settings')
django.setup()

from django.conf import settings

print("=== Проверка ALLOWED_HOSTS ===")
print(f"ALLOWED_HOSTS: {settings.ALLOWED_HOSTS}")
print(f"DEBUG: {settings.DEBUG}")

# Проверим переменные окружения
allowed_hosts_env = os.environ.get('ALLOWED_HOSTS')
print(f"ALLOWED_HOSTS из env: {allowed_hosts_env}")

# Проверим CSRF_TRUSTED_ORIGINS
print(f"CSRF_TRUSTED_ORIGINS: {settings.CSRF_TRUSTED_ORIGINS}")
csrf_origins_env = os.environ.get('CSRF_TRUSTED_ORIGINS')
print(f"CSRF_TRUSTED_ORIGINS из env: {csrf_origins_env}")
