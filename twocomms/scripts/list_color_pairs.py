"""Diagnostic — list every (Category, Color) pair that actually has
products with that colour, so the SEO seed knows which landings to create.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "twocomms.settings")

import django

django.setup()

from collections import defaultdict  # noqa: E402

from productcolors.color_slug_map import english_slug_for_color_name  # noqa: E402
from productcolors.models import ProductColorVariant  # noqa: E402

pairs = defaultdict(set)
for v in (
    ProductColorVariant.objects
    .select_related("product", "product__category", "color")
    .filter(product__is_active=True)
    if hasattr(__import__("storefront.models", fromlist=["Product"]).Product, "is_active")
    else ProductColorVariant.objects.select_related("product", "product__category", "color")
):
    cat = getattr(v.product, "category", None)
    if cat is None:
        continue
    color = v.color
    if not color or not color.name:
        continue
    pairs[(cat.slug, cat.name, color.name)].add(v.product_id)

rows = sorted(pairs.items(), key=lambda kv: (kv[0][0], kv[0][2]))
print(f"valid (category, color) pairs with at least 1 product: {len(rows)}")
for (cat_slug, cat_name, color_name), product_ids in rows:
    slug = english_slug_for_color_name(color_name)
    print(
        f"{cat_slug:<12} | {cat_name:<14} | color={color_name!r:<25} | en_slug={slug:<20} | products={len(product_ids)}"
    )
