"""
Каталог для бота: компактний контекст про товари (ціни, наявність, кольори,
посилання), який підставляється в system_instruction Gemini. Кешується, щоб
не смикати БД на кожне повідомлення.

Джерела:
- storefront.Product (status=published): назва, ціна (final_price), категорія, slug.
- productcolors.ProductColorVariant: кольори + залишок (stock) на вітрині.
"""
from __future__ import annotations

import logging

from django.core.cache import cache

logger = logging.getLogger(__name__)
from django.db.models import Sum

CACHE_KEY = "ig_bot_catalog_ctx"
CACHE_TTL = 600          # 10 хв
MAX_PRODUCTS = 250
# Бюджет підвищено після прод-перевірки 02.08.2026. При 16 000 символів каталог
# важив 15 977 і в промпт потрапляли **48 товарів із 71**: сортування
# `-featured, -id` ставить нові товари першими, тому відрізало найстаріші —
# а це базові моделі id=1 «Футболка класична», id=2 «Худі класичне»,
# id=3 «Класичний лонгслів».
#
# Ціна цієї обрізки видна в переписці клієнта #5: він просив «стандартную
# черную классику», надіслав посилання саме на id=1, а бот відповів, що
# «полностью однотонной черной без рисунка сейчас нет в наличии». Модель не
# вигадувала — вона казала правду про той каталог, який бачила.
#
# 48 000 символів вміщують усі 71 товар із запасом. Для gemini-3.6-flash з
# контекстом на мільйон токенів це дрібниця, а обрізка тут — прямі втрачені
# продажі.
MAX_CHARS = 48000
SITE = "https://twocomms.shop"


def resolve_catalog_sizes(product) -> dict[str, list[str]]:
    """Resolve the published size contract for each active fit option."""
    try:
        from fable5.size_grid_services import (
            normalize_size_value,
            resolve_effective_sizes,
        )
        from storefront.services.size_guides import resolve_product_sizes

        fits = list(product.fit_options.filter(is_active=True).order_by("order", "id"))
        if not fits:
            values = [normalize_size_value(value) for value in resolve_product_sizes(product)]
            return {"default": [value for value in values if value]}
        result: dict[str, list[str]] = {}
        for fit in fits:
            rows = resolve_effective_sizes(product, f"fit={fit.code}")
            values = [
                normalize_size_value(row.get("size"))
                for row in rows
                if isinstance(row, dict) and row.get("is_enabled", True)
            ]
            values = [value for value in values if value]
            if not values:
                values = [normalize_size_value(value) for value in resolve_product_sizes(product)]
                values = [value for value in values if value]
            result[str(fit.code).lower()] = list(dict.fromkeys(values))
        return result
    except Exception:
        return {}


def _build() -> str:
    try:
        from storefront.models import Product, ProductStatus
        from productcolors.models import ProductColorVariant
    except Exception:
        return ""

    qs = (
        Product.objects.filter(status=ProductStatus.PUBLISHED)
        .select_related("category")
        .order_by("-featured", "-id")[:MAX_PRODUCTS]
    )
    products = list(qs)
    if not products:
        return ""
    ids = [p.id for p in products]

    # Кольори + залишки + службові IDs по варіантах одним запитом.
    variants_by_product: dict[int, list[object]] = {}
    stock_by_product: dict[int, int] = {}
    fp_by_product: dict[int, list[str]] = {}
    variants = (
        ProductColorVariant.objects.filter(product_id__in=ids)
        .select_related("color")
        .only("product_id", "stock", "color__name", "metadata")
    )
    for v in variants:
        variants_by_product.setdefault(v.product_id, []).append(v)
        stock_by_product[v.product_id] = stock_by_product.get(v.product_id, 0) + int(v.stock or 0)
        bv = (v.metadata or {}).get("bot_vision") or {}
        seg = (bv.get("summary") or bv.get("print_subject") or "").strip()
        if seg:
            fp_by_product.setdefault(v.product_id, [])
            if seg not in fp_by_product[v.product_id]:
                fp_by_product[v.product_id].append(seg)

    lines = ["Каталог TwoComms (актуальні товари, ціни в грн):"]
    for p in products:
        try:
            price = p.final_price
        except Exception:
            price = p.price
        disc = ""
        try:
            if p.has_discount and p.discount_percent:
                disc = f" (знижка {p.discount_percent}%, було {p.price})"
        except Exception:
            pass
        cat = getattr(p.category, "name", "") or ""
        stock = stock_by_product.get(p.id, 0)
        # «Під замовлення» — не заглушка, а факт: речі відшиваються, і чекаут це
        # дозволяє. Нульовий `stock` означає «облік по варіанту не ведеться»,
        # тому казати клієнту «немає» через нього не можна.
        avail = f", на складі: {stock} шт" if stock > 0 else ", під замовлення (відшиваємо 1-3 дні)"
        fps = fp_by_product.get(p.id, [])
        fp_s = (" | принт: " + "; ".join(fps[:3])) if fps else ""
        # `stock` у рядку варіанта показуємо лише коли він додатний: нуль у цьому
        # проєкті означає «облік не ведеться», і модель читала його як «немає»,
        # хоча сайт цей товар продає.
        variants_s = ", ".join(
            f"{getattr(getattr(v, 'color', None), 'name', '') or 'колір'} "
            f"(variant_id={v.pk}"
            + (f", на складі {int(v.stock or 0)}" if int(getattr(v, "stock", 0) or 0) > 0 else "")
            + ")"
            for v in variants_by_product.get(p.id, [])
            if getattr(getattr(v, "color", None), "name", "")
        )
        colors_s = ("; кольори: " + variants_s) if variants_s else ""
        sizes_by_fit = resolve_catalog_sizes(p)
        fits_s = "; фасони/розміри: " + "; ".join(
            f"{code}: {'/'.join(values)}" for code, values in sizes_by_fit.items() if values
        ) if sizes_by_fit else ""
        url = f"{SITE}/product/{p.slug}/"
        lines.append(
            f"• id={p.id} | {p.title} — {price} грн{disc} [{cat}]"
            f"{colors_s}{avail}{fits_s}{fp_s} | {url}"
        )

    text, _dropped = truncate_catalog_lines(lines, limit=MAX_CHARS)
    return text + "\nПравило: не вигадуй variant_id, фасон або розмір; використовуй тільки значення з цього каталогу."


def _log_catalog_truncation(dropped: int, total: int, limit: int) -> None:
    """Make the truncation visible: it used to happen without a trace."""
    try:
        from management.services.instagram_bot import log

        log(
            "warning",
            "catalog_truncated",
            f"{dropped} of {total} products dropped to fit {limit} chars",
        )
    except Exception:
        logger.warning(
            "Instagram catalog truncated: %s of %s products dropped to fit %s chars",
            dropped,
            total,
            limit,
        )


def truncate_catalog_lines(lines: list[str], *, limit: int = MAX_CHARS) -> tuple[str, int]:
    """Fit the catalog into the budget by whole products, not by characters.

    F-CAT-001: the previous ``text[:MAX_CHARS]`` cut mid-line, so the last
    product arrived truncated and the model could read a partial price or a
    partial variant_id. On production the catalog is 16 118 characters against a
    16 000 limit, which means 22 of 71 published products never reach the prompt
    — and nothing said so.
    """
    total = len(lines)
    kept: list[str] = []
    used = 0
    for line in lines:
        cost = len(line) + 1
        if used + cost > limit:
            break
        kept.append(line)
        used += cost
    dropped = total - len(kept)
    if not dropped:
        return "\n".join(kept), 0
    _log_catalog_truncation(dropped, total, limit)
    kept.append(
        f"…(показано {len(kept)} товарів із {total}; {dropped} не вміщено — "
        "якщо клієнт питає про товар, якого тут немає, скажи що уточниш у менеджера)"
    )
    return "\n".join(kept), dropped


def get_catalog_context(force: bool = False) -> str:
    if not force:
        cached = cache.get(CACHE_KEY)
        if cached is not None:
            return cached
    try:
        text = _build()
    except Exception:
        text = ""
    cache.set(CACHE_KEY, text, CACHE_TTL)
    return text
