#!/usr/bin/env python3
"""
Прямой тест webhook view
"""
import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'twocomms.production_settings')
django.setup()

from accounts.telegram_views import telegram_webhook
from django.test import RequestFactory

print("=== Прямой тест webhook view ===")

try:
    # Создаем тестовые данные
    test_data = {
        "update_id": 123456789,
        "message": {
            "message_id": 1,
            "from": {
                "id": 987654321,
                "is_bot": False,
                "first_name": "Test",
                "username": "testuser"
            },
            "chat": {
                "id": 987654321,
                "first_name": "Test",
                "username": "testuser",
                "type": "private"
            },
            "date": 1694280000,
            "text": "Тест webhook"
        }
    }
    
    # Создаем запрос
    rf = RequestFactory()
    request = rf.post(
        "/accounts/telegram/webhook/",
        data=json.dumps(test_data),
        content_type="application/json"
    )
    
    # Вызываем view
    response = telegram_webhook(request)
    
    print(f"📡 Статус ответа: {response.status_code}")
    print(f"📄 Содержимое ответа: {response.content.decode()}")
    
    if response.status_code == 200:
        print("✅ Webhook view работает корректно!")
    else:
        print("❌ Ошибка в webhook view")
        
except Exception as e:
    print(f"❌ Ошибка при тестировании: {e}")
    import traceback
    traceback.print_exc()
