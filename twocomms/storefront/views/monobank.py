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

from ..models import Product, PromoCode
from orders.models import Order as OrderModel, OrderItem
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
                first_item = order_items[0] if order_items else None
                product_label = ''
                if first_item:
                    product_label = (first_item.title or '').strip()
                    if first_item.size:
                        size_clean = str(first_item.size).strip()
                        if size_clean:
                            product_label = f'{product_label} ({size_clean})' if product_label else size_clean
                if not product_label:
                    product_label = f'замовлення {order.order_number}'

                prepay_label = f'Передплата за товар "{product_label}"'
                
                # КРИТИЧЕСКАЯ ТОЧКА: Вызов get_prepayment_amount()
                monobank_logger.info(f'🔍 Calling order.get_prepayment_amount()...')
                monobank_logger.info(f'🔍 order.pay_type before call: {order.pay_type}')
                payment_amount = order.get_prepayment_amount()
                monobank_logger.info(f'🔍 order.get_prepayment_amount() returned: {payment_amount}')
                monobank_logger.info(f'🔍 Type: {type(payment_amount)}, Value: {payment_amount}')
                
                payment_description = f'{prepay_label} - замовлення {order.order_number}'
                monobank_logger.info(f'✅ Prepayment amount set to: {payment_amount} UAH')
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
            
            # Для предоплаты собираем список ВСЕХ товаров
            if pay_type == 'prepay_200':
                product_names = []
                first_icon_url = ''
                
                for item in order_items[:10]:  # Максимум 10 товаров
                    try:
                        # Запоминаем иконку первого товара
                        if not first_icon_url and item.product.main_image:
                            first_icon_url = request.build_absolute_uri(item.product.main_image.url)
                        
                        # Добавляем название товара в список
                        product_name = f'{item.title}'
                        if item.size:
                            product_name += f' ({item.size})'
                        if item.qty > 1:
                            product_name += f' x{item.qty}'
                        
                        product_names.append(product_name)
                    except Exception as e:
                        monobank_logger.warning(f'Error processing item for prepay: {e}')
                
                # Формируем общее описание со всеми товарами
                if len(product_names) == 1:
                    # Один товар
                    full_description = f'Передплата за товар {product_names[0]}'
                else:
                    # Несколько товаров
                    products_list = ', '.join(product_names)
                    full_description = f'Передплата за замовлення ({products_list})'
                
                basket_sum_kopecks = int(payment_amount * 100)
                monobank_logger.info(f'🔍 PREPAY mode: Creating basket entry with ALL products')
                monobank_logger.info(f'🔍 - name: {full_description}')
                monobank_logger.info(f'🔍 - products count: {len(product_names)}')
                monobank_logger.info(f'🔍 - qty: 1')
                monobank_logger.info(f'🔍 - sum: {basket_sum_kopecks} kopecks ({payment_amount} UAH)')
                
                basket_entries.append({
                    'name': full_description,
                    'qty': 1,
                    'sum': basket_sum_kopecks,  # в копейках (всегда 20000 = 200 грн)
                    'icon': first_icon_url,
                    'unit': 'шт'
                })
            else:
                # Для полной оплаты показываем все товары отдельными позициями
            for item in order_items[:10]:  # Максимум 10 товаров
                try:
                    # Получаем URL изображения
                    icon_url = ''
                    if item.product.main_image:
                        icon_url = request.build_absolute_uri(item.product.main_image.url)
                    
                        basket_sum_kopecks = int(item.line_total * 100)
                        monobank_logger.info(f'🔍 FULL mode: Adding item {item.title}')
                        monobank_logger.info(f'🔍 - qty: {item.qty}')
                        monobank_logger.info(f'🔍 - sum: {basket_sum_kopecks} kopecks ({item.line_total} UAH)')
                        
                        basket_entries.append({
                            'name': f'{item.title} {item.size}'.strip(),
                            'qty': item.qty,
                            'sum': basket_sum_kopecks,  # в копейках
                            'icon': icon_url,
                            'unit': 'шт'
                        })
                except Exception as e:
                    monobank_logger.warning(f'Error formatting basket item: {e}')
            
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
            
            # Сохраняем данные платежа в Order
            payment_payload = {
                'request': payload,
                'create': creation_data,
                'history': []
            }
            order.payment_invoice_id = invoice_id
            order.payment_payload = payment_payload
            order.payment_status = 'checking'
            order.save(update_fields=['payment_invoice_id', 'payment_payload', 'payment_status'])
            
            monobank_logger.info(f'Order {order.order_number} updated with invoice_id={invoice_id}')
            
            # Сохраняем в сессию
            request.session['monobank_invoice_id'] = invoice_id
            request.session['monobank_pending_order_id'] = order.id
            request.session.modified = True
            
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
                'order_ref': order.order_number
            })
            
    except Exception as e:
        monobank_logger.error(f'Error creating order/invoice: {e}', exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'Сталася помилка. Спробуйте ще раз.'
        })
