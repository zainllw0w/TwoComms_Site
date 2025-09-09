#!/usr/bin/env python3
"""
Тест исправленной логики автоматического изменения статуса
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

print("=== Тест исправленной логики автоматического изменения статуса ===")

try:
    # Получаем заказ
    order = Order.objects.get(order_number="TWC09092025N01")
    print(f"✅ Заказ найден: {order.order_number}")
    print(f"📦 ТТН: {order.tracking_number}")
    print(f"📊 Статус посылки: {order.shipment_status}")
    print(f"📋 Статус заказа: {order.status} ({order.get_status_display()})")
    
    # Тестируем исправленную логику
    print(f"\n🔄 Тестирование исправленной логики...")
    service = NovaPoshtaService()
    
    # Создаем тестовый заказ с полученной посылкой, но статусом "ship"
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
        tracking_number=order.tracking_number,
        shipment_status="Відправлення отримано"  # Посылка получена
    )
    
    print(f"✅ Создан тестовый заказ: {test_order.order_number}")
    print(f"📋 Исходный статус заказа: {test_order.status} ({test_order.get_status_display()})")
    print(f"📦 Статус посылки: {test_order.shipment_status}")
    
    # Тестируем обновление статуса (статус посылки не изменится, но статус заказа должен измениться)
    print(f"\n🔄 Тестирование обновления статуса...")
    result = service.update_order_tracking_status(test_order)
    
    print(f"🔄 Результат обновления: {result}")
    print(f"📋 Новый статус заказа: {test_order.status} ({test_order.get_status_display()})")
    print(f"📦 Статус посылки: {test_order.shipment_status}")
    
    if test_order.status == 'done':
        print(f"🎉 Успех! Статус заказа автоматически изменен на 'отримано'!")
    else:
        print(f"❌ Ошибка! Статус заказа не изменился")
    
    # Удаляем тестовый заказ
    test_order.delete()
    print(f"✅ Тестовый заказ удален")
    
    print(f"\n🎉 Тест завершен!")
    
except Exception as e:
    print(f"❌ Ошибка при тестировании: {e}")
    import traceback
    traceback.print_exc()
