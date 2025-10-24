"""
Checkout views - Оформление заказа и оплата.

Содержит views для:
- Оформления заказа (checkout)
- Создания заказа
- Выбора способа оплаты
- Интеграции с платежными системами (Monobank)
- Обработки webhook'ов
- Страниц успеха/ошибки
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from decimal import Decimal

from orders.models import Order, OrderItem
from ..models import Product, PromoCode
from productcolors.models import ProductColorVariant
from accounts.models import UserProfile
from .utils import get_cart_from_session, calculate_cart_total


# ==================== CHECKOUT VIEWS ====================

def checkout(request):
    """
    Страница оформления заказа.
    
    Шаги:
    1. Проверка корзины
    2. Заполнение контактных данных
    3. Выбор способа доставки
    4. Выбор способа оплаты
    5. Подтверждение заказа
    
    Context:
        cart_items: Товары в корзине
        subtotal: Сумма без скидки
        discount: Скидка
        total: Итоговая сумма
        user_profile: Профиль пользователя (если авторизован)
    """
    cart = get_cart_from_session(request)
    
    if not cart:
        return redirect('cart')
    
    # Подготавливаем данные товаров
    cart_items = []
    subtotal = Decimal('0')
    
    for item_key, item_data in cart.items():
        try:
            product_id = item_data.get('product_id')
            product = Product.objects.get(id=product_id)
            
            # ВАЖНО: Цена ВСЕГДА из Product.final_price (актуальная)
            # НЕ используем item_data.get('price') - может быть устаревшей!
            price = product.final_price
            qty = int(item_data.get('qty', 1))
            line_total = price * qty
            
            cart_items.append({
                'key': item_key,
                'product': product,
                'price': price,
                'qty': qty,
                'line_total': line_total,
                'size': item_data.get('size', ''),
                'color': item_data.get('color', '')
            })
            
            subtotal += line_total
            
        except Product.DoesNotExist:
            continue
    
    # Проверяем промокод
    discount = Decimal('0')
    promo_code = None
    promo_code_id = request.session.get('promo_code_id')
    
    if promo_code_id:
        try:
            promo_code = PromoCode.objects.get(id=promo_code_id)
            if promo_code.can_be_used():
                discount = promo_code.calculate_discount(subtotal)
        except PromoCode.DoesNotExist:
            pass
    
    total = subtotal - discount
    
    # Данные пользователя
    user_profile = None
    if request.user.is_authenticated:
        try:
            user_profile = request.user.userprofile
        except UserProfile.DoesNotExist:
            user_profile = UserProfile.objects.create(user=request.user)
    
    return render(
        request,
        'pages/checkout.html',
        {
            'cart_items': cart_items,
            'subtotal': subtotal,
            'discount': discount,
            'total': total,
            'promo_code': promo_code,
            'user_profile': user_profile
        }
    )


@require_POST
@transaction.atomic
def create_order(request):
    """
    Создание заказа из корзины.
    
    POST params:
        full_name: ФИО
        phone: Телефон
        city: Город
        np_office: Отделение Новой Почты
        pay_type: Тип оплаты (full/partial)
        payment_method: Способ оплаты (card/cash)
        
    Returns:
        JsonResponse или redirect: success, order_number
    """
    # TODO: Полная реализация создания заказа
    # Временно импортируем из старого views.py
    from storefront import views as old_views
    if hasattr(old_views, 'create_order'):
        return old_views.create_order(request)
    
    return JsonResponse({
        'success': False,
        'error': 'Not implemented yet'
    }, status=501)


def payment_method(request, order_number):
    """
    Выбор способа оплаты для заказа.
    
    Args:
        order_number (str): Номер заказа
        
    Payment methods:
        - card: Онлайн оплата картой (Monobank)
        - cash: Наложенный платеж
    """
    order = get_object_or_404(Order, order_number=order_number)
    
    # Проверяем права доступа
    if request.user.is_authenticated:
        if order.user and order.user != request.user:
            return redirect('home')
    
    return render(
        request,
        'pages/payment_method.html',
        {'order': order}
    )


@csrf_exempt
@require_POST
def monobank_webhook(request):
    """
    Webhook от Monobank для обновления статуса оплаты.
    
    Monobank отправляет POST запрос когда:
    - Платеж успешен
    - Платеж отменен
    - Платеж истек
    
    Returns:
        HttpResponse: 200 OK
    """
    # ИСПРАВЛЕНО: Убрана рекурсия!
    # Используем реализацию из views.py через уже загруженный модуль
    try:
        from .. import views as parent_views_module
        # Ищем функцию в родительском модуле (views.py)
        # __init__.py может не экспортировать её, поэтому ищем напрямую
        import importlib
        views_py = importlib.import_module('storefront.views')
        
        # Если есть функция в старом views.py, используем её
        if hasattr(views_py, 'monobank_webhook'):
            # Получаем ссылку на функцию из views.py
            webhook_func = getattr(views_py, 'monobank_webhook')
            # Проверяем, что это не наша же функция (избегаем рекурсии)
            if webhook_func.__module__ == 'storefront.views':
                return webhook_func(request)
    except (ImportError, AttributeError, RecursionError) as e:
        import logging
        logger = logging.getLogger('storefront.monobank')
        logger.error(f"Error calling old monobank_webhook: {e}", exc_info=True)
    
    # Fallback - просто возвращаем 200 (Monobank не будет повторять запрос)
    return HttpResponse(status=200)


def payment_callback(request):
    """
    Callback после оплаты (return URL).
    
    Query params:
        order_number: Номер заказа
        status: Статус оплаты (success/failed)
    """
    order_number = request.GET.get('order_number')
    status = request.GET.get('status', 'unknown')
    
    if not order_number:
        return redirect('home')
    
    try:
        order = Order.objects.get(order_number=order_number)
        
        if status == 'success':
            return redirect('order_success', order_number=order_number)
        else:
            return redirect('order_failed')
            
    except Order.DoesNotExist:
        return redirect('home')


def order_success(request, order_number):
    """
    Страница успешного оформления заказа.
    
    Args:
        order_number (str): Номер заказа
    """
    order = get_object_or_404(Order, order_number=order_number)
    
    # Проверяем права доступа
    if request.user.is_authenticated:
        if order.user and order.user != request.user:
            return redirect('home')
    
    # Очищаем корзину
    request.session['cart'] = {}
    if 'promo_code_id' in request.session:
        del request.session['promo_code_id']
    request.session.modified = True
    
    return render(
        request,
        'pages/order_success.html',
        {'order': order}
    )


def order_failed(request):
    """
    Страница ошибки при оформлении заказа.
    """
    return render(request, 'pages/order_failed.html')


def calculate_shipping(request):
    """
    Расчет стоимости доставки (AJAX).
    
    POST params:
        city: Город
        delivery_method: Способ доставки
        
    Returns:
        JsonResponse: shipping_cost
    """
    # TODO: Интеграция с Nova Poshta API для расчета стоимости
    
    return JsonResponse({
        'success': True,
        'shipping_cost': 0,  # Бесплатная доставка
        'message': 'Безкоштовна доставка'
    })
















