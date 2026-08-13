"""Retired Phase 13.5 recraft entry point for standard Products.

Safe-overwrite rules:
  * For SEO/content fields: overwrite only when blank OR when the value
    matches the Phase 13 generator signature.
  * Generated editorial fields and FAQs are fail-closed; only owner-safe
    title/image identifiers remain available.

Flags:
    --dry-run         preview
    --include-drafts  process draft/archived standard products too
    --slug            limit to specific slug(s) (repeatable)
    --force           replace only detected legacy-generated identifiers
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from storefront.models import Product
from storefront.services.product_copy_v2 import (
    STANDARD_CATEGORY_SLUGS,
    build_copy,
    looks_like_phase13_autofill,
)


FIELDS = ("seo_title", "main_image_alt")


class Command(BaseCommand):
    help = "Recraft only owner-safe Product identifiers; editorial generation is retired."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--include-drafts", action="store_true")
        parser.add_argument("--slug", action="append", default=[])
        parser.add_argument("--force", action="store_true",
                            help=(
                                "Replace detected legacy-generated identifiers; "
                                "manual fields remain protected."
                            ))

    def handle(self, *args, **opts):
        qs = Product.objects.filter(
            category__slug__in=STANDARD_CATEGORY_SLUGS,
        ).order_by("id")
        if not opts["include_drafts"]:
            qs = qs.filter(status="published")
        if opts["slug"]:
            qs = qs.filter(slug__in=opts["slug"])

        total = qs.count()
        self.stdout.write(self.style.NOTICE(
            f"Recrafting {total} product(s){' (DRY-RUN)' if opts['dry_run'] else ''}…"
        ))

        changed = 0
        field_changes: dict[str, int] = {}
        unmapped = []

        for p in qs.select_related("category"):
            copy = build_copy(p)
            update_fields = []
            for f in FIELDS:
                raw_field = f"{f}_uk"
                current = getattr(p, raw_field, None) or ""
                new_val = copy.get(f) or ""
                if not new_val:
                    continue
                if current and not looks_like_phase13_autofill(f, current):
                    continue  # keep manually edited / non-phase13 content
                if current == new_val:
                    continue
                setattr(p, raw_field, new_val)
                update_fields.append(raw_field)
                field_changes[raw_field] = field_changes.get(raw_field, 0) + 1

            if update_fields and not opts["dry_run"]:
                p.save(update_fields=update_fields)

            if update_fields:
                changed += 1

            # Keep reporting unmapped standard products for editorial review.
            from storefront.services.product_copy_v2 import get_theme_for_product
            if get_theme_for_product(p) is None:
                unmapped.append((p.id, p.slug, p.title))

        self.stdout.write(self.style.SUCCESS(
            f"\nProcessed: {total}\nChanged:   {changed}\n"
            "FAQs changed: 0 (existing rows untouched)"
        ))
        if field_changes:
            self.stdout.write("\nField overwrite counts:")
            for f, n in sorted(field_changes.items()):
                self.stdout.write(f"  {f:22s} {n}")
        if unmapped:
            self.stdout.write(self.style.WARNING(
                f"\n{len(unmapped)} product(s) without theme mapping:"
            ))
            for pid, slug, title in unmapped[:20]:
                self.stdout.write(f"  #{pid:3} {slug:40s} {title[:40]}")
        if opts["dry_run"]:
            self.stdout.write(self.style.WARNING("\nDry-run: no changes saved."))
