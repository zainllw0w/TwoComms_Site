"""Dynamic meta + canonical for path-style product variants.

Given the segments a user selected via the URL path (``size`` +
``color`` + ``fit``), this module builds three things the product
detail view passes to the template:

* ``canonical_path``      — absolute URL path the ``<link rel=canonical>``
  tag must point at. Self-canonical for base + single-segment pages
  (we want these indexed); collapses to the base product URL for
  multi-segment combos so Google consolidates signal on the main page.
* ``page_title``          — locale-aware title enriched only with the
  selected variant ("Футболка — чорна, розмір M — TwoComms").
  Empty string when no variant segments are in play so the view falls
  back to the standard ``seo_title`` template tag.
* ``page_description``    — empty unless a reviewed, locale-owned
  variant override is supplied by the caller; the helper never invents
  editorial claims for a URL selection.

The helper is pure: no DB access, no request state. The caller
resolves the active colour / size / fit and passes them in.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


SUPPORTED_LANGUAGES = {"uk", "ru", "en"}
SIZE_LABELS = {
    "uk": "розмір",
    "ru": "размер",
    "en": "size",
}
FIT_LABELS = {
    "uk": {
        "classic": "класична",
        "oversize": "оверсайз",
        "relaxed": "вільна",
    },
    "ru": {
        "classic": "классическая",
        "oversize": "оверсайз",
        "relaxed": "свободная",
    },
    "en": {
        "classic": "classic",
        "oversize": "oversize",
        "relaxed": "relaxed",
    },
}


@dataclass(frozen=True)
class VariantMetaInputs:
    """Inputs the view already has at hand after Phase 7.2 parsing."""

    product_title: str
    base_path: str                # e.g. ``/product/foo/``
    current_path: str             # e.g. ``/product/foo/black/m/``
    segments_count: int           # 0..3

    color_name: Optional[str] = None       # "Чорний" — only set if path had colour
    color_slug: Optional[str] = None       # "black"
    size_code: Optional[str] = None        # "M" — only set if path had size
    fit_label: Optional[str] = None        # "Оверсайз" — only set if path had fit
    fit_code: Optional[str] = None         # "oversize"
    language: str = "uk"


def _normalize_language(value: str | None) -> str:
    language = str(value or "uk").lower().replace("_", "-").split("-", 1)[0]
    return language if language in SUPPORTED_LANGUAGES else "uk"


def _lowercase_first(value: str) -> str:
    if not value:
        return ""
    return value[0].lower() + value[1:]


def _join_suffix_parts(parts: list[str]) -> str:
    """Join ``[color, size, fit]`` into a comma-separated human suffix.

    Empty entries are skipped. Result has no trailing separator.
    """
    clean = [p for p in parts if p]
    return ", ".join(clean)


def _fit_label(inputs: VariantMetaInputs) -> str:
    language = _normalize_language(inputs.language)
    code = str(inputs.fit_code or "").strip().lower()
    localized = FIT_LABELS.get(language, {}).get(code)
    if localized:
        return localized
    return _lowercase_first(inputs.fit_label or "")


def _build_title_suffix(inputs: VariantMetaInputs) -> str:
    parts: list[str] = []
    if inputs.color_name:
        parts.append(_lowercase_first(inputs.color_name))
    if inputs.size_code:
        size_label = SIZE_LABELS[_normalize_language(inputs.language)]
        parts.append(f"{size_label} {inputs.size_code}")
    if inputs.fit_label:
        parts.append(_fit_label(inputs))
    return _join_suffix_parts(parts)


def build_variant_meta(inputs: VariantMetaInputs) -> dict:
    """Return a ``dict`` with ``canonical_path`` / ``page_title`` /
    ``page_description`` ready for the template context.

    Callers that detect zero selected segments should still call this —
    the returned dict will signal "no variant" with empty strings and
    the canonical path falling back to ``base_path``.
    """
    if inputs.segments_count <= 0:
        return {
            "canonical_path": inputs.base_path,
            "page_title": "",
            "page_description": "",
            "page_keywords": "",
            "title_suffix": "",
            "is_self_canonical": True,
        }

    suffix = _build_title_suffix(inputs)

    # Canonical strategy:
    #   * 1 segment colour or fit → self (indexable long-tail like
    #     ``/product/x/black/`` or ``/product/x/oversize/``).
    #   * 1 segment size-only      → base URL. Phase 21 (2026-05-10):
    #     ``/product/x/m/`` shows the same product with a preselected
    #     size — the visible content is essentially identical to the
    #     base PDP, so we consolidate signal on the base URL. The page
    #     stays reachable for UX deep links.
    #   * 2+ segments              → base URL, consolidating signal on
    #     the main product page. We still render rich per-variant meta
    #     so users landing on the URL see the right title in the tab.
    is_size_only_single = (
        inputs.segments_count == 1
        and bool(inputs.size_code)
        and not inputs.color_slug
        and not inputs.fit_code
    )
    # SEO 2026-05-19 (VILNI deep review §12.3/§12.4 — TASK I).
    # A 2-segment URL composed of *colour + fit* (no size) is a
    # high-commercial-intent long-tail combo ("чорна футболка
    # оверсайз з принтом"). Indexing it as self-canonical lets the
    # site rank for that combined query instead of collapsing all
    # signal onto the base PDP. Size-bearing combos still consolidate
    # to base (size has near-zero search demand and creates crawl
    # noise — audit §12.3 point 2).
    is_color_fit_combo = (
        inputs.segments_count == 2
        and bool(inputs.color_slug)
        and bool(inputs.fit_code)
        and not inputs.size_code
    )
    if inputs.segments_count == 1 and not is_size_only_single:
        canonical_path = inputs.current_path
        is_self_canonical = True
    elif is_color_fit_combo:
        canonical_path = inputs.current_path
        is_self_canonical = True
    else:
        canonical_path = inputs.base_path
        is_self_canonical = False

    # Variant metadata may safely describe only the factual URL selection.
    # Editorial descriptions and keywords belong to reviewed, locale-owned
    # product/variant fields; generated claims here caused wrong-language and
    # unsupported material/delivery statements on RU/EN URLs.
    page_title = f"{inputs.product_title} — {suffix} — TwoComms" if suffix else ""
    page_description = ""
    page_keywords = ""

    return {
        "canonical_path": canonical_path,
        "page_title": page_title,
        "page_description": page_description,
        "page_keywords": page_keywords,
        "title_suffix": suffix,
        "is_self_canonical": is_self_canonical,
    }


__all__ = ["VariantMetaInputs", "build_variant_meta"]
