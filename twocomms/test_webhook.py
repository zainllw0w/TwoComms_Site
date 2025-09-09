#!/usr/bin/env python3
"""
Тест webhook с реальным пользователем
"""
import os
import django
import requests
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'twocomms.production_settings')
django.setup()

from accounts.models import UserProfile
from django.contrib.auth.models import User

print("=== Тест webhook с реальным пользователем ===")

try:
    # Создаем тестового пользователя
    test_user, created = User.objects.get_or_create(
        username='webhooktest',
        defaults={
            'email': 'webhook@test.com',
            'first_name': 'Webhook',
            'last_name': 'Test'
        }
    )
    
    # Создаем профиль с telegram username
    profile, created = UserProfile.objects.get_or_create(
        user=test_user,
        defaults={
            'telegram': 'webhooktest',
            'full_name': 'Webhook Test User'
        }
    )
    
    if not created:
        profile.telegram = 'webhooktest'
        profile.save()
    
    print(f"✅ Создан тестовый пользователь: {profile.user.username}")
    print(f"📱 Telegram username: {profile.telegram}")
    print(f"🆔 Telegram ID до теста: {profile.telegram_id}")
    
    # Тестируем webhook
    webhook_url = "https://twocomms.shop/accounts/telegram/webhook/"
    test_data = {
        "update_id": 999999999,
        "message": {
            "message_id": 1,
            "from": {
                "id": 987654321,
                "is_bot": False,
                "first_name": "Webhook",
                "username": "webhooktest"
            },
            "chat": {
                "id": 987654321,
                "first_name": "Webhook",
                "username": "webhooktest",
                "type": "private"
            },
            "date": 1694280000,
            "text": "Тест webhook!"
        }
    }
    
    print(f"\n🔄 Отправляем тест на webhook...")
    response = requests.post(webhook_url, json=test_data, timeout=10)
    print(f"📡 Ответ webhook: {response.status_code} - {response.text}")
    
    # Проверяем результат
    profile.refresh_from_db()
    print(f"🆔 Telegram ID после теста: {profile.telegram_id}")
    
    if profile.telegram_id == 987654321:
        print("🎉 Успех! Webhook работает корректно!")
    else:
        print("❌ Ошибка! Telegram ID не обновился")
    
    # Очистка
    print(f"\n🧹 Очистка тестовых данных...")
    profile.delete()
    test_user.delete()
    print("✅ Тестовые данные удалены")
    
except Exception as e:
    print(f"❌ Ошибка при тестировании: {e}")
    import traceback
    traceback.print_exc()
