"""
Phase 10 — category SEO blocks.

Loads ``CategorySeoBlock`` rows for a category, hydrates
``top_cards`` / ``best_prices`` items with live ``Product`` data when
``extra.product_id`` is provided, and packages the result for the
catalog template.

The view is expected to call ``get_category_seo_blocks(category)`` and
pass the returned list as ``category_seo_blocks`` in the context.
"""
from __future__ import annotations

from typing import Any, Dict, List
from urllib.parse import urlsplit, urlunsplit

from django.db.models import Prefetch
from django.urls import reverse
from django.utils import translation
from django.utils.translation import gettext as _

from .locale_publication import _raw_value
from .seo_link_policy import is_internal_ui_state_url


_MAX_PRODUCT_ID = (1 << 63) - 1


def _product_id(item) -> int | None:
    """Return a positive product id from an item's JSON payload."""
    if not isinstance(getattr(item, "extra", None), dict):
        return None
    raw_id = item.extra.get("product_id")
    if type(raw_id) is int:
        product_id = raw_id
    elif (
        isinstance(raw_id, str)
        and raw_id.isascii()
        and raw_id.isdecimal()
    ):
        normalized_id = raw_id.lstrip("0") or "0"
        if len(normalized_id) > 19:
            return None
        product_id = int(normalized_id, 10)
    else:
        return None
    return product_id if 0 < product_id <= _MAX_PRODUCT_ID else None


def _has_product_reference(item) -> bool:
    return (
        isinstance(getattr(item, "extra", None), dict)
        and "product_id" in item.extra
    )


def _normalize_custom_print_url(url: str) -> str:
    """Return the working, locale-aware owner for stale custom-print links."""
    raw_url = str(url or "")
    try:
        parsed = urlsplit(raw_url)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError:
        return raw_url

    is_absolute = bool(parsed.scheme or parsed.netloc)
    if is_absolute:
        if parsed.scheme and parsed.scheme.lower() not in {"http", "https"}:
            return raw_url
        if hostname not in {"twocomms.shop", "www.twocomms.shop"}:
            return raw_url
        if port not in {None, 80, 443}:
            return raw_url
    elif not parsed.path.startswith("/"):
        return raw_url

    if parsed.path.rstrip("/") not in {"/catalog/custom-print", "/custom-print"}:
        return raw_url

    path = reverse("custom_print")
    if is_absolute:
        return urlunsplit(
            ("https", "twocomms.shop", path, parsed.query, parsed.fragment)
        )
    return urlunsplit(("", "", path, parsed.query, parsed.fragment))


def _hydrate_product_items(items, products_by_id):
    """Attach live products and remove unavailable product references."""
    hydrated = []
    for item in items:
        product_id = _product_id(item)
        if _has_product_reference(item):
            if product_id is None:
                continue
            product = products_by_id.get(product_id)
            if product is None:
                continue
            item.product = product
            item.url = reverse("product", kwargs={"slug": product.slug})
        else:
            item.product = None
            item.url = _normalize_custom_print_url(item.url)
            if is_internal_ui_state_url(item.url):
                continue
        hydrated.append(item)
    return hydrated


def get_category_seo_blocks(category) -> List[Dict[str, Any]]:
    """Return active SEO blocks for the given category, ready to render.

    Each entry: ``{"block": CategorySeoBlock, "items": [CategorySeoBlockItem]}``.
    Empty blocks (no items) are dropped to avoid rendering empty rails,
    except for ``best_prices`` which can be rendered dynamically later.
    """
    if category is None:
        return []

    from ..models import CategorySeoBlock, CategorySeoBlockItem, Product

    blocks = list(
        CategorySeoBlock.objects
        .filter(category=category, is_active=True)
        .prefetch_related(
            Prefetch(
                "items",
                queryset=CategorySeoBlockItem.objects.order_by("order", "id"),
            )
        )
        .order_by("order", "id")
    )
    if not blocks:
        return []

    # Collect product ids referenced from any item's extra payload.
    product_ids = set()
    for block in blocks:
        for item in block.items.all():
            product_id = _product_id(item)
            if product_id is not None:
                product_ids.add(product_id)

    products_by_id: Dict[int, Any] = {}
    if product_ids:
        products_by_id = {
            p.id: p
            for p in Product.objects
            .filter(id__in=product_ids, status="published")
            .select_related("category")
        }

    result: List[Dict[str, Any]] = []
    for block in blocks:
        items = _hydrate_product_items(list(block.items.all()), products_by_id)
        if not items and block.block_type != "best_prices":
            continue
        result.append({
            "block": block,
            "items": items,
        })
    return result


# ---------------------------------------------------------------------------
# Phase 10b — structured layout: tabs vs. pricing table.
# ---------------------------------------------------------------------------

# The tab strip mirrors AAC.com.ua / retromagaz: link-only blocks live as
# tabs on a single component, while ``best_prices`` (a pricing table) is
# rendered separately because it has table semantics. The order here is
# the order tabs appear in the strip.
TAB_BLOCK_TYPES: tuple[str, ...] = (
    "top_menu",
    "top_filters",
    "top_queries",
    "top_cards",
)


def _normalize_language(language: str | None) -> str:
    code = str(language or "uk").lower().replace("_", "-").split("-", 1)[0]
    return code if code in {"uk", "ru", "en"} else "uk"


def _localized_category_name(category, language: str) -> str:
    return _raw_value(category, "name", language)


def _locale_safe_top_menu(current_category, language: str) -> Dict[str, Any] | None:
    """Build a RU/EN-owned PDP menu without locale-less SEO-block data.

    ``CategorySeoBlock`` and its items do not have translated fields.  On a
    non-default PDP we therefore expose only category names with their own
    translations plus support pages whose Django gettext entries are reviewed.
    UK keeps the established DB-driven layout below.
    """
    try:
        from .general_catalog_seo import _block, _item
        from ..models import Category
    except Exception:
        return None

    with translation.override(language):
        items = []
        for category in Category.objects.filter(is_active=True).order_by("order", "id"):
            if category.pk == getattr(current_category, "pk", None):
                continue
            label = _localized_category_name(category, language)
            if not label or not category.slug:
                continue
            items.append(_item(
                label=label,
                url=reverse("catalog_by_cat", kwargs={"cat_slug": category.slug}),
            ))

        for label, route in (
            (_("Доставка і оплата"), "delivery"),
            (_("Розмірна сітка"), "size_guide"),
            (_("Догляд за одягом"), "care_guide"),
            (_("Повернення та обмін"), "returns"),
            (_("Про бренд TwoComms"), "about"),
        ):
            items.append(_item(label=label, url=reverse(route)))

        title = _("Розділи каталогу")
        return {"block": _block("top_menu", title), "items": items}


def get_locale_safe_product_seo_layout(category, *, language: str) -> Dict[str, Any]:
    """Return the only safe category rail for an RU/EN standard PDP."""
    language = _normalize_language(language)
    if category is None:
        return {"tab_blocks": [], "best_prices": None, "has_any": False}
    if language == "uk":
        return get_category_seo_layout(category)
    menu = _locale_safe_top_menu(category, language)
    tab_blocks = [menu] if menu and menu.get("items") else []
    return {
        "tab_blocks": tab_blocks,
        "best_prices": None,
        "has_any": bool(tab_blocks),
    }


def get_category_seo_layout(category) -> Dict[str, Any]:
    """Phase 10b — split SEO blocks into tabbed link rails + pricing table.

    Returns a dict::

        {
            "tab_blocks":   [{"block": CategorySeoBlock, "items": [...]}, ...],
            "best_prices":  {"block": ..., "items": [...]} | None,
            "has_any":      bool,
        }

    Tabs preserve the canonical ``TAB_BLOCK_TYPES`` order regardless of
    each block's per-row ``order`` field — tab order is part of the UX
    contract, not editorial priority. ``best_prices`` is returned as a
    single block (the first active one) so the template can render it
    as a real ``<table>`` element.

    SEO molecular-upgrade US-6 (2026-05-17) — when ``top_menu`` is
    empty in the DB we synthesize it from
    ``general_catalog_seo._build_top_menu_items`` so every category
    page gets the same broad internal-navigation set as the catalog
    root. Admins can still override per-category by adding a real
    ``CategorySeoBlock(top_menu)`` row.
    """
    blocks = get_category_seo_blocks(category)

    by_type: Dict[str, Dict[str, Any]] = {}
    for entry in blocks:
        btype = entry["block"].block_type
        by_type.setdefault(btype, entry)

    tab_blocks: List[Dict[str, Any]] = []
    for btype in TAB_BLOCK_TYPES:
        entry = by_type.get(btype)
        if entry and entry["items"]:
            tab_blocks.append(entry)
            continue
        if btype == "top_menu":
            synthetic = _synthesize_top_menu(category)
            if synthetic:
                tab_blocks.append(synthetic)

    best_prices = by_type.get("best_prices")
    if best_prices and not best_prices["items"]:
        best_prices = None

    return {
        "tab_blocks": tab_blocks,
        "best_prices": best_prices,
        "has_any": bool(tab_blocks or best_prices),
    }


def _synthesize_top_menu(current_category) -> Dict[str, Any] | None:
    """Build an in-memory ``top_menu`` block for a category page.

    Re-uses ``_build_top_menu_items`` from the general catalog so the
    same SEO-rich link list (categories + thematic + service + brand
    + B2B) renders on every category landing without a DB row.
    """
    try:
        from .general_catalog_seo import _build_top_menu_items, _block
        from ..models import Category
    except Exception:
        return None

    try:
        categories = list(
            Category.objects.filter(is_active=True).order_by("order", "id")
        )
    except Exception:
        categories = []

    items = _build_top_menu_items(categories)
    if not items:
        return None

    # Drop the current category's own URL so the menu doesn't link
    # back at itself.
    current_url = f"/catalog/{current_category.slug}/" if current_category else ""
    if current_url:
        items = [it for it in items if getattr(it, "url", "") != current_url]

    block = _block("top_menu", _("Розділи каталогу"))
    return {"block": block, "items": items}
