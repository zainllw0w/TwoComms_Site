#!/usr/bin/env python3
import os
import sys
import django

# Add the Django project to the Python path
sys.path.append('/Users/zainllw0w/PycharmProjects/TwoComms/twocomms')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'twocomms.settings')
django.setup()

from orders.models import WholesaleInvoice

print("=== WHOLESALE INVOICES ===")
invoices = WholesaleInvoice.objects.all()
print(f"Total invoices: {invoices.count()}")

for invoice in invoices[:5]:
    print(f"ID: {invoice.id}, Number: {invoice.invoice_number}, Approved: {invoice.is_approved}, Payment: {invoice.payment_status}, Amount: {invoice.total_amount}")
