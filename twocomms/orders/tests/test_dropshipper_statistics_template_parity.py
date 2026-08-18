from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class DropshipperStatisticsTemplateParityTests(TestCase):
    """Keep the full statistics page and its Django 6.1 fragment in sync."""

    def setUp(self):
        user = get_user_model().objects.create_user(
            username="statistics-dropshipper",
            password="test-password",
        )
        self.client.force_login(user)
        self.url = reverse("orders:dropshipper_statistics")

    def test_full_page_and_partial_share_statistics_content(self):
        full_response = self.client.get(self.url)
        partial_response = self.client.get(self.url, {"partial": "1"})

        self.assertEqual(full_response.status_code, 200)
        self.assertEqual(partial_response.status_code, 200)

        markers = (
            "ds-container",
            "ds-statistics-hero",
            "Аналітика продажів",
            "Усього замовлень",
            "Виручка",
            "Чистий прибуток",
            "Середній чек",
            "Товарів доставлено",
            "Конверсія у доставку",
            "ds-statistics-body",
            "Динаміка по місяцях",
            "Топ-товари",
            "Поки немає даних",
            "Ще немає топів",
        )
        for marker in markers:
            with self.subTest(marker=marker):
                self.assertContains(full_response, marker)
                self.assertContains(partial_response, marker)

    def test_full_page_keeps_dashboard_shell_around_partial(self):
        full_response = self.client.get(self.url)
        partial_response = self.client.get(self.url, {"partial": "1"})

        self.assertContains(full_response, 'data-tab-panel="statistics"')
        self.assertContains(full_response, "dropshipper.js")
        self.assertContains(full_response, "ds-modal")
        self.assertNotContains(partial_response, 'data-tab-panel="statistics"')
        self.assertNotContains(partial_response, "dropshipper.js")
