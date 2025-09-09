#!/usr/bin/env python
import os
import sys
import django

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'twocomms.production_settings')
django.setup()

from storefront.models import SiteSession, PageView
from django.utils import timezone
from datetime import timedelta

print("=== ANALYTICS DATA CHECK ===")
print(f"Current time: {timezone.now()}")

# Проверяем данные в таблицах
site_sessions_count = SiteSession.objects.count()
page_views_count = PageView.objects.count()

print(f"SiteSession count: {site_sessions_count}")
print(f"PageView count: {page_views_count}")

if site_sessions_count > 0:
    latest_session = SiteSession.objects.latest('first_seen')
    print(f"Latest SiteSession: {latest_session.first_seen} (user: {latest_session.user_id}, bot: {latest_session.is_bot})")
    
    # Проверяем сегодняшние сессии
    today = timezone.now().date()
    today_sessions = SiteSession.objects.filter(first_seen__date=today, is_bot=False)
    print(f"Today sessions (non-bot): {today_sessions.count()}")
    
    # Проверяем онлайн пользователей
    online_threshold = timezone.now() - timedelta(minutes=5)
    online_users = SiteSession.objects.filter(last_seen__gte=online_threshold, is_bot=False).count()
    print(f"Online users (last 5 min): {online_users}")

if page_views_count > 0:
    latest_pageview = PageView.objects.latest('when')
    print(f"Latest PageView: {latest_pageview.when} (session: {latest_pageview.session_id}, bot: {latest_pageview.is_bot})")
    
    # Проверяем сегодняшние просмотры
    today = timezone.now().date()
    today_pageviews = PageView.objects.filter(when__date=today, is_bot=False)
    print(f"Today pageviews (non-bot): {today_pageviews.count()}")

print("=== END CHECK ===")
