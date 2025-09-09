#!/usr/bin/env python3
"""
Тест Telegram бота для подтверждения пользователей
"""
import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'twocomms.production_settings')
django.setup()

from accounts.telegram_bot import telegram_bot
from accounts.models import UserProfile

print("=== Тест Telegram бота ===")

# Тестовые данные
test_user_id = 123456789
test_username = "testuser"

print(f"Тестируем с user_id: {test_user_id}, username: {test_username}")

# Создаем тестовый профиль пользователя
try:
    from django.contrib.auth.models import User
    
    # Создаем тестового пользователя
    test_user, created = User.objects.get_or_create(
        username='testuser',
        defaults={
            'email': 'test@example.com',
            'first_name': 'Test',
            'last_name': 'User'
        }
    )
    
    # Создаем профиль
    profile, created = UserProfile.objects.get_or_create(
        user=test_user,
        defaults={
            'telegram': 'testuser',  # Без @
            'full_name': 'Test User'
        }
    )
    
    # Обновляем telegram если профиль уже существовал
    if not created:
        profile.telegram = 'testuser'
        profile.save()
    
    print(f"✅ Создан тестовый профиль: {profile.user.username}")
    print(f"📱 Telegram username: {profile.telegram}")
    print(f"🆔 Telegram ID: {profile.telegram_id}")
    
    # Тестируем обработку сообщения
    print(f"\n🔄 Тестируем обработку сообщения...")
    
    # Симулируем webhook update
    webhook_data = {
        'message': {
            'from': {
                'id': test_user_id,
                'username': test_username
            },
            'text': 'Привет!'
        }
    }
    
    result = telegram_bot.process_webhook_update(webhook_data)
    print(f"🔄 Результат обработки: {result}")
    
    # Проверяем, обновился ли telegram_id
    profile.refresh_from_db()
    print(f"🆔 Telegram ID после обработки: {profile.telegram_id}")
    
    if profile.telegram_id == test_user_id:
        print("🎉 Успех! Telegram ID успешно сохранен!")
    else:
        print("❌ Ошибка! Telegram ID не сохранен")
    
    # Тестируем повторное сообщение
    print(f"\n🔄 Тестируем повторное сообщение...")
    result2 = telegram_bot.process_webhook_update(webhook_data)
    print(f"🔄 Результат повторной обработки: {result2}")
    
    # Очистка
    print(f"\n🧹 Очистка тестовых данных...")
    profile.delete()
    test_user.delete()
    print("✅ Тестовые данные удалены")
    
except Exception as e:
    print(f"❌ Ошибка при тестировании: {e}")
    import traceback
    traceback.print_exc()
