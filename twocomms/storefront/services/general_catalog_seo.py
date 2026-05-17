"""Synthesize a Phase 10b SEO layout for the general ``/catalog/`` page.

Per-category catalogs (hoodie / tshirts / long-sleeve) get their bottom
SEO block from ``CategorySeoBlock`` rows. The general ``/catalog/`` root
has no anchoring category and therefore no SEO block — but users still
land on it from search and need the same kind of internal navigation
to drill down into combinations of category + colour. This service
builds an in-memory layout that mirrors the Phase 10b shape (tab_blocks
+ best_prices + has_any) so the existing ``partials/category_seo_blocks.html``
partial can render it without changes.

We intentionally keep this service *purely* in-memory (no DB rows): the
general catalog rarely changes its top-level shape (it's the union of
all categories + all colours), so synthesising on each request is
cheap. The ``catalog`` view already caches per-anon for 10 minutes so
the in-memory cost amortises to near zero.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Sequence

from django.utils.translation import gettext_lazy as _


def _block(block_type: str, title: str) -> SimpleNamespace:
    """Build a synthetic block compatible with the existing template.

    The template reads ``block.block_type``, ``block.title`` and calls
    ``block.get_block_type_display`` (Django auto-invokes callables in
    templates). SimpleNamespace satisfies all three accessors.
    """
    return SimpleNamespace(
        block_type=block_type,
        title=title,
        get_block_type_display=lambda title=title: title,
    )


def _item(
    label: str,
    url: str,
    *,
    extra: Optional[Dict[str, Any]] = None,
    product: Any = None,
) -> SimpleNamespace:
    """Build a synthetic item compatible with the existing template.

    Template accessors: ``item.label``, ``item.url``, ``item.extra``,
    ``item.product``. ``extra`` is a plain dict so chained dotted
    lookups like ``{{ item.extra.price }}`` resolve via Django's
    standard variable resolution.
    """
    return SimpleNamespace(
        label=label,
        url=url,
        extra=dict(extra or {}),
        product=product,
    )


# ---------------------------------------------------------------------------
# Curated top queries — high-intent, brand-relevant searches that funnel
# users into a specific category + colour combination. Kept in code (not
# DB) so the editorial set is reviewable in version control. URLs use the
# colour-filter syntax that the catalog view already understands.
# ---------------------------------------------------------------------------

# Phase 21 (2026-05-10) — every URL in this curated list MUST be
# indexable. ``?color=`` filters live behind ``noindex, follow``
# (see ``catalog.html`` robots block) so linking to them from
# SEO-visible bottom-nav is wasted equity. Routes here therefore use
# only category roots, ``/catalog/``, ``/custom-print/`` or
# colour-variant PDPs once those exist. Re-add a colour query only
# when that page becomes self-canonical and indexable.
_CURATED_TOP_QUERIES: List[Dict[str, Any]] = [
    {"label": _("Купити худі ЗСУ"), "url": "/catalog/hoodie/"},
    {"label": _("Чорна футболка з принтом"), "url": "/catalog/tshirts/"},
    {"label": _("Тризуб футболка"), "url": "/catalog/tshirts/"},
    {"label": _("Лонгслів мілітарі"), "url": "/catalog/long-sleeve/"},
    {"label": _("Худі streetwear"), "url": "/catalog/hoodie/"},
    {"label": _("Футболка унісекс TwoComms"), "url": "/catalog/tshirts/"},
    {"label": _("Кайот худі"), "url": "/catalog/hoodie/"},
    {"label": _("Чорний лонгслів"), "url": "/catalog/long-sleeve/"},
    {"label": _("Власний принт на футболці"), "url": "/custom-print/"},
    {"label": _("Подарунок захиснику"), "url": "/catalog/"},
    {"label": _("Жіноча футболка з принтом"), "url": "/catalog/tshirts/"},
    {"label": _("Худі для пари"), "url": "/catalog/hoodie/"},
    {"label": _("Український стрітвір"), "url": "/catalog/"},
    {"label": _("Donate to ZSU merch"), "url": "/catalog/"},
]


def _build_top_menu_items(categories) -> List[SimpleNamespace]:
    """SEO molecular-upgrade US-6 (2026-05-17) — расширенное top-menu.

    Раньше показывали только категории (3 ссылки). Теперь top_menu —
    полная карта внутренней навигации сайта со всеми SEO-ценными
    маршрутами: категории + тематические landings + сервисные страницы
    + бренд. Это разгружает crawl-budget (Google не должен искать
    delivery/care/returns по нескольким страницам), повышает in-degree
    каждой support-страницы и закрывает hub-spoke архитектуру.
    """
    items: List[SimpleNamespace] = []

    # 1. Базовые категории (все активные).
    for c in categories or []:
        if getattr(c, "is_active", True) and getattr(c, "slug", ""):
            items.append(_item(label=c.name, url=f"/catalog/{c.slug}/"))

    # 2. Тематические landings (US-5).
    items.extend([
        _item(label=str(_("Військовий streetwear")), url="/catalog/theme/military/"),
        _item(label=str(_("Стрітвір з кодом")), url="/catalog/theme/streetwear/"),
        _item(label=str(_("Патріотичний одяг")), url="/catalog/theme/patriotic/"),
        _item(label=str(_("Харківська лінія")), url="/catalog/theme/kharkiv-edition/"),
    ])

    # 3. Кастомний друк (high-intent commercial route).
    items.append(_item(label=str(_("Кастомний DTF-друк")), url="/custom-print/"))

    # 4. Сервісні сторінки — keyword-rich anchors під FAQ /
    # «<page> + brand» інтенти.
    items.extend([
        _item(label=str(_("Доставка і оплата")), url="/delivery/"),
        _item(label=str(_("Розмірна сітка")), url="/rozmirna-sitka/"),
        _item(label=str(_("Догляд за одягом")), url="/doglyad-za-odyagom/"),
        _item(label=str(_("Повернення та обмін")), url="/povernennya-ta-obmin/"),
        _item(label=str(_("FAQ")), url="/faq/"),
        _item(label=str(_("Допомога")), url="/dopomoga/"),
    ])

    # 5. B2B + бренд + контакт.
    items.extend([
        _item(label=str(_("Опт і дропшипінг")), url="/wholesale/"),
        _item(label=str(_("Співпраця з брендами")), url="/cooperation/"),
        _item(label=str(_("Про бренд TwoComms")), url="/pro-brand/"),
        _item(label=str(_("Контакти")), url="/contacts/"),
    ])

    # Дедуп по url, на випадок якщо адмін зареєстрував категорію зі
    # slug, що збігається з тематичним.
    seen = set()
    unique: List[SimpleNamespace] = []
    for it in items:
        if it.url in seen:
            continue
        seen.add(it.url)
        unique.append(it)
    return unique


def _build_top_filters_items(available_colors) -> List[SimpleNamespace]:
    items: List[SimpleNamespace] = []
    for chip in available_colors or []:
        slug = (chip.get("slug") or "").strip()
        label = chip.get("label") or slug.title()
        if not slug:
            continue
        items.append(_item(label=label, url=f"/catalog/?color={slug}"))
    return items


def _build_top_queries_items() -> List[SimpleNamespace]:
    return [_item(label=q["label"], url=q["url"]) for q in _CURATED_TOP_QUERIES]


def get_general_catalog_seo_layout(
    *,
    categories: Sequence[Any],
    available_colors: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    """Return a Phase 10b-shaped layout dict for the general /catalog/ page.

    Args:
        categories: iterable of ``Category`` instances (active only).
            Used to build the ``top_menu`` (Розділи каталогу) tab.
        available_colors: list of chip dicts produced by
            ``services.color_filter.build_available_colors``. Used to
            build the ``top_filters`` (Кольори) tab. Empty when no
            published product carries any colour variant — in that
            case the filter tab is dropped.

    Returns:
        ``{"tab_blocks": [...], "best_prices": None, "has_any": bool}``
        — same shape as ``services.category_seo_blocks.get_category_seo_layout``
        so the existing partial can render the result without edits.
    """
    tab_blocks: List[Dict[str, Any]] = []

    menu_items = _build_top_menu_items(categories or [])
    if menu_items:
        tab_blocks.append({
            "block": _block("top_menu", _("Розділи каталогу")),
            "items": menu_items,
        })

    filter_items = _build_top_filters_items(available_colors or [])
    if filter_items:
        tab_blocks.append({
            "block": _block("top_filters", _("Фільтр за кольором")),
            "items": filter_items,
        })

    query_items = _build_top_queries_items()
    if query_items:
        tab_blocks.append({
            "block": _block("top_queries", _("Популярні запити")),
            "items": query_items,
        })

    return {
        "tab_blocks": tab_blocks,
        "best_prices": None,
        "has_any": bool(tab_blocks),
    }
