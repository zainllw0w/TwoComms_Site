"""
Monobank payment integration - Интеграция платежей Monobank.

Содержит views и helper функции для:
- Создания инвойсов (invoice API)
- Финализации инвойсов (invoice finalize API)
- Checkout API (быстрые платежи)
- Обработки webhooks
- Проверки статусов платежей
- Работы с Monobank API

Monobank документация: https://api.monobank.ua/docs/
API финализации: https://monobank.ua/api-docs/acquiring/methods/ia/post--api--merchant--invoice--finalize
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
from django.contrib import messages

import requests

from ..models import Product, PromoCode
from orders.models import Order as OrderModel, OrderItem
from orders.telegram_notifications import TelegramNotifier
from orders.facebook_conversions_service import get_facebook_conversions_service
from productcolors.models import ProductColorVariant
from accounts.models import UserProfile
from .utils import _reset_monobank_session, get_cart_from_session, _get_color_variant_safe


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


def _monobank_api_request(method, endpoint, json_payload=None, params=None):
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
            response = requests.post(url, json=json_payload, params=params, headers=headers, timeout=30)
        else:
            response = requests.get(url, params=params, headers=headers, timeout=30)
        
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


# ==================== MONOBANK CREATE INVOICE ====================

@require_POST
def monobank_create_invoice(request):
    """
    Создание MonoPay инвойса для оплаты заказа из корзины.
    
    Поддерживает два типа оплаты:
    1. prepay_200 - предоплата 200 грн (остальное при получении)
    2. online_full - полная оплата онлайн
    
    POST params (JSON или из профиля):
        full_name: ПІБ клиента
        phone: Телефон
        city: Город
        np_office: Отделение Новой Почты
        pay_type: Тип оплаты ('prepay_200' или 'online_full')
        
    Returns:
        JsonResponse: 
            success=True: {invoice_url, invoice_id, order_id, order_ref}
            success=False: {error: 'message'}
    """
    monobank_logger.info(f'=== monobank_create_invoice called ===')
    monobank_logger.info(f'User authenticated: {request.user.is_authenticated}')
    
    # Получаем данные из POST (для гостей) или из профиля (для зарегистрированных)
    try:
        body = json.loads(request.body.decode('utf-8')) if request.body else {}
    except Exception:
        body = {}
    
    monobank_logger.info(f'Request body: {body}')
    monobank_logger.info(f'pay_type from body: {body.get("pay_type")}')
    
    # Извлекаем tracking данные из body (отправляет клиент для дедупликации)
    client_tracking = body.get('tracking', {})
    if client_tracking:
        monobank_logger.info(f'📊 Client tracking data received: {client_tracking}')
    
    # Получаем cart
    cart = get_cart_from_session(request)
    if not cart:
        return JsonResponse({
            'success': False,
            'error': 'Кошик порожній. Додайте товари перед оплатою.'
        })
    
    # Получаем данные клиента
    if request.user.is_authenticated:
        try:
            prof = request.user.userprofile
        except Exception as e:
            monobank_logger.error(f'Error getting user profile: {e}')
            return JsonResponse({
                'success': False,
                'error': 'Будь ласка, заповніть профіль доставки!'
            })

        def _body_override(field, default_value):
            value = body.get(field)
            if value is None:
                return default_value
            if isinstance(value, str):
                cleaned = value.strip()
                return cleaned or default_value
            return value or default_value

        full_name = _body_override('full_name', prof.full_name or request.user.username)
        phone = _body_override('phone', prof.phone)
        city = _body_override('city', prof.city)
        np_office = _body_override('np_office', prof.np_office)

        pay_type_raw = (body.get('pay_type') or prof.pay_type or 'online_full')
        normalized_pay_type = (pay_type_raw or '').strip().lower()
        if normalized_pay_type in {'prepay_200', 'prepay', 'prepaid', 'partial', 'partial_payment', 'prepay200', 'cod'}:
            pay_type = 'prepay_200'
        else:
            pay_type = 'online_full'

        monobank_logger.info(
            f"Auth user: pay_type raw={body.get('pay_type')}, profile={prof.pay_type}, normalized={pay_type}"
        )
    else:
        # Для гостей - из POST body
        full_name = body.get('full_name', '').strip()
        phone = body.get('phone', '').strip()
        city = body.get('city', '').strip()
        np_office = body.get('np_office', '').strip()
        pay_type = body.get('pay_type', 'online_full')
        monobank_logger.info(f'Guest user: pay_type={pay_type}')
        
        # Валидация для гостей
        if not all([full_name, phone, city, np_office]):
            return JsonResponse({
                'success': False,
                'error': 'Будь ласка, заповніть всі обов\'язкові поля!'
            })
    
    monobank_logger.info(f'Customer data: full_name={full_name}, pay_type={pay_type}')
    
    # Нормализуем pay_type
    monobank_logger.info(f'🔍 BEFORE normalization: pay_type={pay_type}')
    if pay_type in ['partial', 'prepaid']:
        pay_type = 'prepay_200'
        monobank_logger.info(f'✅ Normalized partial/prepaid to prepay_200')
    elif pay_type in ['full']:
        pay_type = 'online_full'
        monobank_logger.info(f'✅ Normalized full to online_full')
    monobank_logger.info(f'🔍 AFTER normalization: pay_type={pay_type}')
    
    # Создаем заказ в транзакции
    try:
        with transaction.atomic():
            # Получаем товары из БД
            ids = [item['product_id'] for item in cart.values()]
            prods = Product.objects.in_bulk(ids)
            
            # Подсчитываем общую сумму
            total_sum = Decimal('0')
            for key, it in cart.items():
                p = prods.get(it['product_id'])
                if not p:
                    continue
                unit = p.final_price
                line = unit * it['qty']
                total_sum += line
            
            if total_sum <= 0:
                return JsonResponse({
                    'success': False,
                    'error': 'Сума замовлення повинна бути більше 0'
                })
            
            # Создаем Order
            order = OrderModel.objects.create(
                user=request.user if request.user.is_authenticated else None,
                full_name=full_name,
                phone=phone,
                city=city,
                np_office=np_office,
                pay_type=pay_type,
                total_sum=total_sum,
                status='new',
                payment_status='unpaid',
                payment_provider='monobank_pay'
            )
            
            monobank_logger.info(f'Order created: {order.order_number} (ID: {order.id})')
            monobank_logger.info(f'🔍 Order.pay_type = {order.pay_type}')
            monobank_logger.info(f'🔍 Order.total_sum = {order.total_sum}')
            
            # Создаем OrderItem'ы
            order_items = []
            for key, it in cart.items():
                p = prods.get(it['product_id'])
                if not p:
                    continue
                
                color_variant = _get_color_variant_safe(it.get('color_variant_id'))
                unit = p.final_price
                line = unit * it['qty']
                
                order_item = OrderItem(
                    order=order,
                    product=p,
                    color_variant=color_variant,
                    title=p.title,
                    size=it.get('size', ''),
                    qty=it['qty'],
                    unit_price=unit,
                    line_total=line
                )
                order_items.append(order_item)
            
            OrderItem.objects.bulk_create(order_items)
            monobank_logger.info(f'Created {len(order_items)} order items')
            
            # Применяем промокод если есть
            promo_code_id = request.session.get('promo_code_id')
            if promo_code_id:
                try:
                    promo = PromoCode.objects.get(id=promo_code_id)
                    if promo.can_be_used():
                        discount = promo.calculate_discount(total_sum)
                        order.discount_amount = discount
                        order.promo_code = promo
                        promo.use()
                        order.save(update_fields=['discount_amount', 'promo_code'])
                        monobank_logger.info(f'Promo code applied: {promo.code}, discount={discount}')
                except Exception as e:
                    monobank_logger.warning(f'Error applying promo code: {e}')
            
            # Определяем сумму для оплаты в зависимости от pay_type
            monobank_logger.info(f'🔍 Determining payment amount. pay_type={pay_type}, order.pay_type={order.pay_type}')
            
            if pay_type == 'prepay_200':
                monobank_logger.info(f'✅ pay_type is prepay_200! Calculating prepayment...')
                
                # КРИТИЧЕСКАЯ ТОЧКА: Вызов get_prepayment_amount()
                monobank_logger.info(f'🔍 Calling order.get_prepayment_amount()...')
                monobank_logger.info(f'🔍 order.pay_type before call: {order.pay_type}')
                payment_amount = order.get_prepayment_amount()
                monobank_logger.info(f'🔍 order.get_prepayment_amount() returned: {payment_amount}')
                monobank_logger.info(f'🔍 Type: {type(payment_amount)}, Value: {payment_amount}')
                
                # Формируем описание для предоплаты с номером заказа
                total_sum_without_discount = order.total_sum + (order.discount_amount or Decimal('0'))
                remaining_amount = total_sum_without_discount - payment_amount
                payment_description = (
                    f'Передплата 200 грн для замовлення {order.order_number}. '
                    f'Повна сума: {total_sum_without_discount:.2f} грн. '
                    f'Залишок {remaining_amount:.2f} грн оплачується при отриманні через Нову Пошту.'
                )
                monobank_logger.info(f'✅ Prepayment amount set to: {payment_amount} UAH')
                monobank_logger.info(f'✅ Payment description: {payment_description}')
            else:
                monobank_logger.info(f'✅ pay_type is NOT prepay_200 (it is {pay_type}). Using full amount.')
                # Полная оплата
                payment_amount = order.total_sum - order.discount_amount
                payment_description = f'Оплата замовлення {order.order_number}'
                monobank_logger.info(f'✅ Full payment amount: {payment_amount} UAH')
            
            monobank_logger.info(f'🔍 FINAL payment_amount: {payment_amount} (pay_type={pay_type})')
            monobank_logger.info(f'🔍 payment_amount in kopecks: {int(payment_amount * 100)}')
            
            # Формируем basket для Monobank
            monobank_logger.info(f'🔍 Building basket entries for pay_type={pay_type}')
            basket_entries = []
            
            # Для предоплаты показываем товары с полными ценами отдельными позициями
            if pay_type == 'prepay_200':
                total_items_sum = Decimal('0')
                
                # Вычисляем остаток к доплате заранее
                total_sum_without_discount = order.total_sum + (order.discount_amount or Decimal('0'))
                remaining_amount = total_sum_without_discount - payment_amount
                
                # Добавляем все товары с их полными ценами
                items_to_show = order_items[:10]  # Максимум 10 товаров
                items_count = len(items_to_show)
                
                for idx, item in enumerate(items_to_show):
                    try:
                        # Получаем URL изображения
                        icon_url = ''
                        if item.product.main_image:
                            icon_url = request.build_absolute_uri(item.product.main_image.url)
                        
                        # Используем полную стоимость товара (line_total)
                        item_total_kopecks = int(item.line_total * 100)
                        total_items_sum += item.line_total
                        
                        # Формируем название товара
                        item_name = item.title
                        if item.size:
                            item_name += f' ({item.size})'
                        
                        monobank_logger.info(f'🔍 PREPAY mode: Adding item with FULL price')
                        monobank_logger.info(f'🔍 - name: {item_name}')
                        monobank_logger.info(f'🔍 - qty: {item.qty}')
                        monobank_logger.info(f'🔍 - sum: {item_total_kopecks} kopecks ({item.line_total} UAH)')
                        
                        item_entry = {
                            'name': item_name,
                            'qty': item.qty,
                            'sum': item_total_kopecks,  # полная цена товара в копейках
                            'icon': icon_url,
                            'unit': 'шт'
                        }
                        
                        # Для последнего товара добавляем описание с информацией о предоплате
                        if idx == len(items_to_show) - 1:
                            if items_count > 1:
                                item_entry['description'] = f'Передплата 200 грн за {items_count} товарів. Залишок {remaining_amount:.2f} грн — при отриманні на Новій Пошті'
                            else:
                                item_entry['description'] = f'Передплата 200 грн. Залишок {remaining_amount:.2f} грн — при отриманні на Новій Пошті'
                        
                        basket_entries.append(item_entry)
                    except Exception as e:
                        monobank_logger.warning(f'Error processing item for prepay basket: {e}')
                
                # Добавляем позицию "Предоплата" с суммой, которая делает общую сумму basket = 200
                # Если сумма товаров уже больше 200, добавляем отрицательную позицию для баланса
                prepay_kopecks = int(payment_amount * 100)
                current_basket_sum = int(total_items_sum * 100)
                
                if current_basket_sum > prepay_kopecks:
                    # Добавляем отрицательную позицию для баланса
                    balance_kopecks = prepay_kopecks - current_basket_sum
                    monobank_logger.info(f'🔍 PREPAY mode: Adding balance entry')
                    monobank_logger.info(f'🔍 - balance: {balance_kopecks} kopecks')
                    
                    basket_entries.append({
                        'name': f'Часткова оплата (замовлення {order.order_number}). Залишок {remaining_amount:.2f} грн при отриманні через Нову Пошту',
                        'qty': 1,
                        'sum': balance_kopecks,  # отрицательная сумма для баланса
                        'icon': '',
                        'unit': 'шт'
                    })
                elif current_basket_sum < prepay_kopecks:
                    # Добавляем позицию "Предоплата" с остаточной суммой
                    remaining_prepay = prepay_kopecks - current_basket_sum
                    monobank_logger.info(f'🔍 PREPAY mode: Adding prepayment entry')
                    monobank_logger.info(f'🔍 - prepay: {remaining_prepay} kopecks')
                    
                    basket_entries.append({
                        'name': f'Передплата (замовлення {order.order_number}). Залишок {remaining_amount:.2f} грн при отриманні через Нову Пошту',
                        'qty': 1,
                        'sum': remaining_prepay,
                        'icon': '',
                        'unit': 'шт'
                    })
                else:
                    # Суммы совпадают - описание уже добавлено к последнему товару
                    monobank_logger.info(f'🔍 PREPAY mode: Sums match, description already added to last item')
            else:
                # Для полной оплаты показываем все товары отдельными позициями
                for item in order_items[:10]:  # Максимум 10 товаров
                    try:
                        # Получаем URL изображения
                        icon_url = ''
                        if item.product.main_image:
                            icon_url = request.build_absolute_uri(item.product.main_image.url)
                        
                        basket_sum_kopecks = int(item.line_total * 100)
                        
                        # Добавляем информацию о промокоде к названию товара
                        item_name = f'{item.title} {item.size}'.strip()
                        if order.promo_code:
                            item_name += f' [з промокодом {order.promo_code.code}]'
                        
                        monobank_logger.info(f'🔍 FULL mode: Adding item {item_name}')
                        monobank_logger.info(f'🔍 - qty: {item.qty}')
                        monobank_logger.info(f'🔍 - sum: {basket_sum_kopecks} kopecks ({item.line_total} UAH)')
                        
                        basket_entries.append({
                            'name': item_name,
                            'qty': item.qty,
                            'sum': basket_sum_kopecks,  # в копейках
                            'icon': icon_url,
                            'unit': 'шт'
                        })
                    except Exception as e:
                        monobank_logger.warning(f'Error formatting basket item: {e}')
                
                # Добавляем позицию со скидкой если есть промокод
                if order.promo_code and order.discount_amount > 0:
                    discount_kopecks = int(order.discount_amount * 100)
                    monobank_logger.info(f'🔍 Adding discount entry: {discount_kopecks} kopecks')
                    basket_entries.append({
                        'name': f'Знижка по промокоду {order.promo_code.code}',
                        'qty': 1,
                        'sum': -discount_kopecks,  # отрицательная сумма
                        'icon': '',
                        'unit': 'шт'
                    })
            
            if not basket_entries:
                basket_entries.append({
                    'name': payment_description,
                    'qty': 1,
                    'sum': int(payment_amount * 100),
                    'icon': '',
                    'unit': 'шт'
                })
            
            # Создаем Monobank инвойс
            payload = {
                'amount': int(payment_amount * 100),  # сумма в копейках
                'ccy': 980,  # UAH
                'merchantPaymInfo': {
                    'reference': order.order_number,
                    'destination': payment_description,
                    'basketOrder': basket_entries
                },
                'redirectUrl': request.build_absolute_uri('/payments/monobank/return/'),
                'webHookUrl': request.build_absolute_uri('/payments/monobank/webhook/'),
            }
            
            monobank_logger.info(f'Creating Monobank invoice, payload: {json.dumps(payload, indent=2, ensure_ascii=False)}')
            
            try:
                creation_data = _monobank_api_request('POST', '/api/merchant/invoice/create', json_payload=payload)
                monobank_logger.info(f'Monobank response: {creation_data}')
            except MonobankAPIError as exc:
                monobank_logger.error(f'Monobank API error: {exc}')
                # Удаляем созданный заказ при ошибке
                order.delete()
                return JsonResponse({
                    'success': False,
                    'error': f'Помилка створення платежу: {str(exc)}'
                })
            
            # Извлекаем данные из ответа
            result = creation_data.get('result') or creation_data
            invoice_id = result.get('invoiceId')
            invoice_url = result.get('pageUrl')
            
            if not invoice_id or not invoice_url:
                monobank_logger.error(f'Invalid Monobank response: {creation_data}')
                order.delete()
                return JsonResponse({
                    'success': False,
                    'error': 'Не вдалося створити платіж. Спробуйте пізніше.'
                })

            # Детерминированный event_id для дедупликации AddPaymentInfo
            add_payment_event_id = order.get_add_payment_event_id()
            
            # Собираем tracking данные для Facebook/TikTok Conversions API
            tracking_context = {}
            
            # FBP Cookie (Facebook Browser Pixel)
            try:
                fbp_cookie = request.COOKIES.get('_fbp')
            except Exception:
                fbp_cookie = None
            if fbp_cookie:
                tracking_context['fbp'] = fbp_cookie
            
            # FBC Cookie (Facebook Click ID)
            try:
                fbc_cookie = request.COOKIES.get('_fbc')
            except Exception:
                fbc_cookie = None
            if fbc_cookie:
                tracking_context['fbc'] = fbc_cookie
            
            # TikTok Click ID
            try:
                ttclid_cookie = request.COOKIES.get('ttclid')
            except Exception:
                ttclid_cookie = None
            if ttclid_cookie:
                tracking_context['ttclid'] = ttclid_cookie
            
            # Дополняем tracking_context данными от клиента (если есть)
            if isinstance(client_tracking, dict) and client_tracking:
                for key, value in client_tracking.items():
                    if value is None:
                        continue
                    # Игнорируем event_id и lead_event_id - они генерируются при отправке событий
                    if key in ('event_id', 'lead_event_id'):
                        continue
                    # Не перезаписываем server-side значения если они уже есть
                    if key in tracking_context:
                        continue
                    tracking_context[key] = value

            # Сохраняем event_id для AddPaymentInfo, чтобы браузер и CAPI использовали одинаковое значение
            tracking_context['add_payment_event_id'] = add_payment_event_id
            
            # КРИТИЧНО: External ID должен ВСЕГДА быть определен
            external_source = tracking_context.get('external_id')
            if request.user.is_authenticated:
                external_source = external_source or f"user:{request.user.id}"
            else:
                # Пытаемся получить session_key
                try:
                    session_key = request.session.session_key
                    if not session_key:
                        # Создаем сессию если еще не создана
                        request.session.create()
                        session_key = request.session.session_key
                    if session_key:
                        external_source = external_source or f"session:{session_key}"
                except Exception:
                    pass
                
                # Если нет session_key, используем order_number
                if not external_source and order.order_number:
                    external_source = f"order:{order.order_number}"
                
                # Если нет order_number, используем order.id
                if not external_source and order.id:
                    external_source = f"order:{order.id}"
            
            # ГАРАНТИРУЕМ что external_id ВСЕГДА определен
            if not external_source:
                import time
                external_source = f"order:unknown_{int(time.time())}"
            
            tracking_context['external_id'] = external_source
            
            # Добавляем Client IP Address для улучшения атрибуции
            try:
                # Получаем реальный IP (учитываем проксирование)
                x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
                if x_forwarded_for:
                    client_ip = x_forwarded_for.split(',')[0].strip()
                else:
                    client_ip = request.META.get('REMOTE_ADDR')
                
                if client_ip:
                    tracking_context['client_ip_address'] = client_ip
            except Exception:
                pass
            
            # Добавляем User Agent для улучшения атрибуции
            try:
                user_agent = request.META.get('HTTP_USER_AGENT', '')
                if user_agent:
                    tracking_context['client_user_agent'] = user_agent
            except Exception:
                pass
            
            # Сохраняем данные платежа в Order
            payment_payload = {
                'request': payload,
                'create': creation_data,
                'history': [],
                'tracking': tracking_context
            }
            
            # Добавляем client_ip_address и client_user_agent на верхний уровень для совместимости
            if 'client_ip_address' in tracking_context:
                payment_payload['client_ip_address'] = tracking_context['client_ip_address']
            if 'client_user_agent' in tracking_context:
                payment_payload['client_user_agent'] = tracking_context['client_user_agent']
            
            order.payment_invoice_id = invoice_id
            order.payment_payload = payment_payload
            order.payment_status = 'checking'
            order.save(update_fields=['payment_invoice_id', 'payment_payload', 'payment_status'])
            
            monobank_logger.info(f'Order {order.order_number}: Saved tracking context: external_id={external_source}, fbp={bool(fbp_cookie)}, fbc={bool(fbc_cookie)}')

            
            monobank_logger.info(f'Order {order.order_number} updated with invoice_id={invoice_id}')
            
            # Сохраняем в сессию
            request.session['monobank_invoice_id'] = invoice_id
            request.session['monobank_pending_order_id'] = order.id
            request.session.modified = True
            
            # Отправляем AddPaymentInfo через CAPI для дедупликации с пикселем
            try:
                facebook_service = get_facebook_conversions_service()
                facebook_service.send_add_payment_info_event(
                    order=order,
                    payment_amount=float(payment_amount),
                    event_id=add_payment_event_id,
                    source_url=request.build_absolute_uri(request.path),
                )
            except Exception as capi_err:
                monobank_logger.warning(f'⚠️ Failed to send AddPaymentInfo to Facebook CAPI: {capi_err}')
            
            # НЕ очищаем корзину здесь - корзина будет очищена ТОЛЬКО после успешной оплаты
            # в monobank_return или через webhook
            
            # Отправляем Telegram уведомление
            try:
                from orders.telegram_notifications import TelegramNotifier
                notifier = TelegramNotifier()
                notifier.send_new_order_notification(order)
            except Exception as e:
                monobank_logger.warning(f'Failed to send Telegram notification: {e}')
            
            monobank_logger.info(f'✅ Invoice created successfully: {invoice_url}')
            
            return JsonResponse({
                'success': True,
                'invoice_url': invoice_url,
                'invoice_id': invoice_id,
                'order_id': order.id,
                'order_ref': order.order_number,
                'add_payment_event_id': add_payment_event_id
            })
            
    except Exception as e:
        monobank_logger.error(f'Error creating order/invoice: {e}', exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'Сталася помилка. Спробуйте ще раз.'
        })


# ==================== MONOBANK FINALIZE INVOICE ====================

def _monobank_finalize_invoice(order, request=None):
    """
    Финализирует Monobank инвойс после отправки товаров.
    
    ВАЖНО: Финализация НЕ списывает деньги! Деньги уже списаны при оплате.
    
    Финализация нужна ТОЛЬКО для:
    - Фискализации детальных данных в чеках Monobank
    - Добавления детальной информации о товарах, промокодах, предоплатах
    - Обновления налоговой отчетности
    
    Args:
        order: Объект Order
        request: HTTP request (опционально, для build_absolute_uri)
    
    Returns:
        dict: Результат финализации или None при ошибке
    """
    if not order.payment_invoice_id:
        monobank_logger.warning(f'Order {order.order_number} has no invoice_id, skipping finalization')
        return None
    
    # Проверяем что заказ оплачен
    if order.payment_status not in ['paid', 'prepaid']:
        monobank_logger.warning(f'Order {order.order_number} payment_status={order.payment_status}, skipping finalization')
        return None
    
    try:
        # Формируем items для финализации
        items = []
        
        # Добавляем товары
        for item in order.items.all():
            item_name = item.title
            if item.size:
                item_name += f' ({item.size})'
            
            items.append({
                'name': item_name,
                'qty': item.qty,
                'sum': int(item.line_total * 100),  # в копейках
                'icon': '',
                'unit': 'шт'
            })
        
        # Добавляем позицию со скидкой если есть промокод
        if order.promo_code and order.discount_amount > 0:
            items.append({
                'name': f'Знижка по промокоду {order.promo_code.code}',
                'qty': 1,
                'sum': -int(order.discount_amount * 100),  # отрицательная сумма
                'icon': '',
                'unit': 'шт'
            })
        
        # Добавляем комментарий о prepayment если есть
        if order.pay_type == 'prepay_200':
            prepay_amount = order.get_prepayment_amount()
            remaining = order.total_sum - order.discount_amount - prepay_amount
            items.append({
                'name': f'Передплата 200 грн. Залишок {remaining:.2f} грн при отриманні через Нову Пошту',
                'qty': 1,
                'sum': 0,  # информационная позиция
                'icon': '',
                'unit': 'шт'
            })
        
        # Определяем финальную сумму
        final_amount = order.total_sum - order.discount_amount
        
        # Для prepayment финализируем только 200 грн (или факт. списанную сумму)
        if order.pay_type == 'prepay_200':
            # Используем ту сумму, которая была фактически оплачена
            if order.payment_status == 'prepaid':
                final_amount = order.get_prepayment_amount()
            else:
                final_amount = order.total_sum - order.discount_amount
        
        payload = {
            'invoiceId': order.payment_invoice_id,
            'amount': int(final_amount * 100),
            'items': items
        }
        
        monobank_logger.info(f'Finalizing invoice {order.payment_invoice_id} for order {order.order_number}')
        monobank_logger.info(f'Final amount: {final_amount} UAH, items count: {len(items)}')
        
        try:
            result = _monobank_api_request('POST', '/api/merchant/invoice/finalize', json_payload=payload)
            
            # Сохраняем результат в payment_payload
            if order.payment_payload:
                if 'finalize' not in order.payment_payload:
                    order.payment_payload['finalize'] = []
                order.payment_payload['finalize'].append({
                    'timestamp': timezone.now().isoformat(),
                    'payload': payload,
                    'result': result
                })
                order.save(update_fields=['payment_payload'])
            
            monobank_logger.info(f'✅ Invoice {order.payment_invoice_id} finalized successfully')
            return result
            
        except MonobankAPIError as e:
            monobank_logger.error(f'Monobank finalize error for invoice {order.payment_invoice_id}: {e}')
            return None
            
    except Exception as e:
        monobank_logger.error(f'Error finalizing invoice {order.payment_invoice_id}: {e}', exc_info=True)
        return None


# ==================== MONOBANK RETURN & WEBHOOK ====================

def _ensure_payment_payload(order):
    """Guarantee payment_payload has a history list."""
    if not order.payment_payload or not isinstance(order.payment_payload, dict):
        order.payment_payload = {}
    if 'history' not in order.payment_payload or not isinstance(order.payment_payload.get('history'), list):
        order.payment_payload['history'] = []


def _append_payment_history(order, status, payload, source):
    _ensure_payment_payload(order)
    try:
        order.payment_payload['history'].append({
            'ts': timezone.now().isoformat(),
            'status': status,
            'source': source,
            'payload': payload,
        })
    except Exception:
        # keep it safe even if payload is not JSON-serialisable
        order.payment_payload['history'].append({
            'ts': timezone.now().isoformat(),
            'status': status,
            'source': source,
            'payload': str(payload)[:1000],
        })


def _cleanup_after_success(request):
    """Clear cart/promo and Mono session keys after successful payment."""
    request.session.pop('cart', None)
    request.session.pop('promo_code', None)
    request.session.pop('promo_code_id', None)
    request.session.pop('monobank_invoice_id', None)
    request.session.pop('monobank_pending_order_id', None)
    request.session.modified = True


def _apply_monobank_status(order, status_value, payload=None, source='webhook'):
    """
    Apply Monobank status to Order, update history and payment_status.
    """
    status_lower = (status_value or '').lower()
    _append_payment_history(order, status_lower, payload, source)

    updated_fields = ['payment_payload', 'updated']
    old_payment_status = order.payment_status

    if status_lower in MONOBANK_SUCCESS_STATUSES:
        order.payment_status = 'paid' if order.pay_type != 'prepay_200' else 'prepaid'
        updated_fields.append('payment_status')
    elif status_lower in MONOBANK_PENDING_STATUSES:
        order.payment_status = 'checking'
        updated_fields.append('payment_status')
    elif status_lower in MONOBANK_FAILURE_STATUSES:
        order.payment_status = 'unpaid'
        updated_fields.append('payment_status')
    else:
        # Unknown status, keep history only
        order.save(update_fields=['payment_payload'])
        return status_lower

    order.save(update_fields=list(set(updated_fields)))

    # Уведомление в Telegram при смене статуса оплаты на оплачено/предоплата
    if order.payment_status in ('paid', 'prepaid') and order.payment_status != old_payment_status:
        try:
            notifier = TelegramNotifier()
            notifier.send_order_status_update(
                order,
                old_status=old_payment_status or 'unpaid',
                new_status=order.payment_status
            )
        except Exception:
            # Не блокируем основной поток при ошибке уведомления
            pass

    return status_lower


def _get_order_by_payment_refs(invoice_id=None, order_ref=None, order_id=None):
    """
    Locate an order using invoice_id or order_number/id.
    """
    qs = OrderModel.objects.select_related('user')
    if invoice_id:
        order = qs.filter(payment_invoice_id=invoice_id).order_by('-created').first()
        if order:
            return order
    if order_ref:
        order = qs.filter(order_number=order_ref).order_by('-created').first()
        if order:
            return order
    if order_id:
        try:
            return qs.get(id=order_id)
        except OrderModel.DoesNotExist:
            return None
    return None


def monobank_return(request):
    """
    Handle user return from Monobank payment page: fetch status, update order, redirect to thank you.
    """
    invoice_id = request.GET.get('invoiceId') or request.session.get('monobank_invoice_id')
    order_ref = request.GET.get('orderRef')
    order_id = request.GET.get('orderId') or request.session.get('monobank_pending_order_id')

    order = _get_order_by_payment_refs(invoice_id=invoice_id, order_ref=order_ref, order_id=order_id)
    if not order:
        messages.error(request, 'Замовлення не знайдено. Спробуйте ще раз.')
        return redirect('cart')

    status_value = None
    status_payload = None
    if invoice_id:
        try:
            status_payload = _monobank_api_request('GET', '/api/merchant/invoice/status', params={'invoiceId': invoice_id})
            status_value = status_payload.get('status') or status_payload.get('statusCode')
        except MonobankAPIError as exc:
            monobank_logger.warning('Failed to fetch invoice status for %s: %s', invoice_id, exc)

    applied_status = _apply_monobank_status(order, status_value or 'success', payload=status_payload, source='return')

    if applied_status in MONOBANK_SUCCESS_STATUSES:
        _cleanup_after_success(request)
        messages.success(request, 'Оплату успішно отримано!')
        return redirect('order_success', order_id=order.id)

    if applied_status in MONOBANK_PENDING_STATUSES:
        messages.info(request, 'Платіж обробляється. Ми повідомимо, щойно отримаємо підтвердження.')
        return redirect('order_success', order_id=order.id)

    messages.error(request, 'Оплату не завершено. Ви можете повторити спробу або обрати інший спосіб оплати.')
    return redirect('cart')


@csrf_exempt
def monobank_webhook(request):
    """
    Receive status updates from Monobank webhook.
    """
    if request.method != 'POST':
        return HttpResponse(status=405)

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except Exception:
        return HttpResponse(status=400)

    invoice_id = payload.get('invoiceId') or payload.get('invoice_id')
    result = payload.get('result') or payload
    order_ref = result.get('orderRef') or result.get('order_ref')
    order_id = result.get('orderId') or result.get('order_id')

    order = _get_order_by_payment_refs(invoice_id=invoice_id, order_ref=order_ref, order_id=order_id)
    if not order:
        monobank_logger.warning('Webhook received for unknown invoice/order: %s / %s', invoice_id, order_ref)
        return JsonResponse({'ok': True})

    status_value = result.get('status') or payload.get('status')
    _apply_monobank_status(order, status_value, payload=payload, source='webhook')
    return JsonResponse({'ok': True})
