#!/usr/bin/env python
"""
Скрипт для проверки логов предоплаты в заказах.

Использование:
    python check_prepayment_logs.py
    python check_prepayment_logs.py --order-number ORDER123
    python check_prepayment_logs.py --recent-hours 24
"""

import os
import sys
import django
from pathlib import Path
import argparse
from datetime import timedelta

# Добавляем путь к проекту
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'twocomms.settings')
django.setup()

from orders.models import Order
from django.utils import timezone
from django.db.models import Q


def check_prepayment_orders(order_number=None, recent_hours=None):
    """Проверяет заказы с предоплатой и их статусы."""
    
    print("=" * 80)
    print("ПРОВЕРКА ЗАКАЗОВ С ПРЕДОПЛАТОЙ")
    print("=" * 80)
    
    # Фильтруем заказы
    queryset = Order.objects.select_related('user').filter(pay_type='prepay_200')
    
    if order_number:
        queryset = queryset.filter(order_number=order_number)
        print(f"\n🔍 Поиск заказа: {order_number}")
    else:
        print(f"\n🔍 Все заказы с предоплатой (pay_type='prepay_200')")
    
    if recent_hours:
        cutoff = timezone.now() - timedelta(hours=recent_hours)
        queryset = queryset.filter(created__gte=cutoff)
        print(f"⏰ За последние {recent_hours} часов")
    
    orders = queryset.order_by('-created')[:50]
    
    if not orders:
        print("\n❌ Заказы с предоплатой не найдены")
        return
    
    print(f"\n📊 Найдено заказов: {len(orders)}\n")
    
    # Статистика по статусам
    status_counts = {}
    problematic_orders = []
    
    for order in orders:
        status = order.payment_status
        status_counts[status] = status_counts.get(status, 0) + 1
        
        # Проверяем проблемные заказы
        if status not in ('prepaid', 'paid', 'checking', 'unpaid'):
            problematic_orders.append(order)
        elif status == 'unpaid' and order.payment_provider.startswith('monobank'):
            # Заказ оплачен через Monobank, но статус unpaid - это проблема
            problematic_orders.append(order)
    
    print("📈 Статистика по статусам:")
    print("-" * 80)
    for status, count in sorted(status_counts.items(), key=lambda x: -x[1]):
        status_display = {
            'prepaid': '✅ Внесена предоплата',
            'paid': '✅ Оплачено полностью',
            'checking': '⏳ На перевірці',
            'unpaid': '❌ Не оплачено',
        }.get(status, f'❓ {status}')
        print(f"  {status_display}: {count}")
    
    print("\n" + "=" * 80)
    print("ДЕТАЛЬНАЯ ИНФОРМАЦИЯ О ЗАКАЗАХ")
    print("=" * 80)
    
    for order in orders:
        print(f"\n📦 Заказ #{order.order_number}")
        print(f"   ID: {order.id}")
        print(f"   Пользователь: {order.user.username if order.user else 'Гость'}")
        print(f"   Дата создания: {order.created}")
        print(f"   Тип оплаты: {order.pay_type}")
        print(f"   Статус оплаты: {order.payment_status}")
        print(f"   Статус заказа: {order.status}")
        print(f"   Провайдер: {order.payment_provider}")
        print(f"   Сумма: {order.total_sum} грн")
        
        # Проверяем payment_payload для истории
        if order.payment_payload:
            payload = order.payment_payload
            if isinstance(payload, dict):
                history = payload.get('history', [])
                last_status = payload.get('last_status')
                if history:
                    print(f"   📝 История платежей: {len(history)} записей")
                    print(f"   📝 Последний статус: {last_status}")
                    
                    # Показываем последние статусы
                    for entry in history[-3:]:
                        entry_status = entry.get('status', 'unknown')
                        entry_source = entry.get('source', 'unknown')
                        entry_time = entry.get('received_at', 'unknown')
                        print(f"      - {entry_status} (источник: {entry_source}, время: {entry_time})")
        
        # Проверяем, правильно ли установлен статус
        if order.pay_type == 'prepay_200':
            if order.payment_status == 'prepaid':
                print(f"   ✅ Статус корректен для предоплаты")
            elif order.payment_status == 'paid':
                print(f"   ⚠️  ВНИМАНИЕ: Статус 'paid' вместо 'prepaid' для предоплаты!")
            elif order.payment_status == 'unpaid' and order.payment_provider.startswith('monobank'):
                print(f"   ⚠️  ВНИМАНИЕ: Статус 'unpaid' для оплаченного заказа!")
        
        print("-" * 80)
    
    if problematic_orders:
        print(f"\n⚠️  ПРОБЛЕМНЫЕ ЗАКАЗЫ: {len(problematic_orders)}")
        print("=" * 80)
        for order in problematic_orders:
            print(f"   Заказ #{order.order_number}: payment_status={order.payment_status}, pay_type={order.pay_type}")
    
    # Проверяем логи
    print("\n" + "=" * 80)
    print("ИНСТРУКЦИИ ПО ПРОВЕРКЕ ЛОГОВ")
    print("=" * 80)
    print("\nДля проверки логов выполните команды:")
    print("\n1. Проверить логи Django (django.log):")
    print("   tail -n 100 django.log | grep -i 'prepayment\\|prepaid\\|prepay_200'")
    print("\n2. Проверить логи ошибок (stderr.log):")
    print("   tail -n 100 stderr.log | grep -i 'prepayment\\|prepaid\\|prepay_200'")
    print("\n3. Искать конкретный заказ:")
    if order_number:
        print(f"   grep '{order_number}' django.log | grep -i 'prepayment\\|prepaid\\|status'")
    else:
        print("   grep 'ORDER123' django.log | grep -i 'prepayment\\|prepaid\\|status'")
    print("\n4. Проверить логи webhook:")
    print("   grep 'webhook' django.log | grep -i 'prepayment\\|prepaid\\|status'")
    print("\n5. Проверить логи _record_monobank_status:")
    print("   grep '_record_monobank_status\\|prepayment successful' django.log | tail -n 20")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Проверка заказов с предоплатой')
    parser.add_argument('--order-number', '-o', help='Номер заказа для проверки')
    parser.add_argument('--recent-hours', '-h', type=int, help='Заказы за последние N часов')
    args = parser.parse_args()
    
    check_prepayment_orders(
        order_number=args.order_number,
        recent_hours=args.recent_hours
    )















