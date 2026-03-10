import json
import tempfile
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import Client as DjangoClient
from django.test import TestCase, override_settings
from django.urls import reverse
from openpyxl import load_workbook

from management.shop_views import _invoice_summary_from_wholesale_invoice
from orders.models import WholesaleInvoice


@override_settings(ROOT_URLCONF="twocomms.urls_management")
class InvoiceItemNormalizationTests(TestCase):
    def test_normalize_invoice_items_recalculates_auto_and_manual_prices(self):
        from management.invoice_service import normalize_management_invoice_payload

        company_data = {
            "companyName": "ТОВ Тест",
            "contactPhone": "+380000000000",
            "deliveryAddress": "Київ, вул. Тестова, 1",
        }
        order_items = [
            {
                "product": {"id": "1", "type": "tshirt", "title": "Футболка 1"},
                "size": "M",
                "color": "Чорний",
                "quantity": 6,
                "pricing_mode": "auto",
                "extra_description": "з кашкорсе",
            },
            {
                "product": {"id": "2", "type": "tshirt", "title": "Футболка 2"},
                "size": "L",
                "color": "Білий",
                "quantity": 2,
                "pricing_mode": "manual",
                "manual_price": "610",
            },
            {
                "product": {"id": "3", "type": "hoodie", "title": "Худі 1 [фліс]"},
                "size": "XL",
                "color": "Чорний",
                "quantity": 8,
                "pricing_mode": "auto",
            },
        ]

        normalized = normalize_management_invoice_payload(
            company_data=company_data,
            order_items=order_items,
        )

        self.assertEqual(normalized["totals"]["total_tshirts"], 8)
        self.assertEqual(normalized["totals"]["total_hoodies"], 8)
        self.assertEqual(normalized["items"][0]["display_title"], "Футболка 1 [з кашкорсе]")
        self.assertEqual(normalized["items"][0]["base_unit_price"], Decimal("540.00"))
        self.assertEqual(normalized["items"][0]["unit_price"], Decimal("540.00"))
        self.assertEqual(normalized["items"][0]["line_total"], Decimal("3240.00"))
        self.assertEqual(normalized["items"][1]["pricing_mode"], "manual")
        self.assertEqual(normalized["items"][1]["base_unit_price"], Decimal("540.00"))
        self.assertEqual(normalized["items"][1]["unit_price"], Decimal("610.00"))
        self.assertEqual(normalized["items"][1]["line_total"], Decimal("1220.00"))
        self.assertEqual(normalized["items"][2]["base_unit_price"], Decimal("1300.00"))
        self.assertEqual(normalized["items"][2]["line_total"], Decimal("10400.00"))
        self.assertEqual(normalized["totals"]["total_amount"], Decimal("14860.00"))
        self.assertTrue(normalized["pricing"]["has_manual_prices"])
        self.assertEqual(normalized["pricing"]["policy"], "custom_manual")
        self.assertEqual(normalized["items"][0]["base_unit_price"], Decimal("540.00"))
        self.assertEqual(normalized["items"][2]["base_unit_price"], Decimal("1300.00"))

    def test_manual_price_disables_tier_discount_recalculation_for_auto_items(self):
        from management.invoice_service import normalize_management_invoice_payload

        company_data = {
            "companyName": "ТОВ Тест",
            "contactPhone": "+380000000000",
            "deliveryAddress": "Київ, вул. Тестова, 1",
        }
        order_items = [
            {
                "product": {"id": "1", "type": "tshirt", "title": "Футболка 1"},
                "size": "M",
                "color": "Чорний",
                "quantity": 20,
                "pricing_mode": "auto",
            },
            {
                "product": {"id": "2", "type": "tshirt", "title": "Футболка 2"},
                "size": "L",
                "color": "Білий",
                "quantity": 1,
                "pricing_mode": "manual",
                "manual_price": "610",
            },
        ]

        normalized = normalize_management_invoice_payload(
            company_data=company_data,
            order_items=order_items,
        )

        self.assertTrue(normalized["pricing"]["has_manual_prices"])
        self.assertFalse(normalized["pricing"]["discounts_enabled"])
        self.assertEqual(normalized["items"][0]["base_unit_price"], Decimal("540.00"))
        self.assertEqual(normalized["items"][0]["unit_price"], Decimal("540.00"))
        self.assertEqual(normalized["items"][0]["line_total"], Decimal("10800.00"))
        self.assertEqual(normalized["items"][1]["unit_price"], Decimal("610.00"))
        self.assertEqual(normalized["totals"]["total_amount"], Decimal("11410.00"))

    def test_normalize_invoice_items_expands_full_size_run_multiplier(self):
        from management.invoice_service import normalize_management_invoice_payload

        company_data = {
            "companyName": "ТОВ Тест",
            "contactPhone": "+380000000000",
            "deliveryAddress": "Київ, вул. Тестова, 1",
        }
        order_items = [
            {
                "product": {"id": "1", "type": "tshirt", "title": "Футболка 1"},
                "size": "all",
                "run_multiplier": 3,
                "quantity": 4,
                "pricing_mode": "auto",
            },
        ]

        normalized = normalize_management_invoice_payload(
            company_data=company_data,
            order_items=order_items,
        )

        self.assertEqual(normalized["totals"]["total_tshirts"], 12)
        self.assertEqual(normalized["items"][0]["size"], "Всі ростовки (S-XL) ×3")
        self.assertEqual(normalized["items"][0]["run_multiplier"], 3)
        self.assertEqual(normalized["items"][0]["quantity"], 12)
        self.assertEqual(normalized["items"][0]["base_unit_price"], Decimal("540.00"))
        self.assertEqual(normalized["items"][0]["line_total"], Decimal("6480.00"))


@override_settings(
    ROOT_URLCONF="twocomms.urls_management",
    ALLOWED_HOSTS=["testserver", "management.twocomms.shop", "localhost", "127.0.0.1"],
)
class ManagementInvoiceApiTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="manager", password="x", is_staff=True)
        self.client_http = DjangoClient()
        self.client_http.force_login(self.user)

    def test_invoices_page_renders_for_management_user(self):
        response = self.client_http.get(
            reverse("management_invoices"),
            HTTP_HOST="management.twocomms.shop",
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Сформувати накладну")
        self.assertContains(response, "Ручна ціна за 1 шт.")
        self.assertContains(response, "Множник ростовки")
        self.assertContains(response, "Включити 2XL у ростовку")
        self.assertContains(response, '<option value="2XL">2XL</option>', html=True)

    def test_generate_invoice_uses_normalized_rows_and_writes_excel(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with override_settings(MEDIA_ROOT=tmpdir):
                payload = {
                    "companyData": {
                        "companyName": "ТОВ Тест",
                        "companyNumber": "12345678",
                        "contactPhone": "+380000000000",
                        "deliveryAddress": "Київ, вул. Тестова, 1",
                        "storeLink": "https://example.com/store",
                    },
                    "orderItems": [
                        {
                            "product": {"id": "1", "type": "tshirt", "title": "Футболка 1"},
                            "size": "M",
                            "color": "Чорний",
                            "quantity": 6,
                            "pricing_mode": "auto",
                            "extra_description": "з кашкорсе",
                        },
                        {
                            "product": {"id": "2", "type": "tshirt", "title": "Футболка 2"},
                            "size": "L",
                            "color": "Білий",
                            "quantity": 2,
                            "pricing_mode": "manual",
                            "manual_price": "610",
                        },
                    ],
                }

                response = self.client_http.post(
                    reverse("management_invoices_generate_api"),
                    data=json.dumps(payload),
                    content_type="application/json",
                    HTTP_HOST="management.twocomms.shop",
                    secure=True,
                )

                self.assertEqual(response.status_code, 200)
                data = response.json()
                self.assertTrue(data["ok"])

                invoice = WholesaleInvoice.objects.get(id=data["invoice"]["id"])
                self.assertEqual(invoice.total_tshirts, 8)
                self.assertEqual(invoice.total_hoodies, 0)
                self.assertEqual(invoice.total_amount, Decimal("4460.00"))
                self.assertEqual(invoice.order_details["pricing"]["policy"], "custom_manual")
                self.assertFalse(invoice.order_details["pricing"]["discounts_enabled"])

                saved_items = invoice.order_details["order_items"]
                self.assertEqual(saved_items[0]["display_title"], "Футболка 1 [з кашкорсе]")
                self.assertEqual(saved_items[0]["unit_price"], "540.00")
                self.assertEqual(saved_items[1]["pricing_mode"], "manual")
                self.assertEqual(saved_items[1]["unit_price"], "610.00")

                workbook_path = Path(invoice.file_path)
                self.assertTrue(workbook_path.exists())

                wb = load_workbook(workbook_path)
                ws = wb.active

                self.assertEqual(ws.freeze_panes, "A10")
                self.assertEqual(ws["B10"].value, "Назва товару")
                self.assertEqual(ws["B11"].value, "Футболка 1 [з кашкорсе]")
                self.assertTrue(ws["B11"].alignment.wrapText)
                self.assertEqual(ws["F11"].value, 540)
                self.assertEqual(ws["G12"].value, 1220)
                self.assertIn("Ручна ціна", str(ws["A8"].value))
                self.assertIn("₴", ws["F11"].number_format)
                self.assertEqual(ws["B6"].hyperlink.target, "https://example.com/store")

    def test_generate_invoice_serializes_full_size_run_multiplier(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with override_settings(MEDIA_ROOT=tmpdir):
                payload = {
                    "companyData": {
                        "companyName": "ТОВ Тест",
                        "companyNumber": "12345678",
                        "contactPhone": "+380000000000",
                        "deliveryAddress": "Київ, вул. Тестова, 1",
                    },
                    "orderItems": [
                        {
                            "product": {"id": "1", "type": "tshirt", "title": "Футболка 1"},
                            "size": "all",
                            "runMultiplier": 2,
                            "include2xlInRun": True,
                            "quantity": 4,
                            "pricing_mode": "auto",
                        },
                    ],
                }

                response = self.client_http.post(
                    reverse("management_invoices_generate_api"),
                    data=json.dumps(payload),
                    content_type="application/json",
                    HTTP_HOST="management.twocomms.shop",
                    secure=True,
                )

                self.assertEqual(response.status_code, 200)
                data = response.json()
                self.assertTrue(data["ok"])

                invoice = WholesaleInvoice.objects.get(id=data["invoice"]["id"])
                self.assertEqual(invoice.total_tshirts, 10)

                saved_item = invoice.order_details["order_items"][0]
                self.assertEqual(saved_item["size"], "Всі ростовки (S-2XL) ×2")
                self.assertEqual(saved_item["run_multiplier"], 2)
                self.assertTrue(saved_item["include_2xl"])
                self.assertEqual(saved_item["quantity"], 10)

                wb = load_workbook(Path(invoice.file_path))
                ws = wb.active
                self.assertEqual(ws["C11"].value, "Всі ростовки (S-2XL) ×2")
                self.assertEqual(ws["E11"].value, 10)

    def test_generate_invoice_returns_validation_error_for_malformed_order_item(self):
        payload = {
            "companyData": {
                "companyName": "ТОВ Тест",
                "contactPhone": "+380000000000",
                "deliveryAddress": "Київ, вул. Тестова, 1",
            },
            "orderItems": ["broken-item"],
        }

        response = self.client_http.post(
            reverse("management_invoices_generate_api"),
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_HOST="management.twocomms.shop",
            secure=True,
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["ok"])


class InvoiceSummaryTests(TestCase):
    def test_shop_invoice_summary_prefers_normalized_fields(self):
        invoice = WholesaleInvoice(
            invoice_number="INV-1",
            company_name="ТОВ Тест",
            total_tshirts=8,
            total_hoodies=0,
            total_amount=Decimal("4460.00"),
            order_details={
                "company_data": {"companyName": "ТОВ Тест"},
                "order_items": [
                    {
                        "product": {"title": "Футболка 1", "type": "tshirt"},
                        "display_title": "Футболка 1 [з кашкорсе]",
                        "size": "M",
                        "color": "Чорний",
                        "quantity": 6,
                        "unit_price": "540.00",
                        "line_total": "3240.00",
                    }
                ],
            },
        )

        summary = _invoice_summary_from_wholesale_invoice(invoice)

        self.assertEqual(summary["items"][0]["title"], "Футболка 1 [з кашкорсе]")
        self.assertEqual(summary["items"][0]["price"], "540.00")
        self.assertEqual(summary["items"][0]["total"], "3240.00")
