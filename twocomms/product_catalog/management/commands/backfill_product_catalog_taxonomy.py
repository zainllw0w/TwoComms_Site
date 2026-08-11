"""Backfill canonical audience and 225 brigade assignments, dry-run first."""

from __future__ import annotations

import re

from django.core.management.base import BaseCommand
from django.db import transaction

from product_catalog.models import (
    AudienceTag,
    MerchCollection,
    ProductAudience,
    ProductMerchCollection,
)
from storefront.models import Product, ProductStatus


BRIGADE_225_PATTERN = re.compile(r"(?<!\d)225(?!\d)")
BRIGADE_225_CATEGORY_TOKENS = (
    "tshirt",
    "t-shirt",
    "shirt",
    "футбол",
    "hoodie",
    "худі",
    "худи",
)


def is_225_apparel(product: Product) -> bool:
    identity = f"{product.slug or ''} {product.title or ''}".lower()
    category = product.category
    category_identity = (
        f"{getattr(category, 'slug', '')} {getattr(category, 'name', '')}".lower()
    )
    return bool(BRIGADE_225_PATTERN.search(identity)) and any(
        token in category_identity for token in BRIGADE_225_CATEGORY_TOKENS
    )


class Command(BaseCommand):
    help = (
        "Dry-run by default. Add unisex only to products without an explicit "
        "audience and assign the 225 leaf to matching T-shirts and hoodies."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Persist the reviewed assignments in one transaction.",
        )

    def handle(self, *args, **options):
        apply_changes = bool(options["apply"])
        with transaction.atomic():
            unisex = AudienceTag.objects.filter(code="unisex", is_active=True).first()
            brigades = MerchCollection.objects.filter(slug="brigades", is_active=True).first()
            brigade_225 = (
                MerchCollection.objects.select_related("parent")
                .filter(slug="225", is_active=True)
                .first()
            )
            brigade_127 = (
                MerchCollection.objects.select_related("parent")
                .filter(slug="127", is_active=True)
                .first()
            )
            if unisex is None:
                raise RuntimeError("Active unisex audience tag is required")
            if brigades is None or brigade_225 is None or brigade_127 is None:
                raise RuntimeError("Active brigades, 225, and 127 taxonomy nodes are required")
            if brigades.parent_id is not None:
                raise RuntimeError("brigades must remain a top-level manual taxonomy node")
            if brigade_225.parent_id != brigades.pk:
                raise RuntimeError("225 must have brigades as its direct parent")
            if brigade_127.parent_id != brigades.pk:
                raise RuntimeError("127 must have brigades as its direct parent")

            products = list(
                Product.objects.select_for_update()
                .exclude(status=ProductStatus.ARCHIVED)
                .select_related("category")
                .order_by("id")
            )
            product_ids = [product.pk for product in products]
            assigned_audience_ids = set(
                ProductAudience.objects.select_for_update()
                .filter(product_id__in=product_ids)
                .values_list("product_id", flat=True)
            )
            assigned_225_ids = set(
                ProductMerchCollection.objects.select_for_update()
                .filter(product_id__in=product_ids, collection=brigade_225)
                .values_list("product_id", flat=True)
            )
            audience_candidates = [
                product for product in products if product.pk not in assigned_audience_ids
            ]
            brigade_targets = [product for product in products if is_225_apparel(product)]
            brigade_candidates = [
                product
                for product in brigade_targets
                if product.pk not in assigned_225_ids
            ]
            redundant_brigades = list(
                ProductMerchCollection.objects.select_for_update().filter(
                    product_id__in=[product.pk for product in brigade_targets],
                    collection=brigades,
                )
            )

            audiences_created = 0
            brigades_created = 0
            redundant_brigades_removed = 0
            if apply_changes:
                ProductAudience.objects.bulk_create(
                    [
                        ProductAudience(product=product, tag=unisex)
                        for product in audience_candidates
                    ],
                    ignore_conflicts=True,
                )
                ProductMerchCollection.objects.bulk_create(
                    [
                        ProductMerchCollection(
                            product=product,
                            collection=brigade_225,
                            order=0,
                        )
                        for product in brigade_candidates
                    ],
                    ignore_conflicts=True,
                )
                audiences_created = len(audience_candidates)
                brigades_created = len(brigade_candidates)
                redundant_ids = [assignment.pk for assignment in redundant_brigades]
                if redundant_ids:
                    ProductMerchCollection.objects.filter(pk__in=redundant_ids).delete()
                    redundant_brigades_removed = len(redundant_ids)
            else:
                transaction.set_rollback(True)

        audience_ids = ",".join(str(product.pk) for product in audience_candidates) or "-"
        brigade_ids = ",".join(str(product.pk) for product in brigade_candidates) or "-"
        self.stdout.write(
            self.style.SUCCESS(
                "Product catalog taxonomy: "
                f"audience_candidates={len(audience_candidates)} "
                f"audience_ids={audience_ids} "
                f"brigade_225_candidates={len(brigade_candidates)} "
                f"brigade_225_ids={brigade_ids} "
                f"audiences_created={audiences_created} "
                f"brigade_225_created={brigades_created} "
                f"redundant_brigades_candidates={len(redundant_brigades)} "
                f"redundant_brigades_removed={redundant_brigades_removed} "
                f"dry_run={not apply_changes}"
            )
        )
