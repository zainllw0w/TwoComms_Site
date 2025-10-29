#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'twocomms.settings')
django.setup()

from orders.models import Order
from django.db.models import Avg, Count, Sum

# Все заказы
all_orders = Order.objects.all()
total_count = all_orders.count()

# Заказы со статусом paid
paid_orders = all_orders.filter(payment_status='paid')
paid_count = paid_orders.count()

# Средний чек всех заказов
avg_all = all_orders.aggregate(avg=Avg('total_sum'))['avg']

# Средний чек оплаченных заказов
avg_paid = paid_orders.aggregate(avg=Avg('total_sum'))['avg']

# Сумма всех заказов
total_all = all_orders.aggregate(total=Sum('total_sum'))['total']

# Сумма оплаченных заказов
total_paid = paid_orders.aggregate(total=Sum('total_sum'))['total']

print("=== СТАТИСТИКА ЗАКАЗОВ ===")
print(f"Всего заказов: {total_count}")
print(f"Оплаченных заказов: {paid_count}")
print("")
if avg_all:
    print(f"Средний чек (все заказы): {avg_all:.2f} грн")
else:
    print("Средний чек: нет данных")
    
if avg_paid:
    print(f"Средний чек (оплаченные): {avg_paid:.2f} грн")
else:
    print("Средний чек (оплаченные): нет данных")
    
print("")
if total_all:
    print(f"Общая сумма (все заказы): {total_all:.2f} грн")
else:
    print("Общая сумма: 0 грн")
    
if total_paid:
    print(f"Общая сумма (оплаченные): {total_paid:.2f} грн")
else:
    print("Общая сумма (оплаченные): 0 грн")

