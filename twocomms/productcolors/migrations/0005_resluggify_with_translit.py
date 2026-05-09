"""Phase 7.1 hotfix — re-generate ProductColorVariant.slug values
that were filled by 0004 using bare ``slugify`` and therefore fell
back to the hex code for any Cyrillic colour name.

This migration only touches rows whose slug looks like a 6-char hex
fallback (``[0-9a-f]{6}`` optionally followed by ``-N``) so we never
overwrite a hand-curated slug that an editor set explicitly.
"""

from __future__ import annotations

import re

from django.db import migrations


HEX_FALLBACK_RE = re.compile(r"^[0-9a-f]{6}(?:-\d+)?$")


def _transliterate(value: str) -> str:
    """Inline copy of dtf.utils.CYRILLIC_TRANSLIT_MAP behaviour to
    avoid importing application code from a migration. Mirrors the
    map used by ``build_slug`` for stability over time.
    """
    table = {
        "а": "a", "б": "b", "в": "v", "г": "h", "ґ": "g", "д": "d",
        "е": "e", "є": "ie", "ж": "zh", "з": "z", "и": "y", "і": "i",
        "ї": "i", "й": "i", "к": "k", "л": "l", "м": "m", "н": "n",
        "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
        "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
        "ь": "", "ю": "iu", "я": "ia", "ё": "e", "ы": "y", "э": "e",
        "ъ": "",
    }
    out = []
    for char in value or "":
        lower = char.lower()
        repl = table.get(lower)
        if repl is None:
            out.append(char)
        else:
            out.append(repl.upper() if char.isupper() else repl)
    return "".join(out)


def _build_slug(name: str) -> str:
    from django.utils.text import slugify

    base = _transliterate(name or "").strip()
    slug = slugify(base, allow_unicode=False)
    if not slug:
        slug = slugify(name or "", allow_unicode=False)
    return (slug or "").strip("-")


def resluggify_hex_fallbacks(apps, schema_editor):
    ProductColorVariant = apps.get_model("productcolors", "ProductColorVariant")

    by_product: dict[int, list] = {}
    for variant in ProductColorVariant.objects.select_related("color").all():
        by_product.setdefault(variant.product_id, []).append(variant)

    for product_id, variants in by_product.items():
        # First snapshot all existing non-hex slugs as "taken" so we
        # don't collide with editor-curated values.
        taken: set[str] = {
            v.slug for v in variants
            if v.slug and not HEX_FALLBACK_RE.match(v.slug)
        }

        for variant in variants:
            if not variant.slug or not HEX_FALLBACK_RE.match(variant.slug):
                continue

            color = variant.color
            base = _build_slug(getattr(color, "name", "") or "")
            if not base:
                # Keep the hex fallback if the colour has no usable name.
                taken.add(variant.slug)
                continue
            if len(base) <= 4:
                base = f"{base}-c"

            candidate = base
            suffix = 2
            while candidate in taken:
                candidate = f"{base}-{suffix}"
                suffix += 1
            taken.add(candidate)

            variant.slug = candidate
            variant.save(update_fields=["slug"])


def noop(apps, schema_editor):
    return None


class Migration(migrations.Migration):

    dependencies = [
        ("productcolors", "0004_productcolorvariant_slug"),
    ]

    operations = [
        migrations.RunPython(resluggify_hex_fallbacks, noop),
    ]
