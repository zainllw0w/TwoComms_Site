"""Списання за замовленням (з токеном з Telegram-кнопки або з UI)."""
from __future__ import annotations

import uuid
from decimal import Decimal

from django.contrib import messages
from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from orders.models import Order, OrderItem
from warehouse.models import (
    MovementReason,
    Print,
    PrintColorVariant,
    StockItem,
    WriteOffRequest,
)
from warehouse.permissions import warehouse_admin_required
from warehouse.services.inventory import (
    adjust_print_variant,
    adjust_stock_item,
)
from warehouse.services.matching import (
    find_default_print_for_order_item,
    find_stock_items_for_order_item,
)


def _get_or_create_request(order: Order) -> WriteOffRequest:
    pending = order.warehouse_write_off_requests.filter(
        status=WriteOffRequest.STATUS_PENDING
    ).first()
    if pending:
        return pending
    return WriteOffRequest.objects.create(order=order)


@warehouse_admin_required
def write_off_entry(request, token):
    """Сторінка списання: показує позиції замовлення, дозволяє обрати підкатегорію + принт."""
    try:
        token_uuid = uuid.UUID(str(token))
    except (ValueError, AttributeError):
        return render(request, "warehouse/write_off_invalid.html", status=400)

    wo_request = get_object_or_404(
        WriteOffRequest.objects.select_related("order"), token=token_uuid
    )
    order = wo_request.order

    if not wo_request.opened_at:
        wo_request.opened_at = timezone.now()
        wo_request.opened_by = request.user
        wo_request.save(update_fields=["opened_at", "opened_by", "updated_at"])

    rows = []
    for item in order.items.select_related("product", "color_variant__color").all():
        candidates = find_stock_items_for_order_item(item)
        default_print = find_default_print_for_order_item(item)
        prints_qs = Print.objects.filter(is_active=True).order_by("name")
        rows.append(
            {
                "item": item,
                "candidates": candidates,
                "default_print": default_print,
                "all_prints": list(prints_qs),
            }
        )

    context = {
        "wo_request": wo_request,
        "order": order,
        "rows": rows,
        "active_section": "write_off",
    }
    return render(request, "warehouse/write_off.html", context)


@warehouse_admin_required
@require_POST
def write_off_submit(request, token):
    try:
        token_uuid = uuid.UUID(str(token))
    except (ValueError, AttributeError):
        return HttpResponseBadRequest("invalid token")

    wo_request = get_object_or_404(WriteOffRequest, token=token_uuid)
    if wo_request.status != WriteOffRequest.STATUS_PENDING:
        messages.warning(request, "Цей запит на списання вже оброблено.")
        return redirect("warehouse:write_off", token=wo_request.token)

    order = wo_request.order
    actions = []

    for item in order.items.all():
        prefix = f"item_{item.pk}_"
        stock_id_raw = request.POST.get(prefix + "stock_id") or ""
        qty_raw = request.POST.get(prefix + "qty") or "0"
        print_variant_raw = request.POST.get(prefix + "print_variant_id") or ""
        try:
            qty = int(qty_raw)
        except ValueError:
            qty = 0
        if qty <= 0:
            continue

        # списуємо StockItem
        if stock_id_raw and stock_id_raw.isdigit():
            try:
                stock_item = StockItem.objects.get(pk=int(stock_id_raw))
            except StockItem.DoesNotExist:
                stock_item = None
            if stock_item is not None:
                try:
                    adjust_stock_item(
                        stock_item=stock_item,
                        delta=-qty,
                        user=request.user,
                        reason=MovementReason.ORDER_WRITE_OFF,
                        comment=f"Замовлення #{order.order_number}",
                        order=order,
                        write_off_request=wo_request,
                    )
                    actions.append(f"одяг {stock_item.subcategory.name} {stock_item.size} ×{qty}")
                except ValueError as exc:
                    messages.error(request, f"Помилка списання одягу: {exc}")

        # списуємо PrintColorVariant
        if print_variant_raw and print_variant_raw.isdigit():
            try:
                variant = PrintColorVariant.objects.get(pk=int(print_variant_raw))
            except PrintColorVariant.DoesNotExist:
                variant = None
            if variant is not None:
                try:
                    adjust_print_variant(
                        variant=variant,
                        delta=-qty,
                        user=request.user,
                        reason=MovementReason.PRINT_REMOVE,
                        comment=f"Замовлення #{order.order_number}",
                    )
                    actions.append(f"принт {variant.print.name}/{variant.color_name} ×{qty}")
                except ValueError as exc:
                    messages.error(request, f"Помилка списання принта: {exc}")

    wo_request.status = WriteOffRequest.STATUS_COMPLETED
    wo_request.completed_at = timezone.now()
    wo_request.completed_by = request.user
    wo_request.save(update_fields=["status", "completed_at", "completed_by", "updated_at"])

    if actions:
        messages.success(request, "Списано: " + ", ".join(actions))
    else:
        messages.info(request, "Жодних позицій не списано (всі поля пусті).")
    return redirect("warehouse:dashboard")
