"""Принти: список, картка, створення, редагування, коригування."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from storefront.models import Product
from warehouse.models import MovementReason, Print, PrintColorVariant
from warehouse.permissions import warehouse_admin_required
from warehouse.services.inventory import (
    adjust_print_variant,
    set_print_variant_quantity,
)


@warehouse_admin_required
def print_list(request):
    prints = Print.objects.filter(is_active=True).order_by("name").prefetch_related(
        "color_variants"
    )
    context = {
        "prints": prints,
        "active_section": "prints",
    }
    return render(request, "warehouse/print_list.html", context)


@warehouse_admin_required
def print_detail(request, slug):
    pr = get_object_or_404(Print.objects.prefetch_related("color_variants", "default_products"), slug=slug)
    variants = pr.color_variants.all().order_by("order", "id")
    context = {
        "print": pr,
        "variants": variants,
        "active_section": "prints",
    }
    return render(request, "warehouse/print_detail.html", context)


@warehouse_admin_required
def print_create(request):
    if request.method == "POST":
        return _save_print(request, instance=None)
    products = Product.objects.all().order_by("title")[:500]
    context = {
        "products": products,
        "active_section": "prints",
    }
    return render(request, "warehouse/print_form.html", context)


@warehouse_admin_required
def print_edit(request, slug):
    pr = get_object_or_404(Print, slug=slug)
    if request.method == "POST":
        return _save_print(request, instance=pr)
    products = Product.objects.all().order_by("title")[:500]
    selected_product_ids = list(pr.default_products.values_list("id", flat=True))
    context = {
        "print": pr,
        "variants": pr.color_variants.order_by("order", "id"),
        "products": products,
        "selected_product_ids": selected_product_ids,
        "active_section": "prints",
    }
    return render(request, "warehouse/print_form.html", context)


def _save_print(request, instance):
    name = (request.POST.get("name") or "").strip()
    if not name:
        messages.error(request, "Назва принта обовʼязкова")
        return redirect("warehouse:print_create")

    description = (request.POST.get("description") or "").strip()
    is_active = bool(request.POST.get("is_active"))
    product_ids = [int(x) for x in request.POST.getlist("default_products[]") if x.isdigit()]

    if instance is None:
        instance = Print(name=name, description=description, is_active=is_active)
    else:
        instance.name = name
        instance.description = description
        instance.is_active = is_active

    if request.FILES.get("main_image"):
        instance.main_image = request.FILES["main_image"]

    instance.save()

    if product_ids:
        instance.default_products.set(Product.objects.filter(pk__in=product_ids))
    else:
        instance.default_products.clear()

    # Variants (parallel arrays)
    var_ids = request.POST.getlist("variant_id[]")
    var_names = request.POST.getlist("variant_color_name[]")
    var_hex = request.POST.getlist("variant_color_hex[]")
    var_qty = request.POST.getlist("variant_quantity[]")
    var_cost = request.POST.getlist("variant_cost[]")
    var_default = request.POST.get("variant_default")  # index str

    seen_ids = set()
    for idx, (vid, vname, vhex, vqty, vcost) in enumerate(
        zip(var_ids, var_names, var_hex, var_qty, var_cost)
    ):
        vname = (vname or "").strip()
        if not vname:
            continue
        try:
            qty = max(int(vqty or 0), 0)
        except ValueError:
            qty = 0
        try:
            cost = Decimal(vcost or "0")
        except (InvalidOperation, ValueError):
            cost = Decimal("0")

        if vid and vid.isdigit():
            try:
                variant = PrintColorVariant.objects.get(pk=int(vid), print=instance)
            except PrintColorVariant.DoesNotExist:
                variant = PrintColorVariant(print=instance)
        else:
            variant = PrintColorVariant(print=instance)

        previous_qty = variant.quantity if variant.pk else 0
        variant.color_name = vname
        variant.color_hex = (vhex or "").strip()
        variant.cost_price = cost
        variant.order = idx
        variant.is_default = (str(idx) == str(var_default))
        variant.save()
        if qty != previous_qty:
            delta = qty - previous_qty
            try:
                adjust_print_variant(
                    variant=variant,
                    delta=delta,
                    user=request.user,
                    reason=MovementReason.PRINT_ADD if delta > 0 else MovementReason.PRINT_REMOVE,
                    comment="Через форму редагування",
                    cost_price_override=cost,
                )
            except ValueError:
                pass
        seen_ids.add(variant.pk)

    # delete variants not in the form
    instance.color_variants.exclude(pk__in=seen_ids).delete()

    messages.success(request, f"Принт «{instance.name}» збережено.")
    return redirect("warehouse:print_detail", slug=instance.slug)


@warehouse_admin_required
@require_POST
def print_adjust(request):
    """AJAX endpoint: +/- variant or set absolute."""
    try:
        variant_id = int(request.POST.get("variant_id") or 0)
        mode = request.POST.get("mode", "delta")
        delta = int(request.POST.get("delta") or 0)
        quantity = int(request.POST.get("quantity") or 0)
    except (ValueError, TypeError):
        return HttpResponseBadRequest("invalid")
    if not variant_id:
        return HttpResponseBadRequest("variant_id required")

    variant = get_object_or_404(PrintColorVariant, pk=variant_id)

    cost_price_raw = request.POST.get("cost_price")
    cost_price: Decimal | None = None
    if cost_price_raw not in (None, ""):
        try:
            cost_price = Decimal(cost_price_raw)
        except (InvalidOperation, ValueError):
            cost_price = None
    comment = (request.POST.get("comment") or "").strip()[:255]

    try:
        if mode == "set":
            movement = set_print_variant_quantity(
                variant=variant,
                new_quantity=quantity,
                user=request.user,
                comment=comment,
                cost_price_override=cost_price,
            )
        else:
            if delta == 0:
                return JsonResponse({"ok": True, "quantity": variant.quantity})
            movement = adjust_print_variant(
                variant=variant,
                delta=delta,
                user=request.user,
                reason=MovementReason.PRINT_ADD if delta > 0 else MovementReason.PRINT_REMOVE,
                comment=comment,
                cost_price_override=cost_price,
            )
    except ValueError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)

    return JsonResponse(
        {
            "ok": True,
            "variant_id": variant.pk,
            "quantity": variant.quantity,
            "cost_price": str(variant.cost_price),
            "movement_id": movement.pk if movement else None,
        }
    )
