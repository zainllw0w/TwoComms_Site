#!/usr/bin/env python3
"""
Тест отображения деталей товаров в Telegram уведомлениях
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

print("=== Тест отображения деталей товаров в Telegram уведомлениях ===")

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
    for i in range(3):
        product, created = Product.objects.get_or_create(
            slug=f'test-details-product-{i+1}',
            defaults={
                'title': f'Детали товар {i+1}',
                'description': f'Детали товар {i+1} для проверки отображения деталей',
                'price': 299 + i * 100,
                'category': category
            }
        )
        if created:
            print(f"Создан тестовый продукт: {product.title}")
        else:
            print(f"Используется существующий тестовый продукт: {product.title}")
        products.append(product)

    # Создаем тестовый промокод
    promo, created = PromoCode.objects.get_or_create(
        code='DETAILS20',
        defaults={
            'discount_type': 'percentage',
            'discount_value': 20,
            'max_uses': 100,
            'current_uses': 0,
            'is_active': True
        }
    )
    if created:
        print(f"Создан тестовый промокод: {promo.code}")
    else:
        print(f"Используется существующий промокод: {promo.code}")

    # Создаем тестовый заказ
    order = Order.objects.create(
        user=user,
        full_name="Детали Тест Пользователь",
        phone="+380123456789",
        city="Киев",
        np_office="Отделение №1",
        pay_type="full",
        payment_status="unpaid",
        total_sum=0,
        status="new"
    )
    
    # Добавляем товары в заказ с разными характеристиками
    sizes = ['M', 'L', 'XL']
    quantities = [1, 2, 1]
    
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
    
    # Применяем промокод
    subtotal = sum(item.line_total for item in order.items.all())
    discount = promo.calculate_discount(subtotal)
    order.discount_amount = discount
    order.promo_code = promo
    order.total_sum = subtotal - discount
    order.save()
    
    print(f"\n✅ Тестовый заказ создан: #{order.order_number}")
    print(f"📦 Товаров в заказе: {order.items.count()}")
    print(f"💰 Сумма товаров: {subtotal} грн")
    print(f"🎫 Промокод: {promo.code} (скидка: {discount} грн)")
    print(f"💳 Итого к оплате: {order.total_sum} грн")

    # Отправляем уведомление
    print(f"\n📱 Отправка Telegram уведомления с деталями товаров...")
    notifier = TelegramNotifier()
    success = notifier.send_new_order_notification(order)
    print(f"Результат: {'✅ Успешно' if success else '❌ Ошибка'}")

    print(f"\n🎉 Тест завершен! Проверьте Telegram - должно прийти уведомление с деталями товаров!")
    print(f"📋 Особенности отображения деталей товаров:")
    print(f"   • Название товара сверху")
    print(f"   • Под товаром: размер, количество, цвет, цена")
    print(f"   • Все детали в одной строке через запятую")
    print(f"   • Четкое разделение между товарами")

except Exception as e:
    print(f"❌ Ошибка при тестировании: {e}")
    import traceback
    traceback.print_exc()
