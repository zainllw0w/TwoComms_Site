"""Fill missing T-shirt color/fit links to warehouse blank families."""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Prefetch, Q

from product_catalog.models import ProductFitNote, VariantBlankLink, VariantFitRule
from productcolors.models import ProductColorVariant
from storefront.models import Product, ProductFitOption, ProductStatus
from warehouse.models import StorageSubcategory


FIT_TARGET_SLUGS = {
    "classic": "crc-classic-101",
    "oversize": "oversize-erc",
}
THERMO_TARGET_SLUG = "termo"


def _resolve_targets():
    targets = {}
    for slug in (*FIT_TARGET_SLUGS.values(), THERMO_TARGET_SLUG):
        matches = list(
            StorageSubcategory.objects.filter(
                slug=slug,
                is_active=True,
                category__is_active=True,
            ).select_related("category")
        )
        if len(matches) != 1:
            raise CommandError(
                f"Warehouse blank slug '{slug}' must resolve to exactly one active subcategory; "
                f"found {len(matches)}."
            )
        targets[slug] = matches[0]
    return targets


def _tshirt_products(product_ids):
    tshirt_category = (
        Q(category__name__icontains="футбол")
        | Q(category__name__icontains="t-shirt")
        | Q(category__slug__icontains="shirt")
        | Q(category__slug__icontains="tshirt")
    )
    queryset = (
        Product.objects.exclude(status=ProductStatus.ARCHIVED)
        .filter(
            tshirt_category,
            fit_options__code__in=FIT_TARGET_SLUGS,
            fit_options__is_active=True,
        )
        .select_related("category")
        .prefetch_related(
            Prefetch(
                "fit_options",
                queryset=ProductFitOption.objects.filter(
                    is_active=True,
                    code__in=FIT_TARGET_SLUGS,
                ).order_by("order", "id"),
                to_attr="backfill_fit_options",
            ),
            Prefetch(
                "product_catalog_fit_notes",
                queryset=ProductFitNote.objects.filter(fit_code__in=FIT_TARGET_SLUGS),
                to_attr="backfill_fit_notes",
            ),
            Prefetch(
                "color_variants",
                queryset=(
                    ProductColorVariant.objects.select_related(
                        "color",
                        "color__product_catalog_profile",
                    )
                    .prefetch_related(
                        Prefetch(
                            "product_catalog_fit_rules",
                            queryset=VariantFitRule.objects.filter(
                                fit_code__in=FIT_TARGET_SLUGS
                            ),
                            to_attr="backfill_fit_rules",
                        ),
                        "product_catalog_blank_links",
                    )
                    .order_by("id")
                ),
                to_attr="backfill_variants",
            ),
        )
        .distinct()
        .order_by("id")
    )
    if product_ids:
        queryset = queryset.filter(pk__in=product_ids)
    return queryset


def _fit_is_allowed(product, variant, fit_code):
    product_notes = {
        row.fit_code: row for row in getattr(product, "backfill_fit_notes", [])
    }
    variant_rules = {
        row.fit_code: row for row in getattr(variant, "backfill_fit_rules", [])
    }
    product_note = product_notes.get(fit_code)
    variant_rule = variant_rules.get(fit_code)
    return bool(
        (product_note is None or product_note.is_enabled)
        and (variant_rule is None or variant_rule.is_enabled)
    )


class Command(BaseCommand):
    help = (
        "Dry-run by default; fill only missing T-shirt color/fit links to the "
        "classic, oversize, and thermo warehouse blank families."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Persist missing links. Existing explicit links are preserved.",
        )
        parser.add_argument(
            "--product-id",
            action="append",
            type=int,
            default=[],
            help="Limit processing to one product ID. May be repeated.",
        )

    def handle(self, *args, **options):
        apply_changes = bool(options["apply"])
        targets = _resolve_targets()
        products = list(_tshirt_products(options.get("product_id") or []))
        stats = {
            "products": len(products),
            "variants": 0,
            "eligible": 0,
            "create": 0,
            "preserved": 0,
            "disabled": 0,
        }
        plan = []

        for product in products:
            for variant in getattr(product, "backfill_variants", []):
                stats["variants"] += 1
                existing_keys = {
                    row.option_key
                    for row in getattr(variant, "product_catalog_blank_links", []).all()
                }
                profile = getattr(variant.color, "product_catalog_profile", None)
                is_thermo = bool(profile and profile.is_thermo)
                for fit in getattr(product, "backfill_fit_options", []):
                    if not _fit_is_allowed(product, variant, fit.code):
                        stats["disabled"] += 1
                        continue
                    option_key = f"fit={fit.code}"
                    stats["eligible"] += 1
                    if option_key in existing_keys:
                        stats["preserved"] += 1
                        continue
                    target_slug = (
                        THERMO_TARGET_SLUG
                        if is_thermo
                        else FIT_TARGET_SLUGS[fit.code]
                    )
                    target = targets[target_slug]
                    plan.append(
                        VariantBlankLink(
                            variant=variant,
                            option_key=option_key,
                            storage_subcategory=target,
                            note="Automatic T-shirt blank routing backfill",
                        )
                    )
                    stats["create"] += 1
                    self.stdout.write(
                        f"v{variant.id} p{product.id} {option_key} -> {target_slug}"
                    )

        created = 0
        if apply_changes and plan:
            with transaction.atomic():
                VariantBlankLink.objects.bulk_create(plan)
            created = len(plan)

        summary = " ".join(f"{key}={value}" for key, value in stats.items())
        self.stdout.write(
            self.style.SUCCESS(
                f"T-shirt blank links: {summary} created={created} "
                f"dry_run={not apply_changes}"
            )
        )
