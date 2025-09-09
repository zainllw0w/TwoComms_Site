#!/usr/bin/env python
import os
import sys
import django
from datetime import timedelta

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'twocomms.production_settings')
django.setup()

from django.test import RequestFactory
from django.contrib.auth.models import User
from storefront.views import admin_panel
from django.utils import timezone

print("=== TEST PERIODS ===")

# Создаем пользователя-администратора
try:
    admin_user = User.objects.get(username='admin')
except User.DoesNotExist:
    admin_user = User.objects.create_superuser('admin', 'admin@test.com', 'admin123')
    print("Created admin user")

factory = RequestFactory()

# Тестируем разные периоды
periods = ['today', 'week', 'month', 'all_time']
period_names = ['Сьогодні', 'За тиждень', 'За місяць', 'За весь час']

for period, period_name in zip(periods, period_names):
    print(f"\n=== Testing period: {period} ({period_name}) ===")
    
    # Создаем тестовый запрос
    request = factory.get(f'/admin-panel/?section=stats&period={period}', HTTP_HOST='twocomms.shop')
    request.user = admin_user
    
    try:
        # Имитируем вызов admin_panel
        response = admin_panel(request)
        print(f"Response status: {response.status_code}")
        
        if hasattr(response, 'content'):
            content_str = response.content.decode('utf-8')
            
            # Проверяем, есть ли в контенте данные для этого периода
            if period_name in content_str:
                print(f"✓ Found '{period_name}' in content")
            else:
                print(f"✗ '{period_name}' not found in content")
                
            # Проверяем, есть ли period в контенте
            if f'period={period}' in content_str:
                print(f"✓ Found 'period={period}' in content")
            else:
                print(f"✗ 'period={period}' not found in content")
                
            # Проверяем активную кнопку
            if f'period={period}' in content_str and 'active' in content_str:
                print(f"✓ Found active period button for {period}")
            else:
                print(f"✗ Active period button not found for {period}")
                
    except Exception as e:
        print(f"Error: {e}")

print("\n=== END TEST PERIODS ===")
