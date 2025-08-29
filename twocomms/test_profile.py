#!/usr/bin/env python
import os
import sys
import django

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'twocomms.settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User

def test_profile_access():
    client = Client()
    
    # Тест без авторизации
    print("Тест без авторизации:")
    response = client.get('/profile/setup/')
    print(f"Status: {response.status_code}")
    print(f"Redirect: {response.url if hasattr(response, 'url') else 'No redirect'}")
    print()
    
    # Создаем тестового пользователя
    user, created = User.objects.get_or_create(
        username='testuser',
        defaults={'email': 'test@example.com'}
    )
    if created:
        user.set_password('testpass123')
        user.save()
        print(f"Создан тестовый пользователь: {user.username}")
    else:
        print(f"Используется существующий пользователь: {user.username}")
    
    # Авторизуемся
    login_success = client.login(username='testuser', password='testpass123')
    print(f"Авторизация: {'Успешно' if login_success else 'Неудачно'}")
    
    # Тест с авторизацией
    print("\nТест с авторизацией:")
    response = client.get('/profile/setup/')
    print(f"Status: {response.status_code}")
    print(f"Template: {response.template_name if hasattr(response, 'template_name') else 'No template'}")
    
    if response.status_code == 200:
        print("✅ Профиль доступен!")
    else:
        print("❌ Ошибка доступа к профилю")
        print(f"Content: {response.content[:500]}...")

if __name__ == '__main__':
    test_profile_access()
