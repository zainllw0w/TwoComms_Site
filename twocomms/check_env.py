#!/usr/bin/env python3
"""
Скрипт для проверки переменных окружения
"""
import os

print("=== Проверка переменных окружения ===")
print(f"TELEGRAM_BOT_TOKEN: {'УСТАНОВЛЕН' if os.environ.get('TELEGRAM_BOT_TOKEN') else 'НЕ УСТАНОВЛЕН'}")
print(f"TELEGRAM_CHAT_ID: {'УСТАНОВЛЕН' if os.environ.get('TELEGRAM_CHAT_ID') else 'НЕ УСТАНОВЛЕН'}")

# Показываем первые и последние символы токена для проверки
token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
if token:
    print(f"Токен (первые 10 символов): {token[:10]}...")
    print(f"Токен (последние 10 символов): ...{token[-10:]}")
else:
    print("Токен не найден")

chat_id = os.environ.get('TELEGRAM_CHAT_ID', '')
if chat_id:
    print(f"Chat ID: {chat_id}")
else:
    print("Chat ID не найден")

print("\n=== Все переменные окружения ===")
for key, value in sorted(os.environ.items()):
    if 'TELEGRAM' in key:
        print(f"{key}: {value}")
