#!/usr/bin/env python3
"""
Тест исправленной обработки заказов
"""
import os
import django
from datetime import datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'twocomms.production_settings')
django.setup()

from django.contrib.auth import get_user_model
from storefront.models import Product
from orders.models import Order, OrderItem
from django.utils import timezone

User = get_user_model()

print("=== Тест исправленной обработки заказов ===")

try:
    # Создаем тестового пользователя, если его нет
    user, created = User.objects.get_or_create(username='testuser', defaults={'email': 'test@example.com', 'is_staff': True})
    if created:
        user.set_password('testpassword')
        user.save()
        print("Создан тестовый пользователь: testuser")
    else:
        print("Используется существующий тестовый пользователь: testuser")

    # Создаем тестовые продукты, если их нет
    products = []
    for i in range(2):
        product, created = Product.objects.get_or_create(
            slug=f'test-product-{i+1}',
            defaults={
                'title': f'Тестовая футболка {i+1}',
                'description': f'Тестовая футболка {i+1} для проверки исправлений',
                'price': 299.99 + i * 100,
                'is_active': True
            }
        )
        if created:
            print(f"Создан тестовый продукт: {product.title}")
        else:
            print(f"Используется существующий тестовый продукт: {product.title}")
        products.append(product)

    # Создаем тестовый заказ с несколькими товарами
    order = Order.objects.create(
        user=user,
        full_name="Тестовый Пользователь",
        phone="+380123456789",
        city="Киев",
        np_office="Отделение №1",
        pay_type="full",
        payment_status="unpaid",
        total_sum=0,  # Будет обновлено
        status="new"
    )
    
    # Добавляем товары в заказ
    total_sum = 0
    for i, product in enumerate(products):
        qty = i + 1  # Разное количество для каждого товара
        unit_price = product.price
        line_total = unit_price * qty
        total_sum += line_total
        
        OrderItem.objects.create(
            order=order,
            product=product,
            title=product.title,
            qty=qty,
            unit_price=unit_price,
            line_total=line_total
        )
        print(f"Добавлен товар: {product.title} x {qty} шт. ({unit_price} грн/шт)")
    
    # Обновляем общую сумму
    order.total_sum = total_sum
    order.save()
    
    print(f"\n✅ Тестовый заказ создан: #{order.order_number}")
    print(f"📦 Товаров в заказе: {order.items.count()}")
    print(f"💰 Общая сумма: {order.total_sum} грн")
    print(f"👤 Клиент: {order.full_name}")

    # Проверяем товары в заказе
    print(f"\n📋 Товары в заказе:")
    for item in order.items.all():
        print(f"  - {item.title}: {item.qty} шт. x {item.unit_price} грн = {item.line_total} грн")

    print(f"\n🎉 Заказ создан успешно! Проверьте Telegram - должно прийти уведомление с товарами!")

except Exception as e:
    print(f"❌ Ошибка при создании заказа: {e}")
    import traceback
    traceback.print_exc()
