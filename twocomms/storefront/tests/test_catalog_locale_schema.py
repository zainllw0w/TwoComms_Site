"""Rendered CollectionPage facts must respect per-product locale ownership."""

from __future__ import annotations

import json
import re
from urllib.parse import urlparse
from unittest.mock import patch

from django.core.cache import cache, caches
from django.db import connection
from django.db.models import Prefetch
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from storefront.models import Category, Product, ProductFAQ
from storefront.services.locale_publication import (
    PRODUCT_SITEMAP_FIELDS,
    locale_is_indexable,
)


class CatalogLocaleSchemaTests(TestCase):
    """Keep fallback cards navigable without publishing noindex PDPs in JSON-LD."""

    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(
            name="Schema fixtures",
            name_ru="Schema fixtures RU",
            name_en="Schema fixtures EN",
            slug="schema-fixtures",
            is_active=True,
        )
        cls.owned_products = []
        for index in range(5):
            product = Product.objects.create(
                title=f"Українська футболка {index}",
                title_ru=f"Русская футболка {index}",
                title_en=f"English T-shirt {index}",
                slug=f"locale-schema-owned-{index}",
                category=cls.category,
                price=900,
                priority=index,
                status="published",
                seo_title_ru=f"Русская футболка {index} TwoComms",
                seo_title_en=f"English T-shirt {index} TwoComms",
                seo_description_ru=f"Русское описание футболки {index}.",
                seo_description_en=f"English T-shirt {index} description.",
                full_description_ru=f"Русский editorial-текст для футболки {index}.",
                full_description_en=f"English editorial copy for T-shirt {index}.",
            )
            ProductFAQ.objects.create(
                product=product,
                question=f"Українське питання {index}",
                answer=f"Українська відповідь {index}",
                question_ru=f"Русский вопрос {index}",
                answer_ru=f"Русский ответ {index}",
                question_en=f"English question {index}",
                answer_en=f"English answer {index}",
                is_active=True,
            )
            cls.owned_products.append(product)

        cls.untranslated_product = Product.objects.create(
            title="Українська футболка без перекладу",
            slug="locale-schema-untranslated",
            category=cls.category,
            price=900,
            priority=99,
            status="published",
        )
        cls.ru_only_product = Product.objects.create(
            title="Українська футболка лише для RU",
            title_ru="Русская футболка только для RU",
            slug="locale-schema-ru-only",
            category=cls.category,
            price=900,
            priority=5,
            status="published",
            seo_title_ru="Русская футболка TwoComms",
            seo_description_ru="Русское описание футболки.",
            full_description_ru="Русский editorial-текст для футболки.",
        )
        cls.faq_partial_product = Product.objects.create(
            title="Українська футболка з неповним FAQ",
            title_ru="Русская футболка с неполным FAQ",
            title_en="English T-shirt with partial FAQ",
            slug="locale-schema-faq-partial",
            category=cls.category,
            price=900,
            priority=6,
            status="published",
            seo_title_ru="Русская футболка с FAQ TwoComms",
            seo_title_en="English T-shirt with FAQ TwoComms",
            seo_description_ru="Русское описание футболки с FAQ.",
            seo_description_en="English T-shirt description with FAQ.",
            full_description_ru="Русский editorial-текст для футболки с FAQ.",
            full_description_en="English editorial copy for T-shirt with FAQ.",
        )
        ProductFAQ.objects.create(
            product=cls.faq_partial_product,
            question="Українське питання про посадку",
            answer="Українська відповідь про посадку",
            question_ru="Русский вопрос о посадке",
            answer_ru="Русский ответ о посадке",
            question_en="",
            answer_en="English answer about the fit.",
            is_active=True,
        )

    def setUp(self):
        super().setUp()
        cache.clear()
        caches["fragments"].clear()
        for target in (
            "storefront.signals.generate_google_merchant_feed_task.apply_async",
            "storefront.signals.enqueue_indexnow_urls",
        ):
            patcher = patch(target)
            patcher.start()
            self.addCleanup(patcher.stop)

    def _collection_item_list(self, response):
        body = response.content.decode("utf-8")
        for payload in re.findall(
            r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>',
            body,
            flags=re.DOTALL,
        ):
            document = json.loads(payload)
            for node in document.get("@graph", [document]):
                if node.get("@type") == "CollectionPage":
                    return node["mainEntity"]
        self.fail("No CollectionPage ItemList JSON-LD node found")

    def test_localized_category_itemlist_lists_only_owned_products(self):
        locale_owned_product_ids = {
            "ru": {
                product.pk
                for product in (
                    *self.owned_products,
                    self.ru_only_product,
                    self.faq_partial_product,
                )
            },
            "en": {product.pk for product in self.owned_products},
        }

        for language in ("ru", "en"):
            for path in (f"/{language}/catalog/{self.category.slug}/",):
                response = self.client.get(path)

                self.assertEqual(response.status_code, 200)
                self.assertIn(
                    self.untranslated_product.pk,
                    [product.pk for product in response.context["products"]],
                )

                item_list = self._collection_item_list(response)
                item_paths = [
                    urlparse(item["url"]).path
                    for item in item_list["itemListElement"]
                ]
                expected_paths = [
                    f"/{language}/product/{product.slug}/"
                    for product in response.context["products"]
                    if product.pk in locale_owned_product_ids[language]
                ]

                self.assertEqual(item_paths, expected_paths)
                self.assertEqual(
                    item_list["numberOfItems"],
                    len(item_list["itemListElement"]),
                )
                self.assertEqual(
                    [item["position"] for item in item_list["itemListElement"]],
                    list(range(1, len(item_list["itemListElement"]) + 1)),
                )
                self.assertNotIn(
                    f"/{language}/product/{self.untranslated_product.slug}/",
                    item_paths,
                )
                if language == "ru":
                    self.assertIn(
                        f"/ru/product/{self.faq_partial_product.slug}/",
                        item_paths,
                    )
                else:
                    self.assertNotIn(
                        f"/en/product/{self.faq_partial_product.slug}/",
                        item_paths,
                    )

                for item_path in item_paths:
                    product_response = self.client.get(item_path)
                    self.assertEqual(product_response.status_code, 200)
                    self.assertNotContains(product_response, "noindex, follow")

    def test_uk_category_itemlist_remains_the_visible_product_list(self):
        for path in (f"/catalog/{self.category.slug}/",):
            response = self.client.get(path)

            self.assertEqual(response.status_code, 200)
            item_list = self._collection_item_list(response)
            self.assertIs(
                response.context["catalog_schema_products"],
                response.context["products"],
            )
            self.assertEqual(
                [urlparse(item["url"]).path for item in item_list["itemListElement"]],
                [f"/product/{product.slug}/" for product in response.context["products"]],
            )

    def test_localized_catalog_schema_query_count_is_not_per_product(self):
        category = Category.objects.create(
            name="Query-count fixtures",
            name_en="Query-count fixtures EN",
            slug="schema-query-count-fixtures",
            is_active=True,
        )
        for index in range(20):
            Product.objects.create(
                title=f"Українська футболка query {index}",
                title_en=f"English T-shirt query {index}",
                slug=f"locale-schema-query-count-{index}",
                category=category,
                price=900,
                priority=index,
                status="published",
                seo_title_en=f"English T-shirt query {index} TwoComms",
                seo_description_en=f"English query description {index}.",
                full_description_en=f"English editorial copy {index}.",
            )

        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(f"/en/catalog/{category.slug}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["catalog_schema_products"]), 16)
        faq_queries = [
            query
            for query in queries.captured_queries
            if "storefront_productfaq" in query["sql"].lower()
        ]
        self.assertEqual(len(faq_queries), 1)
        # The existing catalog route has 16 queries in this fixture. Locale
        # ownership is allowed one Product batch and one FAQ prefetch, never
        # one query per visible card.
        self.assertLessEqual(len(queries), 18)

    def test_empty_prefetched_faqs_do_not_trigger_a_follow_up_query(self):
        product = Product.objects.create(
            title="Українська футболка без FAQ",
            title_en="English T-shirt without FAQs",
            slug="locale-schema-empty-faqs",
            category=self.category,
            price=900,
            status="published",
            seo_title_en="English T-shirt without FAQs TwoComms",
            seo_description_en="English description without FAQs.",
            full_description_en="English editorial copy without FAQs.",
        )
        schema_product = (
            Product.objects.filter(pk=product.pk)
            .only(*PRODUCT_SITEMAP_FIELDS)
            .prefetch_related(
                Prefetch("faqs", to_attr="_locale_publication_faqs")
            )
            .get()
        )

        self.assertEqual(schema_product._locale_publication_faqs, [])
        with self.assertNumQueries(0):
            self.assertTrue(locale_is_indexable(schema_product, "en"))
