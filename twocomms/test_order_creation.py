#!/usr/bin/env python3
"""
Скрипт для тестирования создания заказа и отправки уведомлений
"""
import os
import django

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'twocomms.production_settings')
django.setup()

from orders.models import Order, OrderItem
from storefront.models import Product
from django.contrib.auth.models import User

def create_test_order():
    """Создает тестовый заказ для проверки уведомлений"""
    
    # Получаем первый доступный товар
    try:
        product = Product.objects.first()
        if not product:
            print("❌ Нет доступных товаров для тестирования")
            return False
    except Exception as e:
        print(f"❌ Ошибка при получении товара: {e}")
        return False
    
    # Создаем тестовый заказ
    try:
        order = Order.objects.create(
            full_name="Тестовый Пользователь",
            phone="+380123456789",
            city="Киев",
            np_office="Отделение №1",
            pay_type="full",
            payment_status="unpaid",
            total_sum=999.99,
            status="new"
        )
        
        # Добавляем товар в заказ
        OrderItem.objects.create(
            order=order,
            product=product,
            title=product.title,
            qty=1,
            unit_price=product.price,
            line_total=product.price
        )
        
        print(f"✅ Тестовый заказ создан: #{order.order_number}")
        print(f"📦 Товар: {product.title}")
        print(f"💰 Сумма: {order.total_sum} грн")
        print(f"👤 Клиент: {order.full_name}")
        print(f"📞 Телефон: {order.phone}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при создании заказа: {e}")
        return False

if __name__ == "__main__":
    print("=== Тест создания заказа и уведомлений ===")
    success = create_test_order()
    
    if success:
        print("\n🎉 Заказ создан! Проверьте Telegram - должно прийти уведомление!")
    else:
        print("\n❌ Ошибка при создании заказа")
