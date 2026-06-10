import re

from django.test import TestCase

from management.email_templates.twocomms_cp import (
    build_twocomms_cp_email,
    get_twocomms_cp_opt_grid,
)
from management.invoice_service import get_management_wholesale_price_context


class OptGridTests(TestCase):
    def test_opt_grid_is_monotonic(self):
        grid = get_twocomms_cp_opt_grid()
        self.assertGreaterEqual(len(grid), 5)
        tee_prices = [row["tee"] for row in grid]
        hoodie_prices = [row["hoodie"] for row in grid]
        # Larger volume tiers must never cost more per unit.
        self.assertEqual(tee_prices, sorted(tee_prices, reverse=True))
        self.assertEqual(hoodie_prices, sorted(hoodie_prices, reverse=True))

    def test_opt_grid_matches_invoice_service(self):
        grid = get_twocomms_cp_opt_grid()
        ctx = get_management_wholesale_price_context()
        self.assertEqual([row["tee"] for row in grid], ctx["tshirt"]["wholesale"])
        self.assertEqual([row["hoodie"] for row in grid], ctx["hoodie"]["wholesale"])


class EmailBuilderTests(TestCase):
    def test_builder_total_on_empty_payload(self):
        build = build_twocomms_cp_email({})
        self.assertTrue(build["html"].strip())
        self.assertTrue(build["text"].strip())

    def test_builder_returns_full_document(self):
        build = build_twocomms_cp_email({"shop_name": "ТестМаг"})
        html = build["html"].lstrip().lower()
        self.assertTrue(html.startswith("<!doctype"))

    def test_email_readable_without_images(self):
        build = build_twocomms_cp_email({"shop_name": "ТестМаг"})
        html_no_img = re.sub(r"<img[^>]*>", "", build["html"], flags=re.IGNORECASE)
        # Key B2B info must survive with images blocked.
        self.assertIn("грн", html_no_img)
        self.assertIn("Зв", html_no_img)  # "Зв'язатися" CTA present

    def test_preview_equals_send_html(self):
        payload = {"shop_name": "ТестМаг", "segment_mode": "NEUTRAL"}
        a = build_twocomms_cp_email(payload)["html"]
        b = build_twocomms_cp_email(payload)["html"]
        self.assertEqual(a, b)
