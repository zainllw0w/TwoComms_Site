"""Settings UI для warehouse — категорії, підкатегорії, розміри, кольори."""
from __future__ import annotations

import re

from django.contrib import messages
from django.db.models import Count, Q, Sum
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from productcolors.models import Color

from warehouse.models import (
    ConsumableCategory,
    PrintCategory,
    StorageCategory,
    StorageSubcategory,
)
from warehouse.permissions import warehouse_admin_required
from warehouse.services.telegram_storage import (
    build_evening_reminder_keyboard,
    build_evening_reminder_text,
    get_admin_chat_ids,
    get_bot_token,
    send_message,
)


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
    print_categories_count = PrintCategory.objects.count()
    print_categories_active = PrintCategory.objects.filter(is_active=True).count()
    consumable_categories_count = ConsumableCategory.objects.count()
    consumable_categories_active = ConsumableCategory.objects.filter(is_active=True).count()

    # Telegram bot status
    bot_token_set = bool(get_bot_token())
    bot_chat_ids_count = len(get_admin_chat_ids()) if bot_token_set else 0

    context = {
        "active_section": "settings",
        "stats": {
            "categories": categories_count,
            "categories_active": categories_active,
            "subcategories": subcategories_count,
            "subcategories_active": subcategories_active,
            "colors": colors_count,
            "print_categories": print_categories_count,
            "print_categories_active": print_categories_active,
            "consumable_categories": consumable_categories_count,
            "consumable_categories_active": consumable_categories_active,
            "bot_token_set": bot_token_set,
            "bot_chat_ids_count": bot_chat_ids_count,
        },
    }
    return render(request, "warehouse/settings/index.html", context)


# ---------------------------------------------------------------------------
# Print categories CRUD
# ---------------------------------------------------------------------------


@warehouse_admin_required
def settings_print_categories(request):
    categories = (
        PrintCategory.objects.all()
        .annotate(active_count=Count("prints", filter=Q(prints__is_active=True)))
        .order_by("-is_active", "order", "name")
    )
    context = {
        "categories": categories,
        "active_section": "settings",
    }
    return render(request, "warehouse/settings/print_categories.html", context)


@warehouse_admin_required
def settings_print_category_form(request, pk: int | None = None):
    instance = get_object_or_404(PrintCategory, pk=pk) if pk else None

    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        if not name:
            messages.error(request, "Назва обов'язкова")
            return redirect(request.path)
        icon = (request.POST.get("icon") or "").strip()[:8]
        description = (request.POST.get("description") or "").strip()[:255]
        order = int(request.POST.get("order") or 0)
        is_active = request.POST.get("is_active") == "on"

        if instance is None:
            instance = PrintCategory(name=name)
        else:
            instance.name = name
        instance.icon = icon
        instance.description = description
        instance.order = order
        instance.is_active = is_active
        instance.save()

        messages.success(request, f"Категорію «{instance.name}» збережено")
        return redirect("warehouse:settings_print_categories")

    context = {
        "instance": instance,
        "active_section": "settings",
    }
    return render(request, "warehouse/settings/print_category_form.html", context)


@warehouse_admin_required
@require_POST
def settings_print_category_toggle(request, pk: int):
    instance = get_object_or_404(PrintCategory, pk=pk)
    instance.is_active = not instance.is_active
    instance.save(update_fields=["is_active", "updated_at"])
    messages.success(
        request,
        f"Категорія «{instance.name}» {'активна' if instance.is_active else 'прихована'}",
    )
    return redirect("warehouse:settings_print_categories")


@warehouse_admin_required
@require_POST
def settings_print_category_delete(request, pk: int):
    instance = get_object_or_404(PrintCategory, pk=pk)
    name = instance.name
    # SET_NULL на Print.category — принти не зникнуть, лише втратять категорію.
    affected = instance.prints.count()
    instance.delete()
    if affected:
        messages.success(
            request,
            f"Категорію «{name}» видалено. {affected} принт(ів) лишилися без категорії.",
        )
    else:
        messages.success(request, f"Категорію «{name}» видалено.")
    return redirect("warehouse:settings_print_categories")


# ---------------------------------------------------------------------------
# Consumable categories CRUD
# ---------------------------------------------------------------------------


@warehouse_admin_required
def settings_consumable_categories(request):
    categories = (
        ConsumableCategory.objects.all()
        .annotate(item_count=Count("items"))
        .order_by("-is_active", "order", "name")
    )
    context = {
        "categories": categories,
        "active_section": "settings",
    }
    return render(request, "warehouse/settings/consumable_categories.html", context)


@warehouse_admin_required
def settings_consumable_category_form(request, pk: int | None = None):
    instance = get_object_or_404(ConsumableCategory, pk=pk) if pk else None

    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        if not name:
            messages.error(request, "Назва обов'язкова")
            return redirect(request.path)
        icon = (request.POST.get("icon") or "").strip()[:8]
        order = int(request.POST.get("order") or 0)
        is_active = request.POST.get("is_active") == "on"

        if instance is None:
            instance = ConsumableCategory(name=name)
        else:
            instance.name = name
        instance.icon = icon
        instance.order = order
        instance.is_active = is_active
        instance.save()

        messages.success(request, f"Категорію «{instance.name}» збережено")
        return redirect("warehouse:settings_consumable_categories")

    context = {
        "instance": instance,
        "active_section": "settings",
    }
    return render(request, "warehouse/settings/consumable_category_form.html", context)


@warehouse_admin_required
@require_POST
def settings_consumable_category_toggle(request, pk: int):
    instance = get_object_or_404(ConsumableCategory, pk=pk)
    instance.is_active = not instance.is_active
    instance.save(update_fields=["is_active", "updated_at"])
    messages.success(
        request,
        f"Категорія «{instance.name}» {'активна' if instance.is_active else 'прихована'}",
    )
    return redirect("warehouse:settings_consumable_categories")


@warehouse_admin_required
@require_POST
def settings_consumable_category_delete(request, pk: int):
    instance = get_object_or_404(ConsumableCategory, pk=pk)
    name = instance.name
    # PROTECT на ConsumableItem.category_fk — не даємо видалити з позиціями.
    items_count = instance.items.count()
    if items_count:
        messages.error(
            request,
            f"Не можна видалити «{name}»: до неї прив'язано {items_count} позицій. "
            f"Спершу перенесіть або видаліть розхідники цієї категорії.",
        )
        return redirect("warehouse:settings_consumable_categories")
    instance.delete()
    messages.success(request, f"Категорію «{name}» видалено.")
    return redirect("warehouse:settings_consumable_categories")


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


@warehouse_admin_required
@require_POST
def settings_category_delete(request, slug: str):
    instance = get_object_or_404(StorageCategory, slug=slug)
    name = instance.name
    # StockItem має PROTECT на subcategory → рахуємо залишки, щоб не зламати облік.
    from warehouse.models import StockItem

    stock_lines = StockItem.objects.filter(subcategory__category=instance).count()
    if stock_lines:
        messages.error(
            request,
            f"Не можна видалити «{name}»: у її кроях є {stock_lines} складських позицій. "
            f"Спершу обнуліть/видаліть залишки або приховайте категорію.",
        )
        return redirect("warehouse:settings_categories")
    # Підкатегорії без позицій можна видалити каскадно.
    sub_count = instance.subcategories.count()
    instance.delete()
    messages.success(
        request,
        f"Категорію «{name}» видалено разом із {sub_count} кроями." if sub_count
        else f"Категорію «{name}» видалено.",
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

    all_colors = Color.objects.all().order_by("name", "primary_hex")
    selected_color_ids = (
        list(instance.colors.values_list("id", flat=True)) if instance else []
    )

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

        # Зчитуємо обрані кольори
        color_ids_raw = request.POST.getlist("color_ids")
        color_ids: list[int] = []
        for cid in color_ids_raw:
            try:
                color_ids.append(int(cid))
            except (ValueError, TypeError):
                continue

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

        # Sync M2M колірів
        if color_ids:
            instance.colors.set(Color.objects.filter(pk__in=color_ids))
        else:
            instance.colors.clear()

        messages.success(request, f"Підкатегорію «{instance.name}» збережено")
        return redirect(f"{reverse('warehouse:settings_subcategories')}?category={category.slug}")

    context = {
        "instance": instance,
        "categories": categories,
        "all_colors": all_colors,
        "selected_color_ids": set(selected_color_ids),
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


@warehouse_admin_required
@require_POST
def settings_subcategory_delete(request, pk: int):
    instance = get_object_or_404(StorageSubcategory, pk=pk)
    name = instance.name
    category_slug = instance.category.slug
    stock_lines = instance.stock_items.count()
    if stock_lines:
        messages.error(
            request,
            f"Не можна видалити крій «{name}»: на ньому {stock_lines} складських позицій. "
            f"Спершу обнуліть/видаліть залишки або приховайте крій.",
        )
    else:
        instance.delete()
        messages.success(request, f"Крій «{name}» видалено.")
    return redirect(f"{reverse('warehouse:settings_subcategories')}?category={category_slug}")


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


# ---------------------------------------------------------------------------
# Push notification preferences
# ---------------------------------------------------------------------------


@warehouse_admin_required
def settings_notifications(request):
    """Налаштування пуш-сповіщень + дублювання в Telegram."""
    from warehouse.models import WarehouseSettings

    ws = WarehouseSettings.load()

    if request.method == "POST":
        ws.push_enabled = request.POST.get("push_enabled") == "on"
        freq = (request.POST.get("push_frequency") or "").strip()
        valid_freq = {c[0] for c in WarehouseSettings.Frequency.choices}
        if freq in valid_freq:
            ws.push_frequency = freq
        ws.push_to_telegram = request.POST.get("push_to_telegram") == "on"
        try:
            day = int(request.POST.get("push_weekly_day") or 0)
        except (ValueError, TypeError):
            day = 0
        ws.push_weekly_day = max(0, min(day, 6))

        valid_content = {c[0] for c in WarehouseSettings.PUSH_CONTENT_CHOICES}
        selected = [c for c in request.POST.getlist("push_content") if c in valid_content]
        ws.push_content = selected
        ws.save()
        messages.success(request, "Налаштування сповіщень збережено.")
        return redirect("warehouse:settings_notifications")

    context = {
        "ws": ws,
        "frequency_choices": WarehouseSettings.Frequency.choices,
        "content_choices": WarehouseSettings.PUSH_CONTENT_CHOICES,
        "selected_content": set(ws.get_push_content()),
        "weekdays": [
            (0, "Понеділок"), (1, "Вівторок"), (2, "Середа"), (3, "Четвер"),
            (4, "П'ятниця"), (5, "Субота"), (6, "Неділя"),
        ],
        "active_section": "settings",
    }
    return render(request, "warehouse/settings/notifications.html", context)


@warehouse_admin_required
@require_POST
def settings_notifications_test(request):
    """Надіслати тестовий звіт зараз (через налаштований канал)."""
    from warehouse.tasks import send_storage_report_task
    from warehouse.models import WarehouseSettings

    ws = WarehouseSettings.load()
    if not ws.push_enabled:
        messages.error(request, "Спершу увімкніть пуш-сповіщення та збережіть налаштування.")
        return redirect("warehouse:settings_notifications")

    result = send_storage_report_task(force_period=ws.push_frequency)
    sent = result.get("sent", 0) if isinstance(result, dict) else 0
    if sent:
        messages.success(request, f"Тестовий звіт надіслано ({sent} отримувач(ів)).")
    else:
        messages.warning(
            request,
            "Звіт сформовано, але не доставлено. Перевірте, що увімкнено "
            "«Дублювати в Telegram» і налаштовано Storage-бот та chat_id.",
        )
    return redirect("warehouse:settings_notifications")


# ---------------------------------------------------------------------------
# Telegram bot diagnostics + test broadcast
# ---------------------------------------------------------------------------


@warehouse_admin_required
def settings_telegram(request):
    """Сторінка діагностики Storage-бота: статус токена, список адмінів, тестова відправка."""
    from warehouse.models import WarehouseSettings
    from django.contrib.auth import get_user_model
    from django.db.models import Q
    from warehouse.permissions import WAREHOUSE_GROUP_NAME

    token = get_bot_token()
    token_masked = (token[:6] + "…" + token[-4:]) if token else ""
    chat_ids = get_admin_chat_ids()

    User = get_user_model()
    admins_qs = User.objects.filter(
        Q(is_superuser=True) | Q(is_staff=True, groups__name=WAREHOUSE_GROUP_NAME),
        is_active=True,
    ).distinct().select_related("userprofile")

    admins = []
    for u in admins_qs:
        profile = getattr(u, "userprofile", None)
        tg_id = getattr(profile, "telegram_id", None) if profile else None
        admins.append(
            {
                "user": u,
                "telegram_id": tg_id,
                "has_tg": bool(tg_id),
            }
        )

    ws = WarehouseSettings.load()

    context = {
        "token_set": bool(token),
        "token_masked": token_masked,
        "chat_ids": chat_ids,
        "chat_ids_count": len(chat_ids),
        "admins": admins,
        "ws": ws,
        "active_section": "settings",
    }
    return render(request, "warehouse/settings/telegram.html", context)


@warehouse_admin_required
@require_POST
def settings_telegram_test(request):
    """Відправити тестове повідомлення усім warehouse-адмінам."""
    mode = (request.POST.get("mode") or "test").strip()
    only_me = request.POST.get("only_me") == "on"

    if not get_bot_token():
        messages.error(request, "Токен Storage-бота не налаштований у .env")
        return redirect("warehouse:settings_telegram")

    if only_me:
        # Спроба знайти chat_id поточного юзера
        profile = getattr(request.user, "userprofile", None)
        tg_id = getattr(profile, "telegram_id", None) if profile else None
        if not tg_id:
            messages.error(
                request,
                "У вашому профілі не вказано telegram_id. "
                "Або додайте його, або зніміть прапорець «тільки мені».",
            )
            return redirect("warehouse:settings_telegram")
        chat_ids = [str(tg_id)]
    else:
        chat_ids = get_admin_chat_ids()
        if not chat_ids:
            messages.error(
                request,
                "Не знайдено жодного chat_id. Перевірте, що в адмінів заповнено telegram_id у профілі.",
            )
            return redirect("warehouse:settings_telegram")

    if mode == "evening":
        from django.utils import timezone as _tz

        today = _tz.localdate()
        text = build_evening_reminder_text(
            movements_count=0,
            unverified_count=0,
            today_str=today.strftime("%d.%m.%Y") + " (тест)",
        )
        from django.urls import reverse as _reverse

        base_url = getattr(__import__("django.conf").conf.settings, "WAREHOUSE_SUBDOMAIN_URL", "https://storage.twocomms.shop").rstrip("/")
        keyboard = build_evening_reminder_keyboard(f"{base_url}/today/")
    else:
        from django.utils import timezone as _tz

        text = (
            "🧪 <b>Тестове повідомлення Storage-бота</b>\n\n"
            f"Відправник: {request.user.username}\n"
            f"Час: {_tz.localtime().strftime('%d.%m.%Y %H:%M')}\n\n"
            "Якщо ви бачите це — ви у списку warehouse-адмінів. "
            "Щоденні нагадування приходять о 22:00 (Київ)."
        )
        keyboard = None

    sent = 0
    failed = 0
    for cid in chat_ids:
        result = send_message(cid, text, reply_markup=keyboard)
        if result and result.get("ok"):
            sent += 1
        else:
            failed += 1

    if sent and not failed:
        messages.success(request, f"Відправлено {sent} повідомлень ✅")
    elif sent and failed:
        messages.warning(
            request, f"Відправлено {sent} з {sent + failed}. Перевірте chat_id для тих, кому не дійшло."
        )
    else:
        messages.error(request, "Жодне повідомлення не доставлено. Перевірте токен та chat_ids.")

    return redirect("warehouse:settings_telegram")


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
