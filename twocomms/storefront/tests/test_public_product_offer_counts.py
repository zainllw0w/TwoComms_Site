from unittest.mock import patch

from django.test import TestCase, override_settings

from storefront.models import Category, Product, ProductStatus
from storefront.sitemaps import ProductSitemap, ProductVariantSitemap
from storefront.services.marketplace_feeds import iter_feed_offers
from storefront.services.public_products import public_products_queryset
from storefront.seo_utils import _homepage_price_aggregate
from productcolors.models import Color, ProductColorVariant


@override_settings(
    SITE_BASE_URL="https://twocomms.shop",
    FEED_BASE_URL="https://twocomms.shop",
)
class PublicProductOfferCountTests(TestCase):
    def setUp(self):
        merchant_patcher = patch(
            "storefront.signals.generate_google_merchant_feed_task.apply_async"
        )
        indexnow_patcher = patch("storefront.signals.enqueue_indexnow_urls")
        self.addCleanup(merchant_patcher.stop)
        self.addCleanup(indexnow_patcher.stop)
        merchant_patcher.start()
        indexnow_patcher.start()

        self.category = Category.objects.create(
            name="Футболки",
            slug="offer-count-tshirts",
            is_active=True,
        )
        self.product = Product.objects.create(
            title="Published offer-count shirt",
            slug="published-offer-count-shirt",
            category=self.category,
            price=1200,
            status=ProductStatus.PUBLISHED,
        )

    def test_public_product_queryset_excludes_non_indexable_offer_rows(self):
        archived = Product.objects.create(
            title="Archived priced shirt",
            slug="archived-priced-shirt",
            category=self.category,
            price=2100,
            status=ProductStatus.ARCHIVED,
        )
        draft = Product.objects.create(
            title="Draft shirt",
            slug="draft-shirt",
            category=self.category,
            price=1400,
            status=ProductStatus.DRAFT,
        )
        empty_slug = Product.objects.create(
            title="Published empty slug shirt",
            slug="",
            category=self.category,
            price=1300,
            status=ProductStatus.PUBLISHED,
        )
        zero_price = Product.objects.create(
            title="Published zero price shirt",
            slug="published-zero-price-shirt",
            category=self.category,
            price=0,
            status=ProductStatus.PUBLISHED,
        )

        eligible_ids = set(public_products_queryset().values_list("id", flat=True))

        self.assertEqual(eligible_ids, {self.product.id})
        self.assertNotIn(archived.id, eligible_ids)
        self.assertNotIn(draft.id, eligible_ids)
        self.assertNotIn(empty_slug.id, eligible_ids)
        self.assertNotIn(zero_price.id, eligible_ids)

    def test_homepage_offer_count_matches_sitemap_and_distinct_feed_products(self):
        Product.objects.create(
            title="Archived priced shirt",
            slug="archived-priced-shirt",
            category=self.category,
            price=2100,
            status=ProductStatus.ARCHIVED,
        )
        Product.objects.create(
            title="Draft shirt",
            slug="draft-shirt",
            category=self.category,
            price=1400,
            status=ProductStatus.DRAFT,
        )

        aggregate = _homepage_price_aggregate()
        eligible_ids = set(public_products_queryset().values_list("id", flat=True))
        sitemap_ids = set(ProductSitemap().items().values_list("id", flat=True))
        feed_offers = iter_feed_offers("https://twocomms.shop")
        feed_product_ids = {offer.product.id for offer in feed_offers}

        self.assertEqual(aggregate["offerCount"], len(eligible_ids))
        self.assertEqual(sitemap_ids, eligible_ids)
        self.assertEqual(feed_product_ids, eligible_ids)

    def test_feed_keeps_variant_offer_expansion_for_each_eligible_product(self):
        feed_offers = iter_feed_offers("https://twocomms.shop")

        self.assertEqual({offer.product.id for offer in feed_offers}, {self.product.id})
        self.assertGreater(len(feed_offers), 1)

    def test_variant_sitemap_excludes_zero_price_products(self):
        color = Color.objects.create(
            name="Offer count black",
            primary_hex="#000000",
        )
        ProductColorVariant.objects.create(
            product=self.product,
            color=color,
            slug="offer-count-black",
        )
        zero_price = Product.objects.create(
            title="Published zero-price variant shirt",
            slug="published-zero-price-variant-shirt",
            category=self.category,
            price=0,
            status=ProductStatus.PUBLISHED,
        )
        ProductColorVariant.objects.create(
            product=zero_price,
            color=color,
            slug="zero-price-black",
        )

        urls = {entry["loc"] for entry in ProductVariantSitemap().items()}

        self.assertIn("/product/published-offer-count-shirt/offer-count-black/", urls)
        self.assertNotIn("/product/published-zero-price-variant-shirt/zero-price-black/", urls)
