"""Focused public rendering contracts for B02.8 policy consumers."""
from copy import deepcopy

from django.contrib.auth.models import AnonymousUser
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase

from storefront.services.approved_policy_copy import (
    PolicyCopyReadinessError,
    approved_policy_copy,
    apply_support_policy_copy,
)
from storefront.support_content import SUPPORT_PAGE_DEFINITIONS
from storefront.support_translations import apply_language_overrides
from storefront.views.static_pages import _build_page_context


class ApprovedPolicyCopyTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_surface_copy_has_no_provider_directives_in_all_public_languages(self):
        for language, dispatch_marker, receipt_marker in (
            ("uk", "після підтвердження оплати", "після отримання"),
            ("ru", "после подтверждения оплаты", "после получения"),
            ("en", "after payment is confirmed", "After receipt"),
        ):
            with self.subTest(language=language):
                policy = approved_policy_copy(language)
                self.assertIn(dispatch_marker, policy["text"]["dispatch"])
                self.assertIn(receipt_marker, policy["text"]["service_boundary"])
                self.assertNotIn("Не називай", "\n".join(policy["text"].values()))
                self.assertNotIn("Do not state", "\n".join(policy["text"].values()))
                self.assertEqual(len(policy["metadata"]["content_hash"]), 64)

    def test_adapter_replaces_all_targeted_support_slots_after_translation(self):
        for language in ("uk", "ru", "en"):
            with self.subTest(language=language):
                policy = approved_policy_copy(language)["text"]
                for page_key in ("delivery", "returns", "help_center", "faq"):
                    page = apply_language_overrides(
                        deepcopy(SUPPORT_PAGE_DEFINITIONS[page_key]), page_key, language
                    )
                    page = apply_support_policy_copy(page, page_key, language)
                    rendered = repr(page)
                    if page_key in {"delivery", "faq"}:
                        self.assertIn(policy["dispatch"], rendered)
                    if page_key in {"returns", "help_center", "faq"}:
                        self.assertIn(policy["service_boundary"], rendered)
                    if page_key == "returns":
                        self.assertNotIn("слідів використання", rendered)
                        self.assertNotIn("не підлягає поверненню", rendered)
                        self.assertNotIn("not subject to return", rendered)

    def test_adapter_uses_labels_not_positions_and_fails_if_a_slot_disappears(self):
        page = apply_language_overrides(
            deepcopy(SUPPORT_PAGE_DEFINITIONS["delivery"]), "delivery", "uk"
        )
        section = next(item for item in page["sections"] if item["title"] == "Базовий сценарій доставки")
        section["cards"].reverse()
        page["faq_items"].reverse()
        adapted = apply_support_policy_copy(page, "delivery", "uk")
        card = next(item for item in section["cards"] if item["title"] == "Строки")
        self.assertEqual(card["text"], approved_policy_copy("uk")["text"]["dispatch"])

        missing = apply_language_overrides(
            deepcopy(SUPPORT_PAGE_DEFINITIONS["delivery"]), "delivery", "uk"
        )
        missing["sections"][0]["cards"][0]["title"] = "Інший слот"
        with self.assertRaises(PolicyCopyReadinessError):
            apply_support_policy_copy(missing, "delivery", "uk")

    def test_released_legacy_hero_labels_and_service_faq_are_supported(self):
        for language, old_label in (
            ("uk", "1-5 днів по Україні"),
            ("ru", "1-5 дней по Украине"),
            ("en", "1-5 days within Ukraine"),
        ):
            with self.subTest(language=language):
                page = apply_language_overrides(
                    deepcopy(SUPPORT_PAGE_DEFINITIONS["delivery"]), "delivery", language,
                )
                page["hero_meta"][0] = old_label
                adapted = apply_support_policy_copy(page, "delivery", language)
                self.assertNotIn(old_label, adapted["hero_meta"])
                returns = apply_language_overrides(
                    deepcopy(SUPPORT_PAGE_DEFINITIONS["returns"]), "returns", language,
                )
                adapted_returns = apply_support_policy_copy(returns, "returns", language)
                self.assertEqual(len(adapted_returns["faq_items"]), 2)
                self.assertNotIn("3-5", repr(adapted_returns["faq_items"]))
                self.assertNotIn("24 год", repr(adapted_returns["faq_items"]))

    def test_checkout_template_renders_only_clean_copy_not_publication_metadata(self):
        policy = approved_policy_copy("en")
        html = render_to_string(
            "pages/ig_checkout.html",
            {
                "approved_policy": policy["text"],
                "approved_policy_manifest": policy["metadata"],
                "copy": {},
                "proposal": {},
                "items": (),
                "payable": True,
                "share_allowed": False,
                "checkout_state": "ready",
            },
        )
        self.assertIn(policy["text"]["dispatch"], html)
        self.assertIn(policy["text"]["service_boundary"], html)
        self.assertNotIn(policy["metadata"]["content_hash"], html)
        self.assertNotIn(policy["metadata"]["version"], html)

    def test_support_pages_render_the_replaced_policy_copy_in_all_languages(self):
        for language in ("uk", "ru", "en"):
            with self.subTest(language=language):
                request = self.factory.get("/delivery/")
                request.LANGUAGE_CODE = language
                request.user = AnonymousUser()
                context = _build_page_context(request, "delivery")
                html = render_to_string("pages/support_page.html", context, request=request)
                self.assertIn(approved_policy_copy(language)["text"]["dispatch"], html)
