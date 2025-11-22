#!/usr/bin/env python
"""
Тестовый скрипт для проверки работы Telegram webhook endpoint
"""
import os
import sys
import django
import json
import requests

# Настройка Django
sys.path.insert(0, '/home/qlknpodo/TWC/TwoComms_Site/twocomms')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'twocomms.production_settings')
django.setup()

from django.test import RequestFactory
from accounts.telegram_views import telegram_webhook

def test_webhook_endpoint():
    """Тестирует webhook endpoint"""
    print("=" * 50)
    print("ТЕСТИРОВАНИЕ TELEGRAM WEBHOOK ENDPOINT")
    print("=" * 50)
    print()
    
    # Создаем тестовые данные
    test_data = {
        "update_id": 123456789,
        "message": {
            "message_id": 1,
            "from": {
                "id": 123456789,
                "is_bot": False,
                "first_name": "Test",
                "username": "testuser"
            },
            "chat": {
                "id": 123456789,
                "first_name": "Test",
                "username": "testuser",
                "type": "private"
            },
            "date": 1234567890,
            "text": "/start"
        }
    }
    
    # Создаем запрос
    factory = RequestFactory()
    request = factory.post(
        '/accounts/telegram/webhook/',
        data=json.dumps(test_data),
        content_type='application/json'
    )
    
    print("1. Тестирование endpoint с тестовыми данными...")
    print(f"   Данные: {json.dumps(test_data, indent=2)}")
    print()
    
    try:
        response = telegram_webhook(request)
        print(f"✅ Endpoint работает!")
        print(f"   Статус: {response.status_code}")
        print(f"   Ответ: {response.content.decode()[:500]}")
        return True
    except Exception as e:
        print(f"❌ Ошибка при тестировании endpoint: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_webhook_url():
    """Тестирует webhook URL через HTTP"""
    print()
    print("2. Тестирование webhook URL через HTTP...")
    webhook_url = "https://twocomms.shop/accounts/telegram/webhook/"
    
    test_data = {
        "update_id": 123456789,
        "message": {
            "message_id": 1,
            "from": {
                "id": 123456789,
                "is_bot": False,
                "first_name": "Test",
                "username": "testuser"
            },
            "chat": {
                "id": 123456789,
                "first_name": "Test",
                "username": "testuser",
                "type": "private"
            },
            "date": 1234567890,
            "text": "test message"
        }
    }
    
    try:
        response = requests.post(
            webhook_url,
            json=test_data,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        print(f"   HTTP статус: {response.status_code}")
        print(f"   Ответ: {response.text[:500]}")
        
        if response.status_code == 200:
            print("   ✅ URL доступен и отвечает")
            return True
        else:
            print(f"   ⚠️  URL доступен, но вернул статус {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Ошибка при запросе к URL: {e}")
        return False

if __name__ == '__main__':
    test_webhook_endpoint()
    test_webhook_url()
    print()
    print("=" * 50)



