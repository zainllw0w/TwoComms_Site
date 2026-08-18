"""Regression coverage for Django 6.1 querystring pagination links."""

from __future__ import annotations

import html
import re
from urllib.parse import parse_qs, urlsplit

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase, override_settings

from warehouse.models import MovementReason, StockMovement


User = get_user_model()


@override_settings(
    ROOT_URLCONF="twocomms.urls_storage",
    SECURE_SSL_REDIRECT=False,
    ALLOWED_HOSTS=["testserver", "storage.twocomms.shop"],
)
class WarehouseQuerystringPaginationTemplateTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(
            username="querystring-pagination-admin",
            email="querystring-pagination@example.invalid",
            password="test-password",
        )
        content_type = ContentType.objects.get_for_model(StockMovement)
        StockMovement.objects.bulk_create(
            [
                StockMovement(
                    content_type=content_type,
                    object_id=1,
                    delta=1,
                    quantity_after=index + 1,
                    reason=MovementReason.MANUAL_ADD,
                )
                for index in range(51)
            ]
        )

    def setUp(self):
        self.client.force_login(self.user)

    def _pagination_hrefs(self, response):
        body = html.unescape(response.content.decode("utf-8"))
        return re.findall(
            r'<a href="([^"]+)" class="btn btn--ghost flex-1">',
            body,
        )

    def _page_query(self, href):
        return parse_qs(urlsplit(href).query, keep_blank_values=True)

    def test_empty_query_builds_next_page_link(self):
        response = self.client.get("/history/", HTTP_HOST="storage.twocomms.shop")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._page_query(self._pagination_hrefs(response)[0]), {"page": ["2"]})

    def test_repeated_query_values_are_preserved(self):
        response = self.client.get(
            "/history/?tag=alpha&tag=beta&reason=manual_add&verified=no",
            HTTP_HOST="storage.twocomms.shop",
        )

        self.assertEqual(response.status_code, 200)
        query = self._page_query(self._pagination_hrefs(response)[0])
        self.assertEqual(query["tag"], ["alpha", "beta"])
        self.assertEqual(query["reason"], ["manual_add"])
        self.assertEqual(query["verified"], ["no"])
        self.assertEqual(query["page"], ["2"])

    def test_page_value_is_replaced_without_duplicate_page_parameter(self):
        response = self.client.get(
            "/history/?page=1&reason=manual_add",
            HTTP_HOST="storage.twocomms.shop",
        )

        self.assertEqual(response.status_code, 200)
        query = self._page_query(self._pagination_hrefs(response)[0])
        self.assertEqual(query["page"], ["2"])
        self.assertEqual(query["reason"], ["manual_add"])

    def test_values_are_url_encoded_and_html_safe(self):
        response = self.client.get(
            "/history/?q=%3Cscript%3Ealert%281%29%3C%2Fscript%3E",
            HTTP_HOST="storage.twocomms.shop",
        )

        self.assertEqual(response.status_code, 200)
        href = self._pagination_hrefs(response)[0]
        self.assertIn("q=%3Cscript%3Ealert%281%29%3C%2Fscript%3E", href)
        self.assertNotIn("<script>", href)
        self.assertEqual(self._page_query(href)["page"], ["2"])
