import logging
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.db import transaction
from django.http import JsonResponse

from orders.nova_poshta_data import apply_nova_poshta_refs, extract_nova_poshta_refs
from orders.models import Order, OrderItem
from storefront.models import Product, PromoCode, CustomPrintLead, CustomPrintModerationStatus
from productcolors.models import ProductColorVariant
from accounts.models import UserProfile
from storefront.custom_print_config import SESSION_CUSTOM_CART_KEY
from .utils import (
    get_cart_from_session,
    clear_cart,
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
    custom_cart = request.session.get(SESSION_CUSTOM_CART_KEY) or {}
    if not cart and not (isinstance(custom_cart, dict) and custom_cart):
        messages.error(request, "Ваш кошик порожній")
        return redirect('cart')

    # Split custom-print items into approved (join the order) and pending
    # (stay in the cart for a later, combined payment). Regular items are paid now.
    approved_custom_leads = []
    pending_custom_keys = []  # custom-cart keys to keep in session after checkout
    if isinstance(custom_cart, dict) and custom_cart:
        key_to_lead_id = {
            k: v.get('lead_id')
            for k, v in custom_cart.items()
            if isinstance(v, dict) and v.get('lead_id')
        }
        lead_ids = [lid for lid in key_to_lead_id.values() if lid]
        leads_qs = list(CustomPrintLead.objects.filter(pk__in=lead_ids)) if lead_ids else []
        leads_by_id = {l.pk: l for l in leads_qs}
        for key, lead_id in key_to_lead_id.items():
            lead = leads_by_id.get(lead_id)
            if lead and lead.moderation_status == CustomPrintModerationStatus.APPROVED:
                approved_custom_leads.append(lead)
            else:
                pending_custom_keys.append(key)
        # If there's nothing payable now (no regulars, no approved customs) — wait.
        if not cart and not approved_custom_leads:
            messages.info(
                request,
                "Кастомний принт ще очікує на перевірку менеджера. Оплата стане доступною після погодження."
            )
            return redirect('cart')

    # Get user data
    if request.user.is_authenticated:
        user = request.user
        try:
            profile = user.userprofile
            full_name = (request.POST.get('full_name') or profile.full_name or user.get_full_name() or '').strip()
            phone = (request.POST.get('phone') or profile.phone or '').strip()
            city = (request.POST.get('city') or profile.city or '').strip()
            np_office = (request.POST.get('np_office') or profile.np_office or '').strip()
            pay_type = (request.POST.get('pay_type') or profile.pay_type or 'online_full').strip()
            delivery_refs = extract_nova_poshta_refs(request.POST or None)
            if not any(delivery_refs.values()):
                delivery_refs = {
                    "np_settlement_ref": getattr(profile, "np_settlement_ref", "") or "",
                    "np_city_ref": getattr(profile, "np_city_ref", "") or "",
                    "np_warehouse_ref": getattr(profile, "np_warehouse_ref", "") or "",
                }
        except UserProfile.DoesNotExist:
            full_name = request.POST.get('full_name', '')
            phone = request.POST.get('phone', '')
            city = request.POST.get('city', '')
            np_office = request.POST.get('np_office', '')
            pay_type = request.POST.get('pay_type', 'online_full')
            delivery_refs = extract_nova_poshta_refs(request.POST or None)
    else:
        user = None
        full_name = request.POST.get('full_name', '')
        phone = request.POST.get('phone', '')
        city = request.POST.get('city', '')
        np_office = request.POST.get('np_office', '')
        pay_type = request.POST.get('pay_type', 'online_full')
        delivery_refs = extract_nova_poshta_refs(request.POST or None)

    # Validate required fields
    if not all([full_name, phone, city, np_office]):
        messages.error(request, "Будь ласка, заповніть всі обов'язкові поля")
        return redirect('cart')

    # Prepay is disabled when custom items are present
    if approved_custom_leads and pay_type == 'prepay_200':
        messages.error(
            request,
            "Передплата 200 грн недоступна з кастомним принтом. Оберіть повну онлайн-оплату."
        )
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
            apply_nova_poshta_refs(order, delivery_refs)
            order.save()

            # Create Order Items
            total_sum = Decimal('0')

            # Bulk fetch products and variants
            product_ids = [item['product_id'] for item in cart.values()]
            products_map = Product.objects.in_bulk(product_ids)

            variant_ids = [item.get('color_variant_id') for item in cart.values() if item.get('color_variant_id')]
            variants_map = ProductColorVariant.objects.in_bulk(variant_ids)

            order_items = []
            for item in cart.values():
                product = products_map.get(int(item['product_id']))
                if not product:
                    continue

                qty = int(item['qty'])
                price = product.final_price

                variant_id = item.get('color_variant_id')
                variant = variants_map.get(int(variant_id)) if variant_id else None

                order_items.append(OrderItem(
                    order=order,
                    product=product,
                    color_variant=variant,
                    title=product.title,
                    size=item.get('size', 'S'),
                    qty=qty,
                    unit_price=price,
                    line_total=price * qty,
                ))
                total_sum += price * qty

            OrderItem.objects.bulk_create(order_items)

            # Attach approved custom-print leads to this order and add their totals
            for lead in approved_custom_leads:
                try:
                    total_sum += Decimal(str(lead.final_price_value))
                except Exception:
                    pass
                lead.order = order
                lead.save(update_fields=["order"])

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

            # Clear regular cart — approved custom items are now attached to the order.
            clear_cart(request)
            # Keep only unapproved custom items in session so the user can pay them later.
            current_custom = request.session.get(SESSION_CUSTOM_CART_KEY) or {}
            if isinstance(current_custom, dict):
                remaining = {
                    k: v for k, v in current_custom.items()
                    if k in pending_custom_keys
                }
                request.session[SESSION_CUSTOM_CART_KEY] = remaining
                request.session.modified = True

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
    order = get_object_or_404(
        Order.objects.prefetch_related('items__product', 'items__color_variant'),
        id=order_id
    )
    return render(request, 'pages/order_success.html', {'order': order})


def order_success_preview(request):
    """
    Preview for order success page.
    """
    # Create a dummy order for preview
    try:
        last_order = Order.objects.last()
    except Exception:
        last_order = None

    return render(request, 'pages/order_success.html', {'order': last_order})


def order_failed(request):
    return render(request, 'pages/order_failed.html')


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
    return JsonResponse({'price': 0})  # Stub


def handle_payment(request):
    return redirect('cart')
