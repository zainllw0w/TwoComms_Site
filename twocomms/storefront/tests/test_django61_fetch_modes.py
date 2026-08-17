from contextlib import contextmanager
from unittest.mock import patch

from django.core.cache import cache
from django.core.exceptions import FieldFetchBlocked
from django.db.models import FETCH_ONE, FETCH_RAISE, QuerySet
from django.test import TestCase
from django.utils import timezone

from product_catalog.models import MerchCollection
from storefront.models import BlogCategory, BlogPost, Category, Product
from storefront.seo_utils import _homepage_price_aggregate
from storefront.services.catalog_facets import redundant_parent_theme_slugs
from storefront.sitemaps import BlogPostSitemap, CategorySitemap, ProductSitemap


@contextmanager
def strict_only_projections():
    original_only = QuerySet.only

    def only_with_raise(queryset, *fields):
        return original_only(queryset, *fields).fetch_mode(FETCH_RAISE)

    with patch.object(QuerySet, "only", only_with_raise):
        yield


class Django61FetchModeContractTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(
            name="Fetch mode category",
            slug="fetch-mode-category",
        )
        cls.product = Product.objects.create(
            title="Fetch mode product",
            slug="fetch-mode-product",
            category=cls.category,
            price=1200,
            discount_percent=25,
            status="published",
        )
        cls.theme = MerchCollection.objects.create(
            slug="fetch-theme",
            kind=MerchCollection.Kind.THEME,
            name_uk="Fetch theme",
            order=1,
        )
        cls.collection = MerchCollection.objects.create(
            slug="fetch-collection",
            kind=MerchCollection.Kind.COLLAB,
            parent=cls.theme,
            name_uk="Fetch collection",
            order=2,
        )
        cls.blog_category = BlogCategory.objects.create(
            name="Fetch mode blog category",
            slug="fetch-mode-blog-category",
        )
        cls.blog_post = BlogPost.objects.create(
            category=cls.blog_category,
            title="Fetch mode blog post",
            slug="fetch-mode-blog-post",
            content_html="<p>Fetch mode contract.</p>",
            published_at=timezone.now(),
            is_published=True,
        )

    def setUp(self):
        cache.clear()

    def test_fetch_raise_blocks_unplanned_deferred_access(self):
        product = (
            Product.objects.only("id")
            .fetch_mode(FETCH_RAISE)
            .get(pk=self.product.pk)
        )

        with self.assertRaises(FieldFetchBlocked):
            _ = product.title

    def test_project_querysets_keep_django_fetch_one_as_the_default(self):
        self.assertIs(Product.objects.all()._fetch_mode, FETCH_ONE)

    def test_catalog_facet_projection_is_complete_under_fetch_raise(self):
        with strict_only_projections():
            redundant = redundant_parent_theme_slugs(
                {
                    "theme": [self.theme.slug],
                    "collection": [self.collection.slug],
                }
            )

        self.assertEqual(redundant, {self.theme.slug})

    def test_homepage_price_projection_is_complete_under_fetch_raise(self):
        with strict_only_projections():
            aggregate = _homepage_price_aggregate()

        self.assertEqual(
            aggregate,
            {"lowPrice": 900, "highPrice": 900, "offerCount": 1},
        )

    def test_sitemap_projections_are_complete_under_fetch_raise(self):
        with strict_only_projections():
            products = list(ProductSitemap().items())
            categories = list(CategorySitemap().items())

            product_payload = [
                (
                    ProductSitemap().location(product),
                    ProductSitemap().lastmod(product),
                    ProductSitemap().get_languages_for_item(product),
                )
                for product in products
            ]
            category_payload = [
                (
                    CategorySitemap().location(category),
                    CategorySitemap().lastmod(category),
                )
                for category in categories
            ]

        self.assertEqual(len(product_payload), 1)
        self.assertEqual(len(category_payload), 1)
        self.assertIn("fetch-mode-product", product_payload[0][0])
        self.assertIn("fetch-mode-category", category_payload[0][0])

    def test_blog_post_sitemap_projection_is_complete_under_fetch_raise(self):
        sitemap = BlogPostSitemap()

        with strict_only_projections():
            posts = list(sitemap.items())
            payload = [
                (sitemap.location(post), sitemap.lastmod(post))
                for post in posts
            ]

        matching_payload = [
            (location, lastmod)
            for location, lastmod in payload
            if self.blog_post.slug in location
        ]
        self.assertEqual(
            matching_payload,
            [(sitemap.location(self.blog_post), self.blog_post.updated_at)],
        )
