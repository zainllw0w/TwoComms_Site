import importlib
import re
from unittest.mock import patch

from django.conf import settings
from django.apps import apps
from django.core.cache import cache, caches
from django.test import SimpleTestCase, TestCase
from django.utils.translation import override

from productcolors.models import Color, ProductColorVariant
from storefront.models import Category, Product, ProductFitOption
from storefront.seo_utils import SEOKeywordGenerator


class ProductTitleAlignmentTests(SimpleTestCase):
    def test_stale_quoted_seo_name_falls_back_to_canonical_product_title(self):
        category = Category(name_uk="Футболки", slug="tshirts")
        product = Product(
            title_uk="Футболка «Серце Та Грощі»",
            seo_title_uk=(
                "Футболка «death grabs ass» — купити футболку TwoComms"
            ),
            category=category,
        )

        with override("uk"):
            title = SEOKeywordGenerator.generate_meta_title(product)

        self.assertEqual(
            title,
            "Футболка «Серце Та Грощі» (Футболки) - TwoComms",
        )

    def test_matching_quoted_seo_name_keeps_editor_copy(self):
        stored = "Футболка «Серце Та Грощі» — купити в TwoComms"
        product = Product(
            title_uk="Футболка «Серце Та Грощі»",
            seo_title_uk=stored,
        )

        with override("uk"):
            title = SEOKeywordGenerator.generate_meta_title(product)

        self.assertEqual(title, stored)

    def test_data_repair_covers_all_audited_products_with_matching_names(self):
        migration = importlib.import_module(
            "storefront.migrations.0082_align_product_seo_titles_with_h1"
        )
        self.assertEqual(len(migration.REPAIRS), 13)

        for slug, payload in migration.REPAIRS.items():
            with self.subTest(slug=slug):
                repaired_seo = migration._seo_new(payload)
                title_name = re.search(r"«([^»]+)»", payload["title"]).group(1)
                seo_name = re.search(r"«([^»]+)»", repaired_seo).group(1)
                self.assertEqual(title_name, seo_name)
                self.assertLessEqual(len(repaired_seo), 70)
                self.assertNotIn(" с ", payload["title"].casefold())


class PosmikhnysVariantSeoRepairTests(TestCase):
    """Regression for the audited product-level keyword-list override.

    The affected color and color-fit URLs must derive concise metadata from
    the actual path state once the stale product override is removed. RU/EN
    remain non-indexable until their complete locale-owned product content is
    authored; this test therefore checks that they no longer expose the stale
    Ukrainian keyword list without inventing translations.
    """

    OLD_TITLE = (
        "молочна футболка з написом, футболка, футболка з принтом, "
        "купити футболку, футболка oversize, бежева футболка, унісекс "
        "футболка, футболка з написом, молочна фут"
    )

    def setUp(self):
        super().setUp()
        for target in (
            "storefront.signals.generate_google_merchant_feed_task.apply_async",
            "storefront.signals.enqueue_indexnow_urls",
        ):
            patcher = patch(target)
            self.addCleanup(patcher.stop)
            patcher.start()

        self.category = Category.objects.create(
            name="Футболки",
            slug="posmikhnys-seo-tshirts",
            is_active=True,
        )
        self.product = Product.objects.create(
            # Explicit id mirrors the production owner used by the guarded
            # data migration while keeping this test independent of fixtures.
            id=107,
            title="Футболка «Посміхнись»",
            slug="futbolka-posmikhnys",
            category=self.category,
            price=1090,
            status="published",
            seo_title=self.OLD_TITLE,
            seo_title_uk=self.OLD_TITLE,
            seo_description_uk=(
                "Молочна oversize-футболка TwoComms «Посміхнись» з "
                "виразним чорним принтом."
            ),
            short_description_uk="Молочна футболка з написом «Посміхнись».",
            full_description_uk="<p>Молочна футболка TwoComms з принтом.</p>",
        )
        self.color = Color.objects.create(
            name="Бежевий",
            primary_hex="#e9d1af",
        )
        ProductColorVariant.objects.create(
            product=self.product,
            color=self.color,
            slug="beige",
            is_default=True,
            order=0,
        )
        ProductFitOption.objects.create(
            product=self.product,
            code="classic",
            label="Класична",
            is_default=True,
            is_active=True,
            order=0,
        )
        ProductFitOption.objects.create(
            product=self.product,
            code="oversize",
            label="Оверсайз",
            is_default=False,
            is_active=True,
            order=1,
        )

    def _run_migration(self, direction="forward"):
        migration = importlib.import_module(
            "storefront.migrations.0093_repair_posmikhnys_variant_seo"
        )
        if direction == "forward":
            migration.repair_posmikhnys_seo(apps, None)
        else:
            migration.reverse_posmikhnys_seo(apps, None)

    def _clear_seo_caches(self):
        cache.clear()
        if "fragments" in settings.CACHES:
            caches["fragments"].clear()

    def test_guarded_migration_clears_only_exact_stale_product_titles(self):
        self._run_migration()
        self.product.refresh_from_db()
        self.assertEqual(self.product.seo_title, "")
        self.assertEqual(self.product.seo_title_uk, "")
        self.assertEqual(self.product.seo_description_uk, (
            "Молочна oversize-футболка TwoComms «Посміхнись» з "
            "виразним чорним принтом."
        ))

        self._run_migration("reverse")
        self.product.refresh_from_db()
        self.assertEqual(self.product.seo_title, self.OLD_TITLE)
        self.assertEqual(self.product.seo_title_uk, self.OLD_TITLE)

    def test_color_and_fit_paths_no_longer_render_keyword_list(self):
        self._run_migration()
        self._clear_seo_caches()
        self.product.refresh_from_db()
        self.assertEqual(self.product.seo_title, "")
        self.assertEqual(self.product.seo_title_uk, "")

        expected = {
            "/product/futbolka-posmikhnys/beige/": "бежевий",
            "/product/futbolka-posmikhnys/beige/classic/": "класична",
            "/product/futbolka-posmikhnys/beige/oversize/": "оверсайз",
        }
        for path, marker in expected.items():
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertIn(marker, response.context["variant_page_title"].lower())
                self.assertNotIn(self.OLD_TITLE, response.context["variant_page_title"])
                self.assertNotIn(
                    f"<title>{self.OLD_TITLE}</title>",
                    response.content.decode(),
                )
                self.assertLessEqual(
                    len(response.context["variant_page_title"]), 70
                )

    def test_untranslated_locale_paths_are_noindex_without_false_locale_owners(self):
        self._run_migration()
        self._clear_seo_caches()

        for language in ("ru", "en"):
            response = self.client.get(
                f"/{language}/product/futbolka-posmikhnys/beige/oversize/"
            )
            self.assertEqual(response.status_code, 200)
            body = response.content.decode()
            self.assertNotIn(f"<title>{self.OLD_TITLE}</title>", body)
            self.assertContains(response, "noindex, follow")
