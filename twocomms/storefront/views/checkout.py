import json
import logging
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.db import transaction
from django.urls import reverse
from django.http import JsonResponse

from orders.models import Order, OrderItem
from storefront.models import Product, PromoCode
from productcolors.models import ProductColorVariant
from accounts.models import UserProfile
from .utils import (
    get_cart_from_session,
    calculate_cart_total,
    clear_cart,
    _normalize_color_variant_id,
    _get_color_variant_safe,
)
# from .cart import clear_cart
from .monobank import monobank_create_invoice

logger = logging.getLogger(__name__)

def checkout_view(request):
    """
    Redirect to cart, as checkout is now integrated into cart view.
    """
    return redirect('cart')

@require_POST
def create_order(request):
    """
    Creates an order from the current cart.
    """
    cart = get_cart_from_session(request)
    if not cart:
        messages.error(request, "Ваш кошик порожній")
        return redirect('cart')

    # Get user data
    if request.user.is_authenticated:
        user = request.user
        try:
            profile = user.userprofile
            full_name = profile.full_name or user.get_full_name()
            phone = profile.phone
            city = profile.city
            np_office = profile.np_office
            pay_type = profile.pay_type
        except UserProfile.DoesNotExist:
            full_name = request.POST.get('full_name', '')
            phone = request.POST.get('phone', '')
            city = request.POST.get('city', '')
            np_office = request.POST.get('np_office', '')
            pay_type = request.POST.get('pay_type', 'online_full')
    else:
        user = None
        full_name = request.POST.get('full_name', '')
        phone = request.POST.get('phone', '')
        city = request.POST.get('city', '')
        np_office = request.POST.get('np_office', '')
        pay_type = request.POST.get('pay_type', 'online_full')

    # Validate required fields
    if not all([full_name, phone, city, np_office]):
        messages.error(request, "Будь ласка, заповніть всі обов'язкові поля")
        return redirect('cart')

    try:
        with transaction.atomic():
            # Create Order
            order = Order(
                user=user,
                full_name=full_name,
                phone=phone,
                city=city,
                np_office=np_office,
                pay_type=pay_type,
                status='new',
                payment_status='unpaid'
            )
            order.save()

            # Create Order Items
            total_sum = Decimal('0')
            
            # Bulk fetch products and variants
            product_ids = [item['product_id'] for item in cart.values()]
            products_map = Product.objects.in_bulk(product_ids)
            
            variant_ids = [item.get('color_variant_id') for item in cart.values() if item.get('color_variant_id')]
            variants_map = ProductColorVariant.objects.in_bulk(variant_ids)

            for item in cart.values():
                product = products_map.get(int(item['product_id']))
                if not product:
                    continue

                qty = int(item['qty'])
                price = product.final_price
                
                variant_id = item.get('color_variant_id')
                variant = variants_map.get(int(variant_id)) if variant_id else None
                
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    color_variant=variant,
                    size=item.get('size', 'S'),
                    quantity=qty,
                    price=price
                )
                total_sum += price * qty

            order.total_sum = total_sum
            
            # Apply Promo Code
            promo_code_str = request.session.get('promo_code')
            if promo_code_str:
                try:
                    promo = PromoCode.objects.get(code=promo_code_str, active=True)
                    if promo.is_valid():
                        discount = promo.calculate_discount(total_sum)
                        order.discount_amount = discount
                        order.total_sum -= discount
                        order.promo_code = promo
                        # Increment usage? (Maybe later)
                except PromoCode.DoesNotExist:
                    pass

            order.save()

            # Clear cart
            clear_cart(request)
            
            # Handle Payment
            if pay_type in ['online_full', 'prepay_200']:
                return monobank_create_invoice(request, order.id)
            
            # COD or other
            return redirect('order_success', order_id=order.id)

    except Exception as e:
        logger.error(f"Error creating order: {e}", exc_info=True)
        messages.error(request, "Сталася помилка при оформленні замовлення. Спробуйте ще раз.")
        return redirect('cart')

def payment_method(request):
    return redirect('cart')

def monobank_webhook(request):
    # This should be handled by monobank views directly if possible, 
    # but for now we stub it or import it if it was here.
    # Assuming webhook logic is in monobank.py or handled via signal?
    # If urls.py points here, we need it.
    # Let's return 200 OK for now to avoid errors if called.
    return JsonResponse({'status': 'ok'})

def payment_callback(request):
    return redirect('home')

def order_success(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    return render(request, 'storefront/order_success.html', {'order': order})

def order_success_preview(request):
    """
    Preview for order success page.
    """
    # Create a dummy order for preview
    try:
        last_order = Order.objects.last()
    except Exception:
        last_order = None
        
    return render(request, 'storefront/order_success.html', {'order': last_order})

def order_failed(request):
    return render(request, 'storefront/order_failed.html')

def update_payment_method(request):
    """
    Update payment method for an order.
    """
    # Stub implementation
    return redirect('my_orders')

def confirm_payment(request):
    """
    Confirm payment for an order.
    """
    # Stub implementation
    return redirect('my_orders')

def calculate_shipping(request):
    return JsonResponse({'price': 0}) # Stub


def handle_payment(request):
    return redirect('cart')
