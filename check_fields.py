#!/usr/bin/env python3
import os
import sys
import django

# Настройка Django
sys.path.append('/Users/zainllw0w/PycharmProjects/TwoComms/twocomms')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'twocomms.settings')
django.setup()

from accounts.models import UserProfile

print("Fields in UserProfile model:")
for field in UserProfile._meta.fields:
    print(f"  {field.name}: {field.__class__.__name__}")

print("\nChecking if company_name field exists:")
try:
    field = UserProfile._meta.get_field('company_name')
    print(f"  company_name field found: {field}")
except:
    print("  company_name field NOT found")

print("\nChecking if company_number field exists:")
try:
    field = UserProfile._meta.get_field('company_number')
    print(f"  company_number field found: {field}")
except:
    print("  company_number field NOT found")
