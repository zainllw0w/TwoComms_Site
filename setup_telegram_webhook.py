#!/usr/bin/env python
"""
Скрипт для установки и проверки Telegram webhook
"""
import os
import sys
import django
import requests
import json

# Настройка Django
sys.path.insert(0, '/home/qlknpodo/TWC/TwoComms_Site/twocomms')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'twocomms.production_settings')
django.setup()

from django.conf import settings
from accounts.telegram_bot import telegram_bot

def check_bot_token():
    """Проверяет наличие токена бота"""
    token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
    if not token:
        print("❌ Токен бота не найден!")
        print("   Установите переменную окружения TELEGRAM_BOT_TOKEN")
        return False
    print(f"✅ Токен найден: {token[:10]}...{token[-5:]}")
    return True

def check_webhook_status():
    """Проверяет текущий статус webhook"""
    token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
    if not token:
        return None
    
    url = f"https://api.telegram.org/bot{token}/getWebhookInfo"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('ok'):
                webhook_info = data.get('result', {})
                return webhook_info
    except Exception as e:
        print(f"❌ Ошибка при проверке webhook: {e}")
    return None

def set_webhook(webhook_url):
    """Устанавливает webhook"""
    token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
    if not token:
        print("❌ Токен бота не найден!")
        return False
    
    url = f"https://api.telegram.org/bot{token}/setWebhook"
    data = {'url': webhook_url}
    
    try:
        response = requests.post(url, json=data, timeout=10)
        if response.status_code == 200:
            result = response.json()
            if result.get('ok'):
                print(f"✅ Webhook успешно установлен: {webhook_url}")
                return True
            else:
                print(f"❌ Ошибка при установке webhook: {result.get('description', 'Unknown error')}")
                return False
        else:
            print(f"❌ HTTP ошибка: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Ошибка при установке webhook: {e}")
        return False

def main():
    print("=" * 50)
    print("ПРОВЕРКА И НАСТРОЙКА TELEGRAM WEBHOOK")
    print("=" * 50)
    print()
    
    # 1. Проверка токена
    if not check_bot_token():
        return
    print()
    
    # 2. Проверка текущего статуса
    print("2. Проверка текущего статуса webhook...")
    webhook_info = check_webhook_status()
    if webhook_info:
        current_url = webhook_info.get('url', '')
        pending = webhook_info.get('pending_update_count', 0)
        last_error = webhook_info.get('last_error_message', '')
        last_error_date = webhook_info.get('last_error_date', 0)
        
        if current_url:
            print(f"   Текущий URL: {current_url}")
            print(f"   Ожидающих обновлений: {pending}")
            if last_error:
                print(f"   ❌ Последняя ошибка: {last_error}")
                if last_error_date:
                    from datetime import datetime
                    error_time = datetime.fromtimestamp(last_error_date)
                    print(f"   Время ошибки: {error_time}")
        else:
            print("   ⚠️  Webhook не установлен")
    else:
        print("   ❌ Не удалось получить информацию о webhook")
    print()
    
    # 3. Установка webhook
    webhook_url = "https://twocomms.shop/accounts/telegram/webhook/"
    print(f"3. Установка webhook на: {webhook_url}")
    
    if webhook_info and webhook_info.get('url') == webhook_url:
        print("   ✅ Webhook уже установлен на правильный URL")
    else:
        if set_webhook(webhook_url):
            print("   ✅ Webhook установлен успешно")
        else:
            print("   ❌ Не удалось установить webhook")
    print()
    
    # 4. Финальная проверка
    print("4. Финальная проверка...")
    webhook_info = check_webhook_status()
    if webhook_info and webhook_info.get('url') == webhook_url:
        print("   ✅ Webhook установлен и работает!")
    else:
        print("   ❌ Webhook не установлен правильно")
    
    print()
    print("=" * 50)

if __name__ == '__main__':
    main()



