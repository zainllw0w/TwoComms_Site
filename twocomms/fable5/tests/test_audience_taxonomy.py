import json
from io import StringIO
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from storefront.models import Category, Product

from fable5.models import AudienceTag, ProductAudience
from fable5.services_audience import (
    get_product_audience_codes,
    set_product_audience_codes,
    validate_published_apparel_audience,
)


class AudienceTaxonomyTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Футболки", slug="tshirts")
        self.product = Product.objects.create(
            title="Audience test tee",
            slug="audience-test-tee",
            category=self.category,
            price=1090,
            status="published",
        )
        self.tags = {
            code: AudienceTag.objects.create(
                code=code,
                label_uk=label,
                label_ru=label,
                label_en=code.title(),
                order=order,
            )
            for order, (code, label) in enumerate(
                (("unisex", "Унісекс"), ("women", "Жіночі"), ("men", "Чоловічі"))
            )
        }
        self.staff = get_user_model().objects.create_user(
            username="audience-editor",
            password="test-password",
            is_staff=True,
        )
        self.client.force_login(self.staff)

    def test_product_supports_multiple_audience_tags_with_unique_assignments(self):
        set_product_audience_codes(self.product, ["unisex", "women"])

        self.assertEqual(get_product_audience_codes(self.product), ["unisex", "women"])
        with self.assertRaises(IntegrityError), transaction.atomic():
            ProductAudience.objects.create(product=self.product, tag=self.tags["unisex"])

    def test_unknown_or_inactive_audience_codes_are_rejected(self):
        self.tags["women"].is_active = False
        self.tags["women"].save(update_fields=["is_active"])

        with self.assertRaises(ValueError):
            set_product_audience_codes(self.product, ["women"])
        with self.assertRaises(ValueError):
            set_product_audience_codes(self.product, ["not-audience"])

    def test_published_apparel_requires_at_least_one_audience_tag(self):
        with self.assertRaises(ValueError):
            validate_published_apparel_audience(self.product)

        set_product_audience_codes(self.product, ["unisex"])
        self.assertIsNone(validate_published_apparel_audience(self.product))

    def test_editor_bootstrap_exposes_tags_and_current_multi_selection(self):
        set_product_audience_codes(self.product, ["unisex", "women"])

        response = self.client.get(
            reverse("fable5_product_edit", args=[self.product.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["bootstrap"]["product"]["audience_codes"],
            ["unisex", "women"],
        )
        self.assertEqual(
            [
                item["code"]
                for item in response.context["bootstrap"]["dictionaries"]["audiences"]
            ],
            ["unisex", "women", "men"],
        )
        self.assertContains(response, 'id="f-audience-options"', html=False)
        self.assertContains(response, 'id="f-audience-summary"', html=False)

    def test_editor_save_persists_multiple_audience_codes(self):
        response = self.client.post(
            reverse("fable5_api_product_save"),
            data={
                "payload": json.dumps(
                    {
                        "id": self.product.pk,
                        "title": self.product.title,
                        "category_id": self.category.pk,
                        "price": self.product.price,
                        "status": "published",
                        "audience_codes": ["women", "unisex"],
                    }
                )
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["product"]["audience_codes"], ["unisex", "women"])
        self.assertEqual(get_product_audience_codes(self.product), ["unisex", "women"])

    def test_editor_rejects_published_tshirt_without_audience(self):
        response = self.client.post(
            reverse("fable5_api_product_save"),
            data={
                "payload": json.dumps(
                    {
                        "id": self.product.pk,
                        "title": self.product.title,
                        "category_id": self.category.pk,
                        "price": self.product.price,
                        "status": "published",
                        "audience_codes": [],
                    }
                )
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("аудитор", response.json()["error"].lower())

    def test_editor_cannot_bypass_published_audience_validation_by_omitting_key(self):
        response = self.client.post(
            reverse("fable5_api_product_save"),
            data={
                "payload": json.dumps(
                    {
                        "id": self.product.pk,
                        "title": "Should roll back",
                        "category_id": self.category.pk,
                        "price": self.product.price,
                        "status": "published",
                    }
                )
            },
        )

        self.assertEqual(response.status_code, 400)
        self.product.refresh_from_db()
        self.assertEqual(self.product.title, "Audience test tee")
        self.assertEqual(get_product_audience_codes(self.product), [])

    def test_backfill_is_idempotent_and_does_not_touch_other_categories(self):
        hoodie_category = Category.objects.create(name="Худі", slug="hoodie")
        hoodie = Product.objects.create(
            title="Audience hoodie",
            slug="audience-hoodie",
            category=hoodie_category,
            price=1490,
            status="published",
        )
        set_product_audience_codes(self.product, ["women"])
        first_output = StringIO()
        second_output = StringIO()

        call_command("backfill_tshirt_audiences", "--apply", stdout=first_output)
        call_command("backfill_tshirt_audiences", "--apply", stdout=second_output)

        self.assertEqual(get_product_audience_codes(self.product), ["unisex", "women"])
        self.assertEqual(get_product_audience_codes(hoodie), [])
        self.assertIn("created=1", first_output.getvalue())
        self.assertIn("created=0", second_output.getvalue())

    def test_editor_assets_define_touch_sized_audience_controls(self):
        root = Path(__file__).resolve().parents[1]
        javascript = (root / "static" / "fable5" / "editor.js").read_text(encoding="utf-8")
        stylesheet = (root / "static" / "fable5" / "editor.css").read_text(encoding="utf-8")

        self.assertIn("audience_codes: collectAudienceCodes()", javascript)
        self.assertIn("min-height: 44px", stylesheet)
