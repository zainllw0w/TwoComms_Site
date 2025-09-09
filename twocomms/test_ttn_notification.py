#!/usr/bin/env python3
"""
Тест уведомления о добавлении ТТН
"""
import os
import django
from datetime import datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'twocomms.production_settings')
django.setup()

from django.contrib.auth import get_user_model
from orders.models import Order
from orders.telegram_notifications import TelegramNotifier

User = get_user_model()

print("=== Тест уведомления о добавлении ТТН ===")

try:
    # Получаем заказ с ТТН
    order = Order.objects.get(order_number="TWC09092025N01")
    print(f"✅ Заказ найден: {order.order_number}")
    print(f"📦 ТТН: {order.tracking_number}")
    print(f"👤 Пользователь: {order.user}")
    
    # Проверяем профиль пользователя
    from accounts.models import UserProfile
    profile = UserProfile.objects.get(user=order.user)
    print(f"📱 Telegram: {profile.telegram}")
    
    # Тестируем уведомление о добавлении ТТН
    print(f"\n📱 Тестирование уведомления о добавлении ТТН...")
    notifier = TelegramNotifier()
    
    # Создаем временный заказ без ТТН для тестирования
    test_order = Order.objects.create(
        user=order.user,
        full_name=order.full_name,
        phone=order.phone,
        city=order.city,
        np_office=order.np_office,
        pay_type=order.pay_type,
        payment_status=order.payment_status,
        total_sum=order.total_sum,
        status=order.status
    )
    
    print(f"✅ Создан тестовый заказ: {test_order.order_number}")
    
    # Добавляем ТТН (это должно вызвать сигнал)
    test_order.tracking_number = "20451239305706"
    test_order.save()
    
    print(f"✅ ТТН добавлен к заказу")
    print(f"📋 ТТН: {test_order.tracking_number}")
    
    # Удаляем тестовый заказ
    test_order.delete()
    print(f"✅ Тестовый заказ удален")
    
    print(f"\n🎉 Тест завершен!")
    print(f"📱 Проверьте Telegram - должно прийти уведомление о добавлении ТТН!")
    
except Exception as e:
    print(f"❌ Ошибка при тестировании: {e}")
    import traceback
    traceback.print_exc()
