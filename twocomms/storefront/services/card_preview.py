"""Phase 14 — color-filter-aware product card preview.

When the catalog is filtered by ``?color=<slug>``, each product card
should show the variant image whose ``slug`` matches one of the
selected slugs — instead of the product's default ``homepage_image``.
The legacy default leads to confusing UX (e.g. the user filters by
"black" but a card still shows "coyote" because that's the default
preview).

Given ``products`` (already ordered, in-memory) and the parsed list of
selected slugs, this helper attaches two attributes per product so the
template can use them without additional DB hits:

  * ``product.preferred_card_image_url`` — the matching variant's first
    image URL, if any. Empty string when no match (template falls back
    to ``homepage_image``).
  * ``product.preferred_card_image_alt`` — variant-aware alt text
    ("<title> — <colour name>") when set, blank otherwise.

Implementation details:
- Operates strictly on data already present in
  ``product.colors_preview`` (populated by
  ``services.catalog_helpers.build_color_preview_map`` upstream), so
  there are no extra queries.
- Picks the first selected slug that is actually present on the
  product, in user-selection order. This means
  ``?color=black,coyote`` shows black for products that have black,
  and coyote for products that only have coyote — exactly the OR-match
  behaviour ``apply_color_filter`` already implements.
- A product without colour variants or with a selected colour that
  doesn't match any of its variants gets blank attributes — template
  falls back to ``homepage_image`` (no regression).

Phase 14 ships only the catalog/search wiring; future phases may use
the same helper on the homepage chip-strip for parity.
"""
from __future__ import annotations

from typing import Iterable, Optional, Sequence


def _variant_for_slug(colors_preview, slug: str):
    """Find the colour preview entry whose slug matches.

    ``colors_preview`` items don't carry a ``slug`` field (it lives on
    ``ProductColorVariant.slug``), so we match by the variant id and
    look it up via the ``catalog_helpers`` mapping. To keep this helper
    free of DB queries we instead match by the lower-cased name first;
    this is reliable because Phase 9's slugs are derived from the
    variant ``Color.name`` via the same translation map.
    """
    needle = (slug or "").strip().lower()
    if not needle:
        return None
    for entry in colors_preview or []:
        # Phase 9's chip slugs are derived from ``Color.name``. The
        # preview map carries the variant slug as ``slug`` (added by
        # ``apply_color_preview_slug`` below) so a direct compare works.
        if (entry.get("slug") or "").strip().lower() == needle:
            return entry
    return None


def attach_preferred_card_image(
    products: Iterable,
    selected_color_slugs: Sequence[str],
) -> None:
    """Attach ``preferred_card_image_url`` / ``preferred_card_image_alt``.

    Mutates each product object in-place. Idempotent: if no slugs are
    selected (or the product has no matching variant), the attributes
    are set to empty strings — the template's ``{% if preferred_image_url %}``
    branch falls back to ``homepage_image``.
    """
    slugs = [s for s in (selected_color_slugs or []) if s]
    for product in products:
        url = ""
        alt = ""
        # Bug-fix 2026-05-10: when the catalog has an active colour
        # filter, also propagate the matching variant's slug so the
        # card link can navigate to ``/product/<slug>/<color>/``. Then
        # the PDP preselects the colour the user actually filtered on
        # (instead of falling back to the first variant in DB order,
        # which is often "Coyote" for legacy reasons). The slug is
        # captured for the FIRST matching colour so a multi-colour
        # filter (?color=black,red) still resolves deterministically.
        preferred_slug = ""
        if slugs:
            colors_preview = getattr(product, "colors_preview", None) or []
            for slug in slugs:
                variant = _variant_for_slug(colors_preview, slug)
                if variant is None:
                    continue
                # Capture variant slug regardless of whether a card
                # image is available — the link itself is meaningful
                # even when the image falls back to homepage_image.
                if not preferred_slug:
                    preferred_slug = (variant.get("slug") or "").strip()
                if variant.get("first_image_url"):
                    url = variant["first_image_url"]
                    name = (variant.get("name") or "").strip()
                    title = getattr(product, "title", "") or ""
                    alt = f"{title} — {name}" if name else title
                    break
        # Always set the attributes so templates don't error on missing
        # attribute access (Django silences AttributeError but explicit
        # empty string is clearer in tests + debugging).
        setattr(product, "preferred_card_image_url", url)
        setattr(product, "preferred_card_image_alt", alt)
        setattr(product, "preferred_color_slug", preferred_slug)


# ---------------------------------------------------------------------------
# Augment ``build_color_preview_map`` output so each preview dict carries
# the variant ``slug``. Implemented as a separate helper so we don't have
# to modify the existing catalog_helpers signature (and risk side-effects
# in unrelated callers).
# ---------------------------------------------------------------------------

def enrich_color_preview_with_slugs(products: Iterable) -> None:
    """Add ``slug`` key to each entry of ``product.colors_preview``.

    The slug is fetched from the corresponding ``ProductColorVariant``
    row via the in-memory ``id`` already present in the preview entry.
    Single batched query → no N+1.
    """
    from django.apps import apps

    products = list(products)
    variant_ids = []
    for p in products:
        for entry in getattr(p, "colors_preview", None) or []:
            vid = entry.get("id")
            if isinstance(vid, int):
                variant_ids.append(vid)
    if not variant_ids:
        return

    try:
        ProductColorVariant = apps.get_model("productcolors", "ProductColorVariant")
    except LookupError:
        return

    slug_by_id = dict(
        ProductColorVariant.objects
        .filter(id__in=variant_ids)
        .values_list("id", "slug")
    )
    if not slug_by_id:
        return

    for p in products:
        for entry in getattr(p, "colors_preview", None) or []:
            vid = entry.get("id")
            entry["slug"] = slug_by_id.get(vid, "") if isinstance(vid, int) else ""
