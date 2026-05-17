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

from django.db.models import Prefetch


def _hydrate_product_items(items, products_by_id):
    """Attach ``product`` to items that reference one via ``extra.product_id``."""
    for item in items:
        product_id = None
        if isinstance(item.extra, dict):
            product_id = item.extra.get("product_id")
        item.product = products_by_id.get(product_id) if product_id else None
    return items


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
            if isinstance(item.extra, dict):
                pid = item.extra.get("product_id")
                if isinstance(pid, int) and pid > 0:
                    product_ids.add(pid)

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
        items = list(block.items.all())
        _hydrate_product_items(items, products_by_id)
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

    block = _block("top_menu", str("Розділи каталогу"))
    return {"block": block, "items": items}
