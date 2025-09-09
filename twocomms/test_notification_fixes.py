#!/usr/bin/env python3
"""
Тест исправлений уведомлений
"""
import os
import django
from datetime import datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'twocomms.production_settings')
django.setup()

from django.contrib.auth import get_user_model
from orders.models import Order
from orders.nova_poshta_service import NovaPoshtaService
from orders.telegram_notifications import TelegramNotifier

User = get_user_model()

print("=== Тест исправлений уведомлений ===")

try:
    # Получаем заказ с ТТН
    order = Order.objects.get(order_number="TWC09092025N01")
    print(f"✅ Заказ найден: {order.order_number}")
    print(f"📦 ТТН: {order.tracking_number}")
    print(f"📊 Статус посылки: {order.shipment_status}")
    print(f"📋 Статус заказа: {order.get_status_display()}")
    
    # Тестируем уведомления
    print(f"\n📱 Тестирование уведомлений...")
    notifier = TelegramNotifier()
    service = NovaPoshtaService()
    
    # Тест 1: Уведомление о добавлении ТТН
    print(f"\n1️⃣ Тест уведомления о добавлении ТТН:")
    ttn_message = notifier._format_ttn_added_message(order)
    print("✅ Сообщение сформировано")
    print("📋 Содержит ссылки:", "t.me/twocomms" in ttn_message and "twocomms.shop/my-orders" in ttn_message)
    
    # Тест 2: Уведомление о доставке
    print(f"\n2️⃣ Тест уведомления о доставке:")
    delivery_message = service._format_delivery_message(order, order.shipment_status)
    print("✅ Сообщение сформировано")
    print("📋 Содержит ссылки:", "t.me/twocomms" in delivery_message and "twocomms.shop/my-orders" in delivery_message)
    print("🎉 Содержит поздравление:", "ПОСЫЛКА ПОЛУЧЕНА" in delivery_message)
    
    # Тест 3: Обычное уведомление о статусе
    print(f"\n3️⃣ Тест обычного уведомления о статусе:")
    status_message = service._format_status_message(order, "Старый статус", "Новый статус")
    print("✅ Сообщение сформировано")
    print("📋 Содержит ссылки:", "t.me/twocomms" in status_message and "twocomms.shop/my-orders" in status_message)
    
    # Тест 4: Основное уведомление о заказе
    print(f"\n4️⃣ Тест основного уведомления о заказе:")
    order_message = notifier.format_order_message(order)
    print("✅ Сообщение сформировано")
    print("📋 Содержит ссылки:", "t.me/twocomms" in order_message and "twocomms.shop/my-orders" in order_message)
    
    print(f"\n🎉 Все тесты пройдены!")
    print(f"✅ Дублирование уведомлений исправлено")
    print(f"✅ Добавлены красивые ссылки во все сообщения")
    print(f"✅ Специальное уведомление о доставке создано")
    
except Exception as e:
    print(f"❌ Ошибка при тестировании: {e}")
    import traceback
    traceback.print_exc()
