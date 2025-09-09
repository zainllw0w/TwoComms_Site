#!/usr/bin/env python3
"""
Отладка автоматического изменения статуса заказа
"""
import os
import django
from datetime import datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'twocomms.production_settings')
django.setup()

from orders.models import Order
from orders.nova_poshta_service import NovaPoshtaService

print("=== Отладка автоматического изменения статуса заказа ===")

try:
    # Получаем заказ
    order = Order.objects.get(order_number="TWC09092025N01")
    print(f"✅ Заказ найден: {order.order_number}")
    print(f"📦 ТТН: {order.tracking_number}")
    print(f"📊 Статус посылки: {order.shipment_status}")
    print(f"📋 Статус заказа: {order.status} ({order.get_status_display()})")
    
    # Тестируем логику определения доставки
    print(f"\n🔍 Отладка логики определения доставки:")
    
    # Разбираем статус посылки
    if order.shipment_status:
        parts = order.shipment_status.split(' - ')
        status = parts[0] if parts else order.shipment_status
        status_description = parts[1] if len(parts) > 1 else ''
        
        print(f"📦 Статус: '{status}'")
        print(f"📝 Описание: '{status_description}'")
        
        # Проверяем ключевые слова
        delivered_keywords = [
            'отримано', 'получено', 'доставлено', 'вручено', 
            'отримано отримувачем', 'получено получателем'
        ]
        
        status_lower = status.lower()
        description_lower = status_description.lower() if status_description else ''
        
        print(f"\n🔍 Проверка ключевых слов:")
        for keyword in delivered_keywords:
            in_status = keyword in status_lower
            in_description = keyword in description_lower
            print(f"  '{keyword}': в статусе={in_status}, в описании={in_description}")
        
        is_delivered = any(keyword in status_lower or keyword in description_lower 
                          for keyword in delivered_keywords)
        
        print(f"\n✅ Посылка получена: {is_delivered}")
        print(f"📋 Статус заказа 'done': {order.status == 'done'}")
        
        if is_delivered and order.status != 'done':
            print(f"🔄 Нужно изменить статус заказа на 'done'")
        else:
            print(f"ℹ️ Изменение статуса не требуется")
    
    # Тестируем обновление статуса
    print(f"\n🔄 Тестирование обновления статуса...")
    service = NovaPoshtaService()
    
    # Создаем копию заказа для тестирования
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
        shipment_status=order.shipment_status
    )
    
    print(f"✅ Создан тестовый заказ: {test_order.order_number}")
    print(f"📋 Исходный статус заказа: {test_order.status} ({test_order.get_status_display()})")
    
    # Тестируем метод обновления статуса
    result = service._update_order_status_if_delivered(
        test_order, 
        "Відправлення отримано", 
        "Посылка получена получателем"
    )
    
    print(f"🔄 Результат обновления: {result}")
    print(f"📋 Новый статус заказа: {test_order.status} ({test_order.get_status_display()})")
    
    # Удаляем тестовый заказ
    test_order.delete()
    print(f"✅ Тестовый заказ удален")
    
except Exception as e:
    print(f"❌ Ошибка при отладке: {e}")
    import traceback
    traceback.print_exc()
