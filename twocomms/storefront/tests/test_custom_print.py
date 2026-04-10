import tempfile
import json
from pathlib import Path
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.contrib.auth.models import User

from storefront.models import Category


PNG_PIXEL = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc`\x00\x00"
    b"\x00\x02\x00\x01\xe2!\xbc3\x00\x00\x00\x00IEND\xaeB`\x82"
)


@override_settings(COMPRESS_ENABLED=False, COMPRESS_OFFLINE=False)
class CustomPrintPageTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._temp_media = tempfile.TemporaryDirectory()

    @classmethod
    def tearDownClass(cls):
        cls._temp_media.cleanup()
        super().tearDownClass()

    def setUp(self):
        self.client = Client(
            HTTP_HOST="twocomms.shop",
            SERVER_PORT="443",
            **{"wsgi.url_scheme": "https"},
        )
        for index, (name, slug) in enumerate(
            (
                ("Футболки", "tshirts"),
                ("Худі", "hoodie"),
                ("Лонгсліви", "long-sleeve"),
            ),
            start=1,
        ):
            Category.objects.create(
                name=name,
                slug=slug,
                is_active=True,
                order=index,
            )

    def _png_file(self, name: str = "design.png") -> SimpleUploadedFile:
        return SimpleUploadedFile(name, PNG_PIXEL, content_type="image/png")

    def _get(self, url, **kwargs):
        return self.client.get(url, secure=True, **kwargs)

    def _post(self, url, data, **kwargs):
        return self.client.post(url, data, secure=True, **kwargs)

    def test_custom_print_page_renders_adaptive_configurator(self):
        response = self._get(reverse("custom_print"), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Для себе")
        self.assertContains(response, "Для тиражу, брендування та мерчу")
        self.assertContains(response, "Оптова партія")
        self.assertContains(response, "Брендування / мерч")
        self.assertContains(response, "Свій одяг")
        self.assertContains(response, "1–4 шт — без знижки")
        self.assertContains(response, "1 стандартне нанесення включено")
        self.assertContains(response, "Доставка Новою Поштою")
        self.assertContains(response, "Надіслати менеджеру")
        self.assertContains(response, "Точний прорахунок після макета там, де це потрібно")
        self.assertContains(response, "від 700 грн")
        self.assertNotContains(response, "Custom Print Studio")
        self.assertNotContains(response, "/admin/storefront/customprintlead/")

    def test_home_page_contains_inline_custom_print_tile_inside_categories_grid(self):
        response = self._get(reverse("home"), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "categories-top-grid")
        self.assertContains(response, "categories-top-grid--exact")
        self.assertContains(response, "categories-cta-wrap")
        self.assertContains(response, "Замовити кастомний одяг")
        self.assertContains(response, "Перейти до заявки")
        self.assertContains(response, "category-card-custom-panel")
        self.assertContains(response, reverse("custom_print"))
        self.assertNotContains(response, "custom-print-home-cta")

    def test_home_page_uses_custom_survey_and_pagination_shells(self):
        from storefront.models import Product

        category = Category.objects.get(slug="tshirts")
        for index in range(1, 10):
            Product.objects.create(
                title=f"Тестовий товар {index}",
                slug=f"test-product-{index}",
                category=category,
                price=1000 + index,
                status="published",
            )

        response = self._get(reverse("home"), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "survey-reward-panel")
        self.assertContains(response, "Промокод на 200 грн")
        self.assertContains(response, "pagination-showcase")
        self.assertContains(response, "pagination-rail")
        self.assertNotContains(response, "page-selector-shell")
        self.assertNotContains(response, "Сторінка")

    @override_settings(MEDIA_ROOT=Path(tempfile.gettempdir()) / "twocomms-custom-print-tests")
    @patch("storefront.views.static_pages.notify_new_custom_print_lead")
    def test_custom_print_ready_submission_creates_lead_and_attachment(self, notify_mock):
        from storefront.models import CustomPrintLead, CustomPrintLeadAttachment

        payload = {
            "service_kind": "ready",
            "product_type": "tshirt",
            "placements": ["front"],
            "placement_specs_json": json.dumps(
                [
                    {
                        "zone": "front",
                        "label": "На грудях / спереду",
                        "variant": "standard",
                        "is_free": True,
                        "format": "standard",
                        "size": "standard",
                        "file_index": 0,
                    }
                ]
            ),
            "pricing_snapshot_json": json.dumps(
                {
                    "product_label": "Футболка",
                    "base_price": 700,
                    "design_price": 0,
                    "discount_percent": 0,
                    "discount_amount": 0,
                    "final_total": 700,
                    "estimate_required": False,
                }
            ),
            "quantity": "2",
            "size_mode": "mixed",
            "sizes_note": "M x1, L x1",
            "client_kind": "personal",
            "name": "Олена",
            "contact_channel": "telegram",
            "contact_value": "@olena_print",
            "brief": "",
            "files": self._png_file(),
        }

        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            response = self._post(
                reverse("custom_print_lead"),
                payload,
                HTTP_X_REQUESTED_WITH="fetch",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(callbacks), 1)
        self.assertJSONEqual(
            response.content,
            {
                "ok": True,
                "lead_number": CustomPrintLead.objects.get().lead_number,
                "message": "Дякуємо! Менеджер зв’яжеться з вами найближчим часом.",
            },
        )
        lead = CustomPrintLead.objects.get()
        self.assertEqual(lead.service_kind, "ready")
        self.assertEqual(lead.product_type, "tshirt")
        self.assertEqual(lead.placements, ["front"])
        self.assertEqual(lead.contact_channel, "telegram")
        self.assertEqual(lead.contact_value, "@olena_print")
        self.assertEqual(lead.source, "main_custom_print")
        self.assertEqual(lead.pricing_snapshot_json["base_price"], 700)
        self.assertEqual(lead.placement_specs_json[0]["zone"], "front")
        attachment = CustomPrintLeadAttachment.objects.get(lead=lead)
        self.assertEqual(attachment.placement_zone, "front")
        self.assertEqual(attachment.attachment_role, "design")
        self.assertEqual(attachment.sort_order, 0)
        notify_mock.assert_called_once_with(lead)

    @override_settings(MEDIA_ROOT=Path(tempfile.gettempdir()) / "twocomms-custom-print-tests")
    @patch("storefront.views.static_pages.notify_new_custom_print_lead")
    def test_custom_print_adjust_submission_creates_lead(self, notify_mock):
        from storefront.models import CustomPrintLead

        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            response = self._post(
                reverse("custom_print_lead"),
                {
                    "service_kind": "adjust",
                    "product_type": "hoodie",
                    "placements": ["back", "sleeve"],
                    "placement_specs_json": json.dumps(
                        [
                            {
                                "zone": "back",
                                "label": "На спині",
                                "variant": "standard",
                                "is_free": True,
                                "format": "standard",
                                "size": "standard",
                                "file_index": 0,
                            },
                            {
                                "zone": "sleeve",
                                "label": "На рукаві",
                                "variant": "extra",
                                "is_free": False,
                                "format": "small",
                                "size": "S",
                            },
                        ]
                    ),
                    "pricing_snapshot_json": json.dumps(
                        {
                            "product_label": "Худі",
                            "base_price": 1600,
                            "design_price": 300,
                            "discount_percent": 10,
                            "discount_amount": 160,
                            "final_total": None,
                            "estimate_required": True,
                            "estimate_reason": "multi_zone",
                        }
                    ),
                    "quantity": "5",
                    "size_mode": "single",
                    "sizes_note": "L x5",
                    "client_kind": "brand",
                    "business_kind": "bulk",
                    "brand_name": "Void Unit",
                    "name": "Микита",
                    "contact_channel": "whatsapp",
                    "contact_value": "+380501112233",
                    "brief": "Потрібно прибрати фон і підчистити контур.",
                    "files": self._png_file("source.png"),
                },
                HTTP_X_REQUESTED_WITH="fetch",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(callbacks), 1)
        lead = CustomPrintLead.objects.get()
        self.assertEqual(lead.service_kind, "adjust")
        self.assertEqual(lead.client_kind, "brand")
        self.assertEqual(lead.business_kind, "bulk")
        self.assertEqual(lead.brand_name, "Void Unit")
        self.assertEqual(lead.placements, ["back", "sleeve"])
        self.assertEqual(lead.contact_channel, "whatsapp")
        self.assertTrue(lead.pricing_snapshot_json["estimate_required"])
        notify_mock.assert_called_once_with(lead)

    @patch("storefront.views.static_pages.notify_new_custom_print_lead")
    def test_custom_print_design_submission_allows_no_file(self, notify_mock):
        from storefront.models import CustomPrintLead, CustomPrintLeadAttachment

        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            response = self._post(
                reverse("custom_print_lead"),
                {
                    "service_kind": "design",
                    "product_type": "customer_garment",
                    "placements": ["custom"],
                    "placement_specs_json": json.dumps(
                        [
                            {
                                "zone": "custom",
                                "label": "Інше",
                                "variant": "estimate",
                                "is_free": False,
                                "format": "custom",
                                "size": "manager_review",
                            }
                        ]
                    ),
                    "pricing_snapshot_json": json.dumps(
                        {
                            "product_label": "Свій одяг",
                            "base_price": None,
                            "design_price": 500,
                            "discount_percent": 0,
                            "discount_amount": 0,
                            "final_total": None,
                            "estimate_required": True,
                            "estimate_reason": "customer_garment",
                        }
                    ),
                    "placement_note": "Хочу вертикальний принт по боковому шву та рукаву.",
                    "quantity": "3",
                    "size_mode": "manager",
                    "sizes_note": "S x1, M x2",
                    "client_kind": "personal",
                    "garment_note": "Моє темно-сіре худі без кишені, щільна тканина.",
                    "name": "Ігор",
                    "contact_channel": "phone",
                    "contact_value": "+380671234567",
                    "brief": "Потрібен мінімалістичний шрифт і техно-естетика.",
                },
                HTTP_X_REQUESTED_WITH="fetch",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(callbacks), 1)
        lead = CustomPrintLead.objects.get()
        self.assertEqual(lead.service_kind, "design")
        self.assertEqual(lead.product_type, "customer_garment")
        self.assertEqual(lead.placements, ["custom"])
        self.assertEqual(lead.placement_note, "Хочу вертикальний принт по боковому шву та рукаву.")
        self.assertEqual(lead.garment_note, "Моє темно-сіре худі без кишені, щільна тканина.")
        self.assertTrue(lead.pricing_snapshot_json["estimate_required"])
        self.assertEqual(CustomPrintLeadAttachment.objects.filter(lead=lead).count(), 0)
        notify_mock.assert_called_once_with(lead)

    def test_custom_print_adjust_requires_brief_and_file(self):
        response = self._post(
            reverse("custom_print_lead"),
            {
                "service_kind": "adjust",
                "product_type": "hoodie",
                "placements": ["front"],
                "quantity": "2",
                "sizes_note": "M x2",
                "name": "Тест",
                "contact_channel": "telegram",
                "contact_value": "@test",
            },
            HTTP_X_REQUESTED_WITH="fetch",
        )

        self.assertEqual(response.status_code, 400)
        self.assertJSONEqual(
            response.content,
            {
                "ok": False,
                "errors": {
                    "brief": ["Опишіть, що саме потрібно змінити у файлі."],
                    "files": ["Додайте файл, який потрібно підготувати."],
                },
            },
        )

    def test_custom_print_design_requires_brief(self):
        response = self._post(
            reverse("custom_print_lead"),
            {
                "service_kind": "design",
                "product_type": "tshirt",
                "placements": ["back"],
                "quantity": "1",
                "sizes_note": "L x1",
                "name": "Тест",
                "contact_channel": "telegram",
                "contact_value": "@test",
            },
            HTTP_X_REQUESTED_WITH="fetch",
        )

        self.assertEqual(response.status_code, 400)
        self.assertJSONEqual(
            response.content,
            {
                "ok": False,
                "errors": {
                    "brief": ["Опишіть ідею, стиль або референси для дизайну."],
                },
            },
        )

    def test_custom_print_custom_placement_requires_note(self):
        response = self._post(
            reverse("custom_print_lead"),
            {
                "service_kind": "design",
                "product_type": "longsleeve",
                "placements": ["custom"],
                "placement_specs_json": json.dumps([{"zone": "custom"}]),
                "quantity": "1",
                "sizes_note": "M x1",
                "name": "Тест",
                "contact_channel": "telegram",
                "contact_value": "@test",
                "brief": "Зробіть щось сміливе.",
            },
            HTTP_X_REQUESTED_WITH="fetch",
        )

        self.assertEqual(response.status_code, 400)
        self.assertJSONEqual(
            response.content,
            {
                "ok": False,
                "errors": {
                    "placement_note": ["Опишіть нестандартне розміщення принта."],
                },
            },
        )

    def test_custom_print_phone_channel_validates_contact_value(self):
        response = self._post(
            reverse("custom_print_lead"),
            {
                "service_kind": "design",
                "product_type": "tshirt",
                "placements": ["front"],
                "placement_specs_json": json.dumps([{"zone": "front"}]),
                "quantity": "1",
                "sizes_note": "M x1",
                "name": "Тест",
                "contact_channel": "phone",
                "contact_value": "abc",
                "brief": "Потрібен дизайн.",
            },
            HTTP_X_REQUESTED_WITH="fetch",
        )

        self.assertEqual(response.status_code, 400)
        self.assertJSONEqual(
            response.content,
            {
                "ok": False,
                "errors": {
                    "contact_value": ["Введіть коректний номер телефону."],
                },
            },
        )


@override_settings(COMPRESS_ENABLED=False, COMPRESS_OFFLINE=False)
class CustomPrintAdminAndNotificationTests(TestCase):
    def setUp(self):
        self.client = Client(
            HTTP_HOST="twocomms.shop",
            SERVER_PORT="443",
            **{"wsgi.url_scheme": "https"},
        )
        self.staff_user = User.objects.create_user(
            username="staff",
            password="secret123",
            is_staff=True,
        )

    def _make_lead(self, **overrides):
        from storefront.models import CustomPrintLead

        payload = {
            "service_kind": "adjust",
            "product_type": "hoodie",
            "placements": ["back", "sleeve"],
            "placement_note": "",
            "placement_specs_json": [
                {
                    "zone": "back",
                    "label": "На спині",
                    "variant": "standard",
                    "is_free": True,
                    "format": "standard",
                    "size": "standard",
                },
                {
                    "zone": "sleeve",
                    "label": "На рукаві",
                    "variant": "extra",
                    "is_free": False,
                    "format": "small",
                    "size": "S",
                },
            ],
            "quantity": 12,
            "size_mode": "mixed",
            "sizes_note": "M x6, L x6",
            "client_kind": "brand",
            "business_kind": "branding",
            "brand_name": "Void Unit",
            "garment_note": "",
            "name": "Микита",
            "contact_channel": "telegram",
            "contact_value": "@void_unit",
            "brief": "Тестовий lead",
            "pricing_snapshot_json": {
                "product_label": "Худі",
                "base_price": 1600,
                "design_price": 300,
                "discount_percent": 5,
                "discount_amount": 80,
                "final_total": None,
                "estimate_required": True,
                "estimate_reason": "multi_zone",
            },
            "source": "main_custom_print",
        }
        payload.update(overrides)
        return CustomPrintLead.objects.create(**payload)

    def test_staff_admin_panel_renders_custom_print_orders_section(self):
        self.client.force_login(self.staff_user)
        lead = self._make_lead()

        response = self.client.get(
            reverse("admin_panel"),
            {"section": "custom_print_orders", "lead": lead.pk},
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Кастомні замовлення")
        self.assertContains(response, lead.lead_number)
        self.assertContains(response, "В роботі", count=0)
        self.assertContains(response, "data-custom-print-lead-detail")

    def test_staff_can_update_custom_print_lead_status_from_custom_admin(self):
        lead = self._make_lead()
        self.client.force_login(self.staff_user)

        response = self.client.post(
            reverse("admin_custom_print_lead_status", args=[lead.pk]),
            data=json.dumps({"status": "in_progress"}),
            content_type="application/json",
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        lead.refresh_from_db()
        self.assertEqual(lead.status, "in_progress")
        self.assertJSONEqual(response.content, {"success": True, "status": "in_progress"})

    def test_custom_print_notification_uses_custom_admin_deeplink(self):
        from storefront.custom_print_notifications import _build_admin_panel_link, _build_message

        lead = self._make_lead()
        link = _build_admin_panel_link(lead)
        message = _build_message(lead)

        self.assertEqual(
            link,
            f"https://twocomms.shop/admin-panel/?section=custom_print_orders&lead={lead.pk}",
        )
        self.assertIn(link, message)
        self.assertNotIn("/admin/storefront/customprintlead/", message)
