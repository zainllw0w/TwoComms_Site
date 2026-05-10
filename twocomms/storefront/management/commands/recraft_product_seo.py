"""Phase 13.5 — replace broken Phase 13 HTML autofill with manually-
crafted plain-text, theme-aware copy (from ``services.product_copy_v2``).

Safe-overwrite rules:
  * For SEO/content fields: overwrite only when blank OR when the value
    matches the Phase 13 generator signature.
  * For FAQs: replace only the 5 Phase-13 universal FAQs. Any FAQ whose
    question doesn't start with a Phase-13 signature prefix is kept.

Flags:
    --dry-run         preview
    --include-drafts  process drafts/archived too
    --slug            limit to specific slug(s) (repeatable)
    --force           overwrite EVERY field (use with care)
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from storefront.models import Product, ProductFAQ
from storefront.services.product_copy_v2 import (
    build_copy,
    looks_like_phase13_autofill,
    looks_like_phase13_faq,
)


FIELDS = (
    "seo_title", "seo_description", "seo_keywords", "main_image_alt",
    "short_description", "full_description", "care_instructions",
    "target_audience",
)


class Command(BaseCommand):
    help = "Recraft product SEO copy (plain text) — overwrite Phase 13 autofill."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--include-drafts", action="store_true")
        parser.add_argument("--slug", action="append", default=[])
        parser.add_argument("--force", action="store_true",
                            help="Overwrite EVERY targeted field regardless of signature.")

    def handle(self, *args, **opts):
        qs = Product.objects.all().order_by("id")
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
        faqs_replaced = 0
        faqs_kept = 0
        unmapped = []

        for p in qs.select_related("category"):
            copy = build_copy(p)
            update_fields = []
            for f in FIELDS:
                current = getattr(p, f, None) or ""
                new_val = copy.get(f) or ""
                if not new_val:
                    continue
                if current and not (opts["force"] or
                                    looks_like_phase13_autofill(f, current)):
                    continue  # keep manually edited / non-phase13 content
                if current == new_val:
                    continue
                setattr(p, f, new_val)
                update_fields.append(f)
                field_changes[f] = field_changes.get(f, 0) + 1

            if update_fields and not opts["dry_run"]:
                p.save(update_fields=update_fields)

            # FAQs — replace only phase13-signature ones; keep custom ones.
            existing = list(ProductFAQ.objects.filter(product=p).order_by("order", "id"))
            phase13_existing = [f for f in existing if looks_like_phase13_faq(f.question)]
            custom_existing = [f for f in existing if not looks_like_phase13_faq(f.question)]

            if opts["force"] or phase13_existing or not existing:
                # Re-create the 5 theme-aware FAQs. Keep custom_existing intact.
                if not opts["dry_run"]:
                    # Delete phase13 FAQs (or all if --force).
                    to_delete = existing if opts["force"] else phase13_existing
                    deleted_ids = [f.id for f in to_delete]
                    if deleted_ids:
                        ProductFAQ.objects.filter(id__in=deleted_ids).delete()

                    # Reorder custom faqs first (keep their order), then append new.
                    base_order = 0
                    for f in custom_existing if not opts["force"] else []:
                        if f.order != base_order:
                            f.order = base_order
                            f.save(update_fields=["order"])
                        base_order += 1
                    for idx, (q, a) in enumerate(copy["faqs"]):
                        ProductFAQ.objects.create(
                            product=p, question=q, answer=a,
                            order=base_order + idx, is_active=True,
                        )
                faqs_replaced += 5
                faqs_kept += len(custom_existing) if not opts["force"] else 0

            if update_fields or phase13_existing or opts["force"]:
                changed += 1

            # Track products without a theme mapping (they used fallback copy).
            from storefront.services.product_copy_v2 import get_theme_for_product
            if get_theme_for_product(p) is None:
                unmapped.append((p.id, p.slug, p.title))

        self.stdout.write(self.style.SUCCESS(
            f"\nProcessed: {total}\nChanged:   {changed}\n"
            f"FAQs replaced: {faqs_replaced} (kept {faqs_kept} custom)"
        ))
        if field_changes:
            self.stdout.write("\nField overwrite counts:")
            for f, n in sorted(field_changes.items()):
                self.stdout.write(f"  {f:22s} {n}")
        if unmapped:
            self.stdout.write(self.style.WARNING(
                f"\n{len(unmapped)} product(s) without theme mapping (fallback copy used):"
            ))
            for pid, slug, title in unmapped[:20]:
                self.stdout.write(f"  #{pid:3} {slug:40s} {title[:40]}")
        if opts["dry_run"]:
            self.stdout.write(self.style.WARNING("\nDry-run: no changes saved."))
