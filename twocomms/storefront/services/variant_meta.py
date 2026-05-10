"""Phase 7.3 — dynamic meta + canonical for path-style product variants.

Given the segments a user selected via the URL path (``size`` +
``color`` + ``fit``), this module builds three things the product
detail view passes to the template:

* ``canonical_path``      — absolute URL path the ``<link rel=canonical>``
  tag must point at. Self-canonical for base + single-segment pages
  (we want these indexed); collapses to the base product URL for
  multi-segment combos so Google consolidates signal on the main page.
* ``page_title``          — Ukrainian-language title enriched with the
  selected variant ("Купити футболку … — чорна, розмір M — TwoComms").
  Empty string when no variant segments are in play so the view falls
  back to the standard ``seo_title`` template tag.
* ``page_description``    — matching meta description with the same
  variant enrichment, or empty string on the base page.

The helper is pure: no DB access, no request state. The caller
resolves the active colour / size / fit and passes them in.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


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


def _build_title_suffix(inputs: VariantMetaInputs) -> str:
    parts: list[str] = []
    if inputs.color_name:
        parts.append(_lowercase_first(inputs.color_name))
    if inputs.size_code:
        parts.append(f"розмір {inputs.size_code}")
    if inputs.fit_label:
        parts.append(_lowercase_first(inputs.fit_label))
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
    #   * 1 segment → self (indexable long-tail like ``/product/x/black/``).
    #   * 2+ segments → base URL, consolidating signal on the main
    #     product page. We still render rich per-variant meta so users
    #     landing on the URL see the right title in the browser tab.
    if inputs.segments_count == 1:
        canonical_path = inputs.current_path
        is_self_canonical = True
    else:
        canonical_path = inputs.base_path
        is_self_canonical = False

    if suffix:
        # Phase 16 — fit-aware enrichment. When the user is on a
        # ``/product/<slug>/<fit>/`` page (1-segment fit), promote the
        # fit term to the *front* of both title and description so it
        # carries Google's primary keyword weight. Multi-segment combos
        # keep the suffix order (color → size → fit).
        fit_lead = inputs.fit_label and inputs.segments_count == 1
        if fit_lead:
            page_title = (
                f"{inputs.fit_label} {inputs.product_title} — "
                f"купити в TwoComms"
            )
            page_description = (
                f"{inputs.fit_label} посадка «{inputs.product_title}»: щільна бавовна, "
                f"DTF-друк, доставка Новою Поштою по всій Україні за 1–3 дні. "
                f"Обирайте {_lowercase_first(inputs.fit_label)}-фіт — лаконічний стрітвеар від українського бренду."
            )
        else:
            page_title = f"Купити {inputs.product_title} — {suffix} — TwoComms"
            page_description = (
                f"Купити {inputs.product_title} ({suffix}) в TwoComms. "
                "Якісний стріт & мілітарі одяг з ексклюзивним дизайном."
            )
    else:
        page_title = ""
        page_description = ""

    # Phase 16 — keywords meta. Only filled when *fit* is the active
    # 1-segment variant; otherwise empty (the standard ``seo_keywords``
    # template tag stays in charge for the base PDP).
    page_keywords = ""
    if inputs.fit_label and inputs.fit_code and inputs.segments_count == 1:
        fit_lc = _lowercase_first(inputs.fit_label)
        page_keywords = (
            f"{fit_lc} {inputs.product_title.lower()}, "
            f"купити {fit_lc} {inputs.product_title.lower()}, "
            f"{fit_lc} посадка, {inputs.fit_code}"
        )

    return {
        "canonical_path": canonical_path,
        "page_title": page_title,
        "page_description": page_description,
        "page_keywords": page_keywords,
        "title_suffix": suffix,
        "is_self_canonical": is_self_canonical,
    }


__all__ = ["VariantMetaInputs", "build_variant_meta"]
