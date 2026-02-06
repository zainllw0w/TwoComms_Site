from decimal import Decimal
import xml.etree.ElementTree as ET

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from .forms import DtfHelpForm, DtfOrderForm
from .models import DtfOrder
from .utils import calculate_pricing


class DtfOrderTests(TestCase):
    def setUp(self):
        self.client = Client(HTTP_HOST="dtf.twocomms.shop")

    def test_order_number_unique(self):
        o1 = DtfOrder.objects.create(
            name="Test",
            phone="+380501112233",
            city="Kyiv",
            np_branch="1",
        )
        o2 = DtfOrder.objects.create(
            name="Test2",
            phone="+380501112234",
            city="Kyiv",
            np_branch="1",
        )
        self.assertNotEqual(o1.order_number, o2.order_number)

    def test_pricing_calc(self):
        result = calculate_pricing(Decimal("2.5"), 10)
        self.assertEqual(result["meters_total"], Decimal("25.00"))
        self.assertGreater(result["price_total"], 0)

    def test_status_lookup(self):
        order = DtfOrder.objects.create(
            name="Client",
            phone="+380501112233",
            city="Kyiv",
            np_branch="1",
        )
        resp = self.client.post(
            "/status/",
            {
                "order_number": order.order_number,
                "phone": "+380501112233",
            },
            secure=True,
        )
        self.assertContains(resp, order.order_number)


class DtfP0RoutesTests(TestCase):
    def setUp(self):
        self.client = Client(HTTP_HOST="dtf.twocomms.shop")

    def test_quality_page_returns_200(self):
        response = self.client.get("/quality/", secure=True)
        self.assertEqual(response.status_code, 200)

    def test_price_page_returns_200(self):
        response = self.client.get("/price/", secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ціни")

    def test_prices_redirects_to_price(self):
        response = self.client.get("/prices/", secure=True)
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response["Location"], "/price/")

    def test_robots_points_to_current_host_sitemap(self):
        response = self.client.get("/robots.txt", secure=True)
        self.assertEqual(response.status_code, 200)
        payload = response.content.decode("utf-8")
        self.assertIn("Sitemap: https://dtf.twocomms.shop/sitemap.xml", payload)
        self.assertNotIn("Sitemap: https://twocomms.shop/sitemap.xml", payload)

    def test_sitemap_uses_request_host_and_contains_price(self):
        response = self.client.get("/sitemap.xml", secure=True)
        self.assertEqual(response.status_code, 200)

        xml_root = ET.fromstring(response.content)
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        locs = [node.text for node in xml_root.findall("sm:url/sm:loc", ns) if node.text]

        self.assertTrue(any(loc.endswith("/price/") for loc in locs))
        self.assertTrue(all(loc.startswith("https://dtf.twocomms.shop/") for loc in locs))
        self.assertFalse(any(loc.startswith("https://twocomms.shop/") for loc in locs))


class DtfUploadSecurityTests(TestCase):
    def test_order_form_rejects_magic_mismatch(self):
        fake_png = SimpleUploadedFile(
            "payload.png",
            b"<?php echo 'bad'; ?>",
            content_type="image/png",
        )
        form = DtfOrderForm(
            data={
                "name": "Client",
                "phone": "+380501112233",
                "contact_channel": "telegram",
                "city": "Kyiv",
                "np_branch": "1",
                "length_m": "1",
                "copies": "1",
            },
            files={"gang_file": fake_png},
        )

        self.assertFalse(form.is_valid())
        self.assertIn("gang_file", form.errors)

    def test_order_form_renames_valid_upload_to_safe_path(self):
        pdf_file = SimpleUploadedFile(
            "my-layout.pdf",
            b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF",
            content_type="application/pdf",
        )
        form = DtfOrderForm(
            data={
                "name": "Client",
                "phone": "+380501112233",
                "contact_channel": "telegram",
                "city": "Kyiv",
                "np_branch": "1",
                "length_m": "1",
                "copies": "1",
            },
            files={"gang_file": pdf_file},
        )

        self.assertTrue(form.is_valid(), form.errors)
        safe_name = form.cleaned_data["gang_file"].name
        self.assertTrue(safe_name.startswith("orders-"))
        self.assertTrue(safe_name.endswith(".pdf"))
        self.assertNotIn("my-layout", safe_name)

    def test_help_form_validates_and_renames_files(self):
        zip_file = SimpleUploadedFile(
            "source-pack.zip",
            b"PK\x03\x04\x14\x00\x00\x00",
            content_type="application/zip",
        )
        form = DtfHelpForm(
            data={
                "name": "Client",
                "phone": "+380501112233",
                "contact_channel": "telegram",
                "city": "Kyiv",
                "np_branch": "1",
                "task_description": "Need gang sheet prep",
            },
            files={"files": zip_file},
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(len(form._validated_files), 1)
        self.assertTrue(form._validated_files[0].name.startswith("leads-"))
        self.assertTrue(form._validated_files[0].name.endswith(".zip"))

    def test_help_form_rejects_unsupported_extension(self):
        bad_file = SimpleUploadedFile(
            "shell.php",
            b"<?php echo 'bad'; ?>",
            content_type="text/x-php",
        )
        form = DtfHelpForm(
            data={
                "name": "Client",
                "phone": "+380501112233",
                "contact_channel": "telegram",
                "city": "Kyiv",
                "np_branch": "1",
                "task_description": "Need prep",
            },
            files={"files": bad_file},
        )

        self.assertFalse(form.is_valid())
        self.assertIn("files", form.errors)


class DtfSubdomainIsolationTests(TestCase):
    def setUp(self):
        self.main_client = Client(HTTP_HOST="twocomms.shop")
        self.dtf_client = Client(HTTP_HOST="dtf.twocomms.shop")

    def test_dtf_home_uses_dtf_template_assets(self):
        response = self.dtf_client.get("/", secure=True)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8", "ignore")
        self.assertIn("/static/dtf/css/dtf.css", html)
        self.assertIn('class="logo-mark">DTF', html)

    def test_dtf_home_hero_uses_responsive_sources(self):
        response = self.dtf_client.get("/", secure=True)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8", "ignore")
        self.assertIn("hero-printhead-512.avif", html)
        self.assertIn("hero-printhead-768.avif", html)
        self.assertIn("hero-printhead-1024.webp", html)
        self.assertIn('fetchpriority="high"', html)
        self.assertIn('width="1024"', html)
        self.assertIn('height="1024"', html)

    def test_robots_are_isolated_by_host(self):
        dtf_robots = self.dtf_client.get("/robots.txt", secure=True).content.decode("utf-8", "ignore")
        main_robots = self.main_client.get("/robots.txt", secure=True).content.decode("utf-8", "ignore")

        self.assertIn("Sitemap: https://dtf.twocomms.shop/sitemap.xml", dtf_robots)
        self.assertNotIn("Sitemap: https://twocomms.shop/sitemap.xml", dtf_robots)
        self.assertIn("Sitemap: https://twocomms.shop/sitemap.xml", main_robots)

    def test_sitemaps_are_isolated_by_host(self):
        dtf_sitemap = self.dtf_client.get("/sitemap.xml", secure=True).content.decode("utf-8", "ignore")
        main_sitemap = self.main_client.get("/sitemap.xml", secure=True).content.decode("utf-8", "ignore")

        self.assertIn("https://dtf.twocomms.shop/", dtf_sitemap)
        self.assertNotIn("https://twocomms.shop/", dtf_sitemap)
        self.assertIn("https://twocomms.shop/", main_sitemap)
