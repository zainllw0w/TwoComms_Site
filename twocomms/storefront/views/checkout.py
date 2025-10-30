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
from .utils import (
    get_cart_from_session,
    calculate_cart_total,
    _get_color_variant_safe,
    _color_label_from_variant
)


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
            
            # ИСПРАВЛЕНО: Цена всегда из Product (актуальная цена, не храним в сессии)
            price = product.final_price
            qty = int(item_data.get('qty', 1))
            line_total = price * qty
            
            # Получаем color_variant вместо обычного color
            color_variant = _get_color_variant_safe(item_data.get('color_variant_id'))
            
            cart_items.append({
                'key': item_key,
                'product': product,
                'price': price,
                'qty': qty,
                'line_total': line_total,
                'size': item_data.get('size', ''),
                'color_variant': color_variant,
                'color_label': _color_label_from_variant(color_variant)
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
    ВОССТАНОВЛЕНА РАБОЧАЯ ЛОГИКА из старого views.py (order_create)
    
    POST params:
        full_name: ФИО
        phone: Телефон
        city: Город
        np_office: Отделение Новой Почты
        pay_type: Тип оплаты (full/partial)
        payment_method: Способ оплаты (card/cash)
        
    Returns:
        redirect: Редирект на страницу успеха или корзину с ошибкой
    """
    from django.contrib import messages
    from django.utils import timezone
    from datetime import timedelta
    from .utils import _reset_monobank_session, _get_color_variant_safe
    
    # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Проверяем аутентификацию ПЕРЕД доступом к userprofile
    if not request.user.is_authenticated:
        messages.error(request, 'Будь ласка, увійдіть в систему для оформлення замовлення!')
        return redirect('login')
    
    # Требуем заполненный профиль доставки
    try:
        prof = request.user.userprofile
    except UserProfile.DoesNotExist:
        messages.error(request, 'Будь ласка, заповніть профіль доставки!')
        return redirect('profile_setup')
    
    # Получаем данные из формы или из профиля
    if request.method == 'POST':
        # Используем данные из формы
        full_name = request.POST.get('full_name', '').strip()
        phone = request.POST.get('phone', '').strip()
        city = request.POST.get('city', '').strip()
        np_office = request.POST.get('np_office', '').strip()
        pay_type = request.POST.get('pay_type', '')
        
        # Валидация данных из формы
        if not full_name or len(full_name) < 3:
            messages.error(request, 'ПІБ повинно містити мінімум 3 символи!')
            return redirect('cart')
        
        if not phone or len(phone.strip()) < 10:
            messages.error(request, 'Введіть коректний номер телефону!')
            return redirect('cart')
        
        if not city or len(city.strip()) < 2:
            messages.error(request, 'Введіть назву міста!')
            return redirect('cart')
        
        if not np_office or len(np_office.strip()) < 1:
            messages.error(request, 'Введіть адресу відділення!')
            return redirect('cart')
        
        if not pay_type:
            messages.error(request, 'Оберіть тип оплати!')
            return redirect('cart')
        
        # Обновляем профиль пользователя данными из формы
        prof.full_name = full_name
        prof.phone = phone
        prof.city = city
        prof.np_office = np_office
        prof.pay_type = pay_type
        prof.save()

    # Корзина должна быть не пустой
    cart = request.session.get('cart') or {}
    if not cart:
        messages.error(request, 'Кошик порожній!')
        return redirect('cart')

    # Защита от дублирования заказов
    recent_orders = Order.objects.select_related('user').filter(
        user=request.user,
        created__gte=timezone.now() - timedelta(minutes=5)
    )
    
    if recent_orders.exists():
        messages.error(request, 'Замовлення вже було створено нещодавно. Спробуйте ще раз через кілька хвилин.')
        return redirect('cart')

    # Пересчёт total и создание заказа в одной транзакции
    ids = [i['product_id'] for i in cart.values()]
    prods = Product.objects.in_bulk(ids)
    total_sum = Decimal('0')
    
    # Создаем заказ
    order = Order.objects.create(
        user=request.user,
        full_name=prof.full_name or request.user.username,
        phone=prof.phone,
        city=prof.city,
        np_office=prof.np_office,
        pay_type=prof.pay_type,
        total_sum=0,
        status='new'
    )
    
    # Создаем все товары заказа
    order_items = []
    for key, it in cart.items():
        p = prods.get(it['product_id'])
        if not p:
            continue
        
        # Получаем информацию о цвете
        color_variant = _get_color_variant_safe(it.get('color_variant_id'))
        
        unit = p.final_price
        line = unit * it['qty']
        total_sum += line
        
        # Создаем OrderItem
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
    
    # Создаем все товары одним запросом
    OrderItem.objects.bulk_create(order_items)
    
    # Применяем промокод если есть
    promo_code_id = request.session.get('promo_code_id')
    if promo_code_id:
        try:
            promo = PromoCode.objects.get(id=promo_code_id, is_active=True)
            if promo.can_be_used():
                discount = promo.calculate_discount(total_sum)
                order.discount_amount = discount
                order.promo_code = promo
                promo.use()  # Увеличиваем счетчик использований
        except PromoCode.DoesNotExist:
            pass
    
    # Обновляем общую сумму заказа
    order.total_sum = total_sum
    order.save()

    # Очищаем корзину и промокод
    _reset_monobank_session(request, drop_pending=True)
    request.session['cart'] = {}
    request.session.pop('promo_code_id', None)
    request.session.modified = True

    # Отправляем Telegram уведомление после создания заказа и товаров
    try:
        from orders.telegram_notifications import TelegramNotifier
        notifier = TelegramNotifier()
        notifier.send_new_order_notification(order)
    except Exception as e:
        # Не прерываем процесс, если уведомление не отправилось
        pass

    messages.success(request, f'Замовлення #{order.order_number} успішно створено!')

    return redirect('my_orders')


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
    ВОССТАНОВЛЕНА РАБОЧАЯ ЛОГИКА из старого views.py
    
    Monobank отправляет POST запрос когда:
    - Платеж успешен
    - Платеж отменен
    - Платеж истек
    
    Returns:
        HttpResponse/JsonResponse: 200 OK или ошибка
    """
    import logging
    import json
    
    monobank_logger = logging.getLogger('storefront.monobank')
    
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
            order = Order.objects.get(payment_invoice_id=invoice_id)
        except Order.DoesNotExist:
            monobank_logger.warning('Webhook received for unknown invoice %s', invoice_id)
            return JsonResponse({'ok': True})

        # Записываем статус платежа
        from storefront.views.utils import _record_monobank_status
        _record_monobank_status(order, payload, source='webhook')
        return JsonResponse({'ok': True})

    # Checkout order webhook requires signature validation
    from storefront.views.utils import _verify_monobank_signature, _update_order_from_checkout_result
    
    if not _verify_monobank_signature(request):
        monobank_logger.warning('Invalid or missing X-Sign for checkout webhook')
        return HttpResponse(status=400)

    result = payload.get('result') or {}
    order_id = result.get('orderId') or result.get('order_id')
    order_ref = result.get('orderRef') or result.get('order_ref')

    order = None
    if order_id:
        order = Order.objects.select_related('user').filter(payment_invoice_id=order_id).first()
    if order is None and order_ref:
        order = Order.objects.select_related('user').filter(order_number=order_ref).first()

    if order is None:
        monobank_logger.warning('Checkout webhook received for unknown order: %s / %s', order_id, order_ref)
        return JsonResponse({'ok': True})

    try:
        _update_order_from_checkout_result(order, result, source='webhook')
    except Exception as exc:
        monobank_logger.exception('Failed to process checkout webhook for order %s: %s', order.order_number, exc)
        return HttpResponse(status=500)

    return JsonResponse({'ok': True})


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
            # ИСПРАВЛЕНО: Редирект с order_id вместо order_number
            return redirect('order_success', order_id=order.id)
        else:
            return redirect('order_failed')
            
    except Order.DoesNotExist:
        return redirect('home')


def order_success(request, order_id):
    """
    Страница успешного оформления заказа.
    
    Args:
        order_id (int): ID заказа (из URL параметра)
    
    ИСПРАВЛЕНО: Параметр изменен с order_number на order_id для соответствия urls.py
    """
    order = get_object_or_404(Order, pk=order_id)
    
    # Проверяем права доступа
    if request.user.is_authenticated:
        if order.user and order.user != request.user:
            return redirect('home')
    
    # Очищаем корзину ТОЛЬКО если оплата успешна
    if order.payment_status in ('paid', 'prepaid'):
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
















