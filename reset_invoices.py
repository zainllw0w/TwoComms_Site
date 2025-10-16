#!/usr/bin/env python3
import os
import sys
import django

# Add the project directory to Python path
sys.path.append('/home/qlknpodo/TWC/TwoComms_Site/twocomms')

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'twocomms.settings')
django.setup()

from orders.models import WholesaleInvoice

print("=== СБРОС СТАТУСОВ НАКЛАДНЫХ ===")
print("Меняем все накладные на статус 'draft' (неотправленные)")

invoices = WholesaleInvoice.objects.all()
print(f"Найдено накладных: {invoices.count()}")

for inv in invoices:
    print(f"Было: ID {inv.id}, статус '{inv.status}' -> меняем на 'draft'")
    inv.status = 'draft'
    inv.save()

print("\nПроверяем результат:")
for inv in WholesaleInvoice.objects.all():
    print(f"  ID: {inv.id}, Статус: '{inv.status}'")

print("\nФильтр админки (должно быть 0):")
admin_filtered = WholesaleInvoice.objects.filter(
    status__in=['pending', 'processing', 'shipped', 'delivered', 'cancelled']
)
print(f"Найдено отправленных: {admin_filtered.count()}")
