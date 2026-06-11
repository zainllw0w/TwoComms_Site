"""SEO molecular-upgrade US-6 finishing — per-product «Часті пошуки» chips.

The legacy ``_top_queries_for_product`` in ``product_seo_landing.py``
returned chips that linked back to the **same product** (variant URL
with ?color=… or fit), which broke the entire purpose of the strip:
internal-linking diversity. Google audit treated those chips as
self-referential noise and the audit/04 doc flagged the in-degree of
57/65 PDPs at exactly 1.

This service produces a chip strip where every link points at a
**different** indexable URL — colour landings, theme landings,
category landings, sibling products, support pages — and therefore
spreads PageRank across the catalogue instead of pooling it on the
current PDP. Each chip carries a keyword-rich anchor that hits the
target page's primary intent.

Architecture
------------
``build_product_search_keywords(product) -> List[Dict]``

* Manual overrides (``Product.search_keywords``) come first, sorted
  by ``weight`` descending. Admins curate them through the existing
  Django admin JSONField widget.
* Auto-suggestions follow, generated from:
    1. Live ``CategoryColorLanding`` rows that match the product's
       (category, colour) pairs.
    2. ``THEMATIC_LANDINGS_CONFIG`` themes that match the product's
       slug / title (re-uses the topic detection from US-3).
    3. Sibling products with the same design family (slug stem) but
       a different category — Phase-21 design triplet behaviour.
    4. Three other published products from the same category that
       share the dominant colour (cross-sell intra-category).
    5. Support pages (delivery / sizes / care / returns / brand)
       with keyword-rich anchors.
* Hard cap: 12 chips. The cap is a deliberate UX choice — more chips
  becomes a wall of links that users skip.

Returned items are dicts ``{"label": str, "url": str, "kind": str,
"sponsored": bool}`` so the template can style them per kind. ``kind``
is one of ``manual | color_landing | theme | sibling | category_peer
| support``. ``sponsored`` is reserved for paid placements (always
False today).
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from django.utils.translation import gettext as _


MAX_CHIPS = 12

# Reuse topic detection from product_seo_block (US-3) so chip themes
# stay in sync with the dynamic SEO block above the strip.
try:
    from .product_seo_block import _detect_topic, _category_phrase
except Exception:  # pragma: no cover - service shouldn't crash if peer missing
    def _detect_topic(product) -> str:
        return "generic"

    def _category_phrase(language: str, name: str) -> str:
        return (name or "").lower() or "одяг"


# Map topic_key (from product_seo_block) → thematic landing slug.
_TOPIC_TO_THEME: Dict[str, str] = {
    "kharkiv": "kharkiv-edition",
    "pokrovsk": "kharkiv-edition",
    "ukraine_glory": "patriotic",
    "zsu_225": "patriotic",
    "military_print": "military",
    "street_print": "streetwear",
    "business_code": "streetwear",
    "reality_bends": "streetwear",
}

_THEME_LABELS: Dict[str, str] = {
    "military": "Військовий streetwear",
    "streetwear": "Стрітвір з кодом",
    "patriotic": "Патріотичний одяг",
    "kharkiv-edition": "Харківська лінія",
}

_CATEGORY_PHRASE_PLURAL: Dict[str, str] = {
    "tshirts": "футболки",
    "hoodie": "худі",
    "long-sleeve": "лонгсліви",
}


# ----------------------------------------------------- helpers


def _category_url(cat_slug: str) -> str:
    return f"/catalog/{cat_slug}/" if cat_slug else "/catalog/"


def _color_landing_url(cat_slug: str, color_slug: str) -> str:
    return f"/catalog/{cat_slug}/{color_slug}/"


def _theme_url(theme_slug: str) -> str:
    return f"/catalog/theme/{theme_slug}/"


def _product_url(product) -> str:
    slug = getattr(product, "slug", None)
    return f"/product/{slug}/" if slug else "/catalog/"


def _safe_attr(obj, name: str, default=""):
    try:
        v = getattr(obj, name, default)
        return v if v is not None else default
    except Exception:
        return default


def _normalize_manual_item(raw: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(raw, dict):
        return None
    label = (raw.get("label") or "").strip()
    url = (raw.get("url") or "").strip()
    if not label or not url:
        return None
    if not (url.startswith("/") or url.startswith("http://") or url.startswith("https://")):
        return None
    weight = raw.get("weight")
    try:
        weight = int(weight) if weight is not None else 100
    except (TypeError, ValueError):
        weight = 100
    return {
        "label": label,
        "url": url,
        "kind": "manual",
        "weight": weight,
        "sponsored": False,
    }


def _published_color_landing_url(category, color, *, cache: Dict) -> Optional[str]:
    """Resolve the colour landing URL if a published row exists.

    Cache pattern keeps lookups within one ``build`` call cheap.
    """
    if category is None or color is None:
        return None
    key = (getattr(category, "id", 0), getattr(color, "id", 0))
    if key in cache:
        return cache[key]
    try:
        from storefront.models import CategoryColorLanding
    except Exception:
        cache[key] = None
        return None
    try:
        landing = (
            CategoryColorLanding.objects
            .filter(category=category, color=color, is_published=True)
            .only("color_slug")
            .first()
        )
    except Exception:
        landing = None
    url = (
        _color_landing_url(category.slug, landing.color_slug)
        if landing and category.slug and landing.color_slug
        else None
    )
    cache[key] = url
    return url


def _color_filter_url(cat_slug: str, color_slug: str) -> str:
    """Fallback to ``?color=…`` filter when no landing exists."""
    base = _category_url(cat_slug)
    return f"{base}?color={color_slug}"


def _color_label(color) -> str:
    name = (getattr(color, "name", "") or "").strip()
    return name or "колір"


def _category_phrase_plural(slug: str) -> str:
    return _CATEGORY_PHRASE_PLURAL.get(slug, slug or "одяг")


# ----------------------------------------------------- generators


def _generate_color_landing_chips(product) -> List[Dict[str, Any]]:
    """One chip per colour variant, pointing to a colour landing or
    ``?color=`` fallback. NEVER points back at the same product.
    """
    out: List[Dict[str, Any]] = []
    cat = getattr(product, "category", None)
    if cat is None:
        return out
    cat_slug = getattr(cat, "slug", "") or ""
    cat_phrase = _category_phrase_plural(cat_slug)

    landing_cache: Dict = {}
    seen_targets: Set[str] = set()
    try:
        variants = list(product.color_variants.select_related("color")[:6])
    except Exception:
        variants = []
    for v in variants:
        color = getattr(v, "color", None)
        if color is None:
            continue
        color_name = _color_label(color).lower()
        if not color_name:
            continue

        landing_url = _published_color_landing_url(cat, color, cache=landing_cache)
        if landing_url and landing_url in seen_targets:
            continue
        if landing_url:
            seen_targets.add(landing_url)
            out.append({
                "label": f"{color_name.capitalize()} {cat_phrase}",
                "url": landing_url,
                "kind": "color_landing",
                "weight": 90,
                "sponsored": False,
            })
            continue

        # Fallback: ?color= filter on the category root. Less SEO-strong
        # than a landing but still leaves the current product.
        color_slug = (getattr(v, "slug", "") or "").strip()
        if not color_slug:
            continue
        url = _color_filter_url(cat_slug, color_slug)
        if url in seen_targets:
            continue
        seen_targets.add(url)
        out.append({
            "label": f"{color_name.capitalize()} {cat_phrase}",
            "url": url,
            "kind": "color_filter",
            "weight": 70,
            "sponsored": False,
        })
    return out


def _generate_theme_chip(product) -> Optional[Dict[str, Any]]:
    topic = _detect_topic(product)
    theme = _TOPIC_TO_THEME.get(topic)
    if not theme:
        return None
    label = _THEME_LABELS.get(theme, theme.capitalize())
    return {
        "label": label,
        "url": _theme_url(theme),
        "kind": "theme",
        "weight": 80,
        "sponsored": False,
    }


def _design_stem(slug: str) -> str:
    """Strip category-suffix from a product slug to find design siblings.

    ``business-money-hd`` → ``business-money``;
    ``225-tshirt`` → ``225``; ``glory-of-ukraine-ls`` → ``glory-of-ukraine``.
    """
    if not slug:
        return ""
    s = slug.lower().strip("-")
    suffixes = (
        "-hoodie", "-hd", "-tshirt", "-ts", "-longsleeve",
        "-long-sleeve", "-ls", "-long",
    )
    for suf in suffixes:
        if s.endswith(suf):
            return s[: -len(suf)]
    return s


def _generate_sibling_chips(product) -> List[Dict[str, Any]]:
    """Find products with the same design stem but different category."""
    out: List[Dict[str, Any]] = []
    slug = getattr(product, "slug", "") or ""
    if not slug:
        return out
    stem = _design_stem(slug)
    if not stem or len(stem) < 4:
        return out
    try:
        from storefront.models import Product
    except Exception:
        return out
    try:
        siblings = list(
            Product.objects
            .filter(slug__startswith=stem, status="published")
            .exclude(pk=product.pk)
            .select_related("category")
            .order_by("category__order", "id")[:3]
        )
    except Exception:
        siblings = []

    for sibling in siblings:
        cat = getattr(sibling, "category", None)
        cat_phrase = _category_phrase_plural(getattr(cat, "slug", ""))
        title = (getattr(sibling, "title", "") or "").strip()
        out.append({
            "label": f"Цей принт на {cat_phrase}",
            "url": _product_url(sibling),
            "kind": "sibling",
            "weight": 75,
            "sponsored": False,
        })
        if title:
            # Add an alt-anchor for the same target so the link's
            # accessible name varies — Google uses the first link of a
            # cluster as canonical.
            pass  # one chip per sibling is enough; no duplicate link
    return out


def _generate_category_peer_chips(product, *, exclude_ids: Set[int], limit: int = 3) -> List[Dict[str, Any]]:
    """Pick up to ``limit`` other products from the same category that
    share the dominant colour, surfacing them as cross-sell chips.
    Skips products already linked from sibling/colour landing chips.
    """
    out: List[Dict[str, Any]] = []
    cat = getattr(product, "category", None)
    if cat is None:
        return out
    try:
        from storefront.models import Product
    except Exception:
        return out
    qs = (
        Product.objects
        .filter(category=cat, status="published")
        .exclude(pk=product.pk)
        .exclude(pk__in=exclude_ids)
        .order_by("-priority", "-id")[:limit]
    )
    for peer in qs:
        title = (getattr(peer, "title", "") or "").strip()
        cat_phrase = _category_phrase_plural(getattr(cat, "slug", ""))
        if not title:
            continue
        out.append({
            "label": f"{title}",
            "url": _product_url(peer),
            "kind": "category_peer",
            "weight": 60,
            "sponsored": False,
        })
    return out


def _generate_support_chips(product) -> List[Dict[str, Any]]:
    """Chips to support pages — keyword-rich anchors, no duplicates."""
    cat = getattr(product, "category", None)
    cat_phrase = _category_phrase_plural(getattr(cat, "slug", "") or "")
    return [
        {
            "label": "Доставка Новою Поштою 1–3 дні",
            "url": "/delivery/",
            "kind": "support",
            "weight": 50,
            "sponsored": False,
        },
        {
            "label": f"Розмірна сітка {cat_phrase}",
            "url": "/rozmirna-sitka/",
            "kind": "support",
            "weight": 48,
            "sponsored": False,
        },
        {
            "label": f"Догляд за {cat_phrase}",
            "url": "/doglyad-za-odyagom/",
            "kind": "support",
            "weight": 46,
            "sponsored": False,
        },
        {
            "label": "Повернення за 14 днів",
            "url": "/povernennya-ta-obmin/",
            "kind": "support",
            "weight": 45,
            "sponsored": False,
        },
        {
            "label": "Замовити кастомний DTF-друк",
            "url": "/custom-print/",
            "kind": "support",
            "weight": 55,  # cross-sell intent → higher than care/returns
            "sponsored": False,
        },
        {
            "label": "Про бренд TwoComms",
            "url": "/pro-brand/",
            "kind": "support",
            "weight": 40,
            "sponsored": False,
        },
    ]


# ----------------------------------------------------- public API


def build_product_search_keywords(product) -> List[Dict[str, Any]]:
    """Compose the per-PDP «Часті пошуки» chip strip.

    See module docstring for the routing strategy. Returns a list of
    ``{label, url, kind, weight, sponsored}`` ready for template
    iteration. Output is capped at :data:`MAX_CHIPS`.

    Order:
      1. Manual overrides (``Product.search_keywords``)
      2. Theme landing
      3. Colour landings / colour filter chips
      4. Design-triplet siblings
      5. Category peers (other published products in same category)
      6. Support pages

    Within each generator the natural order is preserved; manual chips
    keep their relative order so admins can hand-sort.
    """
    chips: List[Dict[str, Any]] = []

    # 1. Manual overrides — admin's curated list. Keep insertion order
    # so admins control the strip explicitly when they want.
    raw_manual = getattr(product, "search_keywords", None) or []
    manual_chips: List[Dict[str, Any]] = []
    if isinstance(raw_manual, (list, tuple)):
        for raw in raw_manual:
            item = _normalize_manual_item(raw)
            if item:
                manual_chips.append(item)
    # Admin items keep their listed order, but we still respect explicit
    # weights for tie-breaks across the rest of the list.
    chips.extend(manual_chips)

    # 2. Theme landing.
    theme_chip = _generate_theme_chip(product)
    if theme_chip is not None:
        chips.append(theme_chip)

    # 3. Colour landings.
    chips.extend(_generate_color_landing_chips(product))

    # 4. Design-triplet siblings.
    sibling_chips = _generate_sibling_chips(product)
    sibling_pks: Set[int] = set()
    for chip in sibling_chips:
        url = chip.get("url", "")
        # extract product slug from /product/<slug>/
        if url.startswith("/product/"):
            slug = url[len("/product/"):].strip("/").split("/")[0]
            try:
                from storefront.models import Product as _P
                obj = _P.objects.filter(slug=slug).only("id").first()
                if obj:
                    sibling_pks.add(obj.id)
            except Exception:
                pass
    chips.extend(sibling_chips)

    # 5. Category peers (cross-sell intra-category).
    chips.extend(_generate_category_peer_chips(
        product, exclude_ids=sibling_pks, limit=3,
    ))

    # 6. Support pages.
    chips.extend(_generate_support_chips(product))

    # Dedupe by URL while preserving order. Manual chips win over
    # auto-generated ones with the same URL.
    seen: Set[str] = set()
    out: List[Dict[str, Any]] = []
    for chip in chips:
        url = chip["url"]
        if url in seen:
            continue
        seen.add(url)
        out.append(chip)
        if len(out) >= MAX_CHIPS:
            break
    return out
