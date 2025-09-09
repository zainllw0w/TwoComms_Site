#!/usr/bin/env python3
"""
Тест реального заказа для проверки Telegram уведомлений
"""
import os
import django
from datetime import datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'twocomms.production_settings')
django.setup()

from django.contrib.auth import get_user_model
from storefront.models import Product, Category, PromoCode
from orders.models import Order, OrderItem
from orders.telegram_notifications import TelegramNotifier

User = get_user_model()

print("=== Тест реального заказа для проверки Telegram уведомлений ===")

try:
    # Создаем тестового пользователя
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

    # Создаем тестовые продукты
    products = []
    for i in range(2):
        product, created = Product.objects.get_or_create(
            slug=f'test-real-product-{i+1}',
            defaults={
                'title': f'Реальный тест товар {i+1}',
                'description': f'Реальный тест товар {i+1} для проверки реальных заказов',
                'price': 299 + i * 100,
                'category': category
            }
        )
        if created:
            print(f"Создан тестовый продукт: {product.title}")
        else:
            print(f"Используется существующий тестовый продукт: {product.title}")
        products.append(product)

    # Создаем тестовый заказ
    order = Order.objects.create(
        user=user,
        full_name="Реальный Тест Пользователь",
        phone="+380123456789",
        city="Киев",
        np_office="Отделение №1",
        pay_type="full",
        payment_status="unpaid",
        total_sum=0,
        status="new"
    )
    
    # Добавляем товары в заказ
    sizes = ['M', 'L']
    quantities = [1, 2]
    
    for i, (product, size, qty) in enumerate(zip(products, sizes, quantities)):
        OrderItem.objects.create(
            order=order,
            product=product,
            title=product.title,
            size=size,
            qty=qty,
            unit_price=product.price,
            line_total=product.price * qty
        )
        print(f"Добавлен товар: {product.title} (размер: {size}, количество: {qty})")
    
    # Рассчитываем итоговую сумму
    subtotal = sum(item.line_total for item in order.items.all())
    order.total_sum = subtotal
    order.save()
    
    print(f"\n✅ Тестовый заказ создан: #{order.order_number}")
    print(f"📦 Товаров в заказе: {order.items.count()}")
    print(f"💰 Сумма товаров: {subtotal} грн")
    print(f"💳 Итого к оплате: {order.total_sum} грн")

    # Отправляем уведомление точно так же, как в views.py
    print(f"\n📱 Отправка Telegram уведомления (как в реальном заказе)...")
    try:
        from orders.telegram_notifications import TelegramNotifier
        notifier = TelegramNotifier()
        success = notifier.send_new_order_notification(order)
        print(f"Результат: {'✅ Успешно' if success else '❌ Ошибка'}")
    except Exception as e:
        print(f"❌ Ошибка при отправке: {e}")

    print(f"\n🎉 Тест завершен! Проверьте Telegram - должно прийти уведомление в том же формате, что и при реальном заказе!")
    print(f"📋 Этот тест использует тот же код, что и при нажатии кнопки 'Оформить заказ'")

except Exception as e:
    print(f"❌ Ошибка при тестировании: {e}")
    import traceback
    traceback.print_exc()
