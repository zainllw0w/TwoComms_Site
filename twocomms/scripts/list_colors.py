"""Tiny diagnostic — print every Color row + its english slug.

Used by the SEO molecular-upgrade work to figure out the canonical
naming the catalogue uses for colours so the seed scripts pick the
right rows.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "twocomms.settings")

import django

django.setup()

from productcolors.models import Color  # noqa: E402
from productcolors.color_slug_map import english_slug_for_color_name  # noqa: E402

rows = list(
    Color.objects.all().values("id", "name", "primary_hex", "secondary_hex")
)
print(f"total: {len(rows)}")
for r in rows:
    second = f"+{r['secondary_hex']}" if r["secondary_hex"] else ""
    slug = english_slug_for_color_name(r["name"]) if r["name"] else None
    print(
        f"{r['id']:>3} | name={r['name']!r:<30} | hex={r['primary_hex']}{second:<8} | slug={slug}"
    )
