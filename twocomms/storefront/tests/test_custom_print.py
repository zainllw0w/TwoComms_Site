import tempfile
from pathlib import Path
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

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

    def test_custom_print_page_renders_progressive_form(self):
        response = self._get(reverse("custom_print"), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Швидка заявка менеджеру")
        self.assertContains(response, "Що вам потрібно?")
        self.assertContains(response, "На чому друкуємо?")
        self.assertContains(response, "Де буде принт?")
        self.assertContains(response, "Як з вами зв’язатися?")
        self.assertContains(response, "Надіслати менеджеру")
        self.assertContains(response, "Що буде далі після заявки")
        self.assertContains(response, "Конструктор скоро буде")
        self.assertContains(response, "Орієнтир: готова футболка з вашим принтом — від 700 грн")
        self.assertNotContains(response, "Custom Print Studio")
        self.assertNotContains(response, "Front / Back")

    def test_home_page_contains_inline_custom_print_tile_inside_categories_grid(self):
        response = self._get(reverse("home"), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "categories-grid-balanced")
        self.assertContains(response, "Замовити кастомний одяг")
        self.assertContains(response, "Перейти до заявки")
        self.assertContains(response, "category-card-custom-panel")
        self.assertContains(response, reverse("custom_print"))
        self.assertNotContains(response, "custom-print-home-cta")

    @override_settings(MEDIA_ROOT=Path(tempfile.gettempdir()) / "twocomms-custom-print-tests")
    @patch("storefront.views.static_pages.notify_new_custom_print_lead")
    def test_custom_print_ready_submission_creates_lead_and_attachment(self, notify_mock):
        from storefront.models import CustomPrintLead, CustomPrintLeadAttachment

        payload = {
            "service_kind": "ready",
            "product_type": "tshirt",
            "placements": ["front"],
            "quantity": "2",
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
        self.assertEqual(CustomPrintLeadAttachment.objects.filter(lead=lead).count(), 1)
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
                    "quantity": "5",
                    "sizes_note": "L x5",
                    "client_kind": "brand",
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
        self.assertEqual(lead.brand_name, "Void Unit")
        self.assertEqual(lead.placements, ["back", "sleeve"])
        self.assertEqual(lead.contact_channel, "whatsapp")
        notify_mock.assert_called_once_with(lead)

    @patch("storefront.views.static_pages.notify_new_custom_print_lead")
    def test_custom_print_design_submission_allows_no_file(self, notify_mock):
        from storefront.models import CustomPrintLead, CustomPrintLeadAttachment

        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            response = self._post(
                reverse("custom_print_lead"),
                {
                    "service_kind": "design",
                    "product_type": "longsleeve",
                    "placements": ["custom"],
                    "placement_note": "Хочу вертикальний принт по боковому шву та рукаву.",
                    "quantity": "3",
                    "sizes_note": "S x1, M x2",
                    "client_kind": "personal",
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
        self.assertEqual(lead.product_type, "longsleeve")
        self.assertEqual(lead.placements, ["custom"])
        self.assertEqual(lead.placement_note, "Хочу вертикальний принт по боковому шву та рукаву.")
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
