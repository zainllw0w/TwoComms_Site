"""
Cart views - Корзина покупок.

Содержит views для:
- Просмотра корзины
- Добавления товаров
- Обновления количества
- Удаления товаров
- Очистки корзины
- Применения промокодов
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.cache import never_cache
from django.contrib import messages
from decimal import Decimal, ROUND_HALF_UP
import logging
import json

from ..models import Product, PromoCode
from productcolors.models import ProductColorVariant
from accounts.models import UserProfile
from .utils import (
    get_cart_from_session,
    save_cart_to_session,
    calculate_cart_total,
    _reset_monobank_session,
    _normalize_color_variant_id,
    _get_color_variant_safe,
    _hex_to_name,
    _translate_color_to_ukrainian,
    _color_label_from_variant,
)
from ..utm_tracking import record_add_to_cart, record_remove_from_cart

# Logger для корзины
cart_logger = logging.getLogger('storefront.cart')
monobank_logger = logging.getLogger('storefront.monobank')

# Константы статусов Monobank
MONOBANK_SUCCESS_STATUSES = {'success', 'hold'}
MONOBANK_PENDING_STATUSES = {'processing'}
MONOBANK_FAILURE_STATUSES = {'failure', 'expired', 'rejected', 'canceled', 'cancelled', 'reversed'}


# ==================== CART VIEWS ====================


def _calculate_original_subtotal(cart):
    """
    Подсчитывает сумму корзины по базовым ценам (без скидок сайта).
    """
    if not cart:
        return Decimal('0')
    ids = [item.get('product_id') for item in cart.values() if item.get('product_id')]
    products = Product.objects.in_bulk(ids)
    total = Decimal('0')
    for item in cart.values():
        product = products.get(item.get('product_id'))
        if not product:
            continue
        try:
            qty = int(item.get('qty', 1))
        except (TypeError, ValueError):
            qty = 1
        total += Decimal(product.price) * qty
    return total

@never_cache
def view_cart(request):
    """
    Страница просмотра корзины.
    
    Context:
        cart_items: Список товаров в корзине с деталями
        subtotal: Сумма без скидки
        discount: Размер скидки (если применен промокод)
        total: Итоговая сумма
        grand_total: Итоговая сумма (алиас для total)
        total_points: Общее количество баллов за заказ
        promo_code: Примененный промокод (если есть)
        applied_promo: Алиас для promo_code
    """
    if request.method == 'POST':
        form_type = request.POST.get('form_type')
        if form_type == 'update_profile':
            if request.user.is_authenticated:
                try:
                    profile = request.user.userprofile
                except UserProfile.DoesNotExist:
                    profile = UserProfile.objects.create(user=request.user)

                profile.full_name = (request.POST.get('full_name') or '').strip()
                profile.phone = (request.POST.get('phone') or '').strip()
                profile.city = (request.POST.get('city') or '').strip()
                profile.np_office = (request.POST.get('np_office') or '').strip()

                pay_type_raw = request.POST.get('pay_type')
                if pay_type_raw:
                    # Импортируем функцию нормализации типа оплаты из старого views
                    try:
                        import storefront.views as old_views
                        if hasattr(old_views, '_normalize_pay_type'):
                            profile.pay_type = old_views._normalize_pay_type(pay_type_raw)
                        else:
                            # Fallback: если функция не найдена, используем значение напрямую или по умолчанию
                            profile.pay_type = pay_type_raw if pay_type_raw in ['online_full', 'prepay_200'] else 'online_full'
                    except Exception as e:
                        cart_logger.error('Error normalizing pay_type: %s', e)
                        # В случае ошибки не обновляем pay_type

                try:
                    profile.save()
                    messages.success(request, 'Дані доставки успішно оновлено!')
                except Exception as e:
                    cart_logger.error('Error saving profile: %s', e, exc_info=True)
                    messages.error(request, 'Помилка при збереженні даних. Спробуйте ще раз.')
            else:
                messages.error(request, 'Будь ласка, увійдіть, щоб зберегти дані доставки.')
        elif form_type == 'guest_order':
            from storefront import views as legacy_views
            return legacy_views.process_guest_order(request)
        elif form_type == 'order_create':
            from storefront import views as legacy_views
            return legacy_views.order_create(request)

    cart = get_cart_from_session(request)
    cart_items = []
    subtotal = Decimal('0')
    original_subtotal = Decimal('0')
    total_points = 0
    content_ids = []
    contents = []
    total_quantity = 0
    
    # Optimization: Fetch all products at once to avoid N+1
    product_ids = [item_data.get('product_id') for item_data in cart.values() if item_data.get('product_id')]
    products_map = Product.objects.select_related('category').in_bulk(product_ids)
    
    # Optimization: Fetch all color variants at once
    color_variant_ids = [item_data.get('color_variant_id') for item_data in cart.values() if item_data.get('color_variant_id')]
    from productcolors.models import ProductColorVariant
    color_variants_map = ProductColorVariant.objects.select_related('color').in_bulk(color_variant_ids)
    
    for item_key, item_data in cart.items():
        try:
            product_id = item_data.get('product_id')
            # product = Product.objects.select_related('category').get(id=product_id) # OLD N+1
            product = products_map.get(int(product_id))
            
            if not product:
                continue
            
            # Цена всегда берется из Product (актуальная цена)
            price = product.final_price
            original_price = Decimal(product.price)
            qty = int(item_data.get('qty', 1))
            line_total = price * qty
            original_line_total = original_price * qty
            site_line_discount = original_line_total - line_total
            if site_line_discount < 0:
                site_line_discount = Decimal('0.00')
            
            # Информация о цвете из color_variant_id
            # color_variant = _get_color_variant_safe(item_data.get('color_variant_id')) # OLD N+1 risk
            color_variant_id = item_data.get('color_variant_id')
            color_variant = color_variants_map.get(int(color_variant_id)) if color_variant_id else None
            
            color_label = _color_label_from_variant(color_variant)
            size_value = (item_data.get('size', '') or 'S').upper()
            # color_variant_id = color_variant.id if color_variant else None # Already have it
            offer_id = product.get_offer_id(color_variant_id, size_value)
            content_ids.append(offer_id)
            contents.append({
                'id': offer_id,
                'quantity': qty,
                'item_price': float(price),
                'item_name': product.title,
                'item_category': product.category.name if getattr(product, 'category', None) else '',
                'brand': 'TwoComms'
            })
            total_quantity += qty
            
            # Считаем баллы за товар
            try:
                if getattr(product, 'points_reward', 0):
                    total_points += int(product.points_reward) * qty
            except Exception:
                pass
            
            cart_items.append({
                'key': item_key,
                'product': product,
                'price': price,  # Для совместимости
                'unit_price': price,  # Шаблон ожидает unit_price!
                'original_unit_price': original_price,
                'qty': qty,
                'line_total': line_total,
                'original_line_total': original_line_total,
                'site_discount_amount': site_line_discount,
                'size': size_value,
                'color_variant': color_variant,
                'color_label': color_label,  # ДОБАВЛЕНО: для отображения цвета
                'offer_id': offer_id,
            })

            subtotal += line_total
            original_subtotal += original_line_total
            
        except Product.DoesNotExist:
            # Товар удален из БД - пропускаем
            continue
    
    # Проверяем промокод
    promo_code = None
    discount = Decimal('0')
    promo_code_id = request.session.get('promo_code_id')
    
    if promo_code_id:
        try:
            promo_code = PromoCode.objects.get(id=promo_code_id)
            if promo_code.can_be_used():
                discount = promo_code.calculate_discount(subtotal)
            else:
                # Промокод больше не валиден
                del request.session['promo_code_id']
                promo_code = None
        except PromoCode.DoesNotExist:
            del request.session['promo_code_id']
    
    total = subtotal - discount
    site_discount_total = (original_subtotal - subtotal).quantize(Decimal('0.01')) if original_subtotal >= subtotal else Decimal('0.00')
    subtotal = subtotal.quantize(Decimal('0.01'))
    original_subtotal = original_subtotal.quantize(Decimal('0.01'))
    discount = discount.quantize(Decimal('0.01'))
    total = total.quantize(Decimal('0.01'))
    total_savings = (site_discount_total + discount).quantize(Decimal('0.01'))
    
    # Определяем начальное значение для отображения "До сплати"
    # Если выбран prepay_200, показываем 200 грн, иначе полную сумму
    pay_now_amount = None
    if request.user.is_authenticated:
        try:
            from accounts.models import UserProfile
            import storefront.views as old_views
            prof = request.user.userprofile
            # Нормализуем pay_type для корректного сравнения
            # В UserProfile pay_type может быть 'partial' или 'full', нужно нормализовать
            if hasattr(old_views, '_normalize_pay_type') and prof.pay_type:
                normalized_pay_type = old_views._normalize_pay_type(prof.pay_type)
            else:
                normalized_pay_type = prof.pay_type if prof.pay_type else None
            if normalized_pay_type == 'prepay_200':
                pay_now_amount = Decimal('200.00')
        except Exception as e:
            cart_logger.warning('Could not determine pay_now_amount from user profile: %s', e)
            pass
    
    checkout_payload = None
    checkout_payload_ids = '[]'
    checkout_payload_contents = '[]'
    checkout_payload_value = float(total)
    checkout_payload_num_items = total_quantity
    if cart_items:
        checkout_payload = {
            'content_ids': content_ids,
            'contents': contents,
            'content_type': 'product',
            'currency': 'UAH',
            'value': float(total),
            'num_items': total_quantity
        }
        checkout_payload_ids = json.dumps(content_ids, ensure_ascii=False)
        checkout_payload_contents = json.dumps(contents, ensure_ascii=False)
    
    return render(
        request,
        'pages/cart.html',
        {
            'items': cart_items,  # Шаблон ожидает 'items', а не 'cart_items'!
            'cart_items': cart_items,  # Оставляем для совместимости
            'subtotal': subtotal,
            'discount': discount,
            'total': total,
            'grand_total': total,  # ДОБАВЛЕНО: алиас для шаблона
            'original_subtotal': original_subtotal,
            'site_discount_total': site_discount_total,
            'total_savings': total_savings,
            'pay_now_amount': pay_now_amount,  # НОВОЕ: начальное значение для "До сплати" (200 грн если prepay_200)
            'total_points': total_points,  # ДОБАВЛЕНО: баллы за заказ
            'promo_code': promo_code,
            'applied_promo': promo_code,  # ДОБАВЛЕНО: алиас для шаблона
            'cart_count': len(cart_items),
            'items_total_qty': total_quantity,
            'checkout_payload': checkout_payload,
            'checkout_payload_ids': checkout_payload_ids,
            'checkout_payload_contents': checkout_payload_contents,
            'checkout_payload_value': checkout_payload_value,
            'checkout_payload_num_items': checkout_payload_num_items
        }
    )


@require_POST
def add_to_cart(request):
    """
    Добавляет товар в корзину (сессия) с учётом размера и цвета, возвращает JSON с количеством и суммой.
    ВОССТАНОВЛЕНА РАБОЧАЯ ЛОГИКА из старого views.py
    """
    pid = request.POST.get('product_id')
    size = ((request.POST.get('size') or '').strip() or 'S').upper()
    color_variant_id = request.POST.get('color_variant_id')
    try:
        qty = int(request.POST.get('qty') or '1')
    except ValueError:
        qty = 1
    qty = max(qty, 1)

    product = get_object_or_404(Product, pk=pid)
    price = product.final_price
    if not isinstance(price, Decimal):
        price = Decimal(str(price))

    cart = request.session.get('cart', {})
    key = f"{product.id}:{size}:{color_variant_id or 'default'}"
    item = cart.get(key, {
        'product_id': product.id,
        'size': size,
        'color_variant_id': color_variant_id,
        'qty': 0
    })
    item['qty'] += qty
    cart[key] = item
    if qty <= 0:
        _reset_monobank_session(request, drop_pending=True)
    request.session['cart'] = cart
    request.session.modified = True

    _reset_monobank_session(request, drop_pending=True)

    try:
        color_variant_int = int(color_variant_id) if color_variant_id else None
    except (TypeError, ValueError):
        color_variant_int = None
    offer_id = product.get_offer_id(color_variant_int, size)
    item_value = (price * qty).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    ids = [i['product_id'] for i in cart.values()]
    prods = Product.objects.in_bulk(ids)
    total_qty = sum(i['qty'] for i in cart.values())
    total_sum = Decimal('0')
    for i in cart.values():
        p = prods.get(i['product_id'])
        if p:
            price_decimal = p.final_price if isinstance(p.final_price, Decimal) else Decimal(str(p.final_price))
            total_sum += Decimal(i['qty']) * price_decimal

    cart_total = total_sum.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    # UTM Tracking: записываем добавление в корзину
    try:
        record_add_to_cart(
            request,
            product_id=product.id,
            product_name=product.title,
            cart_value=float(cart_total)
        )
    except Exception as e:
        cart_logger.warning(f"Failed to record add_to_cart action: {e}")

    return JsonResponse({
        'ok': True,
        'count': total_qty,
        'total': float(cart_total),
        'cart_total': float(cart_total),
        'item': {
            'product_id': product.id,
            'offer_id': offer_id,
            'quantity': qty,
            'item_price': float(price.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            'value': float(item_value),
            'currency': 'UAH',
            'size': size,
            'color_variant_id': color_variant_id,
            'product_title': product.title,
            'product_category': product.category.name if getattr(product, 'category', None) else ''
        }
    })


@require_POST
def update_cart(request):
    """
    Обновление количества товара в корзине (AJAX).
    
    POST params:
        cart_key: Ключ товара в корзине
        qty: Новое количество
        
    Returns:
        JsonResponse: ok, line_total, subtotal, total
    """
    try:
        cart_key = request.POST.get('cart_key')
        qty = int(request.POST.get('qty', 1))
        
        if qty < 1:
            return JsonResponse({
                'success': False,
                'error': 'Кількість має бути не менше 1'
            }, status=400)
        
        cart = get_cart_from_session(request)
        
        if cart_key not in cart:
            return JsonResponse({
                'success': False,
                'error': 'Товар не знайдено у кошику'
            }, status=404)
        
        # Обновляем количество
        cart[cart_key]['qty'] = qty
        save_cart_to_session(request, cart)
        
        # ИСПРАВЛЕНО: Получаем цену из Product, а не из сессии (в сессии нет поля 'price')
        product_id = cart[cart_key]['product_id']
        try:
            product = Product.objects.get(id=product_id)
            price = product.final_price
        except Product.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Товар не знайдено'
            }, status=404)
        
        # Рассчитываем новые суммы
        line_total = price * qty
        subtotal = calculate_cart_total(cart)
        
        # Учитываем промокод
        discount = Decimal('0')
        promo_code_id = request.session.get('promo_code_id')
        if promo_code_id:
            try:
                promo_code = PromoCode.objects.get(id=promo_code_id)
                if promo_code.can_be_used():
                    discount = promo_code.calculate_discount(subtotal)
            except PromoCode.DoesNotExist:
                pass
        
        total = subtotal - discount
        
        return JsonResponse({
            'ok': True,
            'line_total': float(line_total),
            'subtotal': float(subtotal),
            'discount': float(discount),
            'total': float(total)
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@require_POST
def remove_from_cart(request):
    """
    Удаление позиции из корзины: поддерживает key="productId:size:color" и (product_id + size).
    ВОССТАНОВЛЕНА РАБОЧАЯ ЛОГИКА из старого cart_remove
    """
    cart = request.session.get('cart', {})

    key = (request.POST.get('key') or '').strip()
    pid = request.POST.get('product_id')
    size = (request.POST.get('size') or '').strip()

    removed = []

    def remove_key_exact(k: str) -> bool:
        if k in cart:
            cart.pop(k, None)
            removed.append(k)
            return True
        return False

    # 1) Пытаемся удалить по exact key
    if key:
        if not remove_key_exact(key):
            # 1.1) case-insensitive сравнение ключей
            target = key.lower()
            for kk in list(cart.keys()):
                if kk.lower() == target:
                    remove_key_exact(kk)
                    break
            # 1.2) если всё ещё не нашли, попробуем удалить все варианты этого товара
            if not removed and ":" in key:
                pid_part = key.split(":", 1)[0]
                for kk in list(cart.keys()):
                    if kk.split(":", 1)[0] == pid_part:
                        remove_key_exact(kk)
    # 2) Либо удаляем по product_id (+optional size)
    elif pid:
        try:
            pid_str = str(int(pid))
        except (ValueError, TypeError):
            pid_str = str(pid)
        if size:
            candidate = f"{pid_str}:{size}"
            if not remove_key_exact(candidate):
                # case-insensitive
                target = candidate.lower()
                for kk in list(cart.keys()):
                    if kk.lower() == target:
                        remove_key_exact(kk)
                        break
        else:
            for kk in list(cart.keys()):
                if kk.split(":", 1)[0] == pid_str:
                    remove_key_exact(kk)

    # Сохраняем изменения
    request.session['cart'] = cart
    request.session.modified = True

    # Пересчёт сводки с использованием Decimal и учетом промокодов
    ids = [i['product_id'] for i in cart.values()]
    prods = Product.objects.in_bulk(ids)
    total_qty = sum(i['qty'] for i in cart.values())
    total_sum = Decimal('0')
    for i in cart.values():
        p = prods.get(i['product_id'])
        if p:
            price_decimal = p.final_price if isinstance(p.final_price, Decimal) else Decimal(str(p.final_price))
            total_sum += Decimal(i['qty']) * price_decimal
    
    # Учитываем промокод при расчете итоговой суммы
    subtotal = total_sum.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    discount = Decimal('0')
    promo_code_id = request.session.get('promo_code_id')
    if promo_code_id:
        try:
            promo_code = PromoCode.objects.get(id=promo_code_id)
            if promo_code.can_be_used():
                discount = promo_code.calculate_discount(subtotal)
        except PromoCode.DoesNotExist:
            pass
    
    total = (subtotal - discount).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    # UTM Tracking: записываем удаление из корзины
    if removed:
        try:
            # Получаем информацию о удаленном товаре для логирования
            for removed_key in removed:
                # Парсим ключ чтобы получить product_id
                if ':' in removed_key:
                    product_id_str = removed_key.split(':')[0]
                    try:
                        product_id = int(product_id_str)
                        product = Product.objects.get(id=product_id)
                        record_remove_from_cart(
                            request,
                            product_id=product.id,
                            product_name=product.title,
                            cart_value=float(total)
                        )
                    except (ValueError, Product.DoesNotExist):
                        pass
        except Exception as e:
            cart_logger.warning(f"Failed to record remove_from_cart action: {e}")

    return JsonResponse({
        'ok': True, 
        'count': total_qty, 
        'subtotal': float(subtotal),
        'discount': float(discount),
        'total': float(total),
        'removed': removed, 
        'keys': list(cart.keys())
    })


def clear_cart(request):
    """
    Очистка корзины.
    
    Удаляет все товары из корзины и сбрасывает промокод.
    """
    request.session['cart'] = {}
    if 'promo_code_id' in request.session:
        del request.session['promo_code_id']
    if 'promo_code_data' in request.session:
        del request.session['promo_code_data']
    request.session.modified = True
    
    return redirect('cart')


def get_cart_count(request):
    """
    AJAX endpoint для получения количества товаров в корзине.
    
    Returns:
        JsonResponse: cart_count
    """
    cart = get_cart_from_session(request)
    cart_count = sum(item.get('qty', 0) for item in cart.values())
    
    return JsonResponse({
        'cart_count': cart_count
    })


@require_POST
def apply_promo_code(request):
    """
    Применение промокода к корзине (AJAX) с проверкой авторизации и групповых ограничений.
    
    POST params:
        promo_code: Код промокода
        
    Returns:
        JsonResponse: success, discount, total, message, auth_required (если нужна авторизация)
    """
    try:
        code = request.POST.get('promo_code', '').strip().upper()
        
        if not code:
            return JsonResponse({
                'success': False,
                'error': 'Введіть промокод'
            }, status=400)
        
        # Ищем промокод
        try:
            promo_code = PromoCode.objects.get(code=code)
        except PromoCode.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Промокод не знайдено'
            }, status=404)
        
        # НОВАЯ ЛОГИКА: Проверяем авторизацию и права пользователя
        if not request.user.is_authenticated:
            return JsonResponse({
                'success': False,
                'auth_required': True,
                'error': 'Промокоди доступні тільки для зареєстрованих користувачів',
                'message': 'Будь ласка, увійдіть в акаунт або зареєструйтесь, щоб використати промокод'
            }, status=403)
        
        # Проверяем, может ли пользователь использовать этот промокод
        can_use, error_message = promo_code.can_be_used_by_user(request.user)
        
        if not can_use:
            return JsonResponse({
                'success': False,
                'error': error_message
            }, status=400)
        
        # Рассчитываем скидку
        cart = get_cart_from_session(request)
        subtotal = calculate_cart_total(cart)
        original_subtotal = _calculate_original_subtotal(cart)
        discount = promo_code.calculate_discount(subtotal)
        
        if discount <= 0:
            # Проверяем причину
            if promo_code.min_order_amount and subtotal < promo_code.min_order_amount:
                return JsonResponse({
                    'success': False,
                    'error': f'Мінімальна сума замовлення для цього промокоду: {promo_code.min_order_amount} грн'
                }, status=400)
            return JsonResponse({
                'success': False,
                'error': 'Промокод не застосовується до цього замовлення'
            }, status=400)
        
        # Сохраняем промокод в сессию (временно, до создания заказа)
        request.session['promo_code_id'] = promo_code.id
        request.session['promo_code_data'] = {
            'code': promo_code.code,
            'discount': float(discount),
            'discount_type': promo_code.discount_type,
            'promo_type': promo_code.promo_type
        }
        request.session.modified = True
        
        total = subtotal - discount
        site_discount_total = (original_subtotal - subtotal).quantize(Decimal('0.01')) if original_subtotal >= subtotal else Decimal('0.00')
        subtotal = subtotal.quantize(Decimal('0.01'))
        original_subtotal = original_subtotal.quantize(Decimal('0.01'))
        discount = discount.quantize(Decimal('0.01'))
        total = total.quantize(Decimal('0.01'))
        total_savings = (site_discount_total + discount).quantize(Decimal('0.01'))
        
        # Формируем сообщение с учетом типа промокода
        promo_type_label = dict(PromoCode.PROMO_TYPES).get(promo_code.promo_type, '')
        message = f'Промокод застосовано! Знижка: {discount} грн'
        
        if promo_code.promo_type == 'voucher':
            message = f'Ваучер застосовано! Знижка: {discount} грн'
        elif promo_code.group:
            message = f'Промокод з групи "{promo_code.group.name}" застосовано! Знижка: {discount} грн'
        
        return JsonResponse({
            'ok': True,
            'success': True,
            'discount': float(discount),
            'total': float(total),
            'message': message,
            'promo_code': promo_code.code,
            'subtotal': float(subtotal),
            'original_subtotal': float(original_subtotal),
            'site_discount_total': float(site_discount_total),
            'total_savings': float(total_savings),
        })
        
    except Exception as e:
        cart_logger.error(
            'promo_code_error: user=%s code=%s error=%s',
            request.user.id if request.user.is_authenticated else None,
            code if 'code' in locals() else 'unknown',
            str(e)
        )
        return JsonResponse({
            'success': False,
            'error': 'Помилка при застосуванні промокоду'
        }, status=400)


@require_POST
def remove_promo_code(request):
    """
    Удаление промокода из корзины (AJAX).
    
    Returns:
        JsonResponse: success, total, message
    """
    try:
        # Удаляем все данные промокода из сессии
        removed_code = None
        if 'promo_code_data' in request.session:
            removed_code = request.session['promo_code_data'].get('code')
            del request.session['promo_code_data']
        
        if 'promo_code_id' in request.session:
            del request.session['promo_code_id']
            
            request.session.modified = True
        
        cart = get_cart_from_session(request)
        subtotal = calculate_cart_total(cart)
        # После удаления промокода скидка = 0
        total = subtotal
        
        return JsonResponse({
            'ok': True,
            'success': True,
            'subtotal': float(subtotal),
            'discount': 0.0,
            'total': float(total),
            'message': 'Промокод видалено'
        })
        
    except Exception as e:
        cart_logger.error(
            'promo_code_remove_error: user=%s error=%s',
            request.user.id if request.user.is_authenticated else None,
            str(e)
        )
        return JsonResponse({
            'success': False,
            'error': 'Помилка при видаленні промокоду'
        }, status=400)


# ==================== HELPER FUNCTIONS ====================
# Moved to utils.py to avoid duplication


# ==================== AJAX ENDPOINTS ====================

def cart_summary(request):
    """
    Краткая сводка корзины для обновления бейджа (AJAX).
    
    Returns:
        JsonResponse: {ok, count, total}
    """
    cart = request.session.get('cart', {})
    
    if not cart:
        return JsonResponse({'ok': True, 'count': 0, 'total': 0})
    
    ids = [i['product_id'] for i in cart.values()]
    prods = Product.objects.in_bulk(ids)
    
    # Проверяем, какие товары найдены
    found_products = set(prods.keys())
    missing_products = set(ids) - found_products
    
    if missing_products:
        # Удаляем несуществующие товары из корзины
        cart_to_clean = dict(cart)
        for key, item in cart_to_clean.items():
            if item['product_id'] in missing_products:
                cart.pop(key, None)
        _reset_monobank_session(request, drop_pending=True)
        request.session['cart'] = cart
        request.session.modified = True
    
    # Пересчитываем с очищенной корзиной
    total_qty = sum(i['qty'] for i in cart.values())
    total_sum = 0
    for i in cart.values():
        p = prods.get(i['product_id'])
        if p:
            total_sum += i['qty'] * p.final_price
    
    return JsonResponse({'ok': True, 'count': total_qty, 'total': total_sum})


def cart_mini(request):
    """
    HTML для мини‑корзины (выпадающая панель).
    
    Returns:
        HttpResponse: Rendered HTML partial
    """
    cart_sess = request.session.get('cart', {})
    
    if not cart_sess:
        return render(request, 'partials/mini_cart.html', {'items': [], 'total': 0})
    
    ids = [i['product_id'] for i in cart_sess.values()]
    prods = Product.objects.in_bulk(ids)
    
    # Проверяем, какие товары найдены
    found_products = set(prods.keys())
    missing_products = set(ids) - found_products
    
    if missing_products:
        # Удаляем несуществующие товары из корзины
        cart_to_clean = dict(cart_sess)
        for key, item in cart_to_clean.items():
            if item['product_id'] in missing_products:
                cart_sess.pop(key, None)
        _reset_monobank_session(request, drop_pending=True)
        request.session['cart'] = cart_sess
        request.session.modified = True
    
    items = []
    total = 0
    total_points = 0
    
    for key, it in cart_sess.items():
        p = prods.get(it['product_id'])
        if not p:
            continue
        
        # Получаем информацию о цвете
        color_variant = _get_color_variant_safe(it.get('color_variant_id'))
        
        unit = p.final_price
        line = unit * it['qty']
        total += line
        
        # Баллы за товар, если предусмотрены
        try:
            if getattr(p, 'points_reward', 0):
                total_points += int(p.points_reward) * int(it['qty'])
        except Exception:
            pass
        
        size_value = (it.get('size', '') or '').upper()
        if not size_value:
            size_value = 'S'
        color_variant_id = color_variant.id if color_variant else None
        offer_id = p.get_offer_id(color_variant_id, size_value)

        items.append({
            'key': key,
            'product': p,
            'size': size_value,
            'color_variant': color_variant,
            'color_label': _color_label_from_variant(color_variant),
            'qty': it['qty'],
            'unit_price': unit,
            'line_total': line,
            'offer_id': offer_id,
        })
    
    return render(request, 'partials/mini_cart.html', {
        'items': items,
        'total': total,
        'total_points': total_points
    })


@require_POST
def contact_manager(request):
    """
    Обработка формы связи с менеджером из модального окна.
    
    Отправляет Telegram сообщение администратору с:
    - Контактными данными клиента (ПІБ, телефон, Telegram, WhatsApp)
    - Содержимым корзины
    
    POST params:
        full_name: ПІБ клиента
        phone: Телефон (обязательно)
        telegram: Telegram login (опционально)
        whatsapp: WhatsApp (опционально)
        
    Returns:
        JsonResponse: {'success': True/False, 'error': 'message'}
    """
    try:
        # Получаем данные из формы
        full_name = request.POST.get('full_name', '').strip()
        phone = request.POST.get('phone', '').strip()
        telegram = request.POST.get('telegram', '').strip()
        whatsapp = request.POST.get('whatsapp', '').strip()
        
        # Валидация обязательных полей
        if not full_name or len(full_name) < 3:
            return JsonResponse({
                'success': False,
                'error': 'ПІБ повинно містити мінімум 3 символи'
            })
        
        if not phone or len(phone) < 10:
            return JsonResponse({
                'success': False,
                'error': 'Введіть коректний номер телефону'
            })
        
        # Получаем корзину
        cart = get_cart_from_session(request)
        
        if not cart:
            return JsonResponse({
                'success': False,
                'error': 'Кошик порожній'
            })
        
        # Получаем товары из БД
        ids = [item['product_id'] for item in cart.values()]
        products = Product.objects.in_bulk(ids)
        
        # Формируем сообщение для Telegram
        message = f"""📞 <b>ЗАПИТ ЗВ'ЯЗКУ З МЕНЕДЖЕРОМ</b>

👤 <b>Клієнт:</b> {full_name}
📱 <b>Телефон:</b> {phone}"""
        
        if telegram:
            message += f"\n💬 <b>Telegram:</b> @{telegram}"
        
        if whatsapp:
            message += f"\n📲 <b>WhatsApp:</b> {whatsapp}"
        
        message += "\n\n🛒 <b>КОШИК:</b>\n"
        
        total_sum = Decimal('0')
        
        # Добавляем товары
        for key, item_data in cart.items():
            product = products.get(item_data['product_id'])
            if not product:
                continue
            
            qty = item_data.get('qty', 1)
            unit_price = product.final_price
            line_total = unit_price * qty
            total_sum += line_total
            
            # Информация о размере и цвете
            size_info = f" ({item_data.get('size')})" if item_data.get('size') else ""
            
            message += f"• {product.title}{size_info} x {qty} шт = {line_total} грн\n"
        
        message += f"\n💰 <b>Всього:</b> {total_sum} грн"
        message += "\n\n<i>Клієнт очікує на зв'язок менеджера!</i>"
        
        # Отправляем в Telegram
        try:
            from orders.telegram_notifications import TelegramNotifier
            notifier = TelegramNotifier()
            notifier.send_admin_message(message)
            
            return JsonResponse({'success': True})
            
        except Exception as telegram_error:
            cart_logger.error(
                f"Failed to send Telegram notification for contact request: {telegram_error}",
                exc_info=True
            )
            return JsonResponse({
                'success': False,
                'error': 'Не вдалося відправити повідомлення. Спробуйте пізніше'
            })
    
    except Exception as e:
        cart_logger.error(f"Error processing contact manager request: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'Сталася помилка. Спробуйте ще раз'
        })


@never_cache
def cart_items_api(request):
    """
    AJAX endpoint для получения списка товаров в корзине (JSON).
    Используется для автоматического обновления списка товаров на странице корзины.
    
    Returns:
        JsonResponse: {
            'ok': True,
            'items': [...],  # Список товаров с данными
            'subtotal': float,
            'discount': float,
            'total': float,
            'grand_total': float,
            'total_points': int,
            'cart_count': int
        }
    """
    cart = get_cart_from_session(request)
    cart_items = []
    subtotal = Decimal('0')
    original_subtotal = Decimal('0')
    total_points = 0
    total_quantity = 0
    
    for item_key, item_data in cart.items():
        try:
            product_id = item_data.get('product_id')
            product = Product.objects.select_related('category').get(id=product_id)
            
            price = product.final_price
            original_price = Decimal(product.price)
            qty = int(item_data.get('qty', 1))
            line_total = price * qty
            original_line_total = original_price * qty
            site_line_discount = original_line_total - line_total
            if site_line_discount < 0:
                site_line_discount = Decimal('0.00')
            total_quantity += qty
            
            color_variant = _get_color_variant_safe(item_data.get('color_variant_id'))
            color_label = _color_label_from_variant(color_variant)
            size_value = (item_data.get('size', '') or 'S').upper()
            color_variant_id = color_variant.id if color_variant else None
            offer_id = product.get_offer_id(color_variant_id, size_value)
            
            # Баллы за товар
            try:
                if getattr(product, 'points_reward', 0):
                    total_points += int(product.points_reward) * qty
            except Exception:
                pass
            
            # Подготовка изображения (полный URL)
            image_url = None
            if color_variant and color_variant.images.exists():
                image_url = request.build_absolute_uri(color_variant.images.first().image.url)
            elif product.main_image:
                image_url = request.build_absolute_uri(product.main_image.url)
            
            cart_items.append({
                'key': item_key,
                'product_id': product.id,
                'product_title': product.title,
                'product_slug': product.slug,
                'unit_price': float(price),
                'original_unit_price': float(original_price),
                'line_total': float(line_total),
                'original_line_total': float(original_line_total),
                'site_discount_amount': float(site_line_discount),
                'qty': qty,
                'size': size_value,
                'color_variant_id': item_data.get('color_variant_id'),
                'color_label': color_label,
                'image_url': image_url,
                'points_reward': int(getattr(product, 'points_reward', 0) or 0),
                'offer_id': offer_id,
                'item_value': float(line_total),
                'product_category': product.category.name if getattr(product, 'category', None) else '',
                'discount_percent': product.discount_percent or 0,
            })
            
            subtotal += line_total
            original_subtotal += original_line_total
            
        except Product.DoesNotExist:
            continue
    
    promo_code = None
    discount = Decimal('0')
    promo_code_id = request.session.get('promo_code_id')
    
    if promo_code_id:
        try:
            promo_code = PromoCode.objects.get(id=promo_code_id)
            if promo_code.can_be_used():
                discount = promo_code.calculate_discount(subtotal)
            else:
                del request.session['promo_code_id']
                promo_code = None
        except PromoCode.DoesNotExist:
            del request.session['promo_code_id']
    
    total = subtotal - discount
    site_discount_total = (original_subtotal - subtotal).quantize(Decimal('0.01')) if original_subtotal >= subtotal else Decimal('0.00')
    subtotal = subtotal.quantize(Decimal('0.01'))
    original_subtotal = original_subtotal.quantize(Decimal('0.01'))
    discount = discount.quantize(Decimal('0.01'))
    total = total.quantize(Decimal('0.01'))
    total_savings = (site_discount_total + discount).quantize(Decimal('0.01'))
    
    return JsonResponse({
        'ok': True,
        'items': cart_items,
        'subtotal': float(subtotal),
        'original_subtotal': float(original_subtotal),
        'site_discount_total': float(site_discount_total),
        'discount': float(discount),
        'total': float(total),
        'grand_total': float(total),
        'total_points': total_points,
        'cart_count': total_quantity,
        'items_count': total_quantity,
        'positions_count': len(cart_items),
        'applied_promo': promo_code.code if promo_code else None,
        'total_savings': float(total_savings),
    })
