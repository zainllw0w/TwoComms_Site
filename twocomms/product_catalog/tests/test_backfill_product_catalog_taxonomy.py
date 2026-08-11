from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from storefront.models import Category, Product

from product_catalog.models import (
    AudienceTag,
    MerchCollection,
    ProductAudience,
    ProductMerchCollection,
)
from product_catalog.services_audience import get_product_audience_codes
from product_catalog.services_collections import get_product_collection_slugs


class BackfillProductCatalogTaxonomyTests(TestCase):
    def setUp(self):
        self.tshirts = Category.objects.create(name="Футболки", slug="tshirts")
        self.hoodies = Category.objects.create(name="Худі", slug="hoodie")
        self.longsleeves = Category.objects.create(name="Лонгсліви", slug="long-sleeve")
        self.tags = {
            code: AudienceTag.objects.update_or_create(
                code=code,
                defaults={
                    "label_uk": label,
                    "label_ru": label,
                    "label_en": code.title(),
                    "order": index,
                },
            )[0]
            for index, (code, label) in enumerate(
                (("unisex", "Унісекс"), ("women", "Жіночі"), ("men", "Чоловічі"))
            )
        }
        self.military = MerchCollection.objects.update_or_create(
            slug="military",
            defaults={
                "kind": MerchCollection.Kind.THEME,
                "name_uk": "Мілітарі",
                "order": 10,
            },
        )[0]
        self.brigades = MerchCollection.objects.update_or_create(
            slug="brigades",
            defaults={
                "kind": MerchCollection.Kind.THEME,
                "name_uk": "Бригади",
                "order": 20,
                "parent": None,
            },
        )[0]
        self.brigade_225 = MerchCollection.objects.update_or_create(
            slug="225",
            defaults={
                "kind": MerchCollection.Kind.BRIGADE,
                "parent": self.brigades,
                "name_uk": "225 ОШП",
                "order": 30,
            },
        )[0]
        self.brigade_127 = MerchCollection.objects.update_or_create(
            slug="127",
            defaults={
                "kind": MerchCollection.Kind.BRIGADE,
                "parent": self.brigades,
                "name_uk": "127 ОБрТрО",
                "order": 31,
            },
        )[0]
        self.blank = Product.objects.create(
            title="Blank hoodie",
            slug="blank-hoodie",
            category=self.hoodies,
            price=1490,
            status="published",
        )
        self.women = Product.objects.create(
            title="Women longsleeve",
            slug="women-longsleeve",
            category=self.longsleeves,
            price=1290,
            status="published",
        )
        ProductAudience.objects.create(product=self.women, tag=self.tags["women"])
        self.tee_225 = Product.objects.create(
            title="Футболка 225ОШП",
            slug="225-tshirt",
            category=self.tshirts,
            price=1090,
            status="published",
        )
        self.hoodie_225 = Product.objects.create(
            title="Худі Команда Сірко х 225ОШП",
            slug="225-hoodie",
            category=self.hoodies,
            price=1490,
            status="published",
        )

    def test_dry_run_reports_candidates_without_writes(self):
        output = StringIO()

        call_command("backfill_product_catalog_taxonomy", stdout=output)

        self.assertEqual(ProductAudience.objects.count(), 1)
        self.assertEqual(ProductMerchCollection.objects.count(), 0)
        self.assertIn("audience_candidates=3", output.getvalue())
        self.assertIn("brigade_225_candidates=2", output.getvalue())
        self.assertIn("dry_run=True", output.getvalue())

    def test_apply_preserves_explicit_gender_and_assigns_only_225_leaf(self):
        first_output = StringIO()
        second_output = StringIO()

        call_command("backfill_product_catalog_taxonomy", "--apply", stdout=first_output)
        call_command("backfill_product_catalog_taxonomy", "--apply", stdout=second_output)

        self.assertEqual(get_product_audience_codes(self.women), ["women"])
        self.assertEqual(get_product_audience_codes(self.blank), ["unisex"])
        self.assertEqual(get_product_audience_codes(self.tee_225), ["unisex"])
        self.assertEqual(get_product_audience_codes(self.hoodie_225), ["unisex"])
        self.assertEqual(get_product_collection_slugs(self.tee_225), ["225"])
        self.assertEqual(get_product_collection_slugs(self.hoodie_225), ["225"])
        self.assertFalse(
            ProductMerchCollection.objects.filter(collection=self.brigades).exists()
        )
        self.assertFalse(
            ProductMerchCollection.objects.filter(collection=self.military).exists()
        )
        self.assertIn("audiences_created=3", first_output.getvalue())
        self.assertIn("brigade_225_created=2", first_output.getvalue())
        self.assertIn("audiences_created=0", second_output.getvalue())
        self.assertIn("brigade_225_created=0", second_output.getvalue())

    def test_command_refuses_inconsistent_brigade_parent(self):
        self.brigade_225.parent = self.military
        self.brigade_225.save(update_fields=["parent"])

        with self.assertRaisesMessage(RuntimeError, "brigades"):
            call_command("backfill_product_catalog_taxonomy", "--apply")

    def test_command_refuses_brigades_nested_under_military(self):
        self.brigades.parent = self.military
        self.brigades.save(update_fields=["parent"])

        with self.assertRaisesMessage(RuntimeError, "top-level"):
            call_command("backfill_product_catalog_taxonomy", "--apply")

    def test_command_refuses_inconsistent_127_parent(self):
        self.brigade_127.parent = self.military
        self.brigade_127.save(update_fields=["parent"])

        with self.assertRaisesMessage(RuntimeError, "127"):
            call_command("backfill_product_catalog_taxonomy", "--apply")

    def test_apply_removes_redundant_brigades_but_preserves_manual_military(self):
        ProductMerchCollection.objects.create(
            product=self.tee_225,
            collection=self.brigades,
            order=0,
        )
        ProductMerchCollection.objects.create(
            product=self.tee_225,
            collection=self.military,
            order=1,
        )
        output = StringIO()

        call_command("backfill_product_catalog_taxonomy", "--apply", stdout=output)

        stored_slugs = set(
            ProductMerchCollection.objects.filter(product=self.tee_225)
            .values_list("collection__slug", flat=True)
        )
        self.assertEqual(stored_slugs, {"225", "military"})
        self.assertIn("redundant_brigades_removed=1", output.getvalue())
