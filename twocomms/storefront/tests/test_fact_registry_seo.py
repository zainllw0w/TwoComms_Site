from decimal import Decimal

from django.test import Client, TestCase, override_settings


class PublicFactRegistrySeoTests(TestCase):
    def test_homepage_cache_version_changes_when_public_fact_contract_changes(self):
        from storefront.views.catalog import HOME_SEO_FACTS_CACHE_VERSION

        self.assertEqual(HOME_SEO_FACTS_CACHE_VERSION, "seo-facts-v2-20260813")

    def test_organization_schema_does_not_publish_unverified_foundation_or_postal_address(self):
        from storefront.seo_utils import StructuredDataGenerator

        schema = StructuredDataGenerator.generate_organization_schema()

        self.assertNotIn("foundingDate", schema)
        self.assertNotIn("foundingLocation", schema)
        self.assertNotIn("address", schema)

    @override_settings(FREE_SHIPPING_THRESHOLD="2750")
    def test_llms_txt_uses_checkout_shipping_threshold(self):
        response = Client().get("/llms.txt")

        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8")
        self.assertIn("orders of 2750 UAH and above ship for free", body)
        self.assertNotIn("orders of 3000 UAH and above ship for free", body)

    def test_fact_registry_records_owner_source_locale_and_effective_date(self):
        from storefront.services.fact_registry import PUBLIC_FACTS_VERSION, PUBLIC_FACTS

        self.assertTrue(PUBLIC_FACTS_VERSION)
        shipping = PUBLIC_FACTS["free_shipping_threshold"]
        self.assertEqual(shipping.owner, "checkout_settings")
        self.assertEqual(shipping.locale, "all")
        self.assertTrue(shipping.source)
        self.assertTrue(shipping.effective_date)
