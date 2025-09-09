#!/usr/bin/env python3
"""
Отладка Telegram уведомлений
"""
import os
import django
from datetime import datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'twocomms.production_settings')
django.setup()

from django.contrib.auth import get_user_model
from storefront.models import Product, Category
from orders.models import Order, OrderItem
from orders.telegram_notifications import TelegramNotifier

User = get_user_model()

print("=== Отладка Telegram уведомлений ===")

# Проверяем настройки бота
notifier = TelegramNotifier()
print(f"Бот настроен: {notifier.is_configured()}")
print(f"Токен: {notifier.bot_token[:10]}..." if notifier.bot_token else "Токен не найден")
print(f"Chat ID: {notifier.chat_id}")

# Находим последний заказ
try:
    last_order = Order.objects.order_by('-created').first()
    if last_order:
        print(f"\nПоследний заказ: #{last_order.order_number}")
        print(f"Товаров в заказе: {last_order.items.count()}")
        
        # Проверяем товары
        for item in last_order.items.all():
            print(f"  - {item.title}: {item.qty} шт. x {item.unit_price} грн")
            if item.color_variant:
                print(f"    Цвет: {item.color_variant.color.name}")
        
        # Формируем сообщение
        message = notifier.format_order_message(last_order)
        print(f"\nСформированное сообщение:")
        print("=" * 50)
        print(message)
        print("=" * 50)
        
        # Отправляем тестовое сообщение
        print(f"\nОтправка тестового сообщения...")
        success = notifier.send_message(message)
        print(f"Результат отправки: {'✅ Успешно' if success else '❌ Ошибка'}")
        
    else:
        print("Заказы не найдены")
        
except Exception as e:
    print(f"Ошибка: {e}")
    import traceback
    traceback.print_exc()
