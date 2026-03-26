from decimal import Decimal
from datetime import date
import base64
import xml.etree.ElementTree as ET

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from .forms import DtfHelpForm, DtfOrderForm
from .models import (
    BuilderStatus,
    DtfBuilderSession,
    DtfLifecycleStatus,
    DtfOrder,
    DtfQuote,
    DtfSampleLead,
    DtfStatusEvent,
    DtfUpload,
    KnowledgePost,
)
from .utils import calculate_pricing, get_pricing_config
from .pricing import calculate_quote
from .preflight.engine import analyze_upload

try:
    from storefront.models import PromoCode
except Exception:  # pragma: no cover
    PromoCode = None


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

    def test_default_pricing_range_is_350_to_280(self):
        config = get_pricing_config()
        rates = [config["base_rate"], *[tier["rate"] for tier in config["tiers"]]]
        self.assertEqual(max(rates), Decimal("350"))
        self.assertEqual(min(rates), Decimal("280"))

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

    def test_legal_pages_return_200(self):
        for path in ("/privacy/", "/terms/", "/returns/", "/requisites/"):
            with self.subTest(path=path):
                response = self.client.get(path, secure=True)
                self.assertEqual(response.status_code, 200)

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
        self.assertTrue(any(loc.endswith("/privacy/") for loc in locs))
        self.assertTrue(all(loc.startswith("https://dtf.twocomms.shop/") for loc in locs))
        self.assertFalse(any(loc.startswith("https://twocomms.shop/") for loc in locs))


class DtfPricingEngineTests(TestCase):
    def test_small_length_without_discount(self):
        quote = calculate_quote({"length_m": "2", "width_cm": "60", "urgency": "standard"})
        self.assertEqual(str(quote["pricing_tier"]), "base")
        self.assertGreater(quote["breakdown"]["total"], Decimal("0"))

    def test_volume_discount_applies(self):
        quote = calculate_quote({"length_m": "60", "width_cm": "60", "urgency": "standard"})
        self.assertNotEqual(quote["pricing_tier"], "base")
        self.assertGreaterEqual(quote["breakdown"]["discount_total"], Decimal("0"))

    def test_invalid_negative_length_raises(self):
        with self.assertRaises(ValueError):
            calculate_quote({"length_m": "-1", "width_cm": "60"})

    def test_urgency_and_service_fee_impact_total(self):
        regular = calculate_quote({"length_m": "5", "width_cm": "60", "urgency": "standard"})
        rush = calculate_quote(
            {
                "length_m": "5",
                "width_cm": "60",
                "urgency": "rush",
                "help_layout": "1",
                "with_shipping": "1",
            }
        )
        self.assertGreater(rush["breakdown"]["total"], regular["breakdown"]["total"])

    def test_quote_schema_has_required_keys(self):
        quote = calculate_quote({"length_m": "8", "width_cm": "60"})
        for key in ("config_version", "pricing_tier", "unit_price", "breakdown", "valid_until", "disclaimer"):
            self.assertIn(key, quote)
        for key in ("base_total", "discount_total", "urgency_extra", "services_total", "shipping_total", "total"):
            self.assertIn(key, quote["breakdown"])


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
        self.assertIn("hero-printhead-1024.avif", html)
        self.assertIn("imagesrcset=", html)
        self.assertIn('data-ui="dtf:home:hero"', html)
        self.assertIn('id="lens-modal"', html)
        self.assertIn('class="hero scan-hero"', html)

    def test_dtf_home_supports_en_language_switch(self):
        response = self.dtf_client.get("/?lang=en", secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.cookies["dtf_lang"].value, "en")
        html = response.content.decode("utf-8", "ignore")
        self.assertIn('>EN</a>', html)
        self.assertIn('lang=en', html)

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


class DtfPreflightEngineTests(TestCase):
    PNG_1X1 = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/a7wAAAAASUVORK5CYII=")

    def test_rejects_magic_mismatch(self):
        payload = SimpleUploadedFile("bad.png", b"%PDF-1.4\n%%EOF", content_type="image/png")
        result = analyze_upload(payload)
        self.assertEqual(result["result"], "FAIL")
        self.assertIn("PF_MAGIC_MISMATCH", result["errors"])

    def test_accepts_png_and_returns_structured_codes(self):
        payload = SimpleUploadedFile("ok.png", self.PNG_1X1, content_type="image/png")
        result = analyze_upload(payload)
        self.assertIn(result["result"], {"PASS", "WARN"})
        self.assertIn("checks", result)
        self.assertTrue(any("code" in item for item in result["checks"]))


class DtfKnowledgeBaseTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client(HTTP_HOST="dtf.twocomms.shop")
        self.post = KnowledgePost.objects.create(
            title="DTF Test Knowledge Post",
            slug="dtf-test-knowledge-post",
            excerpt="Short excerpt for SEO checks.",
            content_md="## Heading\n\nBody content with **markdown**.",
            pub_date=date.today(),
            is_published=True,
        )

    def test_blog_index_lists_post(self):
        response = self.client.get("/blog/", secure=True)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8", "ignore")
        self.assertIn("База знань", html)
        self.assertIn(self.post.title, html)

    def test_blog_index_invalidates_cached_empty_state_after_post_create(self):
        self.post.delete()

        empty_response = self.client.get("/blog/", secure=True)
        self.assertEqual(empty_response.status_code, 200)
        self.assertIn("База знань готується", empty_response.content.decode("utf-8", "ignore"))

        created_post = KnowledgePost.objects.create(
            title="Fresh DTF Knowledge Post",
            slug="fresh-dtf-knowledge-post",
            excerpt="Post created after cache warmup.",
            content_md="Fresh post body.",
            pub_date=date.today(),
            is_published=True,
        )

        response = self.client.get("/blog/", secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(created_post.title, response.content.decode("utf-8", "ignore"))

    def test_blog_post_renders_article_and_schema(self):
        response = self.client.get(f"/blog/{self.post.slug}/", secure=True)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8", "ignore")
        self.assertIn(self.post.title, html)
        self.assertIn('"@type": "Article"', html)
        self.assertIn('data-reading-progress-bar', html)

    def test_blog_overlay_mode_returns_partial(self):
        response = self.client.get(f"/blog/{self.post.slug}/?overlay=1", secure=True)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8", "ignore")
        self.assertIn("knowledge-overlay-article", html)
        self.assertNotIn("<html", html.lower())

    def test_sitemap_contains_blog_routes(self):
        response = self.client.get("/sitemap.xml", secure=True)
        self.assertEqual(response.status_code, 200)
        xml_root = ET.fromstring(response.content)
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        locs = [node.text for node in xml_root.findall("sm:url/sm:loc", ns) if node.text]
        self.assertIn("https://dtf.twocomms.shop/blog/", locs)
        self.assertIn(f"https://dtf.twocomms.shop/blog/{self.post.slug}/", locs)


class DtfAuthSurfaceTests(TestCase):
    def setUp(self):
        self.client = Client(HTTP_HOST="dtf.twocomms.shop")

    def test_accounts_ajax_routes_are_available_on_dtf_subdomain(self):
        login_resp = self.client.get("/accounts/ajax/login/", secure=True)
        register_resp = self.client.get("/accounts/ajax/register/", secure=True)
        self.assertEqual(login_resp.status_code, 405)
        self.assertEqual(register_resp.status_code, 405)

    def test_guest_profile_menu_contains_login_controls(self):
        response = self.client.get("/", secure=True)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8", "ignore")
        self.assertIn('data-profile-menu', html)
        self.assertIn('/accounts/ajax/login/', html)
        self.assertIn('/accounts/ajax/register/', html)
        self.assertIn('/oauth/login/google-oauth2/', html)
        self.assertIn('>Увійти через Google<', html)
        self.assertIn('>Повна форма входу<', html)

    def test_google_oauth_entrypoint_is_available(self):
        response = self.client.get("/oauth/login/google-oauth2/?next=%2F", secure=True)
        self.assertIn(response.status_code, {301, 302})

    def test_manager_profile_menu_contains_management_link(self):
        user = User.objects.create_user(username="manager_user", password="secure-pass-123")
        profile = user.userprofile
        profile.is_manager = True
        profile.save(update_fields=["is_manager"])
        self.client.force_login(user)

        response = self.client.get("/", secure=True)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8", "ignore")
        self.assertIn('https://management.twocomms.shop/', html)
        self.assertIn('/auth/logout/', html)

    def test_logout_endpoint_clears_session(self):
        user = User.objects.create_user(username="dtf_logout_user", password="secure-pass-123")
        self.client.force_login(user)
        response = self.client.post("/auth/logout/", secure=True, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)


class DtfPart4FeaturesTests(TestCase):
    PNG_1X1 = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/a7wAAAAASUVORK5CYII=")

    def setUp(self):
        self.client = Client(HTTP_HOST="dtf.twocomms.shop")

    def test_part4_public_routes_available(self):
        for path in ("/sample/", "/about/", "/products/", "/constructor/"):
            with self.subTest(path=path):
                response = self.client.get(path, secure=True)
                self.assertEqual(response.status_code, 200)

    def test_sample_form_creates_lead(self):
        response = self.client.post(
            "/sample/",
            {
                "sample_size": "a4",
                "is_brand_volume": "on",
                "name": "Sample Lead",
                "phone": "+380501112255",
                "contact_channel": "telegram",
                "contact_handle": "@sample",
                "city": "Kyiv",
                "np_branch": "12",
                "niche": "Fashion",
                "monthly_volume": "30-50m",
                "comment": "Need sample",
                "consent": "on",
                "honeypot": "",
            },
            secure=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(DtfSampleLead.objects.count(), 1)
        self.assertTrue(DtfSampleLead.objects.first().sample_number.startswith("DTF"))

    def test_constructor_save_generates_session_preview(self):
        image_file = SimpleUploadedFile("design.png", self.PNG_1X1, content_type="image/png")
        response = self.client.post(
            "/constructor/app/",
            {
                "product_type": "tshirt",
                "product_color": "#151515",
                "quantity": "10",
                "size_breakdown": "M:5,L:5",
                "placement": "front",
                "design_file": image_file,
                "delivery_city": "Kyiv",
                "delivery_np_branch": "22",
                "comment": "MVP test",
                "risk_ack": "on",
            },
            secure=True,
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        session = DtfBuilderSession.objects.first()
        self.assertIsNotNone(session)
        self.assertEqual(session.status, BuilderStatus.DRAFT)
        self.assertTrue(bool(session.preflight_json))
        self.assertTrue(bool(getattr(session.preview_image, "name", "")))

    def test_constructor_submit_creates_consultation_lead(self):
        session = DtfBuilderSession.objects.create(
            product_type="tshirt",
            placement="front",
            preflight_json={"checks": [], "has_warn": False, "has_fail": False},
        )
        response = self.client.post(
            "/constructor/submit/",
            {
                "session_id": str(session.session_id),
                "name": "Builder Client",
                "phone": "+380501112266",
                "contact_channel": "telegram",
                "city": "Kyiv",
                "np_branch": "45",
                "risk_ack": "on",
            },
            secure=True,
            HTTP_X_REQUESTED_WITH="fetch",
        )
        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        self.assertEqual(session.status, BuilderStatus.SUBMITTED)
        self.assertIsNotNone(session.submitted_lead_id)

    def test_cabinet_routes_require_auth(self):
        response = self.client.get("/cabinet/", secure=True)
        self.assertEqual(response.status_code, 302)
        user = User.objects.create_user(username="cabinet_user", password="secure-pass-123")
        self.client.force_login(user)
        home = self.client.get("/cabinet/", secure=True)
        orders = self.client.get("/cabinet/orders/", secure=True)
        sessions = self.client.get("/cabinet/sessions/", secure=True)
        self.assertEqual(home.status_code, 200)
        self.assertEqual(orders.status_code, 200)
        self.assertEqual(sessions.status_code, 200)


class DtfPart5Part6Tests(TestCase):
    def setUp(self):
        self.client = Client(HTTP_HOST="dtf.twocomms.shop")

    @override_settings(DTF_EFFECTS_LAB_ENABLED=True)
    def test_effects_lab_route_available(self):
        response = self.client.get("/effects-lab/", secure=True)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8", "ignore")
        self.assertIn("Effects Lab", html)
        self.assertIn('name="robots" content="noindex,nofollow"', html)

    def test_quote_api_json_response(self):
        response = self.client.get(
            "/api/quote/",
            {
                "length_m": "12",
                "width_cm": "60",
                "urgency": "standard",
                "context": "estimate",
            },
            secure=True,
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("ok"))
        self.assertIn("quote_id", data)
        self.assertTrue(DtfQuote.objects.filter(id=data["quote_id"]).exists())

    def test_quote_api_htmx_partial(self):
        response = self.client.get(
            "/api/quote/",
            {"length_m": "4", "context": "estimate"},
            secure=True,
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8", "ignore")
        self.assertIn("грн", html)

    def test_order_submit_creates_lifecycle_event(self):
        pdf_file = SimpleUploadedFile(
            "ready-layout.pdf",
            b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF",
            content_type="application/pdf",
        )
        response = self.client.post(
            "/order/",
            data={
                "tab": "ready",
                "name": "Lifecycle User",
                "phone": "+380501112299",
                "contact_channel": "telegram",
                "contact_handle": "@life",
                "city": "Kyiv",
                "np_branch": "1",
                "gang_file": pdf_file,
                "length_m": "2",
                "copies": "1",
                "comment": "Lifecycle test",
            },
            secure=True,
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        order = DtfOrder.objects.order_by("-id").first()
        self.assertIsNotNone(order)
        self.assertIn(order.lifecycle_status, {DtfLifecycleStatus.NEW, DtfLifecycleStatus.NEEDS_REVIEW})
        self.assertTrue(DtfStatusEvent.objects.filter(order=order).exists())

    def test_status_share_requires_phone(self):
        order = DtfOrder.objects.create(
            name="Client",
            phone="+380501112244",
            city="Kyiv",
            np_branch="1",
        )
        response = self.client.get(f"/status/{order.order_number}/", secure=True)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8", "ignore")
        self.assertIn("Не вдалося знайти замовлення", html)


class DtfAdminAndCabinetV2Tests(TestCase):
    def setUp(self):
        self.client = Client(HTTP_HOST="dtf.twocomms.shop")

    def test_knowledge_post_slug_transliteration(self):
        post = KnowledgePost.objects.create(
            title="Тестова стаття про худі",
            slug="",
            excerpt="Короткий опис",
            content_md="Тест контент",
            is_published=True,
            pub_date=date.today(),
        )
        self.assertTrue(post.slug.startswith("testova-stattya-pro-khudi"))

    def test_admin_panel_access_for_manager(self):
        user = User.objects.create_user(username="dtf_manager", password="secure-pass-123")
        self.client.force_login(user)
        denied = self.client.get("/admin-panel/", secure=True)
        self.assertEqual(denied.status_code, 302)

        profile = user.userprofile
        profile.is_manager = True
        profile.phone = "+380501112233"
        profile.save(update_fields=["is_manager", "phone"])

        allowed = self.client.get("/admin-panel/", secure=True)
        self.assertEqual(allowed.status_code, 200)
        html = allowed.content.decode("utf-8", "ignore")
        self.assertIn("DTF Control Center", html)

    def test_admin_slug_preview_endpoint(self):
        user = User.objects.create_user(username="dtf_slug_admin", password="secure-pass-123", is_staff=True)
        self.client.force_login(user)
        response = self.client.get("/admin-panel/blog/slug-preview/?value=Футболка Київ", secure=True)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload.get("ok"))
        self.assertIn("futbolka-kyyiv", payload.get("slug", ""))

    def test_cabinet_orders_v2_shows_payment_placeholder(self):
        user = User.objects.create_user(username="cabinet_v2", password="secure-pass-123")
        profile = user.userprofile
        profile.phone = "+380501110099"
        profile.save(update_fields=["phone"])
        DtfOrder.objects.create(
            name="Cabinet V2",
            phone="+380501110099",
            city="Kyiv",
            np_branch="1",
            payment_status="awaiting_payment",
        )
        self.client.force_login(user)
        response = self.client.get("/cabinet/orders/", secure=True)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8", "ignore")
        self.assertIn("Оплатити (скоро)", html)

    def test_admin_blog_image_upload_endpoint(self):
        user = User.objects.create_user(username="dtf_blog_media_admin", password="secure-pass-123", is_staff=True)
        self.client.force_login(user)
        png_payload = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/a7wAAAAASUVORK5CYII="
        )
        image = SimpleUploadedFile("editor.png", png_payload, content_type="image/png")
        response = self.client.post(
            "/admin-panel/blog/upload-image/",
            {"file": image},
            secure=True,
            HTTP_X_REQUESTED_WITH="fetch",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload.get("ok"))
        self.assertTrue(payload.get("url", "").startswith("/media/"))
        self.assertTrue(DtfUpload.objects.filter(source="blog_editor").exists())

    def test_admin_promocode_create_endpoint(self):
        if PromoCode is None:
            self.skipTest("storefront.PromoCode is unavailable")
        user = User.objects.create_user(username="dtf_promocode_admin", password="secure-pass-123", is_staff=True)
        self.client.force_login(user)
        response = self.client.post(
            "/admin-panel/promocodes/create/",
            {
                "code": "DTFTEST26",
                "promo_type": "regular",
                "discount_type": "percentage",
                "discount_value": "10.00",
                "description": "DTF test promo",
                "max_uses": "50",
                "one_time_per_user": "1",
                "min_order_amount": "1000.00",
                "is_active": "1",
            },
            secure=True,
            HTTP_X_REQUESTED_WITH="fetch",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload.get("ok"))
        self.assertTrue(PromoCode.objects.filter(code="DTFTEST26").exists())
