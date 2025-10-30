"""
Monobank payment integration - Интеграция платежей Monobank.

Содержит views и helper функции для:
- Создания инвойсов (invoice API)
- Checkout API (быстрые платежи)
- Обработки webhooks
- Проверки статусов платежей
- Работы с Monobank API

Monobank документация: https://api.monobank.ua/docs/
"""

import logging
import hashlib
import hmac
import json
import time
import base64
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.utils import timezone
from django.core.cache import cache
from django.db import transaction

import requests

from ..models import Product, Order
from orders.models import Order as OrderModel
from productcolors.models import ProductColorVariant
from .utils import _reset_monobank_session


# Loggers
monobank_logger = logging.getLogger('storefront.monobank')
cart_logger = logging.getLogger('storefront.cart')

# Константы статусов Monobank
MONOBANK_SUCCESS_STATUSES = {'success', 'hold'}
MONOBANK_PENDING_STATUSES = {'processing'}
MONOBANK_FAILURE_STATUSES = {
    'failure', 'expired', 'rejected', 'canceled', 'cancelled', 'reversed'
}

# API настройки
MONOBANK_API_BASE = 'https://api.monobank.ua'
MONOBANK_PUBLIC_KEY_CACHE_KEY = 'monobank_public_key'
MONOBANK_PUBLIC_KEY_CACHE_TTL = 3600  # 1 час


# ==================== HELPER FUNCTIONS ====================
# _reset_monobank_session moved to utils.py to avoid duplication

def _drop_pending_monobank_order(request):
    """
    Отменяет pending Monobank заказ и очищает сессию.
    """
    _reset_monobank_session(request, drop_pending=True)


def _notify_monobank_order(order, method_label):
    """
    Отправляет уведомление о новом Monobank заказе.
    
    Args:
        order: Объект заказа
        method_label: Название метода оплаты
    """
    try:
        from orders.telegram_notifications import send_order_notification
        send_order_notification(order, method_label=method_label)
    except Exception as e:
        monobank_logger.warning(
            'Failed to send Telegram notification for order %s: %s',
            order.id, e
        )


def _cleanup_expired_monobank_orders():
    """
    Очищает истекшие Monobank заказы (старше 24 часов).
    """
    try:
        cutoff = timezone.now() - timedelta(hours=24)
        expired = OrderModel.objects.filter(
            payment_provider__in=('monobank', 'monobank_checkout', 'monobank_pay'),
            status='pending',
            created_at__lt=cutoff
        )
        count = expired.update(status='cancelled', payment_status='expired')
        if count > 0:
            monobank_logger.info(f'Cleaned up {count} expired Monobank orders')
    except Exception as e:
        monobank_logger.error(f'Error cleaning expired orders: {e}', exc_info=True)


def _get_monobank_public_key():
    """
    Получает публичный ключ Monobank для проверки подписей.
    
    Returns:
        str: Публичный ключ или None
    """
    # Проверяем кеш
    cached_key = cache.get(MONOBANK_PUBLIC_KEY_CACHE_KEY)
    if cached_key:
        return cached_key
    
    try:
        # Запрашиваем у API
        response = requests.get(
            f'{MONOBANK_API_BASE}/api/merchant/pubkey',
            headers={'X-Token': settings.MONOBANK_TOKEN},
            timeout=10
        )
        response.raise_for_status()
        public_key = response.json().get('key')
        
        # Кешируем
        if public_key:
            cache.set(MONOBANK_PUBLIC_KEY_CACHE_KEY, public_key, MONOBANK_PUBLIC_KEY_CACHE_TTL)
        
        return public_key
    except Exception as e:
        monobank_logger.error(f'Failed to get Monobank public key: {e}', exc_info=True)
        return None


def _invalidate_monobank_public_key():
    """Инвалидирует кеш публичного ключа Monobank."""
    cache.delete(MONOBANK_PUBLIC_KEY_CACHE_KEY)


def _verify_monobank_signature(request):
    """
    Проверяет подпись Monobank webhook запроса.
    
    Args:
        request: HTTP request с заголовком X-Sign
        
    Returns:
        bool: True если подпись валидна, False иначе
    """
    try:
        signature = request.headers.get('X-Sign')
        if not signature:
            monobank_logger.warning('Missing X-Sign header in Monobank webhook')
            return False
        
        # Получаем публичный ключ
        public_key_pem = _get_monobank_public_key()
        if not public_key_pem:
            monobank_logger.error('Failed to get Monobank public key for verification')
            return False
        
        # Получаем тело запроса
        body = request.body
        
        # Проверяем подпись
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.hazmat.backends import default_backend
        
        # Загружаем публичный ключ
        public_key = serialization.load_pem_public_key(
            public_key_pem.encode(),
            backend=default_backend()
        )
        
        # Декодируем подпись из base64
        signature_bytes = base64.b64decode(signature)
        
        # Проверяем
        try:
            public_key.verify(
                signature_bytes,
                body,
                padding.PKCS1v15(),
                hashes.SHA256()
            )
            return True
        except Exception as verify_error:
            monobank_logger.warning(
                f'Monobank signature verification failed: {verify_error}'
            )
            return False
            
    except Exception as e:
        monobank_logger.error(
            f'Error verifying Monobank signature: {e}',
            exc_info=True
        )
        return False


def _ensure_session_key(request):
    """
    Обеспечивает наличие session_key у request.
    Django не создает сессию автоматически для анонимных пользователей.
    """
    if not request.session.session_key:
        request.session.create()


def _validate_checkout_payload(raw_payload):
    """
    Валидирует полезную нагрузку для checkout API.
    
    Args:
        raw_payload: dict с данными запроса
        
    Returns:
        tuple: (bool success, str error_message or None)
    """
    try:
        if not raw_payload.get('product_id'):
            return False, 'Missing product_id'
        
        qty = raw_payload.get('qty', 1)
        if not isinstance(qty, int) or qty < 1:
            return False, 'Invalid qty'
        
        return True, None
    except Exception as e:
        return False, str(e)


# ==================== MONOBANK API REQUESTS ====================

class MonobankAPIError(Exception):
    """Ошибка API Monobank"""
    pass


def _monobank_api_request(method, endpoint, json_payload=None):
    """
    Выполняет запрос к API Monobank.
    
    Args:
        method (str): HTTP метод ('GET' или 'POST')
        endpoint (str): API endpoint (напр. '/api/merchant/invoice/create')
        json_payload (dict): JSON данные для POST запроса
        
    Returns:
        dict: Ответ от API
        
    Raises:
        MonobankAPIError: При ошибке API
    """
    token = getattr(settings, 'MONOBANK_TOKEN', None)
    if not token:
        raise MonobankAPIError('Monobank API token не налаштований')
    
    base_url = getattr(settings, 'MONOBANK_API_BASE', 'https://api.monobank.ua').rstrip('/')
    url = f"{base_url}{endpoint}"
    
    headers = {
        'X-Token': token,
        'Content-Type': 'application/json'
    }
    
    try:
        if method.upper() == 'POST':
            response = requests.post(url, json=json_payload, headers=headers, timeout=30)
        else:
            response = requests.get(url, headers=headers, timeout=30)
        
        data = response.json()
        monobank_logger.info(f'Monobank API {method} {endpoint}: status={response.status_code}')
        
        if response.status_code >= 400:
            error_msg = data.get('errText', data.get('errorDescription', 'Unknown error'))
            raise MonobankAPIError(f'Monobank API error: {error_msg}')
        
        return data
    
    except requests.exceptions.Timeout:
        raise MonobankAPIError('Timeout при з\'єднанні з Monobank')
    except requests.exceptions.RequestException as e:
        raise MonobankAPIError(f'Помилка з\'єднання з Monobank: {str(e)}')



