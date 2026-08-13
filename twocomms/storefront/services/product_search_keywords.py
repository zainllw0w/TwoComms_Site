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

from typing import Any, Dict, List, Optional, Set

from django.db.models import Prefetch
from django.urls import reverse
from django.utils import translation
from django.utils.translation import get_language
from django.utils.translation import gettext as _

from productcolors.color_i18n import translate_color_name

from .locale_publication import _raw_value, locale_is_indexable
from .seo_link_policy import is_internal_ui_state_url


MAX_CHIPS = 12
MAX_LOCALE_CANDIDATES = 24
_SUPPORTED_LOCALES = frozenset(("uk", "ru", "en"))

# Reuse topic detection from product_seo_block (US-3) so chip themes
# stay in sync with the dynamic SEO block above the strip.
try:
    from .product_seo_block import _detect_topic
except Exception:  # pragma: no cover - service shouldn't crash if peer missing
    def _detect_topic(product) -> str:
        return "generic"


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


def _normalize_language(language: str | None) -> str:
    code = str(language or get_language() or "uk").lower().replace("_", "-")
    code = code.split("-", 1)[0]
    return code if code in _SUPPORTED_LOCALES else "uk"


def _localized_reverse(route_name: str, language: str, *, kwargs=None) -> str:
    """Resolve an i18n-pattern route under the requested locale."""
    with translation.override(language):
        return reverse(route_name, kwargs=kwargs)


def _locale_owned_text(instance, field: str, language: str) -> str:
    """Read a modeltranslation value without allowing a Ukrainian fallback."""
    return _raw_value(instance, field, language)


def _category_phrase_plural(slug: str) -> str:
    return _CATEGORY_PHRASE_PLURAL.get(slug, slug or "одяг")


def _locale_candidate_window(queryset, *, language: str, result_limit: int = 3):
    """Keep peer selection bounded and avoid per-product FAQ queries.

    RU/EN ownership checks inspect FAQ translations.  Loading that relation
    once for a small, fixed candidate window makes the rail's database cost
    independent of the category size while still allowing us to skip a few
    incomplete translations before finding up to three valid targets.
    """
    if language in {"ru", "en"}:
        try:
            from storefront.models import ProductFAQ
        except Exception:
            return queryset[:MAX_LOCALE_CANDIDATES]
        queryset = queryset.prefetch_related(
            Prefetch(
                "faqs",
                queryset=ProductFAQ.objects.filter(is_active=True).only(
                    "id",
                    "product_id",
                    "is_active",
                    f"question_{language}",
                    f"answer_{language}",
                ),
            )
        )
        return queryset[:MAX_LOCALE_CANDIDATES]
    return queryset[:result_limit]


def _color_landing_url(cat_slug: str, color_slug: str, language: str) -> str:
    return _localized_reverse(
        "catalog_by_cat_color",
        language,
        kwargs={"cat_slug": cat_slug, "color_slug": color_slug},
    )


def _theme_url(theme_slug: str, language: str) -> str:
    return _localized_reverse(
        "catalog_theme_landing", language, kwargs={"theme_slug": theme_slug}
    )


def _product_url(product, language: str) -> str:
    slug = getattr(product, "slug", None)
    if not slug:
        return _localized_reverse("catalog", language)
    return _localized_reverse("product", language, kwargs={"slug": slug})


def _normalize_manual_item(raw: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(raw, dict):
        return None
    label = (raw.get("label") or "").strip()
    url = (raw.get("url") or "").strip()
    if not label or not url:
        return None
    if not (url.startswith("/") or url.startswith("http://") or url.startswith("https://")):
        return None
    if is_internal_ui_state_url(url):
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


def _published_color_landing_url(
    category,
    color,
    *,
    cache: Dict,
    language: str,
) -> Optional[str]:
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
        _color_landing_url(category.slug, landing.color_slug, language)
        if landing and category.slug and landing.color_slug
        else None
    )
    cache[key] = url
    return url


def _color_label(color, language: str) -> str:
    name = (getattr(color, "name", "") or "").strip()
    return translate_color_name(name, language) if name else ""


# ----------------------------------------------------- generators


def _generate_color_landing_chips(product, *, language: str) -> List[Dict[str, Any]]:
    """Link only to published, indexable Ukrainian colour landing owners."""
    out: List[Dict[str, Any]] = []
    # CategoryColorLanding rows have Ukrainian-only editorial copy and must
    # never be promoted from an indexable RU/EN product page.
    if language != "uk":
        return out
    cat = getattr(product, "category", None)
    if cat is None:
        return out
    cat_phrase = _locale_owned_text(cat, "name", language).lower()
    if not cat_phrase:
        return out

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
        color_name = _color_label(color, language).lower()
        if not color_name:
            continue

        landing_url = _published_color_landing_url(
            cat, color, cache=landing_cache, language=language
        )
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

    return out


def _generate_theme_chip(product, *, language: str) -> Optional[Dict[str, Any]]:
    if language != "uk":
        return None
    topic = _detect_topic(product)
    theme = _TOPIC_TO_THEME.get(topic)
    if not theme:
        return None
    label = _THEME_LABELS.get(theme, theme.capitalize())
    return {
        "label": label,
        "url": _theme_url(theme, language),
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


def _generate_sibling_chips(
    product,
    *,
    language: str,
    selected_ids: Optional[Set[int]] = None,
) -> List[Dict[str, Any]]:
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
        siblings = list(_locale_candidate_window(
            Product.objects
            .filter(slug__startswith=stem, status="published")
            .exclude(pk=product.pk)
            .select_related("category")
            .order_by("category__order", "id"),
            language=language,
        ))
    except Exception:
        siblings = []

    for sibling in siblings:
        if not locale_is_indexable(sibling, language):
            continue
        title = _locale_owned_text(sibling, "title", language)
        if not title:
            continue
        if selected_ids is not None:
            selected_ids.add(sibling.pk)
        category = getattr(sibling, "category", None)
        label = (
            f"Цей принт на {_category_phrase_plural(getattr(category, 'slug', ''))}"
            if language == "uk"
            else title
        )
        out.append({
            "label": label,
            "url": _product_url(sibling, language),
            "kind": "sibling",
            "weight": 75,
            "sponsored": False,
        })
        if len(out) >= 3:
            break
    return out


def _generate_category_peer_chips(
    product,
    *,
    exclude_ids: Set[int],
    language: str,
    limit: int = 3,
) -> List[Dict[str, Any]]:
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
    qs = _locale_candidate_window(
        Product.objects
        .filter(category=cat, status="published")
        .exclude(pk=product.pk)
        .exclude(pk__in=exclude_ids)
        .order_by("-priority", "-id"),
        language=language,
        result_limit=limit,
    )
    for peer in qs:
        if not locale_is_indexable(peer, language):
            continue
        title = _locale_owned_text(peer, "title", language)
        if not title:
            continue
        out.append({
            "label": title,
            "url": _product_url(peer, language),
            "kind": "category_peer",
            "weight": 60,
            "sponsored": False,
        })
        if len(out) >= limit:
            break
    return out


def _generate_support_chips(product, *, language: str) -> List[Dict[str, Any]]:
    """Return factual support owners rendered in the requested locale."""
    with translation.override(language):
        if language == "uk":
            category = getattr(product, "category", None)
            category_phrase = _category_phrase_plural(
                getattr(category, "slug", "") or ""
            )
            return [
                {
                    "label": "Доставка Новою Поштою 1–3 дні",
                    "url": reverse("delivery"),
                    "kind": "support",
                    "weight": 50,
                    "sponsored": False,
                },
                {
                    "label": f"Розмірна сітка {category_phrase}",
                    "url": reverse("size_guide"),
                    "kind": "support",
                    "weight": 48,
                    "sponsored": False,
                },
                {
                    "label": f"Догляд за {category_phrase}",
                    "url": reverse("care_guide"),
                    "kind": "support",
                    "weight": 46,
                    "sponsored": False,
                },
                {
                    "label": "Повернення за 14 днів",
                    "url": reverse("returns"),
                    "kind": "support",
                    "weight": 45,
                    "sponsored": False,
                },
                {
                    "label": "Замовити кастомний DTF-друк",
                    "url": reverse("custom_print"),
                    "kind": "support",
                    "weight": 55,
                    "sponsored": False,
                },
                {
                    "label": "Про бренд TwoComms",
                    "url": reverse("about"),
                    "kind": "support",
                    "weight": 40,
                    "sponsored": False,
                },
            ]

        chips = [
            {
                "label": _("Доставка і оплата"),
                "url": reverse("delivery"),
                "kind": "support",
                "weight": 50,
                "sponsored": False,
            },
            {
                "label": _("Розмірна сітка"),
                "url": reverse("size_guide"),
                "kind": "support",
                "weight": 48,
                "sponsored": False,
            },
            {
                "label": _("Догляд за одягом"),
                "url": reverse("care_guide"),
                "kind": "support",
                "weight": 46,
                "sponsored": False,
            },
            {
                "label": _("Повернення та обмін"),
                "url": reverse("returns"),
                "kind": "support",
                "weight": 45,
                "sponsored": False,
            },
            {
                "label": _("Про бренд TwoComms"),
                "url": reverse("about"),
                "kind": "support",
                "weight": 40,
                "sponsored": False,
            },
        ]
    return chips


# ----------------------------------------------------- public API


def build_product_search_keywords(
    product, *, language: str | None = None
) -> List[Dict[str, Any]]:
    """Compose the per-PDP «Часті пошуки» chip strip.

    See module docstring for the routing strategy. Returns a list of
    ``{label, url, kind, weight, sponsored}`` ready for template
    iteration. Output is capped at :data:`MAX_CHIPS`.

    Order:
      1. Manual overrides (``Product.search_keywords``)
      2. Theme landing
      3. Published colour landings (Ukrainian owner only)
      4. Design-triplet siblings
      5. Category peers (other published products in same category)
      6. Support pages

    Within each generator the natural order is preserved; manual chips
    keep their relative order so admins can hand-sort.
    """
    language = _normalize_language(language)
    chips: List[Dict[str, Any]] = []

    with translation.override(language):
        # ``Product.search_keywords`` is a legacy locale-less JSON field.
        # It can be editorially valid only for the canonical Ukrainian owner.
        if language == "uk":
            raw_manual = getattr(product, "search_keywords", None) or []
            if isinstance(raw_manual, (list, tuple)):
                chips.extend(
                    item for raw in raw_manual
                    if (item := _normalize_manual_item(raw))
                )

        # Thematic and color landing content has a Ukrainian owner only.
        if language == "uk":
            theme_chip = _generate_theme_chip(product, language=language)
            if theme_chip is not None:
                chips.append(theme_chip)
            chips.extend(_generate_color_landing_chips(product, language=language))

        sibling_pks: Set[int] = set()
        sibling_chips = _generate_sibling_chips(
            product,
            language=language,
            selected_ids=sibling_pks,
        )
        chips.extend(sibling_chips)

        chips.extend(_generate_category_peer_chips(
            product,
            exclude_ids=sibling_pks,
            language=language,
            limit=3,
        ))
        chips.extend(_generate_support_chips(product, language=language))

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
