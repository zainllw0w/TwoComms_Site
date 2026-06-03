"""Ручне створення замовлень адміністратором.

Дозволяє оператору створити повноцінний :class:`orders.models.Order`
з продажів поза сайтом (Instagram, Bezet, офлайн тощо), переюзовуючи
всю інфраструктуру автоматичних замовлень:

* Нова Пошта — той самий вибір міста/відділення через підписані токени
  (:func:`orders.nova_poshta_checkout.resolve_delivery_selection`), тож
  згодом можна автоматично створити ТТН і вона буде скануватись разом з
  рештою (``NovaPoshtaService.update_all_tracking_statuses``).
* Telegram — те саме сповіщення адмінам з кнопками
  «Створити ТТН / Відправлено / Списати зі складу»
  (:meth:`orders.telegram_notifications.TelegramNotifier.send_new_order_notification`).
* Склад, нарахування балів, статуси — без змін, бо це звичайний ``Order``.

Замовлення позначається ``source='manual'`` + ``created_by`` — щоб у
кастомній адмінці було видно, що воно створене вручну.
"""
from __future__ import annotations

import json
import logging
from decimal import Decimal, InvalidOperation

from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from orders.models import Order, OrderItem
from orders.nova_poshta_checkout import (
    NovaPoshtaSelectionError,
    format_delivery_selection_address,
    resolve_delivery_selection,
)
from orders.nova_poshta_data import apply_nova_poshta_refs
from orders.nova_poshta_documents import normalize_checkout_phone
from orders.telegram_notifications import telegram_notifier
from productcolors.models import ProductColorVariant
from storefront.models import Product, ProductStatus
from storefront.services.size_guides import resolve_product_sizes

logger = logging.getLogger(__name__)

MAX_ITEMS_PER_ORDER = 50
MAX_QTY_PER_ITEM = 999

# Пресети «способу оплати» для UI. Кожен мапиться на канонічну пару
# (pay_type, payment_status), яку розуміють снапшот оплати для ТТН і
# решта системи. Завдяки цьому ТТН/післяплата рахуються коректно.
PAYMENT_PRESETS = {
    'cod': {
        'label': 'Накладений платіж (оплата при отриманні)',
        'pay_type': 'cod',
        'payment_status': 'unpaid',
    },
    'prepaid_200': {
        'label': 'Передплата 200 грн внесена',
        'pay_type': 'prepay_200',
        'payment_status': 'prepaid',
    },
    'paid_full': {
        'label': 'Оплачено повністю',
        'pay_type': 'online_full',
        'payment_status': 'paid',
    },
    'unpaid_full': {
        'label': 'Повна оплата, очікується',
        'pay_type': 'online_full',
        'payment_status': 'unpaid',
    },
    'free': {
        'label': 'Безкоштовно / подарунок',
        'pay_type': 'online_full',
        'payment_status': 'paid',
    },
}
DEFAULT_PAYMENT_PRESET = 'cod'


def _build_products_payload():
    """Серіалізує товари каталогу для вибору в формі (inline JSON).

    Товарів у магазині небагато (десятки), тож віддаємо одразу на сторінку
    і фільтруємо на клієнті — без додаткових запитів до сервера. Кожен
    товар містить ``category`` (id + назва) для групування в пікері.
    """
    products = (
        Product.objects.exclude(status=ProductStatus.ARCHIVED)
        .select_related('category')
        .prefetch_related('color_variants__color', 'color_variants__images')
        .order_by('category__order', 'category__name', 'title')
    )
    payload = []
    for product in products:
        image = product.display_image
        image_url = getattr(image, 'url', '') if image else ''

        variants = []
        for variant in product.color_variants.all():
            color = getattr(variant, 'color', None)
            variants.append({
                'id': variant.id,
                'name': (getattr(color, 'name', '') or '').strip() or 'Колір',
                'primary_hex': getattr(color, 'primary_hex', '') or '',
                'secondary_hex': getattr(color, 'secondary_hex', '') or '',
            })

        try:
            sizes = list(resolve_product_sizes(product))
        except Exception:  # pragma: no cover - захист від нестандартних сіток
            sizes = []

        category = getattr(product, 'category', None)
        payload.append({
            'id': product.id,
            'title': product.title,
            'price': int(product.final_price or 0),
            'image': image_url,
            'sizes': sizes,
            'variants': variants,
            'category_id': getattr(category, 'id', 0) or 0,
            'category_name': (getattr(category, 'name', '') or 'Інше').strip() or 'Інше',
        })
    return payload


def _build_categories_payload():
    """Список активних категорій (для табів пікера), у порядку показу."""
    from storefront.models import Category

    return [
        {'id': c.id, 'name': c.name}
        for c in Category.objects.filter(is_active=True).order_by('order', 'name')
    ]


def _decimal_or_none(raw):
    if raw in (None, ''):
        return None
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if value < 0:
        return None
    return value.quantize(Decimal('0.01'))


def _coerce_int(raw, *, default=1, minimum=1, maximum=MAX_QTY_PER_ITEM):
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(value, maximum))


def _resolve_fit_payload(product, requested_code):
    """Повертає (code, label) обраного крою товару, як у дропшип-формі."""
    try:
        options = list(
            product.fit_options
            .filter(is_active=True)
            .order_by('order', 'id')
            .only('code', 'label', 'is_default')
        )
    except Exception:
        options = []
    if not options:
        return '', ''
    requested = str(requested_code or '').strip().lower()
    selected = next((o for o in options if o.code == requested), None)
    if selected is None:
        selected = next((o for o in options if o.is_default), options[0])
    return selected.code, selected.label


def _build_order_item(raw_item, *, order, products_map, variants_map):
    """Будує (без збереження) OrderItem з одного запису форми.

    Кидає ``ValueError`` з людським повідомленням при некоректних даних.
    """
    kind = str(raw_item.get('kind') or 'catalog').strip()
    qty = _coerce_int(raw_item.get('qty'), default=1)
    size = str(raw_item.get('size') or '').strip()[:16]
    unit_price = _decimal_or_none(raw_item.get('unit_price'))

    if kind == 'custom':
        title = str(raw_item.get('title') or '').strip()
        if not title:
            raise ValueError('Вкажіть назву товару поза каталогом.')
        if unit_price is None:
            raise ValueError(f'Вкажіть коректну ціну для «{title}».')
        color_name = str(raw_item.get('color_name') or '').strip()[:100]
        return OrderItem(
            order=order,
            product=None,
            color_variant=None,
            title=title[:200],
            size=size,
            qty=qty,
            unit_price=unit_price,
            line_total=unit_price * qty,
            is_custom=True,
            color_name_custom=color_name,
        )

    # Каталожна позиція
    try:
        product_id = int(raw_item.get('product_id'))
    except (TypeError, ValueError):
        raise ValueError('Оберіть товар зі списку або додайте позицію вручну.')

    product = products_map.get(product_id)
    if product is None:
        raise ValueError('Обраний товар не знайдено. Оновіть сторінку і спробуйте ще раз.')

    variant = None
    variant_id = raw_item.get('color_variant_id')
    if variant_id:
        try:
            variant = variants_map.get(int(variant_id))
        except (TypeError, ValueError):
            variant = None
        if variant is None or variant.product_id != product.id:
            raise ValueError(f'Невірний колір для товару «{product.title}».')

    if unit_price is None:
        unit_price = Decimal(str(product.final_price or 0)).quantize(Decimal('0.01'))

    fit_code, fit_label = _resolve_fit_payload(product, raw_item.get('fit_option_code') or raw_item.get('fit_option'))

    return OrderItem(
        order=order,
        product=product,
        color_variant=variant,
        title=product.title[:200],
        size=size,
        fit_option_code=fit_code,
        fit_option_label=fit_label,
        qty=qty,
        unit_price=unit_price,
        line_total=unit_price * qty,
        is_custom=False,
    )


def _parse_request_payload(request):
    if request.content_type and 'application/json' in request.content_type:
        try:
            return json.loads(request.body or '{}')
        except (ValueError, TypeError):
            return None
    return request.POST


@staff_member_required
@require_http_methods(["GET", "POST"])
def manual_order_create(request):
    if request.method == 'GET':
        context = {
            'products_json': json.dumps(_build_products_payload(), ensure_ascii=False),
            'categories_json': json.dumps(_build_categories_payload(), ensure_ascii=False),
            'payment_presets': PAYMENT_PRESETS,
            'default_payment_preset': DEFAULT_PAYMENT_PRESET,
            'sale_source_presets': Order.SALE_SOURCE_PRESETS,
        }
        return render(request, 'pages/admin_manual_order.html', context)

    # POST — створення замовлення
    data = _parse_request_payload(request)
    if data is None:
        return JsonResponse({'success': False, 'message': 'Некоректний формат запиту.'}, status=400)

    full_name = str(data.get('full_name') or '').strip()
    raw_phone = str(data.get('phone') or '').strip()
    if not full_name:
        return JsonResponse({'success': False, 'message': 'Вкажіть ПІБ клієнта.'}, status=422)

    phone = normalize_checkout_phone(raw_phone)
    if not phone:
        return JsonResponse(
            {'success': False, 'message': 'Вкажіть коректний український номер телефону. Можна без +380.'},
            status=422,
        )

    # Доставка: або Нова Пошта (з підписаними токенами для авто-ТТН),
    # або ручне введення адреси (без refs — ТТН доведеться робити вручну).
    delivery_method = str(data.get('delivery_method') or 'np').strip()
    delivery_refs = {
        'np_settlement_ref': '',
        'np_city_ref': '',
        'np_warehouse_ref': '',
    }
    delivery_address_display = ''

    if delivery_method == 'manual':
        city = str(data.get('city') or '').strip()[:100]
        np_office = str(data.get('np_office') or '').strip()[:200]
        if not city or not np_office:
            return JsonResponse(
                {'success': False, 'message': 'Вкажіть місто та адресу/відділення доставки.', 'field': 'np_office'},
                status=422,
            )
        delivery_address_display = ', '.join(p for p in (city, np_office) if p)
    else:
        delivery_method = 'np'
        try:
            delivery_selection = resolve_delivery_selection(data)
        except NovaPoshtaSelectionError as exc:
            return JsonResponse({'success': False, 'message': exc.message, 'field': exc.field}, status=422)
        city = delivery_selection.city
        np_office = delivery_selection.np_office
        delivery_refs = {
            'np_settlement_ref': delivery_selection.settlement_ref,
            'np_city_ref': delivery_selection.city_ref,
            'np_warehouse_ref': delivery_selection.warehouse_ref,
        }
        delivery_address_display = format_delivery_selection_address(delivery_selection)

    # Позиції замовлення
    raw_items = data.get('items')
    if isinstance(raw_items, str):
        try:
            raw_items = json.loads(raw_items)
        except (ValueError, TypeError):
            raw_items = None
    if not isinstance(raw_items, list) or not raw_items:
        return JsonResponse({'success': False, 'message': 'Додайте хоча б один товар до замовлення.'}, status=422)
    if len(raw_items) > MAX_ITEMS_PER_ORDER:
        return JsonResponse({'success': False, 'message': 'Забагато позицій у замовленні.'}, status=422)

    preset_key = str(data.get('payment_preset') or DEFAULT_PAYMENT_PRESET).strip()
    preset = PAYMENT_PRESETS.get(preset_key, PAYMENT_PRESETS[DEFAULT_PAYMENT_PRESET])

    sale_source = str(data.get('sale_source') or '').strip()[:120]
    manager_comment = str(data.get('manager_comment') or '').strip()

    # Прев'ялідація позицій — щоб зібрати потрібні id для bulk-запитів
    product_ids = []
    variant_ids = []
    for raw_item in raw_items:
        if str(raw_item.get('kind') or 'catalog').strip() == 'custom':
            continue
        try:
            product_ids.append(int(raw_item.get('product_id')))
        except (TypeError, ValueError):
            continue
        if raw_item.get('color_variant_id'):
            try:
                variant_ids.append(int(raw_item.get('color_variant_id')))
            except (TypeError, ValueError):
                pass

    products_map = Product.objects.in_bulk(product_ids) if product_ids else {}
    variants_map = (
        ProductColorVariant.objects.select_related('color').in_bulk(variant_ids) if variant_ids else {}
    )

    try:
        with transaction.atomic():
            order = Order(
                user=None,
                full_name=full_name[:200],
                phone=phone,
                city=city,
                np_office=np_office,
                pay_type=preset['pay_type'],
                payment_status=preset['payment_status'],
                status='new',
                source='manual',
                created_by=request.user,
                sale_source=sale_source,
                manager_comment=manager_comment,
            )
            apply_nova_poshta_refs(order, delivery_refs)
            order.save()

            order_items = []
            total_sum = Decimal('0')
            for raw_item in raw_items:
                item = _build_order_item(
                    raw_item,
                    order=order,
                    products_map=products_map,
                    variants_map=variants_map,
                )
                order_items.append(item)
                total_sum += item.line_total

            OrderItem.objects.bulk_create(order_items)
            order.total_sum = total_sum
            order.save(update_fields=['total_sum'])
    except ValueError as exc:
        return JsonResponse({'success': False, 'message': str(exc)}, status=422)
    except Exception:
        logger.exception('Failed to create manual order')
        return JsonResponse(
            {'success': False, 'message': 'Не вдалося створити замовлення через внутрішню помилку.'},
            status=500,
        )

    # Telegram-сповіщення адмінам (з кнопками ТТН/Відправлено/Списати зі складу).
    # Не валимо створення замовлення, якщо бот недоступний.
    try:
        telegram_notifier.send_new_order_notification(order)
    except Exception:
        logger.exception('Failed to send Telegram notification for manual order %s', order.pk)

    return JsonResponse({
        'success': True,
        'message': f'Замовлення #{order.order_number} створено.',
        'order_id': order.id,
        'order_number': order.order_number,
        'delivery_address': delivery_address_display,
        'redirect_url': f"{reverse('admin_panel')}?section=orders",
    })
