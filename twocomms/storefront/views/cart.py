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

from ..models import Product, PromoCode
from productcolors.models import ProductColorVariant
from .utils import (
    get_cart_from_session,
    save_cart_to_session,
    calculate_cart_total
)


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

