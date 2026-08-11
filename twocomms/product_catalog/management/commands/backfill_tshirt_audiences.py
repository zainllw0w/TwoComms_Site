"""Add the unisex audience tag to all non-archived T-shirts."""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from product_catalog.models import AudienceTag, ProductAudience
from storefront.models import Product, ProductStatus


def tshirt_products():
    category_match = (
        Q(category__slug__icontains="tshirt")
        | Q(category__slug__icontains="t-shirt")
        | Q(category__slug__icontains="shirt")
        | Q(category__name__icontains="футбол")
        | Q(category__name__icontains="t-shirt")
    )
    return (
        Product.objects.filter(category_match)
        .exclude(status=ProductStatus.ARCHIVED)
        .select_related("category")
        .order_by("id")
    )


class Command(BaseCommand):
    help = "Dry-run by default; add unisex without replacing explicit T-shirt audiences."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Persist missing unisex assignments.",
        )

    def handle(self, *args, **options):
        apply_changes = bool(options["apply"])
        tag, _ = AudienceTag.objects.get_or_create(
            code="unisex",
            defaults={
                "label_uk": "Унісекс",
                "label_ru": "Унисекс",
                "label_en": "Unisex",
                "order": 0,
                "is_active": True,
            },
        )
        products = list(tshirt_products())
        existing_ids = set(
            ProductAudience.objects.filter(
                product_id__in=[product.id for product in products],
            ).values_list("product_id", flat=True)
        )
        rows = [
            ProductAudience(product=product, tag=tag)
            for product in products
            if product.id not in existing_ids
        ]
        created = 0
        if apply_changes and rows:
            with transaction.atomic():
                ProductAudience.objects.bulk_create(rows, ignore_conflicts=True)
            created = len(rows)
        self.stdout.write(
            self.style.SUCCESS(
                f"T-shirt audiences: products={len(products)} missing={len(rows)} "
                f"created={created} dry_run={not apply_changes}"
            )
        )
