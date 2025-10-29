"""
URLs для accounts приложения
"""
from django.urls import path
from . import telegram_views, ajax_auth_views

urlpatterns = [
    # Telegram
    path('telegram/webhook/', telegram_views.telegram_webhook, name='telegram_webhook'),
    path('telegram/link/', telegram_views.link_telegram_account, name='link_telegram_account'),
    path('telegram/status/', telegram_views.check_telegram_status, name='check_telegram_status'),
    path('telegram/unlink/', telegram_views.unlink_telegram, name='unlink_telegram'),
    path('telegram/get-id/', telegram_views.get_telegram_id, name='get_telegram_id'),
    
    # AJAX Auth для дропшипа
    path('ajax/login/', ajax_auth_views.ajax_login, name='ajax_login'),
    path('ajax/register/', ajax_auth_views.ajax_register, name='ajax_register'),
]
