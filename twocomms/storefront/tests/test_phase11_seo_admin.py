"""
Phase 11 — SEO admin dashboard regression tests.

Covers:
  * `build_sitemap_summary` returns the five sub-sitemaps + total tile,
    with non-zero counts for fixtures.
  * `build_ai_panel` reports opt-in objects and aggregate counts.
  * `build_seo_blocks_summary` annotates active block counts per category.
  * `?section=seo` renders the dashboard partial for staff users.
  * `admin_seo_ai_generate` AJAX endpoint:
      - 405 on GET, 401-ish redirect for non-staff,
      - 503 when OpenAI is not configured,
      - 503 when both AI feature flags are off,
      - 400 on unknown target / non-opt-in object,
      - 200 + JSON snapshot when configured & ai_generation_enabled=True.
"""
from __future__ import annotations

import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache, caches
from django.test import TestCase, override_settings
from django.urls import reverse

from storefront.models import (
    Category,
    CategorySeoBlock,
    CategorySeoBlockItem,
    Product,
)
from storefront.services.seo_dashboard import (
    build_ai_panel,
    build_seo_blocks_summary,
    build_seo_dashboard_context,
    build_sitemap_summary,
)


class _BaseSeoAdminTests(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        caches["fragments"].clear()
        merchant_patcher = patch(
            "storefront.signals.generate_google_merchant_feed_task.apply_async"
        )
        indexnow_patcher = patch("storefront.signals.enqueue_indexnow_urls")
        self.addCleanup(merchant_patcher.stop)
        self.addCleanup(indexnow_patcher.stop)
        merchant_patcher.start()
        indexnow_patcher.start()

        self.cat = Category.objects.create(
            name="SEO Cat", slug="seo-cat", is_active=True,
        )
        self.cat_ai = Category.objects.create(
            name="AI Cat", slug="ai-cat", is_active=True,
            ai_generation_enabled=True,
        )
        self.product = Product.objects.create(
            title="SEO Product", slug="seo-product",
            category=self.cat, price=500, status="published",
        )
        self.product_ai = Product.objects.create(
            title="AI Product", slug="ai-product",
            category=self.cat, price=500, status="published",
            ai_generation_enabled=True,
        )

        self.staff = User.objects.create_user(
            username="staff", password="pass", is_staff=True
        )
        self.regular = User.objects.create_user(
            username="user", password="pass"
        )


class SeoDashboardServiceTests(_BaseSeoAdminTests):
    def test_sitemap_summary_includes_all_sections_and_total(self):
        rows = build_sitemap_summary()
        keys = [r["key"] for r in rows]
        self.assertEqual(
            keys,
            ["static", "products", "variants", "categories", "images", "total"],
        )
        # Both fixtures should bump the products and categories counts.
        by_key = {r["key"]: r for r in rows}
        self.assertGreaterEqual(by_key["products"]["count"], 2)
        self.assertGreaterEqual(by_key["categories"]["count"], 2)
        # Total is the sum of the previous five entries.
        total = sum(r["count"] for r in rows if not r.get("is_total"))
        self.assertEqual(by_key["total"]["count"], total)

    def test_ai_panel_returns_opt_in_objects(self):
        panel = build_ai_panel()
        self.assertEqual(panel["ai_counts"]["products_total"], 1)
        self.assertEqual(panel["ai_counts"]["categories_total"], 1)
        product_slugs = [p.slug for p in panel["ai_products"]]
        category_slugs = [c.slug for c in panel["ai_categories"]]
        self.assertIn("ai-product", product_slugs)
        self.assertIn("ai-cat", category_slugs)

    def test_seo_blocks_summary_counts_active_blocks(self):
        block = CategorySeoBlock.objects.create(
            category=self.cat, block_type="top_filters", title="x",
        )
        CategorySeoBlockItem.objects.create(block=block, label="Item", url="/x/")
        CategorySeoBlock.objects.create(
            category=self.cat, block_type="top_queries",
            title="hidden", is_active=False,
        )
        rows = build_seo_blocks_summary()
        by_id = {r["id"]: r for r in rows}
        self.assertEqual(by_id[self.cat.id]["blocks_active"], 1)
        self.assertEqual(by_id[self.cat.id]["blocks_total"], 2)
        self.assertEqual(by_id[self.cat_ai.id]["blocks_active"], 0)


class SeoDashboardViewTests(_BaseSeoAdminTests):
    def test_section_seo_renders_dashboard_for_staff(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("admin_panel") + "?section=seo")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sitemap-index — кількість URL")
        self.assertContains(response, "AI-генерація мета-тегів")
        self.assertContains(response, "Phase 10 — SEO-блоки категорій")
        self.assertContains(response, 'data-action="seo-ai-generate"')

    def test_section_seo_redirects_non_staff(self):
        self.client.force_login(self.regular)
        response = self.client.get(reverse("admin_panel") + "?section=seo")
        # admin_panel redirects non-staff to home (not 403).
        self.assertEqual(response.status_code, 302)


class SeoAiGenerateEndpointTests(_BaseSeoAdminTests):
    def setUp(self):
        super().setUp()
        self.url = reverse("admin_seo_ai_generate")

    def test_get_method_not_allowed(self):
        self.client.force_login(self.staff)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    @override_settings(OPENAI_API_KEY="", USE_AI_KEYWORDS=True)
    def test_missing_api_key_returns_503(self):
        self.client.force_login(self.staff)
        with patch.dict("os.environ", {}, clear=False):
            import os as _os
            _os.environ.pop("OPENAI_API_KEY", None)
            response = self.client.post(
                self.url,
                data=json.dumps({"target": "product", "id": self.product_ai.id}),
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.json()["success"])

    @override_settings(
        OPENAI_API_KEY="sk-test", USE_AI_KEYWORDS=False, USE_AI_DESCRIPTIONS=False
    )
    def test_feature_flags_off_returns_503(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            self.url,
            data=json.dumps({"target": "product", "id": self.product_ai.id}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 503)

    @override_settings(OPENAI_API_KEY="sk-test", USE_AI_KEYWORDS=True)
    def test_unknown_target_returns_400(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            self.url,
            data=json.dumps({"target": "garbage", "id": 1}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    @override_settings(OPENAI_API_KEY="sk-test", USE_AI_KEYWORDS=True)
    def test_non_opt_in_product_returns_400(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            self.url,
            data=json.dumps({"target": "product", "id": self.product.id}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    @override_settings(OPENAI_API_KEY="sk-test", USE_AI_KEYWORDS=True)
    def test_happy_path_returns_snapshot(self):
        self.client.force_login(self.staff)
        # Patch the underlying task body so the test does not call OpenAI.
        with patch(
            "storefront.tasks.generate_ai_content_for_product_task"
        ) as mock_task:
            def _fake(product_id):
                p = Product.objects.get(pk=product_id)
                p.ai_keywords = "fake-keywords-ok"
                p.ai_content_generated = True
                p.save(update_fields=["ai_keywords", "ai_content_generated"])
            mock_task.side_effect = _fake

            response = self.client.post(
                self.url,
                data=json.dumps({"target": "product", "id": self.product_ai.id}),
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["target"], "product")
        self.assertTrue(body["ai_content_generated"])
        self.assertIn("fake-keywords-ok", body["ai_keywords"])
