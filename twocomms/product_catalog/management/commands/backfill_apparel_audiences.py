"""Assign the default unisex audience to apparel without an explicit audience."""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from product_catalog.models import AudienceTag, ProductAudience
from storefront.models import Product


def apparel_products():
    category_match = (
        Q(category__slug__icontains="tshirt")
        | Q(category__slug__icontains="t-shirt")
        | Q(category__slug__icontains="shirt")
        | Q(category__name__icontains="футбол")
        | Q(category__name__icontains="t-shirt")
        | Q(category__slug__icontains="hoodie")
        | Q(category__name__icontains="худі")
        | Q(category__name__icontains="худи")
        | Q(category__slug__icontains="long-sleeve")
        | Q(category__slug__icontains="longsleeve")
        | Q(category__name__icontains="лонг")
    )
    return Product.objects.filter(category_match).select_related("category").order_by("id")


class Command(BaseCommand):
    help = "Dry-run by default; add unisex only to apparel with no explicit audience."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Persist missing unisex assignments.",
        )

    def handle(self, *args, **options):
        apply_changes = bool(options["apply"])
        tag = AudienceTag.objects.filter(code="unisex", is_active=True).first()
        if tag is None and not apply_changes:
            raise CommandError("active unisex audience tag is missing")
        if tag is None:
            tag = AudienceTag.objects.create(
                code="unisex",
                label_uk="Унісекс",
                label_ru="Унисекс",
                label_en="Unisex",
                order=0,
                is_active=True,
            )

        products = list(apparel_products())
        product_ids = [product.id for product in products]
        assigned_ids = set(
            ProductAudience.objects.filter(product_id__in=product_ids).values_list(
                "product_id",
                flat=True,
            )
        )
        missing_products = [
            product for product in products if product.id not in assigned_ids
        ]
        created = 0
        if apply_changes and missing_products:
            with transaction.atomic():
                ProductAudience.objects.bulk_create(
                    [ProductAudience(product=product, tag=tag) for product in missing_products],
                    ignore_conflicts=True,
                )
            created = len(missing_products)

        missing_ids = ",".join(str(product.id) for product in missing_products)
        self.stdout.write(
            self.style.SUCCESS(
                f"Apparel audiences: products={len(products)} "
                f"explicit={len(assigned_ids)} missing={len(missing_products)} "
                f"created={created} dry_run={not apply_changes} "
                f"missing_ids=[{missing_ids}]"
            )
        )
