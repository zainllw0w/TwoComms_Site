"""
URLs для accounts приложения
"""
from django.urls import path
from . import telegram_views

urlpatterns = [
    path('telegram/webhook/', telegram_views.telegram_webhook, name='telegram_webhook'),
    path('telegram/link/', telegram_views.link_telegram_account, name='link_telegram_account'),
]
