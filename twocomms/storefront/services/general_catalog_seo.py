"""Synthesize a Phase 10b SEO layout for the general ``/catalog/`` page.

Per-category catalogs (hoodie / tshirts / long-sleeve) get their bottom
SEO block from ``CategorySeoBlock`` rows. The general ``/catalog/`` root
has no anchoring category, so this service builds an in-memory owned-link
menu that mirrors the Phase 10b shape (tab_blocks + best_prices + has_any).
Interactive colour filters remain in the catalog selector and are not
republished as editorial SEO links.

We intentionally keep this service *purely* in-memory (no DB rows): the
general catalog rarely changes its owned top-level navigation, so
synthesising it on each request is cheap. The ``catalog`` view already
caches per-anon for 10 minutes, so the in-memory cost amortises to near
zero.
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


def get_general_catalog_seo_layout(
    *,
    categories: Sequence[Any],
    available_colors: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    """Return a Phase 10b-shaped layout dict for the general /catalog/ page.

    Args:
        categories: iterable of ``Category`` instances (active only).
            Used to build the ``top_menu`` (Розділи каталогу) tab.
        available_colors: retained for call-site compatibility. Colour chips
            are interactive UI state and are intentionally not exposed here.

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

    return {
        "tab_blocks": tab_blocks,
        "best_prices": None,
        "has_any": bool(tab_blocks),
    }
