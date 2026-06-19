"""
Каталог для бота: компактний контекст про товари (ціни, наявність, кольори,
посилання), який підставляється в system_instruction Gemini. Кешується, щоб
не смикати БД на кожне повідомлення.

Джерела:
- storefront.Product (status=published): назва, ціна (final_price), категорія, slug.
- productcolors.ProductColorVariant: кольори + залишок (stock) на вітрині.
"""
from __future__ import annotations

from django.core.cache import cache
from django.db.models import Sum

CACHE_KEY = "ig_bot_catalog_ctx"
CACHE_TTL = 600          # 10 хв
MAX_PRODUCTS = 250
MAX_CHARS = 16000
SITE = "https://twocomms.shop"


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

    # Кольори + залишки + візуальні відбитки по варіантах одним запитом.
    colors_by_product: dict[int, list[str]] = {}
    stock_by_product: dict[int, int] = {}
    fp_by_product: dict[int, list[str]] = {}
    variants = (
        ProductColorVariant.objects.filter(product_id__in=ids)
        .select_related("color")
        .only("product_id", "stock", "color__name", "metadata")
    )
    for v in variants:
        cname = getattr(v.color, "name", "") or ""
        if cname:
            colors_by_product.setdefault(v.product_id, [])
            if cname not in colors_by_product[v.product_id]:
                colors_by_product[v.product_id].append(cname)
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
        colors = colors_by_product.get(p.id, [])
        colors_s = (", кольори: " + ", ".join(colors[:8])) if colors else ""
        stock = stock_by_product.get(p.id, 0)
        avail = f", на складі: {stock} шт" if stock > 0 else ", під замовлення"
        fps = fp_by_product.get(p.id, [])
        fp_s = (" | принт: " + "; ".join(fps[:3])) if fps else ""
        url = f"{SITE}/product/{p.slug}/"
        lines.append(f"• id={p.id} | {p.title} — {price} грн{disc} [{cat}]{colors_s}{avail}{fp_s} | {url}")

    text = "\n".join(lines)
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + "\n…(перелік скорочено)"
    return text


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
