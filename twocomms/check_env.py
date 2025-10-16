#!/usr/bin/env python3
"""
Скрипт для проверки переменных окружения
"""
import os

# Проверка переменных окружения
token_status = 'УСТАНОВЛЕН' if os.environ.get('TELEGRAM_BOT_TOKEN') else 'НЕ УСТАНОВЛЕН'
chat_id_status = 'УСТАНОВЛЕН' if os.environ.get('TELEGRAM_CHAT_ID') else 'НЕ УСТАНОВЛЕН'
admin_id_status = 'УСТАНОВЛЕН' if os.environ.get('TELEGRAM_ADMIN_ID') else 'НЕ УСТАНОВЛЕН'

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
