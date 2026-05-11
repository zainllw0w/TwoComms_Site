"""Settings UI для warehouse — категорії, підкатегорії, розміри, кольори."""
from __future__ import annotations

import re

from django.contrib import messages
from django.db.models import Count, Sum
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from productcolors.models import Color

from warehouse.models import (
    StorageCategory,
    StorageSubcategory,
)
from warehouse.permissions import warehouse_admin_required


_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def _parse_sizes(raw: str | None) -> list[str]:
    """Розбиває рядок розмірів (CSV або з нових рядків) у список без дублікатів."""
    if not raw:
        return []
    tokens = re.split(r"[,\n\r;]+", raw)
    seen: list[str] = []
    for t in tokens:
        t = t.strip()
        if t and t not in seen:
            seen.append(t)
    return seen


def _normalize_hex(value: str | None) -> str:
    if not value:
        return ""
    value = value.strip()
    if not value:
        return ""
    if not value.startswith("#"):
        value = "#" + value
    return value if _HEX_RE.match(value) else ""


# ---------------------------------------------------------------------------
# Index / dashboard
# ---------------------------------------------------------------------------


@warehouse_admin_required
def settings_index(request):
    """Дашборд налаштувань — посилання на всі секції з лічильниками."""
    categories_count = StorageCategory.objects.count()
    categories_active = StorageCategory.objects.filter(is_active=True).count()
    subcategories_count = StorageSubcategory.objects.count()
    subcategories_active = StorageSubcategory.objects.filter(is_active=True).count()
    colors_count = Color.objects.count()

    context = {
        "active_section": "settings",
        "stats": {
            "categories": categories_count,
            "categories_active": categories_active,
            "subcategories": subcategories_count,
            "subcategories_active": subcategories_active,
            "colors": colors_count,
        },
    }
    return render(request, "warehouse/settings/index.html", context)


# ---------------------------------------------------------------------------
# Categories CRUD
# ---------------------------------------------------------------------------


@warehouse_admin_required
def settings_categories(request):
    categories = (
        StorageCategory.objects.all()
        .annotate(
            sub_count=Count("subcategories", distinct=True),
            stock_total=Sum("subcategories__stock_items__quantity"),
        )
        .order_by("-is_active", "order", "name")
    )
    # Storefront categories doplnit option list pro select
    try:
        from storefront.models import Category as StorefrontCategory

        storefront_categories = list(StorefrontCategory.objects.order_by("title"))
    except Exception:
        storefront_categories = []

    context = {
        "categories": categories,
        "storefront_categories": storefront_categories,
        "active_section": "settings",
    }
    return render(request, "warehouse/settings/categories.html", context)


@warehouse_admin_required
def settings_category_form(request, slug: str | None = None):
    """Створення або редагування StorageCategory."""
    instance = get_object_or_404(StorageCategory, slug=slug) if slug else None

    try:
        from storefront.models import Category as StorefrontCategory

        storefront_categories = list(StorefrontCategory.objects.order_by("title"))
    except Exception:
        storefront_categories = []

    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        if not name:
            messages.error(request, "Назва обовʼязкова")
            return redirect(request.path)

        icon = (request.POST.get("icon") or "").strip()[:64]
        order = int(request.POST.get("order") or 0)
        is_active = request.POST.get("is_active") == "on"

        sf_id_raw = (request.POST.get("linked_storefront_category") or "").strip()
        linked = None
        if sf_id_raw:
            try:
                from storefront.models import Category as StorefrontCategory

                linked = StorefrontCategory.objects.filter(pk=int(sf_id_raw)).first()
            except (ValueError, Exception):
                linked = None

        sizes = _parse_sizes(request.POST.get("sizes"))

        if instance is None:
            instance = StorageCategory(name=name)
        else:
            instance.name = name
        instance.icon = icon
        instance.order = order
        instance.is_active = is_active
        instance.linked_storefront_category = linked
        instance.sizes = sizes
        instance.save()

        messages.success(request, f"Категорію «{instance.name}» збережено")
        return redirect("warehouse:settings_categories")

    context = {
        "instance": instance,
        "storefront_categories": storefront_categories,
        "active_section": "settings",
        "default_sizes": ", ".join(StorageCategory.DEFAULT_SIZES),
    }
    return render(request, "warehouse/settings/category_form.html", context)


@warehouse_admin_required
@require_POST
def settings_category_toggle(request, slug: str):
    instance = get_object_or_404(StorageCategory, slug=slug)
    instance.is_active = not instance.is_active
    instance.save(update_fields=["is_active"])
    messages.success(
        request,
        f"Категорія «{instance.name}» {'активована' if instance.is_active else 'прихована'}",
    )
    return redirect("warehouse:settings_categories")


# ---------------------------------------------------------------------------
# Subcategories CRUD
# ---------------------------------------------------------------------------


@warehouse_admin_required
def settings_subcategories(request):
    category_slug = request.GET.get("category") or ""
    categories = StorageCategory.objects.order_by("order", "name")
    selected_category = None
    if category_slug:
        selected_category = StorageCategory.objects.filter(slug=category_slug).first()

    qs = StorageSubcategory.objects.select_related("category").annotate(
        stock_total=Sum("stock_items__quantity"),
        stock_lines=Count("stock_items", distinct=True),
    )
    if selected_category:
        qs = qs.filter(category=selected_category)
    qs = qs.order_by("-is_active", "category__order", "order", "name")

    context = {
        "subcategories": qs,
        "categories": categories,
        "selected_category": selected_category,
        "active_section": "settings",
    }
    return render(request, "warehouse/settings/subcategories.html", context)


@warehouse_admin_required
def settings_subcategory_form(request, pk: int | None = None):
    instance = get_object_or_404(StorageSubcategory, pk=pk) if pk else None
    categories = StorageCategory.objects.filter(is_active=True).order_by("order", "name")
    if not categories.exists():
        messages.error(request, "Спочатку створіть хоча б одну категорію")
        return redirect("warehouse:settings_categories")

    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        category_id_raw = request.POST.get("category_id")
        if not name or not category_id_raw:
            messages.error(request, "Назва та категорія обовʼязкові")
            return redirect(request.path)
        try:
            category = StorageCategory.objects.get(pk=int(category_id_raw))
        except (ValueError, StorageCategory.DoesNotExist):
            messages.error(request, "Категорію не знайдено")
            return redirect(request.path)

        description = (request.POST.get("description") or "").strip()[:255]
        order = int(request.POST.get("order") or 0)
        is_active = request.POST.get("is_active") == "on"
        is_default = request.POST.get("is_default") == "on"

        if instance is None:
            instance = StorageSubcategory(category=category, name=name)
        else:
            instance.category = category
            instance.name = name
        instance.description = description
        instance.order = order
        instance.is_active = is_active
        instance.is_default = is_default
        instance.save()

        messages.success(request, f"Підкатегорію «{instance.name}» збережено")
        return redirect(f"{reverse('warehouse:settings_subcategories')}?category={category.slug}")

    context = {
        "instance": instance,
        "categories": categories,
        "active_section": "settings",
    }
    return render(request, "warehouse/settings/subcategory_form.html", context)


@warehouse_admin_required
@require_POST
def settings_subcategory_toggle(request, pk: int):
    instance = get_object_or_404(StorageSubcategory, pk=pk)
    instance.is_active = not instance.is_active
    instance.save(update_fields=["is_active"])
    messages.success(
        request,
        f"Підкатегорія «{instance.name}» {'активована' if instance.is_active else 'прихована'}",
    )
    return redirect(
        f"{reverse('warehouse:settings_subcategories')}?category={instance.category.slug}"
    )


# ---------------------------------------------------------------------------
# Colors CRUD (warehouse can create colors that are NOT used on site)
# ---------------------------------------------------------------------------


@warehouse_admin_required
def settings_colors(request):
    colors = Color.objects.all().annotate(
        used_on_site=Count("variants", distinct=True),
        used_warehouse=Count("warehouse_stock_items", distinct=True),
    ).order_by("name", "primary_hex")
    context = {
        "colors": colors,
        "active_section": "settings",
    }
    return render(request, "warehouse/settings/colors.html", context)


@warehouse_admin_required
def settings_color_form(request, pk: int | None = None):
    instance = get_object_or_404(Color, pk=pk) if pk else None

    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()[:100]
        primary = _normalize_hex(request.POST.get("primary_hex"))
        secondary_raw = (request.POST.get("secondary_hex") or "").strip()
        secondary = _normalize_hex(secondary_raw) if secondary_raw else ""

        if not primary:
            messages.error(request, "Основний HEX обовʼязковий і має бути у форматі #RRGGBB")
            return redirect(request.path)

        if not name:
            # name дефолтиться до хексу
            name = primary

        # Перевірка унікальності (primary, secondary)
        qs = Color.objects.filter(primary_hex=primary, secondary_hex=secondary or None)
        if instance:
            qs = qs.exclude(pk=instance.pk)
        if qs.exists():
            messages.error(request, "Такий колір (primary+secondary) вже існує")
            return redirect(request.path)

        if instance is None:
            instance = Color(primary_hex=primary)
        else:
            instance.primary_hex = primary
        instance.name = name
        instance.secondary_hex = secondary or None
        instance.save()
        messages.success(request, f"Колір «{instance.name}» збережено")
        return redirect("warehouse:settings_colors")

    context = {
        "instance": instance,
        "active_section": "settings",
    }
    return render(request, "warehouse/settings/color_form.html", context)


@warehouse_admin_required
@require_POST
def settings_color_create_ajax(request):
    """AJAX endpoint для inline-створення кольору з bulk_add сторінки."""
    name = (request.POST.get("name") or "").strip()[:100]
    primary = _normalize_hex(request.POST.get("primary_hex"))
    secondary_raw = (request.POST.get("secondary_hex") or "").strip()
    secondary = _normalize_hex(secondary_raw) if secondary_raw else ""

    if not primary:
        return JsonResponse({"ok": False, "error": "Невалідний primary_hex"}, status=400)

    if not name:
        name = primary

    existing = Color.objects.filter(primary_hex=primary, secondary_hex=secondary or None).first()
    if existing:
        return JsonResponse(
            {
                "ok": True,
                "id": existing.pk,
                "name": existing.name or existing.primary_hex,
                "primary_hex": existing.primary_hex,
                "secondary_hex": existing.secondary_hex or "",
                "created": False,
            }
        )

    color = Color.objects.create(
        name=name, primary_hex=primary, secondary_hex=secondary or None
    )
    return JsonResponse(
        {
            "ok": True,
            "id": color.pk,
            "name": color.name or color.primary_hex,
            "primary_hex": color.primary_hex,
            "secondary_hex": color.secondary_hex or "",
            "created": True,
        }
    )
