#!/usr/bin/env python3
"""
Скрипт для проверки переменных окружения
"""
import os

# Проверка переменных окружения
token_status = 'УСТАНОВЛЕН' if os.environ.get('TELEGRAM_BOT_TOKEN') else 'НЕ УСТАНОВЛЕН'
chat_id_status = 'УСТАНОВЛЕН' if os.environ.get('TELEGRAM_CHAT_ID') else 'НЕ УСТАНОВЛЕН'
admin_id_status = 'УСТАНОВЛЕН' if os.environ.get('TELEGRAM_ADMIN_ID') else 'НЕ УСТАНОВЛЕН'
monobank_token_status = 'УСТАНОВЛЕН' if os.environ.get('MONOBANK_TOKEN') else 'НЕ УСТАНОВЛЕН'

# Показываем первые и последние символы токена для проверки
token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
if token:
    # Токен найден
    pass
else:
    # Токен не найден
    pass

chat_id = os.environ.get('TELEGRAM_CHAT_ID', '')
if chat_id:
    # Chat ID найден
    pass
else:
    # Chat ID не найден
    pass

admin_id = os.environ.get('TELEGRAM_ADMIN_ID', '')
if admin_id:
    # Admin ID найден
    pass
else:
    # Admin ID не найден
    pass

# Все переменные окружения
telegram_vars = {key: value for key, value in sorted(os.environ.items()) if 'TELEGRAM' in key}
monobank_vars = {key: value for key, value in sorted(os.environ.items()) if 'MONOBANK' in key}

print("=== ПРОВЕРКА ПЕРЕМЕННЫХ ОКРУЖЕНИЯ ===")
print(f"TELEGRAM_BOT_TOKEN: {token_status}")
print(f"TELEGRAM_CHAT_ID: {chat_id_status}")
print(f"TELEGRAM_ADMIN_ID: {admin_id_status}")
print(f"MONOBANK_TOKEN: {monobank_token_status}")
print("\n=== TELEGRAM ПЕРЕМЕННЫЕ ===")
for key, value in telegram_vars.items():
    if 'TOKEN' in key:
        print(f"{key}: {value[:10]}...{value[-10:] if len(value) > 20 else value}")
    else:
        print(f"{key}: {value}")
print("\n=== MONOBANK ПЕРЕМЕННЫЕ ===")
for key, value in monobank_vars.items():
    if 'TOKEN' in key:
        print(f"{key}: {value[:10]}...{value[-10:] if len(value) > 20 else value}")
    else:
        print(f"{key}: {value}")
