"""
View для (повторної) відправки листа-квитанції зі сторінки "Замовлення оформлено".

Дозволяє клієнту ввести email уже після оформлення і отримати чек/квитанцію.
Доступ контролюється: для заказів зареєстрованого користувача — лише власнику,
для гостьових — за збігом session_key, інакше 403.
"""

import json
import logging

from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.core.validators import validate_email
from django.core.exceptions import ValidationError

from orders.models import Order
from orders.email_receipt import send_order_receipt_email

logger = logging.getLogger('orders.email_receipt')


def _user_can_access_order(request, order) -> bool:
    """Перевірка прав на відправку квитанції по замовленню."""
    if order.user_id:
        return request.user.is_authenticated and request.user.id == order.user_id
    # Гостьове замовлення — звіряємо session_key
    session_key = request.session.session_key
    if order.session_key and session_key and order.session_key == session_key:
        return True
    # Адмін/стафф завжди може
    return bool(getattr(request.user, 'is_staff', False))


@require_POST
def send_order_receipt(request, order_id):
    """POST /cart/order/<id>/send-receipt/ — надсилає квитанцію на вказаний email."""
    try:
        order = Order.objects.prefetch_related(
            'items__product', 'items__color_variant__images', 'custom_print_leads'
        ).get(id=order_id)
    except Order.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Замовлення не знайдено.'}, status=404)

    if not _user_can_access_order(request, order):
        return JsonResponse({'success': False, 'error': 'Немає доступу до цього замовлення.'}, status=403)

    # Email з тіла запиту
    try:
        body = json.loads(request.body.decode('utf-8')) if request.body else {}
    except Exception:
        body = {}
    email = (body.get('email') or request.POST.get('email') or '').strip()

    if not email:
        return JsonResponse({'success': False, 'error': 'Вкажіть email.'}, status=400)

    try:
        validate_email(email)
    except ValidationError:
        return JsonResponse({'success': False, 'error': 'Невірний формат email.'}, status=400)

    # Зберігаємо email у замовленні, якщо ще не заданий
    if not order.email:
        try:
            order.email = email
            order.save(update_fields=['email'])
        except Exception:
            logger.warning('Failed to persist email on order %s', order.pk)

    ok, err = send_order_receipt_email(order, force=True, recipient=email)
    if not ok:
        logger.warning('Receipt resend failed for order %s: %s', order.pk, err)
        return JsonResponse({
            'success': False,
            'error': 'Не вдалося надіслати лист. Спробуйте пізніше або напишіть нам у Telegram.'
        }, status=500)

    return JsonResponse({'success': True, 'email': email})
