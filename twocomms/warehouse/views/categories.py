"""Категорії: список, деталь, швидке коригування, масове додавання."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from productcolors.models import Color
from warehouse.models import (
    MovementReason,
    StockItem,
    StorageCategory,
    StorageSubcategory,
)
from warehouse.permissions import warehouse_admin_required
from warehouse.services.inventory import (
    adjust_stock_item,
    set_stock_quantity,
)
from warehouse.services.matching import stock_matrix_for_category


@warehouse_admin_required
def category_list(request):
    categories = StorageCategory.objects.filter(is_active=True).order_by("order", "name")
    context = {
        "categories": categories,
        "active_section": "categories",
    }
    return render(request, "warehouse/category_list.html", context)


@warehouse_admin_required
def category_detail(request, slug):
    category = get_object_or_404(StorageCategory, slug=slug)
    matrix = stock_matrix_for_category(category)
    subcategories = category.subcategories.filter(is_active=True).order_by("order", "name")
    colors = (
        Color.objects.filter(warehouse_stock_items__subcategory__category=category)
        .distinct()
        .order_by("name")
    )
    context = {
        "category": category,
        "matrix": matrix,
        "subcategories": subcategories,
        "colors": colors,
        "active_section": "categories",
    }
    return render(request, "warehouse/category_detail.html", context)


@warehouse_admin_required
@require_POST
def stock_adjust(request):
    """AJAX endpoint: змінити кількість StockItem (delta або абсолютна)."""
    try:
        subcategory_id = int(request.POST.get("subcategory_id") or 0)
        size = (request.POST.get("size") or "").strip()
        color_id_raw = request.POST.get("color_id") or ""
        color_id = int(color_id_raw) if color_id_raw not in ("", "null", "0") else None
        mode = request.POST.get("mode", "delta")  # delta | set
        delta = int(request.POST.get("delta") or 0)
        quantity = int(request.POST.get("quantity") or 0)
        cost_price_raw = request.POST.get("cost_price")
        cost_price: Decimal | None = None
        if cost_price_raw not in (None, ""):
            try:
                cost_price = Decimal(cost_price_raw)
            except (InvalidOperation, ValueError):
                cost_price = None
        reason = request.POST.get("reason") or MovementReason.MANUAL_ADD
        comment = (request.POST.get("comment") or "").strip()[:255]
    except (ValueError, TypeError):
        return HttpResponseBadRequest("invalid params")

    if not subcategory_id or not size:
        return HttpResponseBadRequest("subcategory_id and size are required")

    subcategory = get_object_or_404(StorageSubcategory, pk=subcategory_id)
    color = None
    if color_id:
        color = get_object_or_404(Color, pk=color_id)

    stock_item, _ = StockItem.objects.get_or_create(
        subcategory=subcategory,
        size=size,
        color=color,
        defaults={"quantity": 0, "cost_price": cost_price or Decimal("0.00")},
    )

    try:
        if mode == "set":
            movement = set_stock_quantity(
                stock_item=stock_item,
                new_quantity=quantity,
                user=request.user,
                reason=reason,
                comment=comment,
                cost_price_override=cost_price,
            )
        else:
            if delta == 0:
                return JsonResponse(
                    {"ok": True, "quantity": stock_item.quantity, "movement_id": None}
                )
            movement = adjust_stock_item(
                stock_item=stock_item,
                delta=delta,
                user=request.user,
                reason=reason,
                comment=comment,
                cost_price_override=cost_price,
            )
    except ValueError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)

    return JsonResponse(
        {
            "ok": True,
            "stock_item_id": stock_item.pk,
            "quantity": stock_item.quantity,
            "cost_price": str(stock_item.cost_price),
            "movement_id": movement.pk if movement else None,
        }
    )


@warehouse_admin_required
def stock_bulk_add(request, slug):
    """Швидке масове додавання партії в категорію."""
    category = get_object_or_404(StorageCategory, slug=slug)
    subcategories = category.subcategories.filter(is_active=True).order_by("order", "name")
    colors = Color.objects.all().order_by("name")

    if request.method == "POST":
        subcategory_id = int(request.POST.get("subcategory_id") or 0)
        rows_added = 0
        try:
            subcategory = StorageSubcategory.objects.get(pk=subcategory_id, category=category)
        except StorageSubcategory.DoesNotExist:
            messages.error(request, "Підкатегорію не знайдено")
            return redirect("warehouse:category_bulk_add", slug=slug)

        cost_price_raw = request.POST.get("cost_price") or "0"
        try:
            cost_price = Decimal(cost_price_raw)
        except (InvalidOperation, ValueError):
            cost_price = Decimal("0")

        comment = (request.POST.get("comment") or "").strip()[:255]

        # rows are sent as parallel arrays: size[], color_id[], quantity[]
        sizes = request.POST.getlist("size[]")
        color_ids = request.POST.getlist("color_id[]")
        quantities = request.POST.getlist("quantity[]")
        for size, color_id_raw, qty_raw in zip(sizes, color_ids, quantities):
            size = (size or "").strip()
            try:
                qty = int(qty_raw or 0)
            except ValueError:
                qty = 0
            if not size or qty <= 0:
                continue
            color = None
            if color_id_raw and color_id_raw != "0":
                try:
                    color = Color.objects.get(pk=int(color_id_raw))
                except (Color.DoesNotExist, ValueError):
                    color = None
            stock_item, _ = StockItem.objects.get_or_create(
                subcategory=subcategory,
                size=size,
                color=color,
                defaults={"quantity": 0, "cost_price": cost_price},
            )
            try:
                adjust_stock_item(
                    stock_item=stock_item,
                    delta=qty,
                    user=request.user,
                    reason=MovementReason.BULK_ADD,
                    comment=comment,
                    cost_price_override=cost_price if cost_price > 0 else None,
                )
                rows_added += 1
            except ValueError as exc:
                messages.error(request, str(exc))

        if rows_added:
            messages.success(request, f"Додано {rows_added} рядків у партію.")
        return redirect("warehouse:category_detail", slug=slug)

    context = {
        "category": category,
        "subcategories": subcategories,
        "colors": colors,
        "active_section": "categories",
    }
    return render(request, "warehouse/stock_bulk_add.html", context)
