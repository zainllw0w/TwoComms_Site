from django.test import Client, TestCase, override_settings
from django.urls import reverse

from storefront.models import Category


@override_settings(COMPRESS_ENABLED=False, COMPRESS_OFFLINE=False)
class CustomPrintPageTests(TestCase):
    def setUp(self):
        self.client = Client()
        Category.objects.create(
            name="Футболки",
            slug="tshirts",
            is_active=True,
        )

    def test_custom_print_page_renders_key_sections(self):
        response = self.client.get(reverse("custom_print"), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Футболка")
        self.assertContains(response, "Худі")
        self.assertContains(response, "Лонгслів")
        self.assertContains(response, "300 грн")
        self.assertContains(response, "500 грн")
        self.assertContains(response, "https://dtf.twocomms.shop/constructor/")
        self.assertContains(response, "https://t.me/twocomms")
        self.assertContains(response, "https://dtf.twocomms.shop/")

    def test_home_page_contains_custom_print_cta(self):
        response = self.client.get(reverse("home"), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Замовити свій принт")
        self.assertContains(response, reverse("custom_print"))
