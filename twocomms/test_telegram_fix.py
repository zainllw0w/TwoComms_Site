#!/usr/bin/env python3
"""
Тест исправленных Telegram уведомлений
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

print("=== Тест исправленных Telegram уведомлений ===")

try:
    # Создаем тестового пользователя, если его нет
    user, created = User.objects.get_or_create(username='testuser', defaults={'email': 'test@example.com', 'is_staff': True})
    if created:
        user.set_password('testpassword')
        user.save()
        print("Создан тестовый пользователь: testuser")
    else:
        print("Используется существующий тестовый пользователь: testuser")

    # Получаем категорию
    category = Category.objects.first()
    if not category:
        category = Category.objects.create(name='Тестовая категория', slug='test-category')

    # Создаем тестовый продукт
    product, created = Product.objects.get_or_create(
        slug='test-telegram-product',
        defaults={
            'title': 'Тестовая футболка для Telegram',
            'description': 'Тестовая футболка для проверки Telegram уведомлений',
            'price': 599,
            'category': category
        }
    )
    if created:
        print(f"Создан тестовый продукт: {product.title}")
    else:
        print(f"Используется существующий тестовый продукт: {product.title}")

    # Создаем тестовый заказ
    order = Order.objects.create(
        user=user,
        full_name="Тестовый Пользователь Telegram",
        phone="+380123456789",
        city="Киев",
        np_office="Отделение №1",
        pay_type="full",
        payment_status="unpaid",
        total_sum=0,
        status="new"
    )
    
    # Добавляем товар в заказ
    OrderItem.objects.create(
        order=order,
        product=product,
        title=product.title,
        qty=2,
        unit_price=product.price,
        line_total=product.price * 2
    )
    
    # Обновляем общую сумму
    order.total_sum = product.price * 2
    order.save()
    
    print(f"\n✅ Тестовый заказ создан: #{order.order_number}")
    print(f"📦 Товаров в заказе: {order.items.count()}")
    print(f"💰 Общая сумма: {order.total_sum} грн")
    print(f"👤 Клиент: {order.full_name}")

    # Проверяем товары в заказе
    print(f"\n📋 Товары в заказе:")
    for item in order.items.all():
        print(f"  - {item.title}: {item.qty} шт. x {item.unit_price} грн = {item.line_total} грн")

    # Отправляем уведомление вручную (как это делается в views)
    print(f"\n📱 Отправка Telegram уведомления...")
    notifier = TelegramNotifier()
    success = notifier.send_new_order_notification(order)
    print(f"Результат: {'✅ Успешно' if success else '❌ Ошибка'}")

    print(f"\n🎉 Тест завершен! Проверьте Telegram - должно прийти уведомление с товарами!")

except Exception as e:
    print(f"❌ Ошибка при тестировании: {e}")
    import traceback
    traceback.print_exc()
