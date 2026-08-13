"""Rendered locale contracts for indexable standard catalog and PDP pages.

The matrix grows one verified surface at a time.  It deliberately checks
named buyer-visible values and link ownership rather than treating every
shared brand name or proper noun as a translation defect.
"""

from __future__ import annotations

import json
import re
from unittest.mock import patch

from django.core.cache import cache, caches
from django.test import TestCase
from django.utils import translation

from productcolors.models import Color, ProductColorVariant
from storefront.models import Category, Product, ProductFAQ


class RenderedLocaleMatrixTests(TestCase):
    """Prevent indexable RU/EN standard pages from publishing UK fallbacks."""

    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(
            name="Футболки",
            name_ru="Футболки",
            name_en="T-shirts",
            slug="locale-matrix-tees",
            is_active=True,
        )
        cls.product = Product.objects.create(
            title="Українська футболка",
            title_ru="Русская футболка",
            title_en="English T-shirt",
            slug="locale-matrix-tee",
            category=cls.category,
            price=900,
            status="published",
            seo_title_ru="Русская футболка TwoComms",
            seo_title_en="English T-shirt TwoComms",
            seo_description_ru="Русское описание футболки TwoComms.",
            seo_description_en="English TwoComms T-shirt description.",
            full_description_ru="Русское описание товара для повседневной носки.",
            full_description_en="English product description for everyday wear.",
        )
        ProductFAQ.objects.create(
            product=cls.product,
            question="Як підібрати розмір?",
            answer="Скористайтеся розмірною сіткою.",
            question_ru="Как выбрать размер?",
            answer_ru="Воспользуйтесь размерной сеткой.",
            question_en="How do I choose a size?",
            answer_en="Use the size chart.",
            is_active=True,
        )
        color = Color.objects.create(name="Чорний", primary_hex="#000000")
        ProductColorVariant.objects.create(
            product=cls.product,
            color=color,
            is_default=True,
            order=0,
        )

    def setUp(self):
        super().setUp()
        previous_language = translation.get_language() or "uk"
        self.addCleanup(translation.activate, previous_language)
        cache.clear()
        caches["fragments"].clear()
        for target in (
            "storefront.signals.generate_google_merchant_feed_task.apply_async",
            "storefront.signals.enqueue_indexnow_urls",
        ):
            patcher = patch(target)
            patcher.start()
            self.addCleanup(patcher.stop)

    def _product_seo_landing(self, body: str) -> str:
        match = re.search(
            r'<section class="product-seo-landing".*?</section>',
            body,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(match)
        return match.group(0)

    def _json_ld_node(self, body: str, schema_type: str) -> dict:
        for payload in re.findall(
            r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>',
            body,
            flags=re.DOTALL,
        ):
            data = json.loads(payload)
            candidates = data if isinstance(data, list) else [data]
            for candidate in candidates:
                if (
                    isinstance(candidate, dict)
                    and candidate.get("@type") == schema_type
                ):
                    return candidate
        self.fail(f"No {schema_type} JSON-LD node found")

    def test_standard_pdp_founder_schema_is_locale_owned(self):
        matrix = {
            "ru": {
                "path": "/ru/product/locale-matrix-tee/",
                "job_title": "Основатель TwoComms",
                "description": (
                    "Основатель украинского streetwear-бренда TwoComms из "
                    "Харькова, боевой ветеран."
                ),
            },
            "en": {
                "path": "/en/product/locale-matrix-tee/",
                "job_title": "Founder of TwoComms",
                "description": (
                    "Founder of the Ukrainian streetwear brand TwoComms from "
                    "Kharkiv; a combat veteran."
                ),
            },
        }

        for locale, expected in matrix.items():
            with self.subTest(locale=locale):
                response = self.client.get(expected["path"])
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "index, follow")
                schema = self._json_ld_node(
                    response.content.decode("utf-8"),
                    "Person",
                )

                self.assertEqual(schema["jobTitle"], expected["job_title"])
                self.assertEqual(schema["description"], expected["description"])
                self.assertNotIn("Засновник українського", schema["description"])

    def test_standard_pdp_gallery_exposes_locale_owned_js_labels(self):
        matrix = {
            "ru": {
                "path": "/ru/product/locale-matrix-tee/",
                "region": "Позиция в галерее",
                "status": "Фото {position} из {total}",
                "thumbnail": "Фото товара {position}",
                "initial_status": "Фото 1 из 1",
            },
            "en": {
                "path": "/en/product/locale-matrix-tee/",
                "region": "Gallery position",
                "status": "Photo {position} of {total}",
                "thumbnail": "Product photo {position}",
                "initial_status": "Photo 1 of 1",
            },
        }

        for locale, expected in matrix.items():
            with self.subTest(locale=locale):
                response = self.client.get(expected["path"])
                self.assertEqual(response.status_code, 200)
                body = response.content.decode("utf-8")
                self.assertIn(
                    f'aria-label="{expected["region"]}"',
                    body,
                )
                self.assertIn(
                    f'data-gallery-status-template="{expected["status"]}"',
                    body,
                )
                self.assertIn(
                    f'data-gallery-thumbnail-template="{expected["thumbnail"]}"',
                    body,
                )
                self.assertIn(
                    'product-detail.js?v=20260813-gallery-i18n-v1',
                    body,
                )
                self.assertIn(
                    f'data-gallery-status role="status" aria-live="polite" '
                    f'aria-atomic="true">{expected["initial_status"]}</span>',
                    body,
                )
                self.assertNotIn('aria-label="Позиція у галереї"', body)

    def test_standard_pdp_shared_merchandising_shell_is_locale_owned(self):
        matrix = {
            "ru": {
                "path": "/ru/product/locale-matrix-tee/",
                "context": "Контекст модели",
                "custom_title": "Хочешь этот принт иначе?",
                "custom_copy": (
                    "Сделай похожий вариант на другом цвете, основе или добавь "
                    "свой знак в кастомной DTF-печати."
                ),
                "custom_action": "Создать свой вариант",
            },
            "en": {
                "path": "/en/product/locale-matrix-tee/",
                "context": "Model context",
                "custom_title": "Want this print in a different version?",
                "custom_copy": (
                    "Make a similar version on another color or base, or add "
                    "your own mark with custom DTF printing."
                ),
                "custom_action": "Create your own version",
            },
        }

        ukrainian_markers = (
            "Контекст моделі",
            "Хочеш цей принт інакше?",
            "Зроби схожий варіант на іншому кольорі, основі або додай свій знак у кастомному DTF-друці.",
            "Створити свій варіант",
        )

        for locale, expected in matrix.items():
            with self.subTest(locale=locale):
                response = self.client.get(expected["path"])
                self.assertEqual(response.status_code, 200)
                body = response.content.decode("utf-8")
                for value in (
                    expected["context"],
                    expected["custom_title"],
                    expected["custom_copy"],
                    expected["custom_action"],
                ):
                    self.assertIn(value, body)
                for marker in ukrainian_markers:
                    self.assertNotIn(marker, body)

    def test_standard_pdp_editorial_links_use_locale_owned_labels_and_urls(self):
        matrix = {
            "ru": {
                "path": "/ru/product/locale-matrix-tee/",
                "prefix": "/ru",
                "required": (
                    "Топ-запросы для этой модели",
                    "Разделы каталога",
                    "Доставка и оплата",
                    "Размерная сетка",
                    "Уход за одеждой",
                    "Возврат и обмен",
                    "О бренде TwoComms",
                ),
            },
            "en": {
                "path": "/en/product/locale-matrix-tee/",
                "prefix": "/en",
                "required": (
                    "Top queries for this model",
                    "Catalog sections",
                    "Delivery &amp; payment",
                    "Size chart",
                    "Garment care",
                    "Returns &amp; exchanges",
                    "About TwoComms brand",
                ),
            },
        }

        for locale, expectations in matrix.items():
            with self.subTest(locale=locale):
                response = self.client.get(expectations["path"])
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "index, follow")
                rail = self._product_seo_landing(
                    response.content.decode("utf-8")
                )

                for value in expectations["required"]:
                    self.assertIn(value, rail)
                for route in (
                    "delivery",
                    "rozmirna-sitka",
                    "doglyad-za-odyagom",
                    "povernennya-ta-obmin",
                    "pro-brand",
                ):
                    self.assertIn(
                        f'href="{expectations["prefix"]}/{route}/"',
                        rail,
                    )

                for ukrainian in (
                    "Розділи каталогу",
                    "Доставка Новою Поштою",
                    "Розмірна сітка та посадка",
                    "Повернення за 14 днів",
                    "Замовити кастомний DTF-друк",
                ):
                    self.assertNotIn(ukrainian, rail)

                self.assertNotIn("?color=", rail)
                self.assertNotIn(
                    f'{expectations["prefix"]}/catalog/theme/',
                    rail,
                )
