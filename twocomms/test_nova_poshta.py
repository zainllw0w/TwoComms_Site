#!/usr/bin/env python3
"""
Тест интеграции с Новой Почтой
"""
import os
import django
from datetime import datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'twocomms.production_settings')
django.setup()

from django.contrib.auth import get_user_model
from storefront.models import Product, Category
from orders.models import Order, OrderItem
from orders.nova_poshta_service import NovaPoshtaService

User = get_user_model()

print("=== Тест интеграции с Новой Почтой ===")

try:
    # Проверяем настройки
    from django.conf import settings
    api_key = getattr(settings, 'NOVA_POSHTA_API_KEY', '')
    
    if not api_key:
        print("❌ NOVA_POSHTA_API_KEY не настроен в settings")
        print("📋 Добавьте ключ API Новой Почты в переменные окружения:")
        print("   NOVA_POSHTA_API_KEY=ваш_api_ключ")
        exit(1)
    
    print(f"✅ API ключ настроен: {api_key[:10]}...")
    
    # Создаем тестовый заказ с ТТН
    user, created = User.objects.get_or_create(username='testuser', defaults={'email': 'test@example.com', 'is_staff': True})
    if created:
        user.set_password('testpassword')
        user.save()
        print("Создан тестовый пользователь: testuser")
    
    # Получаем категорию
    category = Category.objects.first()
    if not category:
        category = Category.objects.create(name='Тестовая категория', slug='test-category')
    
    # Создаем тестовый продукт
    product, created = Product.objects.get_or_create(
        slug='test-nova-poshta-product',
        defaults={
            'title': 'Тест товар для Новой Почты',
            'description': 'Тестовый товар для проверки интеграции с Новой Почтой',
            'price': 299,
            'category': category
        }
    )
    if created:
        print(f"Создан тестовый продукт: {product.title}")
    
    # Создаем тестовый заказ
    order = Order.objects.create(
        user=user,
        full_name="Тест Новая Почта",
        phone="+380123456789",
        city="Киев",
        np_office="Отделение №1",
        pay_type="full",
        payment_status="paid",
        total_sum=299,
        status="ship",
        tracking_number="20450123456789"  # Тестовый ТТН
    )
    
    # Добавляем товар в заказ
    OrderItem.objects.create(
        order=order,
        product=product,
        title=product.title,
        size="M",
        qty=1,
        unit_price=product.price,
        line_total=product.price
    )
    
    print(f"✅ Тестовый заказ создан: #{order.order_number}")
    print(f"📦 ТТН: {order.tracking_number}")
    print(f"📊 Статус заказа: {order.get_status_display()}")
    
    # Тестируем сервис Новой Почты
    print(f"\n🔍 Тестирование сервиса Новой Почты...")
    service = NovaPoshtaService()
    
    # Тестируем получение информации о посылке
    print(f"📡 Получение информации о посылке {order.tracking_number}...")
    tracking_info = service.get_tracking_info(order.tracking_number)
    
    if tracking_info:
        status = tracking_info.get('Status', '')
        status_desc = tracking_info.get('StatusDescription', '')
        print(f"✅ Получена информация о посылке:")
        print(f"   Статус: {status}")
        print(f"   Описание: {status_desc}")
        
        # Тестируем обновление статуса
        print(f"\n🔄 Тестирование обновления статуса...")
        if service.update_order_tracking_status(order):
            print(f"✅ Статус заказа обновлен!")
            print(f"   Новый статус: {order.shipment_status}")
            print(f"   Время обновления: {order.shipment_status_updated}")
        else:
            print(f"ℹ️ Статус не изменился")
    else:
        print(f"❌ Не удалось получить информацию о посылке")
        print(f"   Возможные причины:")
        print(f"   - Неверный ТТН")
        print(f"   - Проблемы с API Новой Почты")
        print(f"   - Неверный API ключ")
    
    # Тестируем команду обновления
    print(f"\n⚙️ Тестирование команды обновления...")
    from django.core.management import call_command
    from io import StringIO
    
    # Перенаправляем вывод команды
    out = StringIO()
    call_command('update_tracking_statuses', '--order-number', order.order_number, stdout=out)
    output = out.getvalue()
    print(f"📋 Результат команды:")
    print(output)
    
    print(f"\n🎉 Тест завершен!")
    print(f"📋 Для настройки автоматического обновления добавьте в cron:")
    print(f"   */30 * * * * cd /path/to/project && python manage.py update_tracking_statuses")
    
except Exception as e:
    print(f"❌ Ошибка при тестировании: {e}")
    import traceback
    traceback.print_exc()
