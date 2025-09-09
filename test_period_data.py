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
from storefront.models import SiteSession, PageView
from orders.models import Order

print("=== TEST PERIOD DATA ===")

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

now = timezone.now()
today = now.date()

for period, period_name in zip(periods, period_names):
    print(f"\n=== Testing period: {period} ({period_name}) ===")
    
    # Определяем временные рамки
    if period == 'today':
        start_date = today
        end_date = today
    elif period == 'week':
        start_date = today - timedelta(days=7)
        end_date = today
    elif period == 'month':
        start_date = today - timedelta(days=30)
        end_date = today
    else:  # all_time
        start_date = None
        end_date = None
    
    print(f"Date range: {start_date} to {end_date}")
    
    # Проверяем данные в БД для этого периода
    if start_date and end_date:
        orders_count = Order.objects.filter(created__date__range=[start_date, end_date]).count()
        sessions_count = SiteSession.objects.filter(first_seen__date__range=[start_date, end_date], is_bot=False).count()
        pageviews_count = PageView.objects.filter(when__date__range=[start_date, end_date], is_bot=False).count()
    else:
        orders_count = Order.objects.count()
        sessions_count = SiteSession.objects.filter(is_bot=False).count()
        pageviews_count = PageView.objects.filter(is_bot=False).count()
    
    print(f"DB data: orders={orders_count}, sessions={sessions_count}, pageviews={pageviews_count}")
    
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
            if str(orders_count) in content_str:
                print(f"✓ Found orders count {orders_count} in content")
            else:
                print(f"✗ Orders count {orders_count} not found in content")
                
            if str(sessions_count) in content_str:
                print(f"✓ Found sessions count {sessions_count} in content")
            else:
                print(f"✗ Sessions count {sessions_count} not found in content")
                
            if str(pageviews_count) in content_str:
                print(f"✓ Found pageviews count {pageviews_count} in content")
            else:
                print(f"✗ Pageviews count {pageviews_count} not found in content")
                
    except Exception as e:
        print(f"Error: {e}")

print("\n=== END TEST PERIOD DATA ===")
