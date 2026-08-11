import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from storefront.models import Category, Product

from product_catalog.models import AudienceTag, MerchCollection, ProductMerchCollection
from product_catalog.services_audience import set_product_audience_codes
from product_catalog.services_collections import (
    get_product_collection_slugs,
    product_collection_context,
    set_product_collection_slugs,
)


class MerchCollectionTaxonomyTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Футболки", slug="tshirts")
        self.product = Product.objects.create(
            title="Collection test tee",
            slug="collection-test-tee",
            category=self.category,
            price=1090,
            status="published",
        )
        self.unisex, _created = AudienceTag.objects.update_or_create(
            code="unisex",
            defaults={
                "label_uk": "Унісекс",
                "label_ru": "Унисекс",
                "label_en": "Unisex",
                "order": 0,
                "is_active": True,
            },
        )
        set_product_audience_codes(self.product, ["unisex"])
        self.military, _created = MerchCollection.objects.update_or_create(
            slug="military",
            defaults={
                "kind": MerchCollection.Kind.THEME,
                "parent": None,
                "name_uk": "Мілітарі",
                "name_ru": "Милитари",
                "name_en": "Military",
                "order": 10,
                "indexable": False,
                "is_active": True,
            },
        )
        self.brigades, _created = MerchCollection.objects.update_or_create(
            slug="brigades",
            defaults={
                "kind": MerchCollection.Kind.THEME,
                "parent": None,
                "name_uk": "Бригади",
                "name_ru": "Бригады",
                "name_en": "Brigades",
                "order": 20,
                "indexable": False,
                "is_active": True,
            },
        )
        self.brigade_225, _created = MerchCollection.objects.update_or_create(
            slug="225",
            defaults={
                "kind": MerchCollection.Kind.BRIGADE,
                "parent": self.brigades,
                "name_uk": "225 ОШП",
                "name_ru": "225 ОШП",
                "name_en": "225 Assault Regiment",
                "indexable": True,
                "order": 30,
                "is_active": True,
            },
        )
        self.brigade_127, _created = MerchCollection.objects.update_or_create(
            slug="127",
            defaults={
                "kind": MerchCollection.Kind.BRIGADE,
                "parent": self.brigades,
                "name_uk": "127 бригада",
                "name_ru": "127 бригада",
                "name_en": "127 Brigade",
                "indexable": False,
                "order": 31,
                "is_active": True,
            },
        )
        self.streetwear, _created = MerchCollection.objects.update_or_create(
            slug="streetwear",
            defaults={
                "kind": MerchCollection.Kind.THEME,
                "parent": None,
                "name_uk": "Стрітвір",
                "name_ru": "Стритвир",
                "name_en": "Streetwear",
                "order": 40,
                "indexable": False,
                "is_active": True,
            },
        )
        self.staff = get_user_model().objects.create_user(
            username="collection-editor",
            password="test-password",
            is_staff=True,
        )
        self.client.force_login(self.staff)

    def test_nested_collection_context_has_localized_breadcrumbs_and_public_path(self):
        set_product_collection_slugs(self.product, ["225"])

        context = product_collection_context(self.product, language="en")

        self.assertEqual(context[0]["slug"], "225")
        self.assertEqual(context[0]["label"], "225 Assault Regiment")
        self.assertEqual(
            [item["slug"] for item in context[0]["ancestors"]],
            ["brigades"],
        )
        self.assertEqual(context[0]["public_path"], "/merch/225/")

    def test_product_supports_ordered_multiple_collections_without_duplicates(self):
        set_product_collection_slugs(self.product, ["streetwear", "225"])

        self.assertEqual(get_product_collection_slugs(self.product), ["225", "streetwear"])
        with self.assertRaises(IntegrityError), transaction.atomic():
            ProductMerchCollection.objects.create(
                product=self.product,
                collection=self.brigade_225,
            )

    def test_specific_child_assignment_removes_redundant_parent_assignment(self):
        saved = set_product_collection_slugs(self.product, ["brigades", "225"])

        self.assertEqual(saved, ["225"])
        self.assertEqual(get_product_collection_slugs(self.product), ["225"])
        self.assertEqual(
            [row["path_label"] for row in product_collection_context(self.product)],
            ["Бригади / 225 ОШП"],
        )

    def test_deep_child_assignment_removes_selected_root_without_intermediate(self):
        collaboration = MerchCollection.objects.create(
            slug="225-collaboration",
            kind=MerchCollection.Kind.COLLAB,
            parent=self.brigade_225,
            name_uk="Колаборація 225",
            name_ru="Коллаборация 225",
            name_en="225 Collaboration",
            order=32,
        )

        saved = set_product_collection_slugs(
            self.product,
            ["brigades", collaboration.slug],
        )

        self.assertEqual(saved, [collaboration.slug])
        self.assertEqual(get_product_collection_slugs(self.product), [collaboration.slug])

    def test_inactive_or_non_indexable_collection_never_exposes_public_path(self):
        self.streetwear.indexable = False
        self.streetwear.save(update_fields=["indexable"])
        self.brigade_225.is_active = False
        self.brigade_225.save(update_fields=["is_active"])
        ProductMerchCollection.objects.create(
            product=self.product, collection=self.streetwear, order=1
        )
        ProductMerchCollection.objects.create(
            product=self.product, collection=self.brigade_225, order=2
        )

        context = product_collection_context(
            self.product, language="uk", include_inactive=True
        )

        self.assertEqual([item["public_path"] for item in context], ["", ""])

    def test_unknown_or_inactive_collection_assignment_is_rejected_atomically(self):
        set_product_collection_slugs(self.product, ["streetwear"])
        self.brigade_225.is_active = False
        self.brigade_225.save(update_fields=["is_active"])

        with self.assertRaises(ValueError):
            set_product_collection_slugs(self.product, ["225", "missing"])

        self.assertEqual(get_product_collection_slugs(self.product), ["streetwear"])

    def test_replacing_active_assignments_preserves_inactive_historical_facts(self):
        ProductMerchCollection.objects.create(
            product=self.product, collection=self.brigade_225, order=1
        )
        self.brigade_225.is_active = False
        self.brigade_225.save(update_fields=["is_active"])

        set_product_collection_slugs(self.product, [])

        self.assertEqual(get_product_collection_slugs(self.product), [])
        context = product_collection_context(
            self.product, language="uk", include_inactive=True
        )
        self.assertEqual([item["slug"] for item in context], ["225"])

    def test_editor_bootstrap_exposes_hierarchy_and_current_multi_selection(self):
        set_product_collection_slugs(self.product, ["225", "streetwear"])

        response = self.client.get(reverse("product_catalog_product_edit", args=[self.product.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["bootstrap"]["product"]["collection_slugs"],
            ["225", "streetwear"],
        )
        collection_rows = response.context["bootstrap"]["dictionaries"]["collections"]
        row_225 = next(row for row in collection_rows if row["slug"] == "225")
        self.assertEqual(row_225["parent_slug"], "brigades")
        self.assertEqual(row_225["path_label"], "Бригади / 225 ОШП")
        self.assertContains(response, 'id="f-collection-options"', html=False)
        self.assertContains(response, 'id="f-collection-search"', html=False)

    def test_editor_save_persists_multiple_collection_slugs(self):
        response = self.client.post(
            reverse("product_catalog_api_product_save"),
            data={
                "payload": json.dumps(
                    {
                        "id": self.product.pk,
                        "title": self.product.title,
                        "category_id": self.category.pk,
                        "price": self.product.price,
                        "status": "published",
                        "audience_codes": ["unisex"],
                        "collection_slugs": ["streetwear", "225"],
                    }
                )
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["product"]["collection_slugs"],
            ["225", "streetwear"],
        )
        self.assertEqual(get_product_collection_slugs(self.product), ["225", "streetwear"])

    def test_editor_assets_define_searchable_touch_sized_collection_picker(self):
        root = Path(__file__).resolve().parents[1]
        javascript = (root / "static" / "product_catalog" / "editor.js").read_text(encoding="utf-8")
        stylesheet = (root / "static" / "product_catalog" / "editor.css").read_text(encoding="utf-8")

        self.assertIn("collection_slugs: collectCollectionSlugs()", javascript)
        self.assertIn("renderCollectionOptions", javascript)
        self.assertIn("min-height: 44px", stylesheet)
