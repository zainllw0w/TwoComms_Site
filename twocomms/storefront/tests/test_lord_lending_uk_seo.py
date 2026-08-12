"""Regression coverage for the audited Ukrainian PDP metadata of product 31."""

from __future__ import annotations

from html.parser import HTMLParser
import json
import re
from types import SimpleNamespace
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from storefront.models import Category, Product


class _SeoParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta = {}
        self.h1 = ""
        self._in_h1 = False
        self.json_ld = []
        self._in_json_ld = False
        self._json_ld_parts = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "meta":
            key = attrs.get("name") or attrs.get("property")
            if key in {"description", "og:description"}:
                self.meta[key] = attrs.get("content", "")
        elif tag == "h1":
            self._in_h1 = True
        elif tag == "script" and attrs.get("type") == "application/ld+json":
            self._in_json_ld = True
            self._json_ld_parts = []

    def handle_endtag(self, tag):
        if tag == "h1":
            self._in_h1 = False
        elif tag == "script" and self._in_json_ld:
            self._in_json_ld = False
            try:
                self.json_ld.append(json.loads("".join(self._json_ld_parts)))
            except json.JSONDecodeError:
                pass

    def handle_data(self, data):
        if self._in_h1:
            self.h1 += data
        if self._in_json_ld:
            self._json_ld_parts.append(data)


@override_settings(
    SITE_BASE_URL="https://twocomms.shop",
    COMPRESS_ENABLED=False,
    COMPRESS_OFFLINE=False,
    NOVA_POSHTA_FALLBACK_ENABLED=False,
)
class LordOfTheLendingUkSeoTests(TestCase):
    def setUp(self):
        self.feed_task_patcher = patch(
            "storefront.signals.generate_google_merchant_feed_task.apply_async",
            return_value=None,
        )
        self.feed_task_patcher.start()
        self.addCleanup(self.feed_task_patcher.stop)
        self.category = Category.objects.create(
            name_uk="Футболки",
            slug="tshirts",
            is_active=True,
        )
        self.product = Product.objects.create(
            id=31,
            title_uk="Футболка «Це Моя Посадка»",
            slug="lord-of-the-lending",
            category=self.category,
            price=1000,
            description_uk="Авторський принт TwoComms.",
            status="published",
            main_image=SimpleUploadedFile(
                "lord-of-the-lending.png", b"not-an-image", content_type="image/png"
            ),
            seo_description_uk=(
                "Футболка «Lord Of The Lending» TwoComms — сатирична фентезі-пародія "
                "про владу банків і кредитів. Шиємо в Україні, DTF-друк, бавовна. "
                "Доставка Новою Поштою. Підтримуємо ЗСУ."
            ),
            main_image_alt_uk=(
                "Футболка «LORD OF THE LENDING» TwoComms - стильная футболка з "
                "унікальним дизайном для модних поціновувачів."
            ),
        )

    def test_uk_rendered_identity_is_consistent_across_meta_schema_and_main_alt(self):
        migration = __import__(
            "storefront.migrations.0092_repair_lord_lending_uk_seo",
            fromlist=["repair_lord_lending_uk_seo"],
        )
        migration.repair_lord_lending_uk_seo(
            SimpleNamespace(get_model=lambda _app, _model: Product),
            schema_editor=None,
        )
        response = self.client.get(reverse("product", kwargs={"slug": self.product.slug}))

        self.assertEqual(response.status_code, 200)
        parser = _SeoParser()
        parser.feed(response.content.decode("utf-8"))

        self.assertEqual(parser.h1.strip(), "Футболка «Це Моя Посадка»")
        for field in ("description", "og:description"):
            self.assertIn("Футболка «Це Моя Посадка»", parser.meta[field])
            self.assertIn("Lord Of The Lending", parser.meta[field])
            self.assertNotIn("Футболка «Lord Of The Lending»", parser.meta[field])

        product_nodes = [
            node
            for graph in parser.json_ld
            for node in graph.get("@graph", [])
            if node.get("@type") == "Product"
        ]
        self.assertTrue(product_nodes)
        product_node = product_nodes[0]
        self.assertEqual(product_node["name"], "Футболка «Це Моя Посадка»")
        self.assertIn("Футболка «Це Моя Посадка»", product_node["description"])
        self.assertIn("Lord Of The Lending", product_node["description"])
        self.assertNotIn("Футболка «Lord Of The Lending»", product_node["description"])

        hero = re.search(r'<img[^>]+id="mainProductImage"[^>]+alt="([^"]+)"', response.content.decode("utf-8"))
        self.assertIsNotNone(hero)
        self.assertIn("Футболка «Це Моя Посадка»", hero.group(1))
        self.assertIn("Lord Of The Lending", hero.group(1))
