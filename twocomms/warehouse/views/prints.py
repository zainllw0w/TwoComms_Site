"""Принти: список, картка, створення, редагування, коригування."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from storefront.models import Product
from productcolors.models import Color
from warehouse.models import MovementReason, Print, PrintCategory, PrintColorVariant
from warehouse.permissions import warehouse_admin_required
from warehouse.services.inventory import (
    adjust_print_variant,
    set_print_variant_quantity,
)


@warehouse_admin_required
def print_list(request):
    selected_cat = (request.GET.get("category") or "").strip()
    selected_placement = (request.GET.get("placement") or "").strip()
    q = (request.GET.get("q") or "").strip()

    prints = (
        Print.objects.filter(is_active=True)
        .select_related("category")
        .prefetch_related("color_variants", "color_variants__colors", "garment_colors")
        .order_by("category__order", "category__name", "name")
    )
    if selected_cat:
        if selected_cat == "_none":
            prints = prints.filter(category__isnull=True)
        else:
            prints = prints.filter(category__slug=selected_cat)
    if selected_placement:
        prints = prints.filter(placement=selected_placement)
    if q:
        prints = prints.filter(name__icontains=q)

    # Group by category for the cards view
    groups: list[dict] = []
    buckets: dict[int, list] = {}
    cat_objs: dict[int, PrintCategory | None] = {}
    none_key = -1
    for pr in prints:
        key = pr.category_id or none_key
        buckets.setdefault(key, []).append(pr)
        if key != none_key and key not in cat_objs:
            cat_objs[key] = pr.category
    # ordered: by category.order then "no category" last
    for cid in sorted(cat_objs.keys(), key=lambda k: (cat_objs[k].order, cat_objs[k].name)):
        groups.append({"category": cat_objs[cid], "prints": buckets[cid]})
    if none_key in buckets:
        groups.append({"category": None, "prints": buckets[none_key]})

    # Tabs / filter chips
    all_categories = PrintCategory.objects.filter(is_active=True).order_by("order", "name")
    has_uncategorized = Print.objects.filter(is_active=True, category__isnull=True).exists()

    # Placement filter chips — only показуємо ті, що реально використовуються
    used_placements = set(
        Print.objects.filter(is_active=True)
        .exclude(placement="")
        .values_list("placement", flat=True)
    )
    placement_chips = [
        {"value": value, "label": label}
        for value, label in Print.Placement.choices
        if value in used_placements
    ]

    context = {
        "groups": groups,
        "all_categories": all_categories,
        "has_uncategorized": has_uncategorized,
        "selected_cat": selected_cat,
        "selected_placement": selected_placement,
        "placement_chips": placement_chips,
        "query": q,
        "total_count": sum(len(g["prints"]) for g in groups),
        "active_section": "prints",
    }
    return render(request, "warehouse/print_list.html", context)


@warehouse_admin_required
def print_detail(request, slug):
    pr = get_object_or_404(
        Print.objects.prefetch_related(
            "color_variants", "color_variants__colors", "default_products", "garment_colors"
        ),
        slug=slug,
    )
    variants = pr.color_variants.all().order_by("order", "id")
    context = {
        "print": pr,
        "variants": variants,
        "active_section": "prints",
    }
    return render(request, "warehouse/print_detail.html", context)


def _build_product_groups():
    """Повертає список (category_name, [products]) для UI вибору.

    Тільки активні товари, відсортовано по категорії й title. Підтягуємо
    main_image окремо щоб не робити N+1 на колір-варіанти.
    """
    qs = (
        Product.objects.select_related("category")
        .order_by("category__order", "category__name", "title")
    )
    groups: list[tuple[str, list]] = []
    bucket: dict[int, list] = {}
    cat_names: dict[int, str] = {}
    for p in qs:
        cat_id = p.category_id or 0
        cat_names[cat_id] = p.category.name if p.category_id else "Без категорії"
        bucket.setdefault(cat_id, []).append(p)
    for cat_id, items in bucket.items():
        groups.append((cat_names[cat_id], items))
    return groups


@warehouse_admin_required
def print_create(request):
    if request.method == "POST":
        return _save_print(request, instance=None)
    product_groups = _build_product_groups()
    print_categories = PrintCategory.objects.filter(is_active=True).order_by("order", "name")
    context = {
        "product_groups": product_groups,
        "selected_product_ids": set(),
        "print_categories": print_categories,
        "all_colors": Color.objects.all().order_by("name", "primary_hex"),
        "placement_choices": Print.Placement.choices,
        "garment_fit_choices": Print.GarmentFit.choices,
        "color_mode_choices": PrintColorVariant.ColorMode.choices,
        "active_section": "prints",
    }
    return render(request, "warehouse/print_form.html", context)


@warehouse_admin_required
def print_edit(request, slug):
    pr = get_object_or_404(Print, slug=slug)
    if request.method == "POST":
        return _save_print(request, instance=pr)
    product_groups = _build_product_groups()
    selected_product_ids = set(pr.default_products.values_list("id", flat=True))
    print_categories = PrintCategory.objects.filter(is_active=True).order_by("order", "name")
    variants = pr.color_variants.prefetch_related("colors").order_by("order", "id")
    # Per-variant selected color ids (for the picker)
    for v in variants:
        v.selected_color_ids = list(v.colors.values_list("id", flat=True))
    context = {
        "print": pr,
        "variants": variants,
        "product_groups": product_groups,
        "selected_product_ids": selected_product_ids,
        "print_categories": print_categories,
        "all_colors": Color.objects.all().order_by("name", "primary_hex"),
        "placement_choices": Print.Placement.choices,
        "garment_fit_choices": Print.GarmentFit.choices,
        "color_mode_choices": PrintColorVariant.ColorMode.choices,
        "selected_garment_color_ids": set(pr.garment_colors.values_list("id", flat=True)),
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

    # Print category (FK)
    category_id_raw = (request.POST.get("category_id") or "").strip()
    category = None
    if category_id_raw and category_id_raw.isdigit():
        category = PrintCategory.objects.filter(pk=int(category_id_raw)).first()

    # Placement + garment fit
    placement = (request.POST.get("placement") or "").strip()
    valid_placements = {c[0] for c in Print.Placement.choices}
    if placement not in valid_placements:
        placement = ""

    garment_fit = (request.POST.get("garment_fit") or Print.GarmentFit.ANY).strip()
    valid_fits = {c[0] for c in Print.GarmentFit.choices}
    if garment_fit not in valid_fits:
        garment_fit = Print.GarmentFit.ANY

    garment_color_ids = [
        int(x) for x in request.POST.getlist("garment_colors[]") if str(x).isdigit()
    ]

    if instance is None:
        instance = Print(name=name, description=description, is_active=is_active, category=category)
    else:
        instance.name = name
        instance.description = description
        instance.is_active = is_active
        instance.category = category
    instance.placement = placement
    instance.garment_fit = garment_fit

    if request.FILES.get("main_image"):
        instance.main_image = request.FILES["main_image"]

    instance.save()

    if product_ids:
        instance.default_products.set(Product.objects.filter(pk__in=product_ids))
    else:
        instance.default_products.clear()

    # Garment colors (only meaningful for fit == specific, але зберігаємо як є)
    if garment_fit == Print.GarmentFit.SPECIFIC and garment_color_ids:
        instance.garment_colors.set(Color.objects.filter(pk__in=garment_color_ids))
    else:
        instance.garment_colors.clear()

    # Variants (parallel arrays)
    var_ids = request.POST.getlist("variant_id[]")
    var_modes = request.POST.getlist("variant_color_mode[]")
    var_colors = request.POST.getlist("variant_colors[]")  # comma-joined ids per row
    var_qty = request.POST.getlist("variant_quantity[]")
    var_cost = request.POST.getlist("variant_cost[]")
    var_default = request.POST.get("variant_default")  # index str

    valid_modes = {c[0] for c in PrintColorVariant.ColorMode.choices}

    seen_ids = set()
    for idx in range(len(var_qty)):
        mode = (var_modes[idx] if idx < len(var_modes) else "") or PrintColorVariant.ColorMode.SINGLE
        if mode not in valid_modes:
            mode = PrintColorVariant.ColorMode.SINGLE
        vid = var_ids[idx] if idx < len(var_ids) else ""
        colors_raw = var_colors[idx] if idx < len(var_colors) else ""
        color_ids = [int(x) for x in colors_raw.split(",") if x.strip().isdigit()]

        # single/combo вимагають хоча б один колір; mix/standard — ні
        if mode in (PrintColorVariant.ColorMode.SINGLE, PrintColorVariant.ColorMode.COMBO) and not color_ids:
            # порожній рядок — пропускаємо
            continue

        try:
            qty = max(int(var_qty[idx] or 0), 0)
        except (ValueError, IndexError):
            qty = 0
        try:
            cost = Decimal((var_cost[idx] if idx < len(var_cost) else "0") or "0")
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
        variant.color_mode = mode
        variant.cost_price = cost
        variant.order = idx
        variant.is_default = (str(idx) == str(var_default))
        variant.save()

        # M2M colors
        if mode in (PrintColorVariant.ColorMode.SINGLE, PrintColorVariant.ColorMode.COMBO):
            if mode == PrintColorVariant.ColorMode.SINGLE:
                color_ids = color_ids[:1]
            variant.colors.set(Color.objects.filter(pk__in=color_ids))
        else:
            variant.colors.clear()
        # Перерахувати підпис/хекс після оновлення M2M
        variant.sync_color_label(save=True)

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
def print_delete(request, slug):
    """Повне видалення принта разом із варіантами кольорів."""
    pr = get_object_or_404(Print, slug=slug)
    name = pr.name
    pr.delete()  # CASCADE на PrintColorVariant
    messages.success(request, f"Принт «{name}» видалено.")
    return redirect("warehouse:print_list")


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
