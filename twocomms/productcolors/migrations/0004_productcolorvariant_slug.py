"""Phase 7.1 — add ``slug`` to ProductColorVariant for path-style URLs.

The schema migration adds a SlugField (nullable initially via ``blank=True``
but tightened by uniqueness in the next ``AlterUniqueTogether`` step), an
explicit index on ``(product, slug)``, and a uniqueness constraint scoped
to the parent product. The data migration backfills slugs for every
existing variant using the same algorithm as
``ProductColorVariant._generate_url_slug``: slugify the colour name, fall
back to the primary hex if the name is empty, append ``-c`` for one/two
letter bases that would collide with size codes, and append ``-N``
numeric suffixes on intra-product collisions.
"""

from __future__ import annotations

from django.db import migrations, models
from django.utils.text import slugify


def _candidate_slug(color, used: set[str]) -> str:
    base = ""
    if color is not None:
        base = slugify(color.name or "") or ""
        if not base and getattr(color, "primary_hex", ""):
            base = slugify(color.primary_hex.lstrip("#")) or ""
    if not base:
        base = "color"
    if len(base) <= 4:
        base = f"{base}-c"

    candidate = base
    suffix = 2
    while candidate in used:
        candidate = f"{base}-{suffix}"
        suffix += 1
    used.add(candidate)
    return candidate


def backfill_variant_slugs(apps, schema_editor):
    ProductColorVariant = apps.get_model("productcolors", "ProductColorVariant")

    # Group by product so uniqueness is enforced per product.
    by_product: dict[int, list] = {}
    for variant in ProductColorVariant.objects.select_related("color").all():
        by_product.setdefault(variant.product_id, []).append(variant)

    for product_id, variants in by_product.items():
        used: set[str] = set()
        for variant in variants:
            if variant.slug:
                used.add(variant.slug)
                continue
        for variant in variants:
            if variant.slug:
                continue
            variant.slug = _candidate_slug(variant.color, used)
            variant.save(update_fields=["slug"])


def noop_reverse(apps, schema_editor):
    """Reverse path: clear all slugs (column is dropped on full reverse)."""
    ProductColorVariant = apps.get_model("productcolors", "ProductColorVariant")
    ProductColorVariant.objects.update(slug="")


class Migration(migrations.Migration):

    dependencies = [
        ("productcolors", "0003_variant_inventory_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="productcolorvariant",
            name="slug",
            field=models.SlugField(
                blank=True,
                help_text="Унікальний у межах товару фрагмент URL для path-варіантів.",
                max_length=80,
                verbose_name="URL slug",
            ),
        ),
        migrations.RunPython(backfill_variant_slugs, noop_reverse),
        migrations.AddIndex(
            model_name="productcolorvariant",
            index=models.Index(
                fields=["product", "slug"], name="idx_variant_product_slug"
            ),
        ),
        migrations.AlterUniqueTogether(
            name="productcolorvariant",
            unique_together={("product", "color"), ("product", "slug")},
        ),
    ]
