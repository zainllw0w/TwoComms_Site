"""Phase 15 — per-product SEO landing block (rendered before footer).

Each product page gets a landing block that mirrors the category-page
structure (long SEO text + tabbed top_filters / top_queries / top_menu)
but with **per-product** content:

  * ``landing_html`` — unique text built from the Phase 13.5 theme system
    + city/region paragraphs + colour/fit paragraphs. Plain-text is
    returned as a string with paragraphs already wrapped in ``<p>`` so
    that admins can later override with their own HTML in the optional
    ``Product.seo_bottom_html`` field (rendered with ``|safe``).
  * ``top_queries_items`` — 10–14 dicts ``{"label", "url", "is_external"}``
    with **product-specific** queries; each ``url`` is a real internal
    link (catalog with colour filter, fit-specific path-URL, custom-print,
    etc.). No JS — pure ``<a href>``.
  * ``category_layout`` — re-uses ``top_filters`` and ``top_menu`` from
    the parent category (already curated by Phase 10b). Empty when the
    category has no SEO blocks.
  * ``override_html`` — populated when ``Product.seo_bottom_html`` is set
    (admin override path). Bypasses generated content.

The view passes the result via context as ``product_seo_landing``;
``partials/product_seo_landing.html`` renders the block.

Public API:
  ``build_landing(product, *, fit_code=None) → dict``
"""
from __future__ import annotations

from typing import List, Dict, Any, Optional
from urllib.parse import urlencode

from django.utils.html import escape

from .product_copy_v2 import (
    CATEGORY_COMMON,
    LABEL_NOM,
    LABEL_ACC,
    LABEL_GEN,
    get_theme_for_product,
    build_copy,
)


# Cities where TwoComms ships most. Used both for paragraph weaving and
# top_queries chip labels. URLs always point to the relevant catalog
# category (we don't have city-specific landing pages — yet).
CITY_KEYWORDS = (
    "Київ", "Харків", "Львів", "Одеса", "Дніпро", "Запоріжжя", "Вінниця",
)

# Fit-related label dictionary. Codes mirror ProductFitOption.code.
FIT_LABELS = {
    "oversize": "оверсайз",
    "classic":  "класичну",
    "regular":  "регуляр",
}
FIT_LABELS_NOM = {
    "oversize": "оверсайз",
    "classic":  "класична",
    "regular":  "регуляр",
}

# Phase 16 — fit-specific SEO paragraph templates. Rendered ONLY when
# the user is on a path-fit URL (``/product/<slug>/<fit>/``) so the page
# carries unique content distinct from the base PDP. Each template ends
# with a soft CTA pointing back to the alternate fit so internal
# linking signal is bidirectional.
FIT_SEO_COPY: Dict[str, Dict[str, str]] = {
    "oversize": {
        "h3": "Чому оверсайз-посадка",
        "body": (
            "Оверсайз — це посадка з широкою лінією плечей, подовженим "
            "корпусом і вільним рукавом. Вона додає об'єму силуету, "
            "візуально розслаблює образ і добре поєднується з шарами "
            "(лонгслів під низ, легка куртка зверху). Оверсайз-фіт від "
            "TwoComms шиється з власних лекал: плечі довші на 4–6 см "
            "проти класичної посадки, корпус — на 5–7 см. Ідеально "
            "підходить для streetwear-образів і повсякденного носіння, "
            "коли вам потрібна свобода руху без втрати характеру."
        ),
    },
    "classic": {
        "h3": "Чому класична посадка",
        "body": (
            "Класична посадка тримає тіло природньо: плечовий шов "
            "на місці плеча, корпус прямий, рукав — стандартної довжини. "
            "Це універсальний фіт, який легко поєднується з будь-яким "
            "стилем — від casual до бізнес-кежуала під сорочку чи "
            "піджак. Класика від TwoComms відшивається з тих самих "
            "матеріалів, що й оверсайз: щільна бавовна 280–320 г/м² "
            "і DTF-друк, який витримує понад 50 циклів прання. "
            "Обирайте класику, якщо цінуєте лаконічну форму без "
            "акцентів на об'ємі."
        ),
    },
    "regular": {
        "h3": "Чому регуляр-посадка",
        "body": (
            "Регуляр — золота середина між класикою і оверсайзом: трохи "
            "ширша лінія плечей, дещо подовжений корпус, але без "
            "вираженого «упалого» плеча. Підійде тим, хто хоче більше "
            "свободи, ніж дає класична посадка, але не готовий до "
            "повного оверсайз-силуету."
        ),
    },
}


# --------------------------------------------------------------- helpers

def _nom(cat):     return LABEL_NOM.get(cat, "товар")
def _acc(cat):     return LABEL_ACC.get(cat, "товар")
def _gen(cat):     return LABEL_GEN.get(cat, "товару")
def _nom_cap(cat): return _nom(cat).capitalize()


# SEO Audit 2026-05-15 (Part 4) — sibling-design cross-link map.
# Same-design garments share a slug stem like ``my-little-baby``,
# ``my-little-baby-hd`` (hoodie), ``my-little-baby-ls`` (longsleeve).
# We strip the trailing category marker to derive the design family.
_SLUG_CATEGORY_MARKERS = ("-hd", "-ls", "-ts")
# Phase ordering: ts → tshirts (no suffix), hd → hoodie, ls → long-sleeve.
_CATEGORY_TO_MARKER = {
    "tshirts":     "",
    "hoodie":      "-hd",
    "long-sleeve": "-ls",
}
_MARKER_TO_CATEGORY = {marker: cat for cat, marker in _CATEGORY_TO_MARKER.items() if marker}


def _design_family_stem(slug: str) -> str:
    """Strip the category marker so siblings share a stem.

    Examples:
        ``my-little-baby``      → ``my-little-baby``
        ``my-little-baby-hd``   → ``my-little-baby``
        ``my-little-baby-ls``   → ``my-little-baby``
        ``-225-tshirt-`` (legacy) → ``-225-tshirt-`` (no marker → unchanged)
    """
    if not slug:
        return ""
    for marker in _SLUG_CATEGORY_MARKERS:
        if slug.endswith(marker):
            stem = slug[: -len(marker)]
            return stem.rstrip("-")
    return slug


def _design_family_siblings(product) -> List[Dict[str, str]]:
    """Find sibling products (same design, different category).

    SEO Audit 2026-05-15 (Part 4) recommended cross-linking the three
    variants (футболка / худі / лонгслів) of each design so internal
    PageRank flows between them and Google can cluster the design
    semantically. The lookup is purely heuristic on slug stems —
    works for ~80% of the catalogue where slugs follow the convention.

    Returns a list of dicts ``{"label": str, "url": str, "title": str}``
    suitable for both the landing block and the top_queries chips.
    """
    try:
        # Local import to avoid circular deps at module load.
        from storefront.models import Product  # type: ignore
    except Exception:
        return []

    base_slug = product.slug or ""
    stem = _design_family_stem(base_slug)
    if not stem or stem == base_slug and not any(
        base_slug.endswith(m) for m in _SLUG_CATEGORY_MARKERS
    ):
        # No recognisable family marker on this product → still try to
        # find siblings by attaching markers to the (unchanged) stem.
        pass

    candidate_slugs = {stem}
    for marker in _CATEGORY_TO_MARKER.values():
        if marker:
            candidate_slugs.add(f"{stem}{marker}")

    # Exclude the current product.
    candidate_slugs.discard(base_slug)
    if not candidate_slugs:
        return []

    qs = (
        Product.objects.filter(slug__in=candidate_slugs)
        .select_related("category")
        .only("id", "slug", "title", "category__slug", "category__name", "status")
    )

    siblings: List[Dict[str, str]] = []
    for sibling in qs:
        # Only surface siblings that are publishable.
        status = getattr(sibling, "status", "")
        if status and str(status).lower() not in {"published", "active", "publish", "live"}:
            continue
        cat = getattr(sibling, "category", None)
        cat_slug = getattr(cat, "slug", "") or ""
        cat_label = _nom(cat_slug) or "товар"
        siblings.append({
            "url":      f"/product/{sibling.slug}/",
            "label":    cat_label,           # «худі», «футболка», «лонгслів»
            "title":    sibling.title or "",
            "cat_slug": cat_slug,
        })

    # Stable ordering: tshirts → hoodie → long-sleeve.
    order = {"tshirts": 0, "hoodie": 1, "long-sleeve": 2}
    siblings.sort(key=lambda s: order.get(s["cat_slug"], 99))
    return siblings


def _siblings_paragraph(product) -> str:
    """Render the sibling-design paragraph for the SEO landing block.

    Returns empty string if there are no siblings — keeping the block
    short on standalone designs avoids artificially-empty paragraphs.
    """
    siblings = _design_family_siblings(product)
    if not siblings:
        return ""

    parts = [
        f'<a href="{escape(s["url"])}">{escape(s["label"])}</a>'
        for s in siblings
    ]
    if len(parts) == 1:
        anchors = parts[0]
    elif len(parts) == 2:
        anchors = f"{parts[0]} та {parts[1]}"
    else:
        anchors = ", ".join(parts[:-1]) + f" та {parts[-1]}"

    return (
        f"Дизайн «{escape(product.title)}» доступний також у форматі "
        f"{anchors} — щоб ви могли зібрати капсулу одного принту під "
        f"різну погоду."
    )


def _category_url(cat_slug: str, **params) -> str:
    base = f"/catalog/{cat_slug}/" if cat_slug else "/catalog/"
    if params:
        # Filter out empty values; sort for deterministic output.
        kv = [(k, v) for k, v in params.items() if v]
        if kv:
            return f"{base}?{urlencode(kv, doseq=True)}"
    return base


def _product_variant_url(product, *, color_slug: str = "", fit_code: str = "") -> str:
    """Build a variant path-URL for the product (Phase 7 path-URL system).

    Order: ``/product/<slug>/<color>/<fit>/`` (Phase 7.1 contract).
    Empty segments are skipped.
    """
    base = f"/product/{product.slug}"
    parts = [seg for seg in (color_slug, fit_code) if seg]
    if parts:
        return base + "/" + "/".join(parts) + "/"
    return base + "/"


# ----------------------------------------------------- landing_html

def _city_paragraph(product, cat_slug: str, fit_code: Optional[str] = None) -> str:
    """Geo-aware delivery paragraph.

    SEO Audit 2026-05-15 (Part 6) — the legacy implementation listed
    eight cities in a single sentence and added "доставка день у день
    при замовленні до 14:00", which (a) was identical across all 65
    PDPs (only the title changed) and (b) over-promised an hourly SLA
    that is not part of the live delivery policy.

    The new copy keeps the geo signal (Ukraine + 4 anchor cities) and
    adds a *fit-aware* sentence so each PDP renders a unique bottom
    paragraph: classic / oversize / regular each get their own clause.
    The "до 14:00" courier promise is dropped.
    """
    cat_name_acc = _acc(cat_slug)
    fit_acc = FIT_LABELS.get(fit_code or "")
    fit_phrase = f"{fit_acc} " if fit_acc else ""

    fit_clause_map = {
        "oversize": (
            "Oversize-силует тримає форму на росту 165–195 см і виглядає "
            "однаково добре і поверх лонгсліва, і самостійно."
        ),
        "classic": (
            "Класичний крій підходить тим, хто шукає чисту базу під "
            "джинси, карго або шари у міжсезоння."
        ),
        "regular": (
            "Помірний regular-силует — між класикою й оверсайзом, "
            "коли треба універсальний шар на щодня."
        ),
        "slim": (
            "Slim-силует акцентує посадку — підходить тим, хто будує "
            "комплекти з лаконічним низом."
        ),
        "loose": (
            "Loose-силует залишає простір для шарів і вільної посадки "
            "без агресивного оверсайзу."
        ),
    }
    fit_clause = fit_clause_map.get(fit_code or "", "")

    return (
        f"Замовити {fit_phrase}{cat_name_acc} «{product.title}» можна по "
        f"всій Україні: Київ, Харків, Львів, Одеса, Дніпро та інші міста. "
        f"Доставка Новою Поштою — 1–3 робочі дні після відправлення, "
        f"відстеження по TTN. {fit_clause}"
    ).strip()


def _color_paragraph(product, cat_slug: str) -> str:
    """Paragraph mentioning available colors with internal links."""
    variants = list(product.color_variants.select_related("color").all()) \
        if hasattr(product, "color_variants") else []
    if not variants:
        return ""

    color_phrases = []
    for v in variants[:6]:
        color = getattr(v, "color", None)
        color_name = (getattr(color, "name", "") or "").strip()
        slug = (v.slug or "").strip()
        if color_name and slug:
            url = _product_variant_url(product, color_slug=slug)
            color_phrases.append(f'<a href="{escape(url)}">{escape(color_name)}</a>')
        elif color_name:
            color_phrases.append(escape(color_name))

    if not color_phrases:
        return ""
    nom = _nom(cat_slug)
    if len(color_phrases) == 1:
        joined = color_phrases[0]
    elif len(color_phrases) == 2:
        joined = " та ".join(color_phrases)
    else:
        joined = ", ".join(color_phrases[:-1]) + f" та {color_phrases[-1]}"
    return (
        f"Ця {nom} доступна у кольорах {joined}. Кожен варіант — це окрема "
        f"посадка, тому фотографії на сторінці товару точно відображають "
        f"той колір, який ви оберете у фільтрі."
    )


def _fit_paragraph(product, cat_slug: str, fit_code: Optional[str] = None) -> str:
    """Paragraph mentioning available fits."""
    if not hasattr(product, "fit_options"):
        return ""
    try:
        from .catalog_helpers import get_active_fit_options
        options = list(get_active_fit_options(product))
    except Exception:
        options = []
    if not options:
        return ""

    fit_links = []
    for opt in options:
        code = (opt.code or "").strip().lower()
        label = (opt.label or FIT_LABELS_NOM.get(code) or code).strip()
        if code:
            url = _product_variant_url(product, fit_code=code)
            fit_links.append(f'<a href="{escape(url)}">{escape(label)}</a>')

    if not fit_links:
        return ""

    nom = _nom(cat_slug)
    if fit_code and fit_code in FIT_LABELS_NOM:
        active = FIT_LABELS_NOM[fit_code]
        return (
            f"Ви переглядаєте цю {nom} у посадці <strong>{escape(active)}</strong>. "
            f"Доступні також інші посадки: {', '.join(fit_links)}. "
            f"Перемикання між посадками змінює текст і ключові слова сторінки "
            f"для коректного індексу пошуковими системами."
        )
    return (
        f"Ця {nom} доступна у кількох посадках: {', '.join(fit_links)}. "
        f"Виберіть свою — від класичного, ближчого до тіла силуету, до "
        f"виразного оверсайз-фіту."
    )


def _theme_long_paragraph(product) -> str:
    """The Phase-13.5 theme intro_long, wrapped in <p>."""
    copy = build_copy(product)
    text = (copy.get("full_description") or "").strip()
    if not text:
        return ""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    return "".join(f"<p>{escape(p)}</p>" for p in paragraphs)


def _seo_closing_paragraph(product, cat_slug: str) -> str:
    nom = _nom(cat_slug)
    title = product.title.strip()
    return (
        f"TwoComms — це український streetwear-бренд із мілітарним ДНК. "
        f"Кожна {nom}, як і модель «{title}», шиється в Україні зі щільної "
        f"бавовни, з нанесенням принта DTF-друком, який витримує понад 50 "
        f"циклів прання без втрати яскравості. Частина прибутку від кожної "
        f"покупки йде на потреби Збройних Сил України."
    )


def _build_landing_html(product, fit_code: Optional[str] = None) -> str:
    cat_slug = product.category.slug if product.category else "tshirts"
    parts: List[str] = []

    # Header H2.
    if fit_code and fit_code in FIT_LABELS_NOM:
        h2 = (
            f"{escape(product.title)} ({FIT_LABELS_NOM[fit_code].title()}) "
            f"— деталі моделі"
        )
    else:
        h2 = f"{escape(product.title)} — деталі моделі"
    parts.append(f'<h2 class="product-seo-landing__title">{h2}</h2>')

    # Theme intro paragraphs (from Phase 13.5).
    theme_html = _theme_long_paragraph(product)
    if theme_html:
        parts.append(theme_html)

    # Color paragraph (skip when no color variants).
    color_html = _color_paragraph(product, cat_slug)
    if color_html:
        parts.append(f"<p>{color_html}</p>")

    # SEO Audit 2026-05-15 (Part 4) — sibling-design cross-link
    # paragraph. Each design has up to 3 garments (футболка/худі/
    # лонгслів) sharing a slug stem; surfacing them here gives Google
    # an explicit signal that the variants belong to one product
    # cluster and lets buyers pivot between formats without leaving
    # the design.
    siblings_html = _siblings_paragraph(product)
    if siblings_html:
        parts.append(f"<p>{siblings_html}</p>")

    # Fit paragraph (skip when no fit options).
    fit_html = _fit_paragraph(product, cat_slug, fit_code=fit_code)
    if fit_html:
        parts.append(f"<p>{fit_html}</p>")

    # Phase 16 — fit-specific unique SEO paragraph (oversize/classic/regular).
    # Rendered only when a path-fit is actively selected so the page text
    # differs from the base PDP and from the alternate-fit page.
    if fit_code and fit_code in FIT_SEO_COPY:
        fit_copy = FIT_SEO_COPY[fit_code]
        parts.append(
            f'<h3 class="product-seo-landing__fit-h3">{escape(fit_copy["h3"])}</h3>'
        )
        parts.append(f'<p>{escape(fit_copy["body"])}</p>')

    # City keywords paragraph.
    parts.append(f"<p>{escape(_city_paragraph(product, cat_slug, fit_code=fit_code))}</p>")

    # SEO closing paragraph (brand + DTF + ZSU).
    parts.append(f"<p>{escape(_seo_closing_paragraph(product, cat_slug))}</p>")

    return "".join(parts)


# ----------------------------------------------------- top_queries

def _top_queries_for_product(product, fit_code: Optional[str] = None) -> List[Dict[str, str]]:
    """Generate 10–14 product-specific query chips with real internal URLs."""
    cat_slug = product.category.slug if product.category else ""
    nom = _nom(cat_slug)
    acc = _acc(cat_slug)
    title = product.title.strip()
    items: List[Dict[str, str]] = []

    # 1. Available colors (one chip per variant, up to 4).
    try:
        color_variants = list(product.color_variants.select_related("color").all()[:4])
    except Exception:
        color_variants = []
    for v in color_variants:
        color = getattr(v, "color", None)
        color_name = (getattr(color, "name", "") or "").strip()
        slug = (v.slug or "").strip()
        if not (color_name and slug):
            continue
        items.append({
            "label": f"Купити {acc} «{title}» — {color_name.lower()}",
            "url":   _product_variant_url(product, color_slug=slug),
        })

    # 1b. Sibling-design chips (Part 4 cross-links). Inserted right
    # after the color chips so Google sees variant-cluster signal
    # near the top of the chip strip rather than buried at the end.
    for sibling in _design_family_siblings(product):
        sibling_label = (sibling.get("label") or "").strip()
        sibling_url = sibling.get("url") or ""
        if not (sibling_label and sibling_url):
            continue
        items.append({
            "label": f"Цей дизайн у форматі «{sibling_label}»",
            "url":   sibling_url,
        })

    # 2. Fit options.
    try:
        from .catalog_helpers import get_active_fit_options
        fit_options = list(get_active_fit_options(product))
    except Exception:
        fit_options = []
    for opt in fit_options[:2]:
        code = (opt.code or "").strip().lower()
        if not code or code == (fit_code or "").lower():
            continue  # skip current fit
        label = (opt.label or FIT_LABELS_NOM.get(code) or code).strip().lower()
        items.append({
            "label": f"Купити {acc} «{title}» {label}",
            "url":   _product_variant_url(product, fit_code=code),
        })

    # 3. Phase 21 (2026-05-10) — city chips removed.
    #
    # Pre-Phase-21 we surfaced "Купити <product> Київ / Харків / Львів /
    # Одеса" chips here. They linked to the category page with no
    # city-specific content, so Google treated them as keyword-stuffing
    # signals and the audit (TWOCOMMS_ECOMMERCE_SEO_AUDIT_2026-05-10.md
    # §FAQ/Content) called them out as a ranking liability. Real city
    # landing pages would need locally-relevant content (delivery times
    # per branch, store list, etc.); we don't have that yet.
    #
    # The ``city_url`` shortcut is preserved here because the category
    # fallback chip below (4-5) still uses it. ``CITY_KEYWORDS`` stays
    # in the module-level constant for future opt-in.
    city_url = _category_url(cat_slug)

    # 3b. Phase 21 (PR-5 T11.2) — buyer-facing chips replacing the
    # removed city chips. Each links to a support page that already
    # carries unique content (covered by FAQPage schema there) so we
    # get topical relevance without thin city-page duplication.
    items.append({
        "label": "Доставка Новою Поштою 1-3 дні",
        "url":   "/delivery/",
    })
    items.append({
        "label": "Розмірна сітка та посадка",
        "url":   "/rozmirna-sitka/",
    })
    items.append({
        "label": "Повернення та обмін за 14 днів",
        "url":   "/povernennya-ta-obmin/",
    })

    # 4. Custom print.
    items.append({
        "label": "Замовити кастомний друк свого принта",
        "url":   "/custom-print/",
    })
    items.append({
        "label": f"{nom.capitalize()} зі своїм принтом",
        "url":   "/custom-print/",
    })

    # 5. Category fallback chips.
    items.append({
        "label": f"Усі {nom}и TwoComms",
        "url":   city_url,
    })

    # 6. Theme-specific keywords (one chip per top theme keyword).
    theme = get_theme_for_product(product)
    if theme:
        # Use the first 2 theme keywords as chips → /catalog/<cat>/.
        for kw in theme.get("kw", [])[:2]:
            label = kw.format(nom=nom, gen=_gen(cat_slug)).strip()
            if not label:
                continue
            items.append({
                "label": label.capitalize(),
                "url":   city_url,
            })

    # Hard cap to keep the chip strip readable.
    return items[:14]


# ----------------------------------------------------- category layout reuse

def _category_layout_for_product(product) -> Dict[str, Any]:
    """Re-use ``top_filters`` and ``top_menu`` from the parent category.

    Skips ``top_cards`` and ``best_prices`` (catalog-specific).
    """
    if not product.category:
        return {"tab_blocks": [], "best_prices": None, "has_any": False}

    from .category_seo_blocks import get_category_seo_layout
    layout = get_category_seo_layout(product.category)
    # Filter to only the link-only blocks; product page has its own
    # top_queries + per-product cards (recommended + landing copy).
    keep_types = {"top_filters", "top_menu"}
    layout["tab_blocks"] = [
        e for e in layout.get("tab_blocks", [])
        if e["block"].block_type in keep_types
    ]
    # Drop best_prices; the product page is one of the rows.
    layout["best_prices"] = None
    layout["has_any"] = bool(layout["tab_blocks"])
    return layout


# ----------------------------------------------------- public API

def build_landing(product, *, fit_code: Optional[str] = None) -> Dict[str, Any]:
    """Public entry point. Returns dict suitable for template context.

    SEO molecular-upgrade US-6 finishing (2026-05-17) — top_queries_items
    now comes from ``product_search_keywords.build_product_search_keywords``
    so every chip points at a *different* indexable URL (colour landing,
    theme landing, design-triplet sibling, category peer, support page)
    rather than back at the same product. The legacy
    ``_top_queries_for_product`` is kept below as ``_legacy_top_queries``
    for reference; remove after a few weeks of stable production.
    """
    from .product_search_keywords import build_product_search_keywords

    chips = build_product_search_keywords(product)

    override = (getattr(product, "seo_bottom_html", "") or "").strip()
    if override:
        return {
            "override_html":     override,
            "landing_html":      "",
            "top_queries_items": chips,
            "category_layout":   _category_layout_for_product(product),
            "fit_code":          fit_code or "",
        }

    return {
        "override_html":     "",
        "landing_html":      _build_landing_html(product, fit_code=fit_code),
        "top_queries_items": chips,
        "category_layout":   _category_layout_for_product(product),
        "fit_code":          fit_code or "",
    }


# ----------------------------------------------------- legacy (will be removed)
_legacy_top_queries = _top_queries_for_product

