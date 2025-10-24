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
from decimal import Decimal
import logging

from ..models import Product, PromoCode
from productcolors.models import ProductColorVariant
from .utils import (
    get_cart_from_session,
    save_cart_to_session,
    calculate_cart_total
)

# Logger для корзины
cart_logger = logging.getLogger('storefront.cart')
monobank_logger = logging.getLogger('storefront.monobank')

# Note: Monobank status constants moved to checkout.py where they're actually used


# ==================== CART VIEWS ====================

def view_cart(request):
    """
    Страница просмотра корзины.
    
    Context:
        cart_items: Список товаров в корзине с деталями
        subtotal: Сумма без скидки
        discount: Размер скидки (если применен промокод)
        total: Итоговая сумма
        promo_code: Примененный промокод (если есть)
    """
    cart = get_cart_from_session(request)
    cart_items = []
    subtotal = Decimal('0')
    
    for item_key, item_data in cart.items():
        try:
            product_id = item_data.get('product_id')
            product = Product.objects.select_related('category').get(id=product_id)
            
            # Цена товара
            price = Decimal(str(item_data.get('price', product.final_price)))
            qty = int(item_data.get('qty', 1))
            line_total = price * qty
            
            # Информация о цвете
            color_name = item_data.get('color', '')
            color_hex = item_data.get('color_hex', '')
            
            cart_items.append({
                'key': item_key,
                'product': product,
                'price': price,
                'qty': qty,
                'line_total': line_total,
                'size': item_data.get('size', ''),
                'color': color_name,
                'color_hex': color_hex,
                'image_url': item_data.get('image_url', product.display_image.url if product.display_image else '')
            })
            
            subtotal += line_total
            
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
    
    return render(
        request,
        'pages/cart.html',
        {
            'cart_items': cart_items,
            'subtotal': subtotal,
            'discount': discount,
            'total': total,
            'promo_code': promo_code,
            'cart_count': len(cart_items)
        }
    )


@require_POST
def add_to_cart(request):
    """
    Добавление товара в корзину (AJAX).
    
    POST params:
        product_id: ID товара
        size: Размер
        color: Название цвета (опционально)
        color_hex: HEX код цвета (опционально)
        color_variant_id: ID цветового варианта (опционально)
        qty: Количество (по умолчанию 1)
        
    Returns:
        JsonResponse: success, cart_count, message
    """
    try:
        product_id = request.POST.get('product_id')
        size = request.POST.get('size', 'M')
        color = request.POST.get('color', '')
        color_hex = request.POST.get('color_hex', '')
        color_variant_id = request.POST.get('color_variant_id')
        qty = int(request.POST.get('qty', 1))
        
        product = Product.objects.get(id=product_id)
        price = product.final_price
        
        # Получаем корзину из сессии
        cart = get_cart_from_session(request)
        
        # Уникальный ключ товара: product_id + size + color
        cart_key = f"{product_id}_{size}_{color}"
        
        # Получаем изображение
        image_url = ''
        if color_variant_id:
            try:
                variant = ProductColorVariant.objects.get(id=color_variant_id)
                first_image = variant.images.first()
                if first_image:
                    image_url = first_image.image.url
            except ProductColorVariant.DoesNotExist:
                pass
        
        if not image_url and product.display_image:
            image_url = product.display_image.url
        
        # Если товар уже в корзине - увеличиваем количество
        if cart_key in cart:
            cart[cart_key]['qty'] = cart[cart_key].get('qty', 0) + qty
        else:
            # Добавляем новый товар
            cart[cart_key] = {
                'product_id': product_id,
                'title': product.title,
                'price': float(price),
                'qty': qty,
                'size': size,
                'color': color,
                'color_hex': color_hex,
                'image_url': image_url
            }
        
        # Сохраняем в сессию
        save_cart_to_session(request, cart)
        
        cart_count = sum(item.get('qty', 0) for item in cart.values())
        
        return JsonResponse({
            'success': True,
            'cart_count': cart_count,
            'message': f'Товар "{product.title}" додано до кошика'
        })
        
    except Product.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Товар не знайдено'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@require_POST
def update_cart(request):
    """
    Обновление количества товара в корзине (AJAX).
    
    POST params:
        cart_key: Ключ товара в корзине
        qty: Новое количество
        
    Returns:
        JsonResponse: success, line_total, subtotal, total
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
        
        # Рассчитываем новые суммы
        price = Decimal(str(cart[cart_key]['price']))
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
            'success': True,
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
    Удаление товара из корзины (AJAX).
    
    POST params:
        cart_key: Ключ товара в корзине
        
    Returns:
        JsonResponse: success, cart_count, subtotal, total
    """
    try:
        cart_key = request.POST.get('cart_key')
        
        cart = get_cart_from_session(request)
        
        if cart_key in cart:
            del cart[cart_key]
            save_cart_to_session(request, cart)
        
        cart_count = sum(item.get('qty', 0) for item in cart.values())
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
            'success': True,
            'cart_count': cart_count,
            'subtotal': float(subtotal),
            'discount': float(discount),
            'total': float(total),
            'message': 'Товар видалено з кошика'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


def clear_cart(request):
    """
    Очистка корзины.
    
    Удаляет все товары из корзины и сбрасывает промокод.
    """
    request.session['cart'] = {}
    if 'promo_code_id' in request.session:
        del request.session['promo_code_id']
    request.session.modified = True
    
    return redirect('view_cart')


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
    Применение промокода к корзине (AJAX).
    
    POST params:
        promo_code: Код промокода
        
    Returns:
        JsonResponse: success, discount, total, message
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
        
        # Проверяем валидность
        if not promo_code.can_be_used():
            return JsonResponse({
                'success': False,
                'error': 'Промокод більше не дійсний або вичерпано кількість використань'
            }, status=400)
        
        # Рассчитываем скидку
        cart = get_cart_from_session(request)
        subtotal = calculate_cart_total(cart)
        discount = promo_code.calculate_discount(subtotal)
        
        if discount <= 0:
            return JsonResponse({
                'success': False,
                'error': 'Промокод не застосовується до цього замовлення'
            }, status=400)
        
        # Сохраняем промокод в сессию
        request.session['promo_code_id'] = promo_code.id
        request.session.modified = True
        
        total = subtotal - discount
        
        return JsonResponse({
            'success': True,
            'discount': float(discount),
            'total': float(total),
            'message': f'Промокод застосовано! Знижка: {discount} грн'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@require_POST
def remove_promo_code(request):
    """
    Удаление промокода из корзины (AJAX).
    
    Returns:
        JsonResponse: success, total, message
    """
    try:
        if 'promo_code_id' in request.session:
            del request.session['promo_code_id']
            request.session.modified = True
        
        cart = get_cart_from_session(request)
        total = calculate_cart_total(cart)
        
        return JsonResponse({
            'success': True,
            'total': float(total),
            'message': 'Промокод видалено'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


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
                from orders.models import Order
                qs = Order.objects.select_related('user').filter(
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


def _normalize_color_variant_id(raw):
    """
    Приводит значение идентификатора цветового варианта к int либо None.
    Отсекает плейсхолдеры вида 'default', 'null', 'None', 'false', 'undefined'.
    """
    if raw is None:
        return None
    if isinstance(raw, int):
        return raw if raw > 0 else None
    try:
        value = str(raw).strip()
    except Exception:
        return None
    if not value:
        return None
    lowered = value.lower()
    if lowered in {'default', 'none', 'null', 'false', 'undefined'}:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _get_color_variant_safe(color_variant_id):
    """
    Возвращает экземпляр ProductColorVariant либо None, не выбрасывая ошибок.
    """
    normalized_id = _normalize_color_variant_id(color_variant_id)
    if not normalized_id:
        return None
    try:
        return ProductColorVariant.objects.get(id=normalized_id)
    except (ProductColorVariant.DoesNotExist, ValueError, TypeError):
        return None


def _hex_to_name(hex_value: str):
    """Конвертирует hex цвета в украинское название."""
    if not hex_value:
        return None
    h = hex_value.strip().lstrip('#').upper()
    mapping = {
        '000000': 'чорний',
        'FFFFFF': 'білий',
        'FAFAFA': 'білий',
        'F5F5F5': 'білий',
        'FF0000': 'червоний',
        'C1382F': 'бордовий',
        'FFA500': 'помаранчевий',
        'FFFF00': 'жовтий',
        '00FF00': 'зелений',
        '0000FF': 'синій',
        '808080': 'сірий',
        'A52A2A': 'коричневий',
        '800080': 'фіолетовий',
    }
    return mapping.get(h)


def _translate_color_to_ukrainian(color_name):
    """Переводит название цвета на украинский."""
    if not color_name:
        return color_name
    # Простой маппинг, можно расширить
    translations = {
        'black': 'чорний',
        'white': 'білий',
        'red': 'червоний',
        'blue': 'синій',
        'green': 'зелений',
        'yellow': 'жовтий',
        'orange': 'помаранчевий',
        'purple': 'фіолетовий',
        'pink': 'рожевий',
        'gray': 'сірий',
        'grey': 'сірий',
        'brown': 'коричневий',
    }
    lower_name = color_name.lower()
    return translations.get(lower_name, color_name)


def _color_label_from_variant(color_variant):
    """
    Возвращает текстовую метку цвета из варианта.
    """
    if not color_variant:
        return None
    color = getattr(color_variant, 'color', None)
    if not color:
        return None
    name = (getattr(color, 'name', '') or '').strip()
    if name:
        return _translate_color_to_ukrainian(name)
    primary = (getattr(color, 'primary_hex', '') or '').strip()
    secondary = (getattr(color, 'secondary_hex', '') or '').strip()
    if secondary:
        label = _translate_color_to_ukrainian(
            '/'.join(filter(None, [_hex_to_name(primary), _hex_to_name(secondary)]))
        )
        if label:
            return label
        return f'{primary}+{secondary}'
    if primary:
        label = _hex_to_name(primary)
        if label:
            return label
        return primary
    return None


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
        cart_logger.warning(
            'cart_summary_cleanup: session=%s user=%s removed_products=%s remaining_keys=%s',
            request.session.session_key,
            request.user.id if request.user.is_authenticated else None,
            list(missing_products),
            list(cart.keys())
        )
    
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
        cart_logger.warning(
            'cart_mini_cleanup: session=%s user=%s removed_products=%s remaining_keys=%s',
            request.session.session_key,
            request.user.id if request.user.is_authenticated else None,
            list(missing_products),
            list(cart_sess.keys())
        )
    
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
        
        items.append({
            'key': key,
            'product': p,
            'size': it.get('size', ''),
            'color_variant': color_variant,
            'color_label': _color_label_from_variant(color_variant),
            'qty': it['qty'],
            'unit_price': unit,
            'line_total': line
        })
    
    return render(request, 'partials/mini_cart.html', {
        'items': items,
        'total': total,
        'total_points': total_points
    })














