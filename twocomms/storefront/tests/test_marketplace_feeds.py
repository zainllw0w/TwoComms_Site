import xml.etree.ElementTree as ET
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings

from productcolors.models import Color, ProductColorVariant
from storefront.models import Category, Product, ProductStatus


G_NS = {"g": "http://base.google.com/ns/1.0"}


@override_settings(
    SITE_BASE_URL="https://twocomms.shop",
    FEED_BASE_URL="https://twocomms.shop",
    ROZETKA_CATEGORY_RZ_ID_MAP={"futbolki": "4637839"},
)
class MarketplaceFeedServiceTests(TestCase):
    def setUp(self):
        super().setUp()
        merchant_patcher = patch("storefront.signals.generate_google_merchant_feed_task.apply_async")
        indexnow_patcher = patch("storefront.signals.enqueue_indexnow_urls")
        self.addCleanup(merchant_patcher.stop)
        self.addCleanup(indexnow_patcher.stop)
        merchant_patcher.start()
        indexnow_patcher.start()

        self.category = Category.objects.create(name="Футболки", slug="futbolki", is_active=True)
        self.product = Product.objects.create(
            title="Футболка TwoComms Test",
            slug="twocomms-test-shirt",
            category=self.category,
            price=1500,
            discount_percent=20,
            full_description="Український опис товару з характером.",
            description="Український опис товару з характером.",
            seo_schema={"video_link": "https://twocomms.shop/media/products/test-shirt.mp4"},
            main_image="products/test-shirt-main.jpg",
            status=ProductStatus.PUBLISHED,
        )
        color = Color.objects.create(name="Чорний", primary_hex="#000000")
        self.variant = ProductColorVariant.objects.create(
            product=self.product,
            color=color,
            sku="TWC-TEST-BLACK",
            barcode="4006381333931",
            stock=7,
        )
        Product.objects.create(
            title="Draft Product",
            slug="draft-product",
            category=self.category,
            price=999,
            status=ProductStatus.DRAFT,
        )

    def test_rozetka_feed_contains_required_fields_for_every_size_offer(self):
        from storefront.services.marketplace_feeds import build_rozetka_feed_xml

        root = ET.fromstring(build_rozetka_feed_xml(base_url="https://twocomms.shop"))
        categories = root.find("shop/categories")
        category = categories.find("category")
        offers = root.findall("shop/offers/offer")

        self.assertEqual(category.attrib["id"], str(self.category.id))
        self.assertEqual(category.attrib["rz_id"], "4637839")
        self.assertEqual(len(offers), 5)

        articles = {offer.findtext("article") for offer in offers}
        offer_ids = {offer.attrib["id"] for offer in offers}
        self.assertEqual(articles, {"TWC-TEST-BLACK"})
        self.assertNotIn("TWC-TEST-BLACK", offer_ids)

        first = offers[0]
        self.assertEqual(first.attrib["available"], "true")
        self.assertEqual(first.findtext("price"), "1200")
        self.assertEqual(first.findtext("price_old"), "1500")
        self.assertEqual(first.findtext("currencyId"), "UAH")
        self.assertEqual(first.findtext("categoryId"), str(self.category.id))
        self.assertEqual(first.findtext("vendor"), "TwoComms")
        self.assertEqual(first.findtext("stock_quantity"), "7")
        self.assertTrue(first.findtext("picture").startswith("https://twocomms.shop/media/products/"))
        self.assertIn("Чорний", first.findtext("name_ua"))
        self.assertIn("Эксклюзивный дизайн", first.findtext("description"))
        self.assertNotIn("Український опис", first.findtext("description"))

        params = {(param.attrib["name"], param.text) for param in first.findall("param")}
        self.assertIn(("Розмір", first.findtext("param")), params)
        self.assertIn(("Колір", "Чорний"), params)
        self.assertIn(("Країна-виробник товару", "Україна"), params)

    def test_google_feed_uses_current_merchant_attributes_and_valid_identifiers(self):
        from storefront.services.marketplace_feeds import build_google_merchant_feed_xml

        root = ET.fromstring(build_google_merchant_feed_xml(base_url="https://twocomms.shop"))
        items = root.findall("./channel/item")

        self.assertEqual(root.tag, "rss")
        self.assertEqual(len(items), 5)

        first = items[0]
        self.assertEqual(first.findtext("g:item_group_id", namespaces=G_NS), f"TC-GROUP-{self.product.id}")
        self.assertTrue(first.findtext("g:id", namespaces=G_NS).startswith("TC-"))
        self.assertIn("Чорний", first.findtext("g:title", namespaces=G_NS))
        self.assertEqual(first.findtext("g:availability", namespaces=G_NS), "in_stock")
        self.assertEqual(first.findtext("g:price", namespaces=G_NS), "1500.00 UAH")
        self.assertEqual(first.findtext("g:sale_price", namespaces=G_NS), "1200.00 UAH")
        self.assertEqual(first.findtext("g:brand", namespaces=G_NS), "TwoComms")
        self.assertEqual(first.findtext("g:gtin", namespaces=G_NS), "4006381333931")
        self.assertEqual(first.findtext("g:mpn", namespaces=G_NS), f"TWC-TEST-BLACK-{self.product.id}")
        self.assertEqual(first.findtext("g:google_product_category", namespaces=G_NS), "1604")
        self.assertEqual(first.findtext("g:condition", namespaces=G_NS), "new")
        self.assertEqual(
            first.findtext("g:video_link", namespaces=G_NS),
            "https://twocomms.shop/media/products/test-shirt.mp4",
        )
        self.assertGreaterEqual(len(first.findall("g:product_detail", namespaces=G_NS)), 5)
        self.assertGreaterEqual(len(first.findall("g:product_highlight", namespaces=G_NS)), 4)

    def test_feed_routes_return_dynamic_xml(self):
        response = self.client.get("/rozetka-feed.xml", secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/xml; charset=utf-8")
        self.assertIn(b"<yml_catalog", response.content)

        google = self.client.get("/google_merchant_feed.xml", secure=True)
        self.assertEqual(google.status_code, 200)
        self.assertIn(b"<g:id>", google.content)

    def test_management_commands_write_distinct_marketplace_files(self):
        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            google_path = tmp_path / "google.xml"
            rozetka_path = tmp_path / "rozetka.xml"
            prom_path = tmp_path / "prom.xml"

            call_command("generate_google_merchant_feed", output=str(google_path), base_url="https://twocomms.shop")
            call_command("generate_rozetka_feed", output=str(rozetka_path), base_url="https://twocomms.shop")
            call_command("generate_prom_feed", output=str(prom_path), base_url="https://twocomms.shop")

            google_xml = google_path.read_text(encoding="utf-8")
            rozetka_xml = rozetka_path.read_text(encoding="utf-8")
            prom_xml = prom_path.read_text(encoding="utf-8")

        self.assertIn("<rss", google_xml)
        self.assertIn("<g:id>", google_xml)
        self.assertIn("<yml_catalog", rozetka_xml)
        self.assertIn("<article>TWC-TEST-BLACK</article>", rozetka_xml)
        self.assertNotIn("<g:id>", rozetka_xml)
        self.assertIn("<oldprice>1500</oldprice>", prom_xml)
        self.assertNotIn("<article>", prom_xml)
