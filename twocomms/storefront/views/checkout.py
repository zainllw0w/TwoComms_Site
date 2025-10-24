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
from django.contrib.auth.decorators import login_required
from django.db import transaction
from decimal import Decimal
import hashlib
import logging

from orders.models import Order, OrderItem
from ..models import Product, PromoCode
from productcolors.models import ProductColorVariant
from accounts.models import UserProfile
from .utils import get_cart_from_session, calculate_cart_total

# Логер
monobank_logger = logging.getLogger('storefront.monobank')

# Helper функції з cart.py
def _get_color_variant_safe(color_variant_id):
    """Безпечне отримання color variant."""
    if not color_variant_id:
        return None
    try:
        return ProductColorVariant.objects.get(id=color_variant_id)
    except ProductColorVariant.DoesNotExist:
        return None

def _reset_monobank_session(request, drop_pending=False):
    """Скидання Monobank сесії."""
    keys_to_remove = [
        'monobank_invoice_id',
        'monobank_invoice_url',
        'monobank_checkout_url',
    ]
    if drop_pending:
        keys_to_remove.append('pending_monobank_order_id')
    
    for key in keys_to_remove:
        request.session.pop(key, None)
    request.session.modified = True


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
        return redirect('view_cart')
    
    # Подготавливаем данные товаров
    cart_items = []
    subtotal = Decimal('0')
    
    for item_key, item_data in cart.items():
        try:
            product_id = item_data.get('product_id')
            product = Product.objects.get(id=product_id)
            
            price = Decimal(str(item_data.get('price', product.final_price)))
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
    # TODO: Полная реализация webhook обработки
    # Временно импортируем из старого views.py
    from storefront import views as old_views
    if hasattr(old_views, 'monobank_webhook'):
        return old_views.monobank_webhook(request)
    
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


# ==================== ORDER PROCESSING ====================

def process_guest_order(request):
    """
    Обробка замовлення для неавторизованого користувача.
    
    POST params:
        full_name: ПІБ
        phone: Телефон
        city: Місто
        np_office: Відділення Нової Пошти
        pay_type: Тип оплати (full/partial)
    
    Returns:
        Redirect: До сторінки успіху або кошика з помилкою
    """
    from django.contrib import messages
    from django.utils import timezone
    from datetime import timedelta
    
    # Перевіряємо кошик
    cart = request.session.get('cart', {})
    if not cart:
        messages.error(request, 'Кошик порожній!')
        return redirect('cart')
    
    # Валідація даних доставки
    full_name = request.POST.get('full_name', '').strip()
    phone = request.POST.get('phone', '').strip()
    city = request.POST.get('city', '').strip()
    np_office = request.POST.get('np_office', '').strip()
    pay_type = request.POST.get('pay_type', '')
    
    # Перевіряємо обов'язкові поля
    if not full_name or len(full_name) < 3:
        messages.error(request, 'ПІБ повинно містити мінімум 3 символи!')
        return redirect('cart')
    
    if not phone:
        messages.error(request, 'Введіть номер телефону!')
        return redirect('cart')
    
    if not city:
        messages.error(request, 'Введіть місто!')
        return redirect('cart')
    
    if not np_office or len(np_office.strip()) < 1:
        messages.error(request, 'Введіть адресу відділення!')
        return redirect('cart')
    
    if not pay_type:
        messages.error(request, 'Оберіть тип оплати!')
        return redirect('cart')
    
    # Перевіряємо формат телефону
    phone_clean = ''.join(filter(str.isdigit, phone))
    if not phone.startswith('+380') or len(phone_clean) != 12:
        messages.error(request, 'Невірний формат телефону! Використовуйте формат +380XXXXXXXXX')
        return redirect('cart')
    
    # Перевіряємо, що не створюється дублюючий заказ
    delivery_hash = hashlib.md5(f"{full_name}{phone}{city}{np_office}".encode()).hexdigest()
    
    # Перевіряємо, чи не було вже замовлення з такими даними в останні 5 хвилин
    recent_orders = Order.objects.select_related('user').filter(
        full_name=full_name,
        phone=phone,
        city=city,
        np_office=np_office,
        created__gte=timezone.now() - timedelta(minutes=5)
    )
    
    if recent_orders.exists():
        messages.error(request, 'Замовлення з такими даними вже було створено нещодавно. Спробуйте ще раз через кілька хвилин.')
        return redirect('cart')
    
    # Створюємо замовлення
    ids = [i['product_id'] for i in cart.values()]
    prods = Product.objects.in_bulk(ids)
    total_sum = 0
    
    order = Order.objects.create(
        user=None,  # Гостьове замовлення
        full_name=full_name,
        phone=phone,
        city=city,
        np_office=np_office,
        pay_type=pay_type,
        total_sum=0,
        status='new'
    )
    
    # Додаємо товари в замовлення
    for key, it in cart.items():
        p = prods.get(it['product_id'])
        if not p:
            continue
        
        # Отримуємо інформацію про колір
        color_variant = _get_color_variant_safe(it.get('color_variant_id'))
        
        unit = p.final_price
        line = unit * it['qty']
        total_sum += line
        
        monobank_logger.info('Creating OrderItem: product=%s, unit_price=%s, qty=%s, line_total=%s', 
                           p.title, unit, it['qty'], line)
        
        if not unit:
            monobank_logger.error('Product %s has null final_price: price=%s, discount_percent=%s', 
                                p.title, p.price, getattr(p, 'discount_percent', 'N/A'))
        
        OrderItem.objects.create(
            order=order,
            product=p,
            color_variant=color_variant,
            title=p.title,
            size=it.get('size', ''),
            qty=it['qty'],
            unit_price=unit,
            line_total=line
        )
    
    # Застосовуємо промокод якщо є
    promo_code = request.session.get('applied_promo_code')
    if promo_code:
        try:
            promo = PromoCode.objects.get(code=promo_code, is_active=True)
            if promo.can_be_used():
                discount = promo.calculate_discount(total_sum)
                order.discount_amount = discount
                order.promo_code = promo
                promo.use()  # Збільшуємо лічильник використань
        except PromoCode.DoesNotExist:
            pass
    
    order.total_sum = total_sum
    order.save()
    
    # Очищаємо кошик та промокод
    _reset_monobank_session(request, drop_pending=True)
    request.session['cart'] = {}
    request.session.pop('applied_promo_code', None)
    request.session.modified = True
    
    # Відправляємо Telegram повідомлення після створення замовлення та товарів
    try:
        from orders.telegram_notifications import TelegramNotifier
        notifier = TelegramNotifier()
        notifier.send_new_order_notification(order)
    except Exception as e:
        # Не переривуємо процес, якщо повідомлення не відправилось
        pass
    
    messages.success(request, f'Замовлення #{order.order_number} успішно створено!')
    
    # Для неавторизованих користувачів перенаправляємо на сторінку успіху
    if not request.user.is_authenticated:
        return redirect('order_success', order_id=order.id)
    
    return redirect('my_orders')


@login_required
def order_create(request):
    """
    Створення замовлення для авторизованого користувача.
    
    POST params:
        full_name: ПІБ (опціонально, якщо вже є в профілі)
        phone: Телефон
        city: Місто
        np_office: Відділення Нової Пошти
        pay_type: Тип оплати
    
    Returns:
        Redirect: До my_orders або cart з помилкою
    """
    from django.contrib import messages
    from django.utils import timezone
    from datetime import timedelta
    
    # Потребуємо заповнений профіль доставки
    try:
        prof = request.user.userprofile
    except UserProfile.DoesNotExist:
        return redirect('profile_setup')
    
    # Отримуємо дані з форми або з профілю
    if request.method == 'POST':
        # Використовуємо дані з форми
        full_name = request.POST.get('full_name', '').strip()
        phone = request.POST.get('phone', '').strip()
        city = request.POST.get('city', '').strip()
        np_office = request.POST.get('np_office', '').strip()
        pay_type = request.POST.get('pay_type', '')
        
        # Валідація даних з форми
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
        
        # Оновлюємо профіль користувача даними з форми
        prof.full_name = full_name
        prof.phone = phone
        prof.city = city
        prof.np_office = np_office
        prof.pay_type = pay_type
        prof.save()
        
    else:
        # Використовуємо дані з профілю (для GET запитів)
        full_name = getattr(prof, 'full_name', '') or request.user.username
        phone = prof.phone
        city = prof.city
        np_office = prof.np_office
        pay_type = prof.pay_type
        
        # Перевіряємо обов'язкові поля з більш строгою валідацією
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

    # Кошик повинен бути не порожній
    cart = request.session.get('cart') or {}
    if not cart:
        return redirect('cart')

    # Захист від дублювання замовлень
    # Перевіряємо, чи не було вже замовлення від цього користувача в останні 5 хвилин
    recent_orders = Order.objects.select_related('user').filter(
        user=request.user,
        created__gte=timezone.now() - timedelta(minutes=5)
    )
    
    if recent_orders.exists():
        messages.error(request, 'Замовлення вже було створено нещодавно. Спробуйте ще раз через кілька хвилин.')
        return redirect('cart')

    # Перерахунок total і створення замовлення в одній транзакції
    with transaction.atomic():
        ids = [i['product_id'] for i in cart.values()]
        prods = Product.objects.in_bulk(ids)
        total_sum = 0
        
        # Створюємо замовлення
        order = Order.objects.create(
            user=request.user,
            full_name=full_name,
            phone=phone, city=city, np_office=np_office,
            pay_type=pay_type, total_sum=0, status='new'
        )
        
        # Створюємо всі товари замовлення
        order_items = []
        for key, it in cart.items():
            p = prods.get(it['product_id'])
            if not p:
                continue
            
            # Отримуємо інформацію про колір
            color_variant = _get_color_variant_safe(it.get('color_variant_id'))
            
            unit = p.final_price
            line = unit * it['qty']
            total_sum += line
            
            # Створюємо OrderItem
            order_item = OrderItem(
                order=order, product=p, color_variant=color_variant, title=p.title, size=it.get('size', ''),
                qty=it['qty'], unit_price=unit, line_total=line
            )
            order_items.append(order_item)
        
        # Створюємо всі товари одним запитом
        OrderItem.objects.bulk_create(order_items)
        
        # Застосовуємо промокод якщо є
        promo_code = request.session.get('applied_promo_code')
        if promo_code:
            try:
                promo = PromoCode.objects.get(code=promo_code, is_active=True)
                if promo.can_be_used():
                    discount = promo.calculate_discount(total_sum)
                    order.discount_amount = discount
                    order.promo_code = promo
                    promo.use()  # Збільшуємо лічильник використань
            except PromoCode.DoesNotExist:
                pass
        
        # Оновлюємо загальну суму замовлення
        order.total_sum = total_sum
        order.save()

    # Очищаємо кошик та промокод
    _reset_monobank_session(request, drop_pending=True)
    request.session['cart'] = {}
    request.session.pop('applied_promo_code', None)
    request.session.modified = True

    # Відправляємо Telegram повідомлення після створення замовлення та товарів
    try:
        from orders.telegram_notifications import TelegramNotifier
        notifier = TelegramNotifier()
        notifier.send_new_order_notification(order)
    except Exception as e:
        # Не переривуємо процес, якщо повідомлення не відправилось
        pass

    messages.success(request, f'Замовлення #{order.order_number} успішно створено!')

    return redirect('my_orders')


@login_required
def my_orders(request):
    """
    Список замовлень поточного користувача.
    
    Context:
        orders: QuerySet замовлень користувача
    """
    qs = Order.objects.select_related('user').filter(
        user=request.user
    ).prefetch_related('items__product').order_by('-created')
    
    return render(request, 'pages/my_orders.html', {'orders': qs})


@login_required
@require_POST
def update_payment_method(request):
    """
    AJAX view для оновлення методу оплати замовлення.
    
    Параметри:
    - order_id: ID замовлення
    - payment_method: full (повна передоплата) або partial (часткова)
    
    Перевірки:
    - Замовлення належить користувачу
    - Валідний метод оплати
    """
    order_id = request.POST.get('order_id')
    payment_method = request.POST.get('payment_method')
    
    if not order_id or not payment_method:
        return JsonResponse({
            'success': False,
            'error': 'Відсутні необхідні дані'
        })
    
    if payment_method not in ['full', 'partial']:
        return JsonResponse({
            'success': False,
            'error': 'Невірний метод оплати'
        })
    
    try:
        order = Order.objects.get(id=order_id, user=request.user)
    except Order.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Замовлення не знайдено'
        })
    
    # Обновляем метод оплаты
    order.pay_type = payment_method
    order.save()
    
    # Определяем отображаемое название метода
    method_display = 'Повна передоплата' if payment_method == 'full' else 'Часткова передоплата'
    
    return JsonResponse({
        'success': True,
        'payment_method': payment_method,
        'method_display': method_display
    })


@login_required
@require_POST
def confirm_payment(request):
    """
    AJAX view для підтвердження оплати замовлення.
    
    Параметри:
    - order_id: ID замовлення
    - payment_screenshot: Файл зі скріншотом оплати
    
    Функціонал:
    - Зберігає скріншот оплати
    - Змінює статус на "checking" (перевірка)
    - Відправляє JSON відповідь
    """
    order_id = request.POST.get("order_id")
    payment_screenshot = request.FILES.get("payment_screenshot")
    
    if not order_id:
        return JsonResponse({
            "success": False,
            "error": "Відсутній ID замовлення"
        })
    
    if not payment_screenshot:
        return JsonResponse({
            "success": False,
            "error": "Будь ласка, завантажте скріншот оплати"
        })
    
    try:
        order = Order.objects.get(id=order_id, user=request.user)
    except Order.DoesNotExist:
        return JsonResponse({
            "success": False,
            "error": "Замовлення не знайдено"
        })
    
    # Сохраняем скриншот оплаты
    order.payment_screenshot = payment_screenshot
    order.payment_status = "checking"
    order.save()
    
    return JsonResponse({
        "success": True,
        "message": "Скріншот оплати успішно завантажено"
    })
















