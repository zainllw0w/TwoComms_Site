import json
from types import SimpleNamespace
from pathlib import Path
from uuid import uuid4

from django.urls import Resolver404, resolve, reverse
from django.test import Client, TestCase, override_settings
from django.contrib.auth import get_user_model

from storefront.models import (
    Category,
    GoogleIndexingSubmission,
    IndexNowSubmission,
    Product,
)
from storefront.views.admin import _build_catalogs_context
from product_catalog.models import AudienceTag, MerchCollection, ProductAudience
from product_catalog.services_audience import get_effective_audience_codes
from product_catalog.services_collections import collection_picker_state
from product_catalog.views import _print_preview


class ProductCatalogContractsTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Contract tee", slug="contract-tee")
        self.product = Product.objects.create(
            title="Contract product",
            slug="contract-product",
            category=self.category,
            price=1090,
        )
        self.staff = get_user_model().objects.create_user(
            username="catalog-staff",
            password="secret",
            is_staff=True,
        )

    def test_unisex_exposes_male_and_female_as_effective_audience(self):
        unisex, _ = AudienceTag.objects.get_or_create(
            code="unisex",
            defaults={
                "label_uk": "Унісекс",
                "label_ru": "Унисекс",
                "label_en": "Unisex",
                "order": 0,
            },
        )
        men, _ = AudienceTag.objects.get_or_create(
            code="men",
            defaults={
                "label_uk": "Чоловічі",
                "label_ru": "Мужские",
                "label_en": "Men",
                "order": 20,
            },
        )
        women, _ = AudienceTag.objects.get_or_create(
            code="women",
            defaults={
                "label_uk": "Жіночі",
                "label_ru": "Женские",
                "label_en": "Women",
                "order": 10,
            },
        )
        ProductAudience.objects.create(product=self.product, tag=unisex)

        self.assertEqual(
            get_effective_audience_codes(self.product),
            ["unisex", "women", "men"],
        )
        self.assertTrue(men.is_active and women.is_active)

    def test_collection_picker_marks_ancestors_as_derived_and_locked(self):
        suffix = uuid4().hex[:8]
        parent_slug = f"test-brigades-{suffix}"
        child_slug = f"test-225-{suffix}"
        parent = MerchCollection.objects.create(
            slug=parent_slug,
            kind=MerchCollection.Kind.BRIGADE,
            name_uk="Бригади",
            order=10,
        )
        child = MerchCollection.objects.create(
            slug=child_slug,
            kind=MerchCollection.Kind.BRIGADE,
            parent=parent,
            name_uk="225",
            order=20,
        )

        rows = collection_picker_state(
            [
                {"slug": parent.slug, "parent_slug": "", "path_label": "Бригади"},
                {"slug": child.slug, "parent_slug": parent.slug, "path_label": "Бригади / 225"},
            ],
            [child.slug],
        )

        parent_row = next(row for row in rows if row["slug"] == parent.slug)
        child_row = next(row for row in rows if row["slug"] == child.slug)
        self.assertEqual(parent_row["selection_state"], "derived")
        self.assertTrue(parent_row["is_locked"])
        self.assertEqual(child_row["selection_state"], "selected")
        self.assertFalse(child_row["is_locked"])

    def test_active_collection_dictionary_keeps_parents_before_children(self):
        suffix = uuid4().hex[:8]
        parent = MerchCollection.objects.create(
            slug=f"parent-{suffix}",
            kind=MerchCollection.Kind.BRIGADE,
            name_uk="Бригади",
            order=20,
        )
        child = MerchCollection.objects.create(
            slug=f"child-{suffix}",
            kind=MerchCollection.Kind.BRIGADE,
            parent=parent,
            name_uk="225",
            order=10,
        )

        from product_catalog.services_collections import active_collection_dictionary

        rows = active_collection_dictionary()
        slugs = [row["slug"] for row in rows if row["slug"] in {parent.slug, child.slug}]
        self.assertEqual(slugs, [parent.slug, child.slug])
        by_slug = {row["slug"]: row for row in rows}
        self.assertEqual(by_slug[parent.slug]["depth"], 0)
        self.assertEqual(by_slug[child.slug]["depth"], 1)
        self.assertEqual(by_slug[parent.slug]["kind_label"], "Бригада")
        self.assertEqual(by_slug[child.slug]["kind_label"], "Бригада")

    def test_print_preview_never_falls_back_to_finished_product_artwork(self):
        item = SimpleNamespace(
            main_image=None,
            product_catalog_image_variants=[],
            product_catalog_preview_products=[
                SimpleNamespace(main_image=SimpleNamespace(url="/media/finished-tee.webp"))
            ],
        )

        self.assertEqual(_print_preview(item), ("", "missing"))

    def test_editor_uses_catalog_paths_and_no_product_catalog_path_alias(self):
        self.assertEqual(
            reverse("product_catalog_product_new"),
            "/admin-panel/catalog/products/new/",
        )
        self.assertEqual(
            reverse("product_catalog_product_edit", args=[self.product.pk]),
            f"/admin-panel/catalog/products/{self.product.pk}/edit/",
        )
        self.assertIsNotNone(resolve("/admin-panel/catalog/products/new/"))
        with self.assertRaises(Resolver404):
            resolve("/admin-panel/product_catalog/product/new/")

    def test_editor_cover_cards_expose_progress_and_retry_overlays(self):
        template = Path(__file__).resolve().parents[1] / "templates/product_catalog/editor.html"
        source = template.read_text(encoding="utf-8")
        for element_id in (
            "f-main-cover-visual",
            "f-home-cover-visual",
            "f-main-image-progress",
            "f-home-image-progress",
            "f-main-image-retry",
            "f-home-image-retry",
        ):
            with self.subTest(element_id=element_id):
                self.assertIn(f'id="{element_id}"', source)

    def test_custom_admin_catalog_uses_dense_visual_card_grids(self):
        project_root = Path(__file__).resolve().parents[2]
        template = (
            project_root
            / "twocomms_django_theme/templates/pages/admin_panel.html"
        ).read_text(encoding="utf-8")
        styles = (
            project_root
            / "twocomms_django_theme/static/css/styles.css"
        ).read_text(encoding="utf-8")
        purged_styles = (
            project_root
            / "twocomms_django_theme/static/css/styles.purged.css"
        ).read_text(encoding="utf-8")

        for marker in (
            'class="catalog-product-media"',
            'class="catalog-product-metrics"',
            'class="catalog-product-metric"',
            'class="catalog-product-footer"',
            'class="catalog-category-media"',
            'data-product-id="{{ product.id }}"',
            'data-order-position="{{ forloop.counter }}"',
            'data-drag-handle',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, template)

        self.assertIn(
            "grid-template-columns: repeat(4, minmax(0, 1fr));",
            styles,
        )
        self.assertIn(
            "grid-template-columns: repeat(3, minmax(0, 1fr));",
            styles,
        )
        self.assertIn("aspect-ratio: 4 / 3;", styles)
        self.assertNotIn("aspect-ratio: 4 / 5;", styles)
        self.assertRegex(
            styles,
            r"\.catalog-workspace \.catalog-product-metrics \{[^}]*"
            r"grid-template-columns: repeat\(5, minmax\(0, 1fr\)\);",
        )
        self.assertIn("container: catalog-workspace / inline-size;", styles)
        self.assertIn("@container catalog-workspace (max-width: 1040px)", styles)
        self.assertRegex(
            styles,
            r'\.catalog-index-button\[data-index-state="accepted"\] \{[^}]*'
            r"background: #143c2d;[^}]*border-color: #2f7f58;",
        )
        self.assertIn("product.items_sold", template)
        self.assertIn(
            'aria-label="Користувачі: {{ user_data|length }}"',
            template,
        )
        for marker in (
            ".catalog-workspace .products-grid{",
            ".catalog-workspace .catalog-product-media{",
            ".catalog-workspace .catalog-product-metrics{",
            ".catalog-workspace .catalog-product-footer{",
            ".catalog-taxonomy-board{",
            ".catalog-taxonomy-panel{",
        ):
            with self.subTest(purged_marker=marker):
                self.assertIn(marker, purged_styles)

    def test_catalog_cards_keep_status_readable_and_catalog_shell_uses_management_tone(self):
        project_root = Path(__file__).resolve().parents[2]
        template = (
            project_root
            / "twocomms_django_theme/templates/pages/admin_panel.html"
        ).read_text(encoding="utf-8")
        styles = (
            project_root
            / "twocomms_django_theme/static/css/styles.css"
        ).read_text(encoding="utf-8")
        purged_styles = (
            project_root
            / "twocomms_django_theme/static/css/styles.purged.css"
        ).read_text(encoding="utf-8")
        editor_styles = (
            project_root / "product_catalog/static/product_catalog/editor.css"
        ).read_text(encoding="utf-8")

        self.assertIn('class="catalog-product-status-row"', template)
        self.assertIn(
            ".catalog-workspace .catalog-product-status-row {",
            styles,
        )
        self.assertIn(
            "class=\"admin-panel{% if section == 'catalogs' %} admin-panel--catalogs{% endif %}\"",
            template,
        )
        self.assertIn(
            ".admin-panel--catalogs .admin-header",
            styles,
        )
        self.assertIn(
            ".admin-panel--catalogs .admin-header",
            purged_styles,
        )
        self.assertIn(
            ".catalog-workspace .catalog-product-status-row{",
            purged_styles,
        )
        self.assertIn("@font-face", editor_styles)
        self.assertIn("Inter-Regular.woff2", editor_styles)
        self.assertIn("max-height: 54px", editor_styles)

    def test_catalog_search_restores_card_layout_without_inline_display_override(self):
        project_root = Path(__file__).resolve().parents[2]
        template = (
            project_root
            / "twocomms_django_theme/templates/pages/admin_panel.html"
        ).read_text(encoding="utf-8")
        filter_source = template.split("function filterCatalogs(searchTerm) {", 1)[1].split(
            "function clearCatalogsSearch() {",
            1,
        )[0]

        self.assertEqual(filter_source.count("card.style.display = '';"), 2)
        self.assertNotIn("card.style.display = 'block';", filter_source)

    def test_compact_status_selector_rolls_back_after_rejected_update(self):
        project_root = Path(__file__).resolve().parents[2]
        template = (
            project_root
            / "twocomms_django_theme/templates/pages/admin_panel.html"
        ).read_text(encoding="utf-8")
        status_source = template.split("(function setupProductStatus() {", 1)[1].split(
            "function updateOrderStatus(",
            1,
        )[0]

        self.assertIn("const previousStatus = select.dataset.previousStatus || select.value;", status_source)
        self.assertIn("select.dataset.previousStatus = status;", status_source)
        self.assertIn("select.value = previousStatus;", status_source)

    def test_legacy_product_crud_paths_are_unresolved(self):
        for path in (
            "/add-product/",
            "/admin-panel/product/add/",
            "/admin-panel/product/new/",
            "/admin-panel/product/1/edit/",
            "/admin-panel/product/1/edit-simple/",
            "/admin-panel/product/1/edit-unified/",
            "/admin-panel/product/1/builder/",
            "/admin-panel/product/builder/",
            "/admin-panel/product/1/colors/",
        ):
            with self.subTest(path=path), self.assertRaises(Resolver404):
                resolve(path)

    def test_canonical_delete_is_staff_only_post_and_removes_product(self):
        delete_url = reverse("product_catalog_api_product_delete")

        self.assertEqual(self.client.post(delete_url, data={"product_id": self.product.pk}).status_code, 403)

        self.client.force_login(self.staff)
        response = self.client.get(delete_url)
        self.assertEqual(response.status_code, 405)

        response = self.client.post(
            delete_url,
            data=json.dumps({"product_id": self.product.pk}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Product.objects.filter(pk=self.product.pk).exists())

    def test_canonical_delete_requires_csrf_token(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.staff)

        response = csrf_client.post(
            reverse("product_catalog_api_product_delete"),
            data=json.dumps({"product_id": self.product.pk}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(Product.objects.filter(pk=self.product.pk).exists())

    def test_product_save_normalizes_youtube_and_assigns_next_priority(self):
        Product.objects.create(
            title="High priority product",
            slug="high-priority-product",
            category=self.category,
            price=1000,
            priority=30,
        )
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("product_catalog_api_product_save"),
            data={
                "payload": json.dumps({
                    "title": "New canonical product",
                    "category_id": self.category.pk,
                    "price": 1200,
                    "priority": 0,
                    "video_url": "https://youtu.be/dQw4w9WgXcQ?t=5",
                })
            },
        )

        self.assertEqual(response.status_code, 200, response.content)
        product = Product.objects.get(pk=response.json()["product"]["id"])
        self.assertEqual(product.priority, 31)
        self.assertEqual(
            product.video_url,
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        )

    def test_product_save_rejects_non_youtube_video_url(self):
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("product_catalog_api_product_save"),
            data={
                "payload": json.dumps({
                    "title": "Invalid video product",
                    "category_id": self.category.pk,
                    "price": 1200,
                    "video_url": "https://vimeo.com/12345",
                })
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("YouTube", response.json()["error"])
        self.assertFalse(Product.objects.filter(title="Invalid video product").exists())

    @override_settings(SITE_BASE_URL="https://twocomms.shop")
    def test_catalog_context_restores_truthful_index_api_states(self):
        self.product.status = "published"
        self.product.save(update_fields=["status"])
        public_url = "https://twocomms.shop/product/contract-product/"
        GoogleIndexingSubmission.objects.create(
            url=public_url,
            notification_type=GoogleIndexingSubmission.NOTIFICATION_URL_UPDATED,
            status=GoogleIndexingSubmission.STATUS_SUCCESS,
            http_status=200,
            source="admin",
        )
        IndexNowSubmission.objects.create(
            url=public_url,
            status=IndexNowSubmission.STATUS_SUCCESS,
            http_status=202,
            source="admin",
        )

        product = _build_catalogs_context()["products"][0]

        self.assertEqual(product.google_index_state, "accepted")
        self.assertEqual(product.google_index_state_label, "Прийнято API")
        self.assertEqual(product.indexnow_state, "accepted")
        self.assertEqual(product.indexnow_state_label, "Прийнято API")

    def test_catalog_context_exposes_paid_items_sold_for_product_cards(self):
        product = _build_catalogs_context()["products"][0]

        self.assertEqual(product.items_sold, 0)
