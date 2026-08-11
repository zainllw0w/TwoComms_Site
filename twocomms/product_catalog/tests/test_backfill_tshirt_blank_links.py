from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from product_catalog.models import ColorProfile, VariantBlankLink, VariantFitRule
from productcolors.models import Color, ProductColorVariant
from storefront.models import Category, Product, ProductFitOption
from warehouse.models import StorageCategory, StorageSubcategory


class BackfillTshirtBlankLinksCommandTests(TestCase):
    def setUp(self):
        StorageSubcategory.objects.filter(
            slug__in=("crc-classic-101", "oversize-erc", "termo")
        ).delete()
        self.category = Category.objects.create(name="Футболки", slug="tshirts-backfill")
        self.product = Product.objects.create(
            title="Fit routed T-shirt",
            slug="fit-routed-tshirt",
            category=self.category,
            price=900,
        )
        ProductFitOption.objects.create(
            product=self.product,
            code="classic",
            label="Класична",
            is_default=True,
            order=10,
        )
        ProductFitOption.objects.create(
            product=self.product,
            code="oversize",
            label="Оверсайз",
            order=20,
        )

        normal_color = Color.objects.create(name="Black", primary_hex="#101010")
        self.normal_variant = ProductColorVariant.objects.create(
            product=self.product,
            color=normal_color,
            is_default=True,
        )
        thermo_color = Color.objects.create(name="Thermo green", primary_hex="#4A8A66")
        self.thermo_variant = ProductColorVariant.objects.create(
            product=self.product,
            color=thermo_color,
        )
        ColorProfile.objects.create(color=thermo_color, is_thermo=True)
        VariantFitRule.objects.create(
            variant=self.thermo_variant,
            fit_code="classic",
            is_enabled=False,
        )
        VariantFitRule.objects.create(
            variant=self.thermo_variant,
            fit_code="oversize",
            is_enabled=True,
        )

        storage_category = StorageCategory.objects.create(
            name="Футболки склад",
            slug="tshirts-storage-backfill",
        )
        self.classic_blank = StorageSubcategory.objects.create(
            category=storage_category,
            name="CRC Classic 101",
            slug="crc-classic-101",
        )
        self.oversize_blank = StorageSubcategory.objects.create(
            category=storage_category,
            name="Oversize ERC",
            slug="oversize-erc",
        )
        self.thermo_blank = StorageSubcategory.objects.create(
            category=storage_category,
            name="Thermo",
            slug="termo",
        )

    def _run(self, **options):
        output = StringIO()
        call_command("backfill_tshirt_blank_links", stdout=output, **options)
        return output.getvalue()

    def test_default_dry_run_reports_all_missing_links_without_writing(self):
        output = self._run()

        self.assertEqual(VariantBlankLink.objects.count(), 0)
        self.assertIn("create=3", output)
        self.assertIn("dry_run=True", output)
        self.assertIn("crc-classic-101", output)
        self.assertIn("oversize-erc", output)
        self.assertIn("termo", output)

    def test_apply_maps_normal_fits_and_thermo_then_is_idempotent(self):
        first_output = self._run(apply=True)

        links = {
            (link.variant_id, link.option_key): link.storage_subcategory.slug
            for link in VariantBlankLink.objects.select_related("storage_subcategory")
        }
        self.assertEqual(
            links,
            {
                (self.normal_variant.id, "fit=classic"): "crc-classic-101",
                (self.normal_variant.id, "fit=oversize"): "oversize-erc",
                (self.thermo_variant.id, "fit=oversize"): "termo",
            },
        )
        self.assertNotIn((self.thermo_variant.id, "fit=classic"), links)
        self.assertIn("created=3", first_output)

        second_output = self._run(apply=True)

        self.assertEqual(VariantBlankLink.objects.count(), 3)
        self.assertIn("create=0", second_output)
        self.assertIn("created=0", second_output)

    def test_existing_explicit_link_is_preserved(self):
        manual_blank = StorageSubcategory.objects.create(
            category=self.classic_blank.category,
            name="Manual special blank",
            slug="manual-special-blank",
        )
        existing = VariantBlankLink.objects.create(
            variant=self.normal_variant,
            option_key="fit=classic",
            storage_subcategory=manual_blank,
            note="Manager override",
        )

        output = self._run(apply=True)

        existing.refresh_from_db()
        self.assertEqual(existing.storage_subcategory, manual_blank)
        self.assertEqual(existing.note, "Manager override")
        self.assertIn("preserved=1", output)

    def test_product_scope_does_not_touch_other_tshirts(self):
        other = Product.objects.create(
            title="Other T-shirt",
            slug="other-fit-routed-tshirt",
            category=self.category,
            price=900,
        )
        ProductFitOption.objects.create(
            product=other,
            code="classic",
            label="Класична",
            is_default=True,
        )
        other_variant = ProductColorVariant.objects.create(
            product=other,
            color=self.normal_variant.color,
        )

        self._run(apply=True, product_id=[other.id])

        self.assertTrue(
            VariantBlankLink.objects.filter(
                variant=other_variant,
                option_key="fit=classic",
                storage_subcategory=self.classic_blank,
            ).exists()
        )
        self.assertFalse(
            VariantBlankLink.objects.filter(variant__product=self.product).exists()
        )
