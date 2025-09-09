#!/usr/bin/env python3
"""
Тест нового расположения статуса ТТН и автоматического изменения статуса заказа
"""
import os
import django
from datetime import datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'twocomms.production_settings')
django.setup()

from django.contrib.auth import get_user_model
from orders.models import Order
from orders.nova_poshta_service import NovaPoshtaService

User = get_user_model()

print("=== Тест нового расположения статуса ТТН ===")

try:
    # Получаем заказ с ТТН
    order = Order.objects.get(order_number="TWC09092025N01")
    print(f"✅ Заказ найден: {order.order_number}")
    print(f"📦 ТТН: {order.tracking_number}")
    print(f"📊 Статус посылки: {order.shipment_status}")
    print(f"📋 Статус заказа: {order.get_status_display()}")
    
    # Тестируем автоматическое изменение статуса заказа
    print(f"\n🔄 Тестирование автоматического изменения статуса заказа...")
    service = NovaPoshtaService()
    
    # Создаем тестовый заказ для проверки
    test_order = Order.objects.create(
        user=order.user,
        full_name=order.full_name,
        phone=order.phone,
        city=order.city,
        np_office=order.np_office,
        pay_type=order.pay_type,
        payment_status=order.payment_status,
        total_sum=order.total_sum,
        status="ship",  # Статус "отправлено"
        tracking_number="20451239305706"
    )
    
    print(f"✅ Создан тестовый заказ: {test_order.order_number}")
    print(f"📋 Исходный статус заказа: {test_order.get_status_display()}")
    
    # Обновляем статус посылки (должно автоматически изменить статус заказа)
    if service.update_order_tracking_status(test_order):
        print(f"✅ Статус посылки обновлен")
        print(f"📦 Новый статус посылки: {test_order.shipment_status}")
        print(f"📋 Новый статус заказа: {test_order.get_status_display()}")
        
        # Проверяем, изменился ли статус заказа на "отримано"
        if test_order.status == 'done':
            print(f"🎉 Статус заказа автоматически изменен на 'отримано'!")
        else:
            print(f"ℹ️ Статус заказа не изменился (посылка еще не получена)")
    else:
        print(f"ℹ️ Статус посылки не изменился")
    
    # Удаляем тестовый заказ
    test_order.delete()
    print(f"✅ Тестовый заказ удален")
    
    print(f"\n🎉 Тест завершен!")
    print(f"📱 Проверьте интерфейс - статус ТТН должен быть справа от блока ТТН!")
    
except Exception as e:
    print(f"❌ Ошибка при тестировании: {e}")
    import traceback
    traceback.print_exc()
