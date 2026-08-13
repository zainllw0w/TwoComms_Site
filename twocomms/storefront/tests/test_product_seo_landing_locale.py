"""Locale-ownership contracts for the standard PDP editorial rail."""

from __future__ import annotations

from unittest.mock import patch

from django.core.cache import cache, caches
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import translation

from productcolors.models import Color, ProductColorVariant
from storefront.models import (
    Category,
    CategorySeoBlock,
    CategorySeoBlockItem,
    Product,
    ProductFAQ,
)
from storefront.services.product_search_keywords import (
    MAX_LOCALE_CANDIDATES,
    _generate_category_peer_chips,
    build_product_search_keywords,
)
from storefront.services.category_seo_blocks import get_category_seo_layout
from storefront.services.product_seo_landing import (
    _category_layout_for_product,
    build_landing,
)


class ProductSeoLandingLocaleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(
            name="Футболки",
            name_ru="Футболки",
            name_en="T-shirts",
            slug="locale-rail-tees",
            is_active=True,
        )
        cls.related_category = Category.objects.create(
            name="Худі",
            name_ru="Худи",
            name_en="Hoodies",
            slug="hoodie",
            is_active=True,
        )
        cls.product = Product.objects.create(
            title="Українська футболка",
            title_ru="Русская футболка",
            title_en="English T-shirt",
            slug="locale-rail-tee",
            category=cls.category,
            price=900,
            status="published",
            search_keywords=[
                {
                    "label": "Legacy Ukrainian manual chip",
                    "url": "/catalog/locale-rail-tees/?color=black",
                }
            ],
        )
        color = Color.objects.create(name="Чорний", primary_hex="#000000")
        ProductColorVariant.objects.create(
            product=cls.product,
            color=color,
            is_default=True,
            order=0,
        )
        block = CategorySeoBlock.objects.create(
            category=cls.category,
            block_type="top_menu",
            title="Legacy Ukrainian database block",
            is_active=True,
        )
        CategorySeoBlockItem.objects.create(
            block=block,
            label="Legacy Ukrainian database item",
            url="/catalog/theme/military/",
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

    def test_russian_keywords_use_same_locale_support_owners_only(self):
        with translation.override("ru"):
            chips = build_product_search_keywords(self.product, language="ru")

        urls = [item["url"] for item in chips]
        labels = [item["label"] for item in chips]

        self.assertEqual(
            urls,
            [
                "/ru/delivery/",
                "/ru/rozmirna-sitka/",
                "/ru/doglyad-za-odyagom/",
                "/ru/povernennya-ta-obmin/",
                "/ru/pro-brand/",
            ],
        )
        self.assertEqual(
            labels,
            [
                "Доставка и оплата",
                "Размерная сетка",
                "Уход за одеждой",
                "Возврат и обмен",
                "О бренде TwoComms",
            ],
        )
        self.assertFalse(any("?color=" in url for url in urls))
        self.assertFalse(any("custom-print" in url for url in urls))
        self.assertFalse(any("/catalog/theme/" in url for url in urls))

    def test_ukrainian_keywords_preserve_existing_support_and_sibling_anchors(self):
        sibling = Product.objects.create(
            title="Українське худі",
            slug="locale-rail-tee-hd",
            category=self.related_category,
            price=1200,
            status="published",
        )

        with translation.override("uk"):
            chips = build_product_search_keywords(self.product, language="uk")

        labels_by_url = {item["url"]: item["label"] for item in chips}
        self.assertEqual(
            labels_by_url[f"/product/{sibling.slug}/"],
            "Цей принт на худі",
        )
        self.assertEqual(
            labels_by_url["/delivery/"],
            "Доставка та оплата",
        )
        self.assertNotIn("1–3", labels_by_url["/delivery/"])
        self.assertEqual(
            labels_by_url["/rozmirna-sitka/"],
            "Розмірна сітка locale-rail-tees",
        )
        self.assertEqual(
            labels_by_url["/custom-print/"],
            "Замовити кастомний DTF-друк",
        )
        self.assertFalse(any("?color=" in item["url"] for item in chips))

    def test_english_category_layout_fails_closed_on_locale_less_database_blocks(self):
        with translation.override("en"):
            layout = _category_layout_for_product(self.product, language="en")

        self.assertEqual(len(layout["tab_blocks"]), 1)
        menu = layout["tab_blocks"][0]
        self.assertEqual(menu["block"].block_type, "top_menu")
        self.assertEqual(menu["block"].title, "Catalog sections")

        labels = [item.label for item in menu["items"]]
        urls = [item.url for item in menu["items"]]
        self.assertIn("Delivery & payment", labels)
        self.assertIn("Size chart", labels)
        self.assertIn("Garment care", labels)
        self.assertIn("Returns & exchanges", labels)
        self.assertIn("About TwoComms brand", labels)
        self.assertIn("Hoodies", labels)
        self.assertTrue(all(url.startswith("/en/") for url in urls))
        self.assertNotIn("Legacy Ukrainian database item", labels)
        self.assertFalse(any("/catalog/theme/" in url for url in urls))
        self.assertFalse(any("custom-print" in url for url in urls))

    def test_existing_synthetic_menu_title_uses_active_locale(self):
        CategorySeoBlock.objects.filter(category=self.related_category).delete()

        with translation.override("en"):
            layout = get_category_seo_layout(self.related_category)

        self.assertEqual(layout["tab_blocks"][0]["block"].title, "Catalog sections")

    def test_english_keywords_link_to_owned_peer_but_not_fallback_peer(self):
        owned_peer = Product.objects.create(
            title="Український peer",
            title_en="English owned peer",
            slug="locale-rail-owned-peer",
            category=self.category,
            price=900,
            status="published",
            seo_title_en="English owned peer TwoComms",
            seo_description_en="English owned peer description.",
            full_description_en="English owned peer editorial description.",
        )
        fallback_peer = Product.objects.create(
            title="Український fallback peer",
            slug="locale-rail-fallback-peer",
            category=self.category,
            price=900,
            status="published",
        )

        with translation.override("en"):
            chips = build_product_search_keywords(self.product, language="en")

        urls = [item["url"] for item in chips]
        labels = [item["label"] for item in chips]
        self.assertIn(f"/en/product/{owned_peer.slug}/", urls)
        self.assertIn("English owned peer", labels)
        self.assertNotIn(f"/en/product/{fallback_peer.slug}/", urls)

    def test_non_uk_landing_override_requires_owned_locale_copy(self):
        self.product.seo_bottom_html = "<p>Український SEO-блок</p>"
        self.product.seo_bottom_html_ru = ""
        self.product.seo_bottom_html_en = ""
        self.product.save()

        with translation.override("ru"):
            russian = build_landing(self.product, language="ru")
        with translation.override("en"):
            english = build_landing(self.product, language="en")

        self.assertEqual(russian["override_html"], "")
        self.assertEqual(english["override_html"], "")

        self.product.seo_bottom_html_en = "<p>English SEO block</p>"
        self.product.save(update_fields=["seo_bottom_html_en"])
        with translation.override("en"):
            english = build_landing(self.product, language="en")

        self.assertEqual(english["override_html"], "<p>English SEO block</p>")

    def _create_english_faq_fallback_peer(self, index: int) -> Product:
        peer = Product.objects.create(
            title=f"Український peer {index}",
            title_en=f"English peer {index}",
            slug=f"locale-rail-faq-fallback-{index}",
            category=self.category,
            price=900,
            priority=index,
            status="published",
            seo_title_en=f"English peer {index} TwoComms",
            seo_description_en=f"English peer {index} description.",
            full_description_en=f"English peer {index} editorial description.",
        )
        ProductFAQ.objects.create(
            product=peer,
            question=f"Українське питання {index}",
            answer=f"Українська відповідь {index}",
            question_en="",
            answer_en="",
            is_active=True,
        )
        return peer

    def test_english_peer_scan_is_bounded_and_prefetches_faqs(self):
        for index in range(MAX_LOCALE_CANDIDATES + 5):
            self._create_english_faq_fallback_peer(index)

        # Resolve the category before the measured block. The contract below
        # concerns the candidate product and FAQ loading only.
        self.product.category
        with CaptureQueriesContext(connection) as queries:
            chips = _generate_category_peer_chips(
                self.product,
                exclude_ids=set(),
                language="en",
            )

        self.assertEqual(chips, [])
        self.assertLessEqual(len(queries), 2)

    def test_english_peer_scan_stops_at_locale_candidate_window(self):
        for index in range(MAX_LOCALE_CANDIDATES + 5):
            self._create_english_faq_fallback_peer(index)

        with patch(
            "storefront.services.product_search_keywords.locale_is_indexable",
            return_value=False,
        ) as is_indexable:
            _generate_category_peer_chips(
                self.product,
                exclude_ids=set(),
                language="en",
            )

        self.assertEqual(is_indexable.call_count, MAX_LOCALE_CANDIDATES)
