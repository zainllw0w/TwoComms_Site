"""SEO Audit 2026-05-15 — regression tests for Part 1-6 fixes.

Each test maps to a finding in the audit and guards against a
regression that would re-introduce the issue. References to the
relevant audit document (Part 1 .. Part 6) are inline.
"""
from __future__ import annotations

from unittest.mock import patch

from django.core.cache import cache, caches
from django.test import Client, TestCase

from storefront.models import Category, Product
from storefront.services.product_seo_autofill import (
    UNIVERSAL_FAQS,
    _build_care_instructions,
    _build_faqs,
    _build_target_audience,
)
from storefront.services.product_seo_landing import (
    _city_paragraph,
    _design_family_siblings,
    _design_family_stem,
    _siblings_paragraph,
    build_landing,
)


class _SeoAuditBase(TestCase):
    """Shared fixtures with a small design family (ts/hd/ls)."""

    def setUp(self):
        super().setUp()
        cache.clear()
        caches["fragments"].clear()
        for target in (
            "storefront.signals.generate_google_merchant_feed_task.apply_async",
            "storefront.signals.enqueue_indexnow_urls",
        ):
            p = patch(target)
            self.addCleanup(p.stop)
            p.start()

        self.cat_ts = Category.objects.create(
            name="Футболки", slug="tshirts", is_active=True,
        )
        self.cat_hd = Category.objects.create(
            name="Худі", slug="hoodie", is_active=True,
        )
        self.cat_ls = Category.objects.create(
            name="Лонгсліви", slug="long-sleeve", is_active=True,
        )

        self.product_ts = Product.objects.create(
            title="My Little Baby", slug="my-little-baby",
            category=self.cat_ts, price=900, status="published",
        )
        self.product_hd = Product.objects.create(
            title="My Little Baby HD", slug="my-little-baby-hd",
            category=self.cat_hd, price=1500, status="published",
        )
        self.product_ls = Product.objects.create(
            title="My Little Baby LS", slug="my-little-baby-ls",
            category=self.cat_ls, price=1100, status="published",
        )


class DesignFamilyStemTests(TestCase):
    """Audit Part 4 §17.3 — sibling-design cross-link helper."""

    def test_strips_hd_marker(self):
        self.assertEqual(_design_family_stem("my-little-baby-hd"), "my-little-baby")

    def test_strips_ls_marker(self):
        self.assertEqual(_design_family_stem("my-little-baby-ls"), "my-little-baby")

    def test_strips_ts_marker(self):
        # Some ts variants in the legacy catalogue carry an explicit
        # ``-ts`` suffix (death-grabs-ass-ts etc.).
        self.assertEqual(_design_family_stem("kha-style-ts"), "kha-style")

    def test_returns_unchanged_when_no_marker(self):
        self.assertEqual(_design_family_stem("classic-tshirt"), "classic-tshirt")

    def test_handles_empty_input(self):
        self.assertEqual(_design_family_stem(""), "")


class SiblingDesignCrossLinksTests(_SeoAuditBase):
    """Audit Part 4 §17.3 — cross-links between same-design variants."""

    def test_finds_sibling_hoodie_and_longsleeve_from_tshirt(self):
        siblings = _design_family_siblings(self.product_ts)
        urls = {s["url"] for s in siblings}
        self.assertIn(f"/product/{self.product_hd.slug}/", urls)
        self.assertIn(f"/product/{self.product_ls.slug}/", urls)
        # The current product itself must never appear as a sibling.
        self.assertNotIn(f"/product/{self.product_ts.slug}/", urls)

    def test_finds_sibling_tshirt_and_longsleeve_from_hoodie(self):
        siblings = _design_family_siblings(self.product_hd)
        urls = {s["url"] for s in siblings}
        self.assertIn(f"/product/{self.product_ts.slug}/", urls)
        self.assertIn(f"/product/{self.product_ls.slug}/", urls)

    def test_orders_siblings_by_category(self):
        # Ordering: tshirts → hoodie → long-sleeve (audit-friendly).
        siblings = _design_family_siblings(self.product_hd)
        order = [s["cat_slug"] for s in siblings]
        # tshirts comes before long-sleeve.
        self.assertLess(
            order.index("tshirts"), order.index("long-sleeve"),
            f"Unexpected sibling order: {order}",
        )

    def test_excludes_unpublished_siblings(self):
        self.product_ls.status = "draft"
        self.product_ls.save(update_fields=["status"])
        siblings = _design_family_siblings(self.product_ts)
        urls = {s["url"] for s in siblings}
        self.assertNotIn(f"/product/{self.product_ls.slug}/", urls)

    def test_paragraph_includes_anchor_links(self):
        html = _siblings_paragraph(self.product_ts)
        self.assertIn(f'href="/product/{self.product_hd.slug}/"', html)
        self.assertIn(f'href="/product/{self.product_ls.slug}/"', html)
        self.assertIn(self.product_ts.title, html)

    def test_paragraph_empty_for_standalone_design(self):
        # Standalone design with no siblings → no paragraph.
        Product.objects.create(
            title="Лонлі", slug="lonely-one",
            category=self.cat_ts, price=900, status="published",
        )
        product = Product.objects.get(slug="lonely-one")
        self.assertEqual(_siblings_paragraph(product), "")

    def test_landing_html_includes_sibling_paragraph(self):
        html = build_landing(self.product_ts)["landing_html"]
        self.assertIn(f'/product/{self.product_hd.slug}/', html)
        self.assertIn(f'/product/{self.product_ls.slug}/', html)


class CityParagraphTests(_SeoAuditBase):
    """Audit Part 6 §30.3 — city paragraph cleanup."""

    def test_paragraph_drops_unsupported_courier_promise(self):
        text = _city_paragraph(self.product_ts, "tshirts")
        # The legacy "до 14:00" courier promise is no longer accurate
        # and must not return.
        self.assertNotIn("14:00", text)

    def test_paragraph_keeps_geo_signal(self):
        text = _city_paragraph(self.product_ts, "tshirts")
        for city in ("Київ", "Харків", "Львів", "Одеса", "Дніпро"):
            self.assertIn(city, text)

    def test_paragraph_includes_fit_specific_clause(self):
        text_classic = _city_paragraph(self.product_ts, "tshirts", fit_code="classic")
        text_oversize = _city_paragraph(self.product_ts, "tshirts", fit_code="oversize")
        # Fit-specific clauses must differ — driving uniqueness across PDPs.
        self.assertNotEqual(text_classic, text_oversize)


class CareInstructionsTests(_SeoAuditBase):
    """Audit Part 5 §22 + Part 6 §29.3 — per-category care text."""

    def test_hoodie_text_mentions_threading_specifics(self):
        text = _build_care_instructions(self.product_hd)
        self.assertIn("трикотаж", text.lower())
        # Hoodie text describes hood handling — not present in the
        # tshirts/longsleeve copy.
        self.assertIn("капюшон", text.lower())

    def test_longsleeve_text_differs_from_tshirts(self):
        text_ts = _build_care_instructions(self.product_ts)
        text_ls = _build_care_instructions(self.product_ls)
        self.assertNotEqual(text_ts, text_ls)


class TargetAudienceTests(_SeoAuditBase):
    """Audit Part 6 §29.3 — per-category target audience text."""

    def test_audiences_differ_between_categories(self):
        text_ts = _build_target_audience(self.product_ts)
        text_hd = _build_target_audience(self.product_hd)
        text_ls = _build_target_audience(self.product_ls)
        self.assertNotEqual(text_ts, text_hd)
        self.assertNotEqual(text_hd, text_ls)
        self.assertNotEqual(text_ts, text_ls)


class FaqQuestionAnchoringTests(_SeoAuditBase):
    """Audit Part 6 §31.3 — FAQ questions anchored on product title."""

    def test_universal_faqs_template_includes_title_placeholder(self):
        # Q1..Q4 must mention the product title; Q5 ("Чи можна замовити
        # з власним принтом?") is a category-level intent question and
        # is intentionally generic — guarding 4/5 still defeats the
        # original audit finding (FAQ #3-#5 byte-identical across PDPs)
        # because Q3 + Q4 now carry the title.
        title_anchored = [q for q, _ in UNIVERSAL_FAQS if "{title}" in q]
        self.assertGreaterEqual(
            len(title_anchored), 4,
            "At least four FAQ questions must anchor on the product title "
            "to prevent rich-result clustering across PDPs.",
        )

    def test_built_faqs_include_product_title_in_majority_of_questions(self):
        faqs = _build_faqs(self.product_ts)
        questions = [q for q, _ in faqs]
        anchored = [q for q in questions if self.product_ts.title in q]
        # Same threshold (≥4 of 5) as the template-level guard.
        self.assertGreaterEqual(len(anchored), 4)

    def test_built_faqs_differ_between_products_in_same_category(self):
        ts2 = Product.objects.create(
            title="Other Print", slug="other-print",
            category=self.cat_ts, price=900, status="published",
        )
        q_ts = [q for q, _ in _build_faqs(self.product_ts)]
        q_ts2 = [q for q, _ in _build_faqs(ts2)]
        self.assertNotEqual(q_ts, q_ts2)


class HomepageTitleTests(TestCase):
    """Audit Part 4 §21 — homepage title cleanup."""

    def setUp(self):
        super().setUp()
        cache.clear()
        caches["fragments"].clear()
        for target in (
            "storefront.signals.generate_google_merchant_feed_task.apply_async",
            "storefront.signals.enqueue_indexnow_urls",
        ):
            p = patch(target)
            self.addCleanup(p.stop)
            p.start()
        self.client = Client()

    def test_homepage_title_does_not_include_legacy_suffix(self):
        # The old "| Головна" suffix wasted SERP budget without adding
        # semantic value. After the audit fix the title leads with the
        # brand + a geo-signal ("з Харкова").
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        title = response.content.decode("utf-8", errors="ignore")
        # Look for the title element only (avoid false matches in JSON-LD).
        import re
        m = re.search(r"<title>(.*?)</title>", title, re.S)
        self.assertIsNotNone(m, "Homepage missing <title>")
        title_text = m.group(1).strip()
        self.assertNotIn("| Головна", title_text)
        self.assertIn("Харкова", title_text)


class RobotsTxtVariantPolicyTests(TestCase):
    """Audit Part 4 §19 / clarification — variant URLs are *not*
    blocked in robots.txt because that would prevent Googlebot from
    seeing the canonical+noindex hints we already emit.
    """

    def test_variant_query_strings_remain_crawlable(self):
        response = self.client.get("/robots.txt")
        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8")
        for pattern in ("?color=", "?fit=", "?size="):
            self.assertNotIn(
                pattern, body,
                f"robots.txt must not Disallow {pattern} (would block "
                f"Googlebot from honouring canonical+noindex)."
            )
