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
import os
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
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

from ..models import Product, Order, PromoCode
from orders.models import Order as OrderModel, OrderItem
from productcolors.models import ProductColorVariant
from django.contrib import messages

# Импорт helper функций из cart.py
from .cart import _normalize_color_variant_id, _get_color_variant_safe

# Loggers
monobank_logger = logging.getLogger('storefront.monobank')
cart_logger = logging.getLogger('storefront.cart')


# ==================== EXCEPTIONS ====================

class MonobankAPIError(Exception):
    """Raised when Monobank API returns an error"""
    pass

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

def _reset_monobank_session(request, drop_pending=False):
    """
    Сбрасывает связанные с Mono checkout данные в сессии.
    
    Args:
        request: HTTP request
        drop_pending: Если True, отменяет pending заказ в БД
    """
    if drop_pending:
        pending_id = request.session.get('monobank_pending_order_id')
        if pending_id:
            try:
                qs = OrderModel.objects.select_related('user').filter(
                    id=pending_id,
                    payment_provider__in=('monobank', 'monobank_checkout', 'monobank_pay')
                )
                if qs.exists():
                    qs.update(status='cancelled', payment_status='unpaid')
            except Exception:
                monobank_logger.debug(
                    'Failed to cancel pending Monobank order %s',
                    pending_id,
                    exc_info=True
                )

    for key in (
        'monobank_pending_order_id',
        'monobank_invoice_id',
        'monobank_order_id',
        'monobank_order_ref'
    ):
        if key in request.session:
            request.session.pop(key, None)

    request.session.modified = True


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
    Validate checkout payload and return (errors, cleaned_data).
    
    Args:
        raw_payload: dict с данными запроса
        
    Returns:
        tuple: (list of error strings, dict of cleaned data)
    """
    full_name = (raw_payload.get('full_name') or '').strip()
    phone = (raw_payload.get('phone') or '').strip()
    city = (raw_payload.get('city') or '').strip()
    np_office = (raw_payload.get('np_office') or '').strip()
    pay_type = (raw_payload.get('pay_type') or 'full').strip().lower() or 'full'

    errors = []
    if len(full_name) < 3:
        errors.append('ПІБ повинно містити мінімум 3 символи.')

    digits = ''.join(filter(str.isdigit, phone))
    if not phone.startswith('+380') or len(digits) != 12:
        errors.append('Невірний формат телефону. Використовуйте формат +380XXXXXXXXX.')

    if len(city) < 2:
        errors.append('Введіть назву міста.')

    if len(np_office) < 1:
        errors.append('Введіть адресу відділення або поштомата.')

    if pay_type not in ('full', 'partial'):
        errors.append('Невідомий тип оплати.')

    if pay_type != 'full':
        errors.append('Для онлайн-оплати карткою потрібно обрати «Повна передоплата».')

    cleaned = {
        'full_name': full_name,
        'phone': phone,
        'city': city,
        'np_office': np_office,
        'pay_type': 'full'
    }
    return errors, cleaned


# ==================== MONOBANK API REQUESTS ====================

def _monobank_api_request(method, endpoint, *, params=None, json_payload=None, timeout=10):
    """
    Make a request to Monobank API.
    
    Args:
        method: HTTP method (GET or POST)
        endpoint: API endpoint path
        params: Query parameters
        json_payload: JSON payload for POST requests
        timeout: Request timeout in seconds
        
    Returns:
        dict: Response data
        
    Raises:
        MonobankAPIError: If request fails or returns error
    """
    base_url = settings.MONOBANK_API_BASE.rstrip('/')
    url = f"{base_url}{endpoint}"
    headers = {'X-Token': settings.MONOBANK_TOKEN}

    monobank_logger.info('Monobank API request: %s %s, payload: %s', method, endpoint, json_payload)

    try:
        if method.upper() == 'POST':
            response = requests.post(url, params=params, json=json_payload, headers=headers, timeout=timeout)
        elif method.upper() == 'GET':
            response = requests.get(url, params=params, headers=headers, timeout=timeout)
        else:
            raise MonobankAPIError('Unsupported HTTP method')
    except requests.RequestException as exc:
        monobank_logger.error('Monobank API request failed: %s', exc)
        raise MonobankAPIError(f'Помилка з\'єднання з платіжним сервісом: {exc}') from exc

    try:
        data = response.json()
    except ValueError:
        data = {}

    monobank_logger.info('Monobank API response: status=%s, data=%s', response.status_code, data)

    if response.status_code >= 400 or 'errCode' in data:
        err_text = data.get('errText') or data.get('message') or f'HTTP {response.status_code}'
        monobank_logger.error('Monobank API error: %s', err_text)
        raise MonobankAPIError(err_text)

    return data


def _prepare_checkout_customer_data(request):
    """
    Prepare customer data for checkout from request.
    
    Args:
        request: HTTP request
        
    Returns:
        dict: Customer data with keys: full_name, phone, city, np_office, pay_type, user
    """
    if request.user.is_authenticated:
        try:
            profile = request.user.userprofile
            return {
                'full_name': profile.full_name or f'{request.user.first_name} {request.user.last_name}'.strip() or 'Користувач',
                'phone': profile.phone or '',
                'city': profile.city or '',
                'np_office': profile.np_office or '',
                'pay_type': profile.pay_type or 'full',
                'user': request.user
            }
        except Exception:
            pass
    
    # Default data for guests
    return {
        'full_name': 'Користувач',
        'phone': '',
        'city': '',
        'np_office': '',
        'pay_type': 'full',
        'user': None
    }


def _record_monobank_status(order, payload, source='api'):
    """
    Record Monobank status update in order.
    
    Args:
        order: Order instance
        payload: Status payload from Monobank
        source: Source of update ('api', 'webhook', 'return')
    """
    if not payload:
        return

    status = payload.get('status')
    payment_payload = order.payment_payload or {}
    history = payment_payload.get('history', [])
    history.append({
        'status': status,
        'data': payload,
        'source': source,
        'received_at': timezone.now().isoformat()
    })
    payment_payload['history'] = history[-20:]
    payment_payload['last_status'] = status
    payment_payload['last_update_source'] = source
    payment_payload['last_update_at'] = timezone.now().isoformat()
    order.payment_payload = payment_payload

    update_fields = ['payment_payload']

    if status in MONOBANK_SUCCESS_STATUSES:
        previous_status = order.payment_status
        order.payment_status = 'paid'
        update_fields.append('payment_status')
        try:
            order.save(update_fields=update_fields)
        except Exception:
            order.save()
        if previous_status != 'paid':
            try:
                from orders.telegram_notifications import TelegramNotifier
                notifier = TelegramNotifier()
                notifier.send_new_order_notification(order)
            except Exception:
                monobank_logger.exception('Failed to send Telegram notification for paid order %s', order.id)
        return

    if status in MONOBANK_PENDING_STATUSES:
        order.payment_status = 'checking'
        update_fields.append('payment_status')
    elif status in MONOBANK_FAILURE_STATUSES:
        order.payment_status = 'unpaid'
        update_fields.append('payment_status')

    try:
        order.save(update_fields=update_fields)
    except Exception:
        order.save()


def _create_or_update_monobank_order(request, customer_data):
    """
    Create or update an order for Monobank payment.
    
    Args:
        request: HTTP request
        customer_data: Dict with customer information
        
    Returns:
        tuple: (order, amount_decimal, basket_order)
        
    Raises:
        ValueError: If cart is empty
    """
    cart = request.session.get('cart') or {}
    if not cart:
        raise ValueError('cart_empty')

    product_ids = [item['product_id'] for item in cart.values()]
    products = Product.objects.in_bulk(product_ids)

    session_key = request.session.session_key
    if not session_key:
        request.session.create()
        session_key = request.session.session_key
        
    order = None

    # В случае, если в сессии всё же остался pending id — сбрасываем.
    pending_order_id = request.session.get('monobank_pending_order_id')
    if pending_order_id:
        monobank_logger.info('Discarding leftover pending Monobank order %s', pending_order_id)
        _drop_pending_monobank_order(request)

    with transaction.atomic():
        if order is None:
            order = OrderModel.objects.create(
                user=request.user if request.user.is_authenticated else None,
                session_key=session_key,
                full_name=customer_data['full_name'],
                phone=customer_data['phone'],
                city=customer_data['city'],
                np_office=customer_data['np_office'],
                pay_type='full',
                status='new',
                payment_status='checking',
                total_sum=Decimal('0'),
                discount_amount=Decimal('0')
            )
        else:
            OrderItem.objects.filter(order=order).delete()
            order.full_name = customer_data['full_name']
            order.phone = customer_data['phone']
            order.city = customer_data['city']
            order.np_office = customer_data['np_office']
            order.pay_type = 'full'
            order.session_key = session_key
            order.payment_status = 'checking'
            order.discount_amount = Decimal('0')
            order.total_sum = Decimal('0')
            order.save(update_fields=['full_name', 'phone', 'city', 'np_office', 'pay_type', 'session_key', 'payment_status', 'discount_amount', 'total_sum'])

        order_items = []
        total_sum = Decimal('0')

        for key, item in cart.items():
            product = products.get(item['product_id'])
            if not product:
                continue
            try:
                qty = int(item.get('qty', 1) or 1)
            except (TypeError, ValueError):
                qty = 1
            qty = max(qty, 1)
            try:
                unit_price = Decimal(str(product.final_price))
            except (Exception, TypeError, ValueError):
                monobank_logger.warning('Skipping cart item %s: invalid price %s', key, product.final_price)
                continue
            line_total = unit_price * qty
            total_sum += line_total
            color_variant = _get_color_variant_safe(item.get('color_variant_id'))

            order_items.append(OrderItem(
                order=order,
                product=product,
                color_variant=color_variant,
                title=product.title,
                size=item.get('size', ''),
                qty=qty,
                unit_price=unit_price,
                line_total=line_total
            ))

        if not order_items:
            raise ValueError('cart_empty')

        OrderItem.objects.bulk_create(order_items)

        basket_order = []
        saved_items = (
            order.items
            .select_related('product', 'color_variant__color')
            .prefetch_related('color_variant__images')
        )

        for saved in saved_items:
            display_name = saved.title
            if saved.size:
                display_name = f"{display_name} • розмір {saved.size}"
            if saved.color_name:
                display_name = f"{display_name} • {saved.color_name}"
            display_name = display_name[:128]

            image_url = None
            try:
                img = saved.product_image
                if img and hasattr(img, 'url'):
                    image_url = request.build_absolute_uri(img.url)
                    if image_url.startswith('http://'):
                        image_url = 'https://' + image_url[len('http://'):]
            except Exception:
                image_url = None

            line_total = Decimal(str(saved.line_total))
            basket_item = {
                'name': display_name,
                'qty': saved.qty,
                'sum': int((line_total * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP)),
                'unit': 'шт.',
                'code': str(getattr(saved.product, 'sku', saved.product.id))
            }
            if image_url:
                basket_item['iconUrl'] = image_url
                basket_item['imageUrl'] = image_url
            basket_order.append(basket_item)

        discount = Decimal('0')
        promo = None
        promo_code_value = request.session.get('applied_promo_code')
        if promo_code_value:
            try:
                potential_promo = PromoCode.objects.get(code=promo_code_value, is_active=True)
                if potential_promo.can_be_used():
                    possible_discount = potential_promo.calculate_discount(total_sum)
                    if possible_discount > 0:
                        discount = possible_discount
                        promo = potential_promo
                        promo.use()
            except PromoCode.DoesNotExist:
                pass

        order.discount_amount = discount
        order.promo_code = promo if discount > 0 else None
        order.payment_provider = 'monobank'
        order.total_sum = total_sum - discount
        order.save(update_fields=['discount_amount', 'promo_code', 'payment_provider', 'total_sum'])

    request.session['monobank_pending_order_id'] = order.id
    return order, order.total_sum, basket_order


def _build_monobank_checkout_payload(order, amount_decimal, total_qty, request, items=None):
    """
    Build payload for Monobank Checkout API.
    
    Args:
        order: Order instance
        amount_decimal: Total amount as Decimal
        total_qty: Total quantity of items
        request: HTTP request
        items: Optional list of order items
        
    Returns:
        dict: Payload for Monobank Checkout API
        
    Raises:
        MonobankAPIError: If cart is empty or validation fails
    """
    if items is None:
        items = list(order.items.select_related('product', 'color_variant__color'))
    
    def _as_number(dec: Decimal):
        """Convert Decimal to int if possible, otherwise to float."""
        if dec == dec.to_integral():
            return int(dec)
        return float(dec)

    products = []
    total_amount_major = Decimal('0')
    total_count = 0

    for item in items:
        qty_value = getattr(item, 'qty', None)
        if qty_value is None:
            qty_value = getattr(item, 'quantity', None)

        monobank_logger.info('Building product data for item: %s, qty=%s, unit_price=%s',
                             item.product.title, qty_value, getattr(item, 'unit_price', None))

        try:
            qty = int(qty_value) if qty_value is not None else 0
        except (TypeError, ValueError):
            qty = 0

        if qty <= 0:
            monobank_logger.error('Item has non-positive qty: %s', qty)
            qty = 1

        try:
            line_total_major = Decimal(str(item.line_total)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        except Exception as exc:
            monobank_logger.exception('Failed to convert line total for item %s: %s', 
                                    item.id if hasattr(item, 'id') else item.product_id, exc)
            continue

        if line_total_major <= 0:
            monobank_logger.error('Item has non-positive line total: %s', line_total_major)
            continue

        total_amount_major += line_total_major
        total_count += qty

        name_parts = [item.title or item.product.title]
        if item.size:
            name_parts.append(f"розмір {item.size}")
        if item.color_name:
            name_parts.append(item.color_name)

        product_data = {
            'name': ' • '.join(filter(None, name_parts)),
            'cnt': qty,
            'price': _as_number(line_total_major),
        }

        code_product = getattr(item.product, 'sku', None) or getattr(item.product, 'id', None)
        if code_product is not None:
            product_data['code_product'] = str(code_product)
        if item.product.main_image:
            product_data['icon'] = request.build_absolute_uri(item.product.main_image.url)
        if item.color_name:
            product_data['description'] = item.color_name

        products.append(product_data)

    if not products:
        monobank_logger.error('No products collected for monobank checkout payload')
        raise MonobankAPIError('Кошик порожній. Додайте товари перед оплатою.')

    if total_count <= 0:
        total_count = sum(max(int(getattr(item, 'qty', 1) or 1), 1) for item in items)

    amount_major = Decimal(str(amount_decimal)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    if total_amount_major and amount_major != total_amount_major:
        amount_major = total_amount_major

    payload = {
        'order_ref': order.order_number,
        'amount': _as_number(amount_major),
        'ccy': 980,  # гривна
        'count': int(total_count),
        'products': products,
        'destination': getattr(settings, 'MONOBANK_CHECKOUT_DESTINATION_TEMPLATE', 'Оплата замовлення {order_number}').format(order_number=order.order_number)
    }

    delivery_methods = getattr(settings, 'MONOBANK_CHECKOUT_DELIVERY_METHODS', None)
    if delivery_methods and 'MONOBANK_CHECKOUT_DELIVERY_METHODS' in os.environ:
        payload['dlv_method_list'] = delivery_methods

    payment_methods = getattr(settings, 'MONOBANK_CHECKOUT_PAYMENT_METHODS', None)
    if payment_methods and 'MONOBANK_CHECKOUT_PAYMENT_METHODS' in os.environ:
        payload['payment_method_list'] = payment_methods

    if getattr(settings, 'MONOBANK_CHECKOUT_DLV_PAY_MERCHANT', False) and 'MONOBANK_CHECKOUT_DLV_PAY_MERCHANT' in os.environ:
        payload['dlv_pay_merchant'] = True

    payments_number = getattr(settings, 'MONOBANK_CHECKOUT_PAYMENTS_NUMBER', None)
    if payments_number:
        payload['payments_number'] = payments_number

    callback_url = getattr(settings, 'MONOBANK_CHECKOUT_CALLBACK_URL', '')
    return_url = getattr(settings, 'MONOBANK_CHECKOUT_RETURN_URL', '')
    default_callback = request.build_absolute_uri('/payments/monobank/webhook/').replace('http://', 'https://', 1)
    default_return = request.build_absolute_uri('/payments/monobank/return/').replace('http://', 'https://', 1)
    payload['callback_url'] = callback_url or default_callback
    payload['return_url'] = return_url or default_return
    
    monobank_logger.info('Built Monobank Checkout payload: %s', payload)
    
    return payload


def _create_single_product_order(product, size, qty, color_variant_id, customer):
    """
    Create a temporary order for a single product for Monobank Checkout.
    
    Args:
        product: Product instance
        size: Product size
        qty: Quantity
        color_variant_id: Color variant ID
        customer: Customer data dict
        
    Returns:
        tuple: (order, line_total)
    """
    customer_data = {
        'user': customer.get('user'),
        'full_name': (customer.get('full_name') or 'Користувач').strip() or 'Користувач',
        'phone': customer.get('phone', '') or '',
        'city': customer.get('city', '') or '',
        'np_office': customer.get('np_office', '') or '',
        'pay_type': customer.get('pay_type', 'full') or 'full'
    }

    try:
        qty_int = max(int(qty or 1), 1)
    except (TypeError, ValueError):
        qty_int = 1
    unit_price_raw = product.final_price if product.final_price is not None else getattr(product, 'price', None)
    try:
        unit_price = Decimal(str(unit_price_raw or '0'))
    except (InvalidOperation, TypeError, ValueError):
        monobank_logger.warning('Single checkout: invalid price for product %s (%s)', product.id, unit_price_raw)
        unit_price = Decimal('0')
    line_total = (unit_price * qty_int).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    color_variant = _get_color_variant_safe(color_variant_id)

    order = OrderModel.objects.create(
        user=customer_data['user'],
        full_name=customer_data['full_name'],
        phone=customer_data['phone'],
        city=customer_data['city'],
        np_office=customer_data['np_office'],
        pay_type=customer_data['pay_type'],
        payment_status='checking',
        status='new',
        total_sum=line_total,
        discount_amount=Decimal('0'),
        payment_provider='monobank_checkout'
    )

    OrderItem.objects.create(
        order=order,
        product=product,
        color_variant=color_variant,
        title=product.title,
        size=size or '',
        qty=qty_int,
        unit_price=unit_price,
        line_total=line_total
    )

    return order, line_total


def _fetch_and_apply_invoice_status(order, invoice_id, source):
    """
    Fetch and apply invoice status from Monobank API.
    
    Args:
        order: Order instance
        invoice_id: Invoice ID
        source: Source of update ('api', 'webhook', 'return')
        
    Returns:
        dict: Status data from Monobank
        
    Raises:
        MonobankAPIError: If API request fails
    """
    try:
        status_data = _monobank_api_request('GET', '/api/merchant/invoice/status', params={'invoiceId': invoice_id})
    except MonobankAPIError as exc:
        monobank_logger.warning('Failed to fetch invoice status for %s: %s', invoice_id, exc)
        raise

    _record_monobank_status(order, status_data, source=source)
    return status_data


def _fetch_and_apply_checkout_status(order, source='api'):
    """
    Fetch and apply checkout status (stub - needs implementation).
    
    Args:
        order: Order instance
        source: Source of update ('api', 'webhook', 'return')
        
    Returns:
        dict: Status data
    """
    # TODO: Implement actual checkout status fetching
    return {'payment_status': 'unknown'}


def _update_order_from_checkout_result(order, result, source='api'):
    """
    Update order from checkout result (stub - needs implementation).
    
    Args:
        order: Order instance
        result: Result data from checkout
        source: Source of update ('api', 'webhook', 'return')
    """
    # TODO: Implement actual order update logic
    pass


def _cleanup_after_success(request):
    """
    Clean up session after successful payment.
    
    Args:
        request: HTTP request
    """
    request.session.pop('cart', None)
    request.session.pop('applied_promo_code', None)
    request.session.pop('monobank_invoice_id', None)
    request.session.pop('monobank_pending_order_id', None)
    request.session.pop('monobank_order_id', None)
    request.session.pop('monobank_order_ref', None)
    request.session.modified = True


# ==================== MAIN VIEWS ====================

@require_POST
def monobank_create_invoice(request):
    """
    Create Monobank pay invoice and return redirect URL.
    
    Args:
        request: HTTP request
        
    Returns:
        JsonResponse: Success with invoice_url or error
    """
    _cleanup_expired_monobank_orders()
    _drop_pending_monobank_order(request)
    try:
        # Try to take guest checkout fields from JSON body when user is not authenticated
        body = {}
        try:
            body = json.loads(request.body.decode('utf-8')) if request.body else {}
        except Exception:
            body = {}

        if not request.user.is_authenticated and any(k in (body or {}) for k in ('full_name','phone','city','np_office','pay_type')):
            errors, cleaned = _validate_checkout_payload(body or {})
            if errors:
                return JsonResponse({'success': False, 'error': '\n'.join(errors)})
            customer = {
                'full_name': cleaned['full_name'],
                'phone': cleaned['phone'],
                'city': cleaned['city'],
                'np_office': cleaned['np_office'],
                'pay_type': cleaned['pay_type'],
                'user': None
            }
        else:
            customer = _prepare_checkout_customer_data(request)
        order, amount_decimal, _ = _create_or_update_monobank_order(request, customer)
    except ValueError:
        _reset_monobank_session(request, drop_pending=True)
        return JsonResponse({'success': False, 'error': 'Кошик порожній. Додайте товари перед оплатою.'})

    items_qs = list(order.items.select_related('product', 'color_variant__color'))
    total_qty = sum(item.qty for item in items_qs)
    if total_qty <= 0 or amount_decimal <= 0:
        _reset_monobank_session(request, drop_pending=True)
        return JsonResponse({'success': False, 'error': 'Сума для оплати повинна бути більшою за 0.'})

    try:
        basket_entries = []
        for item in items_qs:
            name_parts = [item.product.title]
            if item.size:
                name_parts.append(f"розмір {item.size}")
            color_name = getattr(item, 'color_name', None)
            if color_name:
                name_parts.append(color_name)
            display_name = ' • '.join(filter(None, name_parts))[:128]
            try:
                line_total_minor = int(Decimal(str(item.line_total)) * 100)
            except (InvalidOperation, TypeError, ValueError):
                monobank_logger.warning('Skipping item %s in Mono Pay basket: invalid line total %s', item.id, item.line_total)
                continue

            icon_url = ''
            try:
                image_obj = None
                if getattr(item, 'color_variant', None) and item.color_variant.images.exists():
                    image_obj = item.color_variant.images.first().image
                elif item.product.main_image:
                    image_obj = item.product.main_image
                if image_obj and hasattr(image_obj, 'url'):
                    icon_url = request.build_absolute_uri(image_obj.url)
                    if icon_url.startswith('http://'):
                        icon_url = 'https://' + icon_url[len('http://'):]
            except Exception:
                icon_url = ''

            try:
                qty_minor = max(int(getattr(item, 'qty', 1) or 1), 1)
            except (TypeError, ValueError):
                qty_minor = 1

            basket_entries.append({
                'name': display_name or item.product.title[:128],
                'qty': qty_minor,
                'sum': line_total_minor,
                'icon': icon_url
            })

        if not basket_entries:
            _reset_monobank_session(request, drop_pending=True)
            return JsonResponse({'success': False, 'error': 'Кошик порожній. Додайте товари перед оплатою.'})

        # Для Monobank Pay используем API эквайринга
        payload = {
            'amount': int(amount_decimal * 100),  # сумма в копейках
            'ccy': 980,  # гривна
            'merchantPaymInfo': {
                'reference': order.order_number,
                'destination': f'Оплата замовлення {order.order_number}',
                'basketOrder': basket_entries
            },
            'redirectUrl': request.build_absolute_uri('/payments/monobank/return/'),
            'webHookUrl': request.build_absolute_uri('/payments/monobank/webhook/'),
        }
        
        creation_data = _monobank_api_request('POST', '/api/merchant/invoice/create', json_payload=payload)
    except MonobankAPIError as exc:
        monobank_logger.warning('Monobank pay invoice creation failed: %s', exc)
        _reset_monobank_session(request, drop_pending=True)
        return JsonResponse({'success': False, 'error': str(exc)})
    except Exception as exc:
        monobank_logger.exception('Failed to build Mono Pay payload: %s', exc)
        _reset_monobank_session(request, drop_pending=True)
        return JsonResponse({'success': False, 'error': 'Не вдалося підготувати дані для платежу. Спробуйте ще раз.'})

    result = creation_data.get('result') or creation_data
    invoice_id = result.get('invoiceId')
    invoice_url = result.get('pageUrl')

    if not invoice_id or not invoice_url:
        _reset_monobank_session(request, drop_pending=True)
        return JsonResponse({'success': False, 'error': 'Не вдалося створити платіж. Спробуйте пізніше.'})

    payment_payload = {
        'request': payload,
        'create': creation_data,
        'history': []
    }
    order.payment_invoice_id = invoice_id
    order.payment_payload = payment_payload
    order.payment_status = 'checking'
    order.payment_provider = 'monobank_pay'
    order.save(update_fields=['payment_invoice_id', 'payment_payload', 'payment_status', 'payment_provider'])

    request.session['monobank_invoice_id'] = invoice_id
    request.session['monobank_pending_order_id'] = order.id
    request.session.modified = True

    try:
        _notify_monobank_order(order, 'Mono Pay')
    except Exception:
        pass

    return JsonResponse({
        'success': True,
        'invoice_url': invoice_url,
        'invoice_id': invoice_id,
        'order_id': order.id,
        'order_ref': order.order_number
    })


@require_POST
def monobank_create_checkout(request):
    """
    Create Monobank checkout order and return redirect URL.
    
    Args:
        request: HTTP request
        
    Returns:
        JsonResponse: Success with redirect_url or error
    """
    _cleanup_expired_monobank_orders()
    _drop_pending_monobank_order(request)
    try:
        # Проверяем, создаем ли заказ на один товар
        body = json.loads(request.body.decode('utf-8')) if request.body else {}
        single_product = body.get('single_product', False)
        
        monobank_logger.info('Monobank checkout request: single_product=%s, body=%s', single_product, body)
        
        if single_product:
            # Создаем заказ на один товар
            product_id = body.get('product_id')
            size = body.get('size', 'S')
            try:
                qty = int(body.get('qty', 1))
            except (TypeError, ValueError):
                qty = 1
            qty = max(qty, 1)
            color_variant_id = body.get('color_variant_id')
            
            monobank_logger.info('Single product checkout: product_id=%s, size=%s, qty=%s, color_variant_id=%s', 
                               product_id, size, qty, color_variant_id)
            
            if not product_id:
                return JsonResponse({'success': False, 'error': 'Не вказано ID товару.'})
            
            try:
                product = Product.objects.get(id=product_id)
                monobank_logger.info('Found product: %s, price: %s', product.title, product.final_price)
            except Product.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Товар не знайдено.'})
            
            # Создаем временный заказ на один товар
            if not request.user.is_authenticated and any(k in (body or {}) for k in ('full_name','phone','city','np_office','pay_type')):
                errors, cleaned = _validate_checkout_payload(body or {})
                if errors:
                    return JsonResponse({'success': False, 'error': '\n'.join(errors)})
                customer = {
                    'full_name': cleaned['full_name'],
                    'phone': cleaned['phone'],
                    'city': cleaned['city'],
                    'np_office': cleaned['np_office'],
                    'pay_type': cleaned['pay_type'],
                    'user': None
                }
            else:
                customer = _prepare_checkout_customer_data(request)
            monobank_logger.info('Customer data: %s', customer)
            order, amount_decimal = _create_single_product_order(product, size, qty, color_variant_id, customer)
            monobank_logger.info('Created single product order: %s, amount: %s', order.order_number, amount_decimal)
        else:
            # Обычная логика для корзины
            if not request.user.is_authenticated and any(k in (body or {}) for k in ('full_name','phone','city','np_office','pay_type')):
                errors, cleaned = _validate_checkout_payload(body or {})
                if errors:
                    return JsonResponse({'success': False, 'error': '\n'.join(errors)})
                customer = {
                    'full_name': cleaned['full_name'],
                    'phone': cleaned['phone'],
                    'city': cleaned['city'],
                    'np_office': cleaned['np_office'],
                    'pay_type': cleaned['pay_type'],
                    'user': None
                }
            else:
                customer = _prepare_checkout_customer_data(request)
            order, amount_decimal, _ = _create_or_update_monobank_order(request, customer)
    except ValueError as e:
        _reset_monobank_session(request, drop_pending=True)
        return JsonResponse({'success': False, 'error': str(e)})
    except Exception as e:
        monobank_logger.exception('Error in monobank_create_checkout: %s', e)
        _reset_monobank_session(request, drop_pending=True)
        return JsonResponse({'success': False, 'error': 'Помилка при створенні замовлення.'})

    items_qs = list(order.items.select_related('product', 'color_variant__color'))
    total_qty = sum(item.qty for item in items_qs)
    if total_qty <= 0 or amount_decimal <= 0:
        _reset_monobank_session(request, drop_pending=True)
        return JsonResponse({'success': False, 'error': 'Сума для оплати повинна бути більшою за 0.'})

    try:
        payload = _build_monobank_checkout_payload(order, amount_decimal, total_qty, request, items=items_qs)
    except MonobankAPIError as exc:
        _reset_monobank_session(request, drop_pending=True)
        return JsonResponse({'success': False, 'error': str(exc)})
    except Exception as exc:
        monobank_logger.exception('Failed to build Mono Checkout payload: %s', exc)
        _reset_monobank_session(request, drop_pending=True)
        return JsonResponse({'success': False, 'error': 'Не вдалося підготувати дані для платежу. Спробуйте ще раз.'})

    try:
        creation_data = _monobank_api_request('POST', '/personal/checkout/order', json_payload=payload)
    except MonobankAPIError as exc:
        monobank_logger.warning('Monobank checkout order creation failed: %s', exc)
        _reset_monobank_session(request, drop_pending=True)
        return JsonResponse({'success': False, 'error': str(exc)})

    result = creation_data.get('result') or creation_data
    order_id = result.get('order_id') or result.get('orderId')
    redirect_url = result.get('redirect_url') or result.get('redirectUrl')
    if not order_id or not redirect_url:
        _reset_monobank_session(request, drop_pending=True)
        return JsonResponse({'success': False, 'error': 'Не вдалося створити замовлення. Спробуйте пізніше.'})

    payment_payload = {
        'request': payload,
        'create': creation_data,
        'history': []
    }
    order.payment_invoice_id = order_id
    order.payment_payload = payment_payload
    order.payment_status = 'checking'
    order.payment_provider = 'monobank_checkout'
    order.save(update_fields=['payment_invoice_id', 'payment_payload', 'payment_status', 'payment_provider'])

    request.session['monobank_order_id'] = order_id
    request.session['monobank_order_ref'] = order.order_number
    request.session['monobank_invoice_id'] = order_id
    request.session['monobank_pending_order_id'] = order.id
    request.session.modified = True

    try:
        _notify_monobank_order(order, 'Mono Checkout')
    except Exception:
        pass

    return JsonResponse({
        'success': True,
        'redirect_url': redirect_url,
        'order_id': order.id,
        'order_ref': order.order_number
    })


def monobank_return(request):
    """
    Handle user return from Monobank payment page.
    
    Args:
        request: HTTP request
        
    Returns:
        HttpResponse: Redirect to appropriate page with messages
    """
    order_id = request.GET.get('orderId') or request.session.get('monobank_order_id')
    invoice_id = request.GET.get('invoiceId') or request.session.get('monobank_invoice_id')
    order_ref = request.GET.get('orderRef') or request.session.get('monobank_order_ref')

    order = None
    if order_id:
        order = OrderModel.objects.select_related('user').filter(payment_invoice_id=order_id).order_by('-created').first()

    if order is None and invoice_id:
        pending_id = request.session.get('monobank_pending_order_id')
        if pending_id:
            try:
                order = OrderModel.objects.get(id=pending_id)
            except OrderModel.DoesNotExist:
                order = None

    if order is None and invoice_id:
        order = OrderModel.objects.select_related('user').filter(payment_invoice_id=invoice_id).order_by('-created').first()

    if order is None and order_ref:
        order = OrderModel.objects.select_related('user').filter(order_number=order_ref).order_by('-created').first()

    if order is None:
        messages.error(request, 'Замовлення не знайдено. Спробуйте ще раз.')
        return redirect('cart')

    try:
        if order.payment_provider == 'monobank_checkout' or order_id:
            result = _fetch_and_apply_checkout_status(order, source='return')
            status = (result.get('payment_status') or '').lower()
        else:
            status_data = _fetch_and_apply_invoice_status(order, invoice_id, source='return')
            status = status_data.get('status')
    except MonobankAPIError as exc:
        messages.error(request, f'Не вдалося підтвердити статус платежу: {exc}')
        return redirect('my_orders' if request.user.is_authenticated else 'cart')


    if status in MONOBANK_SUCCESS_STATUSES:
        _cleanup_after_success(request)
        messages.success(request, 'Оплату успішно отримано!')
        if request.user.is_authenticated:
            return redirect('my_orders')
        return redirect('order_success', order_id=order.id)

    if status in MONOBANK_PENDING_STATUSES:
        messages.info(request, 'Платіж обробляється. Ми повідомимо, щойно отримаємо підтвердження.')
        if request.user.is_authenticated:
            return redirect('my_orders')
        return redirect('order_success', order_id=order.id)

    messages.error(request, 'Оплату не завершено. Ви можете повторити спробу або обрати інший спосіб оплати.')
    return redirect('cart')


@csrf_exempt
def monobank_webhook(request):
    """
    Receive status updates from Monobank webhook.
    
    Args:
        request: HTTP request
        
    Returns:
        JsonResponse or HttpResponse: Success/error response
    """
    if request.method != 'POST':
        return HttpResponse(status=405)

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return HttpResponse(status=400)

    # Legacy invoice webhook
    invoice_id = payload.get('invoiceId')
    if invoice_id:
        try:
            order = OrderModel.objects.get(payment_invoice_id=invoice_id)
        except OrderModel.DoesNotExist:
            monobank_logger.warning('Webhook received for unknown invoice %s', invoice_id)
            return JsonResponse({'ok': True})

        _record_monobank_status(order, payload, source='webhook')
        return JsonResponse({'ok': True})

    # Checkout order webhook requires signature validation
    if not _verify_monobank_signature(request):
        monobank_logger.warning('Invalid or missing X-Sign for checkout webhook')
        return HttpResponse(status=400)

    result = payload.get('result') or {}
    order_id = result.get('orderId') or result.get('order_id')
    order_ref = result.get('orderRef') or result.get('order_ref')

    order = None
    if order_id:
        order = OrderModel.objects.select_related('user').filter(payment_invoice_id=order_id).first()
    if order is None and order_ref:
        order = OrderModel.objects.select_related('user').filter(order_number=order_ref).first()

    if order is None:
        monobank_logger.warning('Checkout webhook received for unknown order: %s / %s', order_id, order_ref)
        return JsonResponse({'ok': True})

    try:
        _update_order_from_checkout_result(order, result, source='webhook')
    except Exception as exc:
        monobank_logger.exception('Failed to process checkout webhook for order %s: %s', order.order_number, exc)
        return HttpResponse(status=500)

    return JsonResponse({'ok': True})
