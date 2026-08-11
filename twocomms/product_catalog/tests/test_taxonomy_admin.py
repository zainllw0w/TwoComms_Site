import json
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from product_catalog.models import MerchCollection


TEST_CACHES = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
    "fragments": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
}


class TaxonomyAdminApiTests(TestCase):
    @staticmethod
    def _png_upload(name="taxonomy.png", *, padding=0):
        buffer = BytesIO()
        Image.new("RGBA", (2, 2), "#7c3aed").save(buffer, format="PNG")
        return SimpleUploadedFile(
            name,
            buffer.getvalue() + (b"0" * padding),
            content_type="image/png",
        )

    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username="taxonomy-staff",
            password="secret",
            is_staff=True,
        )
        self.suffix = uuid4().hex[:8]
        self.parent_slug = f"test-brigades-{self.suffix}"
        self.child_slug = f"test-225-{self.suffix}"
        self.parent = MerchCollection.objects.create(
            slug=self.parent_slug,
            kind=MerchCollection.Kind.THEME,
            name_uk="Бригади",
            order=10,
        )

    def test_collection_save_is_staff_only_and_persists_taxonomy_assets_and_seo(self):
        url = reverse("product_catalog_api_collection_save")
        anonymous = self.client.post(url, {"name_uk": "225"})
        self.assertEqual(anonymous.status_code, 403)

        self.client.force_login(self.staff)
        response = self.client.post(
            url,
            {
                "slug": self.child_slug,
                "kind": MerchCollection.Kind.BRIGADE,
                "parent_id": str(self.parent.pk),
                "name_uk": "225",
                "name_ru": "225",
                "name_en": "225 Brigade",
                "description_uk": "Окрема підкатегорія бригад.",
                "seo_title_uk": "Одяг 225 бригади",
                "seo_h1_uk": "Одяг та принти 225 бригади",
                "seo_description_uk": "Каталог одягу та принтів 225 бригади.",
                "seo_keywords_uk": "225 бригада, одяг, принти",
                "indexable": "1",
                "is_active": "1",
                "icon": self._png_upload("225.png"),
            },
        )

        self.assertEqual(response.status_code, 200, response.content)
        collection = MerchCollection.objects.get(slug=self.child_slug)
        self.assertEqual(collection.parent, self.parent)
        self.assertEqual(collection.seo_h1_uk, "Одяг та принти 225 бригади")
        self.assertEqual(collection.seo_keywords_uk, "225 бригада, одяг, принти")
        self.assertTrue(collection.indexable)
        self.assertRegex(
            collection.icon.name,
            r"^product_catalog/merch_collection_icons/225(?:_[A-Za-z0-9]+)?\.png$",
        )

    def test_collection_save_rejects_invalid_or_oversized_icon_content(self):
        self.client.force_login(self.staff)
        url = reverse("product_catalog_api_collection_save")
        base_payload = {
            "slug": self.child_slug,
            "kind": MerchCollection.Kind.BRIGADE,
            "parent_id": str(self.parent.pk),
            "name_uk": "225",
            "is_active": "1",
        }

        invalid = self.client.post(
            url,
            {
                **base_payload,
                "icon": SimpleUploadedFile(
                    "fake.png",
                    b"not-an-image",
                    content_type="image/png",
                ),
            },
        )
        oversized = self.client.post(
            url,
            {
                **base_payload,
                "icon": self._png_upload("large.png", padding=(2 * 1024 * 1024)),
            },
        )

        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(oversized.status_code, 400)
        self.assertFalse(MerchCollection.objects.filter(slug=self.child_slug).exists())

    def test_system_taxonomy_hierarchy_cannot_make_military_implicit(self):
        military, _created = MerchCollection.objects.update_or_create(
            slug="military",
            defaults={
                "kind": MerchCollection.Kind.THEME,
                "name_uk": "Мілітарі",
                "parent": None,
            },
        )
        brigades, _created = MerchCollection.objects.update_or_create(
            slug="brigades",
            defaults={
                "kind": MerchCollection.Kind.THEME,
                "name_uk": "Бригади",
                "parent": None,
            },
        )
        brigade_225, _created = MerchCollection.objects.update_or_create(
            slug="225",
            defaults={
                "kind": MerchCollection.Kind.BRIGADE,
                "name_uk": "225",
                "parent": brigades,
            },
        )
        self.client.force_login(self.staff)
        url = reverse("product_catalog_api_collection_save")

        nested_brigades = self.client.post(
            url,
            {
                "id": str(brigades.pk),
                "slug": "brigades",
                "kind": brigades.kind,
                "name_uk": brigades.name_uk,
                "parent_id": str(military.pk),
                "is_active": "1",
            },
        )
        detached_leaf = self.client.post(
            url,
            {
                "id": str(brigade_225.pk),
                "slug": "225",
                "kind": brigade_225.kind,
                "name_uk": brigade_225.name_uk,
                "parent_id": str(military.pk),
                "is_active": "1",
            },
        )
        renamed_leaf = self.client.post(
            url,
            {
                "id": str(brigade_225.pk),
                "slug": "renamed-225",
                "kind": brigade_225.kind,
                "name_uk": brigade_225.name_uk,
                "parent_id": str(brigades.pk),
                "is_active": "1",
            },
        )

        self.assertEqual(nested_brigades.status_code, 400)
        self.assertEqual(detached_leaf.status_code, 400)
        self.assertEqual(renamed_leaf.status_code, 400)
        brigades.refresh_from_db()
        brigade_225.refresh_from_db()
        self.assertIsNone(brigades.parent_id)
        self.assertEqual(brigade_225.parent_id, brigades.pk)
        self.assertEqual(brigade_225.slug, "225")

    def test_collection_save_rejects_parent_cycles(self):
        child = MerchCollection.objects.create(
            slug=self.child_slug,
            kind=MerchCollection.Kind.BRIGADE,
            parent=self.parent,
            name_uk="225",
        )
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("product_catalog_api_collection_save"),
            {
                "id": str(self.parent.pk),
                "slug": self.parent.slug,
                "kind": self.parent.kind,
                "name_uk": self.parent.name_uk,
                "parent_id": str(child.pk),
                "is_active": "1",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("цикл", response.json()["error"].lower())

    def test_collection_save_cannot_deactivate_parent_with_active_children(self):
        child = MerchCollection.objects.create(
            slug=self.child_slug,
            kind=MerchCollection.Kind.BRIGADE,
            parent=self.parent,
            name_uk="225",
            is_active=True,
        )
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("product_catalog_api_collection_save"),
            {
                "id": str(self.parent.pk),
                "slug": self.parent.slug,
                "kind": self.parent.kind,
                "name_uk": self.parent.name_uk,
                "is_active": "0",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("доч", response.json()["error"].lower())
        self.parent.refresh_from_db()
        child.refresh_from_db()
        self.assertTrue(self.parent.is_active)
        self.assertTrue(child.is_active)

    def test_collection_save_cannot_activate_child_under_inactive_parent(self):
        self.parent.is_active = False
        self.parent.save(update_fields=("is_active", "updated_at"))
        child = MerchCollection.objects.create(
            slug=self.child_slug,
            kind=MerchCollection.Kind.BRIGADE,
            parent=self.parent,
            name_uk="225",
            is_active=False,
        )
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("product_catalog_api_collection_save"),
            {
                "id": str(child.pk),
                "slug": child.slug,
                "kind": child.kind,
                "name_uk": child.name_uk,
                "parent_id": str(self.parent.pk),
                "is_active": "1",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("актив", response.json()["error"].lower())
        child.refresh_from_db()
        self.assertFalse(child.is_active)

    def test_collection_save_can_clear_existing_icon_and_cover(self):
        self.parent.icon = SimpleUploadedFile(
            "brigades.png",
            b"\x89PNG\r\n\x1a\n",
            content_type="image/png",
        )
        self.parent.cover_image = SimpleUploadedFile(
            "brigades-cover.png",
            b"\x89PNG\r\n\x1a\n",
            content_type="image/png",
        )
        self.parent.save(update_fields=("icon", "cover_image"))
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("product_catalog_api_collection_save"),
            {
                "id": str(self.parent.pk),
                "slug": self.parent.slug,
                "kind": self.parent.kind,
                "name_uk": self.parent.name_uk,
                "is_active": "1",
                "clear_icon": "1",
                "clear_cover": "1",
            },
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.parent.refresh_from_db()
        self.assertFalse(self.parent.icon)
        self.assertFalse(self.parent.cover_image)

    def test_collection_archive_refuses_active_children(self):
        MerchCollection.objects.create(
            slug=self.child_slug,
            kind=MerchCollection.Kind.BRIGADE,
            parent=self.parent,
            name_uk="225",
        )
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("product_catalog_api_collection_archive"),
            data=json.dumps({"id": self.parent.pk}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.parent.refresh_from_db()
        self.assertTrue(self.parent.is_active)

    def test_collection_reorder_updates_stable_order(self):
        second = MerchCollection.objects.create(
            slug=f"test-streetwear-{self.suffix}",
            kind=MerchCollection.Kind.THEME,
            name_uk="Streetwear",
            order=20,
        )
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("product_catalog_api_collection_reorder"),
            data=json.dumps({"ids": [second.pk, self.parent.pk]}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.parent.refresh_from_db()
        second.refresh_from_db()
        self.assertLess(second.order, self.parent.order)

    def test_catalog_category_rows_use_the_scoped_desktop_operations_style(self):
        template = (
            Path(__file__).resolve().parents[2]
            / "twocomms_django_theme"
            / "templates"
            / "pages"
            / "admin_panel.html"
        ).read_text(encoding="utf-8")
        stylesheet = (
            Path(__file__).resolve().parents[2]
            / "twocomms_django_theme"
            / "static"
            / "css"
            / "styles.css"
        ).read_text(encoding="utf-8")
        purged_stylesheet = (
            Path(__file__).resolve().parents[2]
            / "twocomms_django_theme"
            / "static"
            / "css"
            / "styles.purged.css"
        ).read_text(encoding="utf-8")

        self.assertIn('class="categories-grid catalog-category-list"', template)
        self.assertIn(".catalog-workspace .categories-grid", stylesheet)
        self.assertIn(".catalog-workspace .category-card", stylesheet)
        self.assertIn(".catalog-workspace .catalog-icon-button:focus-visible", stylesheet)
        self.assertIn(".catalog-workspace .catalogs-search-input", stylesheet)
        self.assertIn("color: #f3f4f6 !important", stylesheet)
        self.assertIn(".catalog-workspace .status-select .form-select", stylesheet)
        self.assertIn("height: 34px !important", stylesheet)
        self.assertIn("padding: 0.35rem 2rem 0.35rem 0.7rem !important", stylesheet)
        self.assertIn(".catalog-workspace .section-header {", stylesheet)
        self.assertIn('class="stat-badge-label">Категорії</span>', template)
        self.assertIn('class="stat-badge-label">Товари</span>', template)
        self.assertIn(".catalog-index-button", purged_stylesheet)
        self.assertIn(".catalog-workspace .catalogs-search-input{", purged_stylesheet)
        self.assertIn("color:#f3f4f6!important", purged_stylesheet)
        self.assertIn(
            ".catalog-workspace .section-header{border-bottom:1px solid rgba(240,162,90,.24)",
            purged_stylesheet,
        )
        self.assertRegex(
            stylesheet,
            r"\.catalog-taxonomy-actions \{[^}]*grid-column: 3;[^}]*grid-row: 2;",
        )
        self.assertIn("height: 32px;", stylesheet)
        self.assertIn("height: 30px;", stylesheet)
        self.assertIn("width: 28px;", stylesheet)
        self.assertRegex(
            stylesheet,
            r"\.catalog-taxonomy-roots \{[^}]*align-items: stretch;[^}]*grid-template-columns: repeat\(auto-fit, minmax\(230px, 1fr\)\);",
        )
        self.assertIn(
            ".catalog-workspace .status-select .form-select{background-color:#171d26!important",
            purged_stylesheet,
        )

    def test_taxonomy_rows_support_desktop_drag_reordering(self):
        row_template = (
            Path(__file__).resolve().parents[2]
            / "twocomms_django_theme"
            / "templates"
            / "partials"
            / "catalog_taxonomy_row.html"
        ).read_text(encoding="utf-8")
        page_template = (
            Path(__file__).resolve().parents[2]
            / "twocomms_django_theme"
            / "templates"
            / "pages"
            / "admin_panel.html"
        ).read_text(encoding="utf-8")

        self.assertIn('draggable="true"', row_template)
        self.assertIn("is-drop-target", page_template)
        self.assertIn("JSON.stringify({ids: ordered})", page_template)

    def test_taxonomy_manager_is_rendered_before_garment_categories(self):
        template = (
            Path(__file__).resolve().parents[2]
            / "twocomms_django_theme"
            / "templates"
            / "pages"
            / "admin_panel.html"
        ).read_text(encoding="utf-8")

        taxonomy_position = template.index('class="catalog-taxonomy-section"')
        categories_position = template.index('class="categories-admin-section"')
        self.assertLess(taxonomy_position, categories_position)

    @override_settings(CACHES=TEST_CACHES)
    def test_taxonomy_manager_groups_descendants_inside_root_board_panels(self):
        child = MerchCollection.objects.create(
            slug=self.child_slug,
            kind=MerchCollection.Kind.BRIGADE,
            parent=self.parent,
            name_uk="225",
            order=20,
        )
        grandchild = MerchCollection.objects.create(
            slug=f"test-225-collab-{self.suffix}",
            kind=MerchCollection.Kind.COLLAB,
            parent=child,
            name_uk="Колаборація 225",
            order=30,
        )
        self.client.force_login(self.staff)

        response = self.client.get(
            reverse("admin_panel"),
            {"section": "catalogs"},
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        group = next(
            item
            for item in response.context["merch_collection_groups"]
            if item["root"]["id"] == self.parent.pk
        )
        self.assertEqual(
            [item["id"] for item in group["descendants"]],
            [child.pk, grandchild.pk],
        )
        self.assertContains(
            response,
            'class="catalog-taxonomy-list catalog-taxonomy-board"',
            html=False,
        )
        self.assertContains(
            response,
            f'class="catalog-taxonomy-panel" role="none" data-root-id="{self.parent.pk}"',
            html=False,
        )

    def test_taxonomy_board_starts_compact_and_uses_one_shared_detail_shelf(self):
        template_root = Path(__file__).resolve().parents[2]
        template = (
            template_root
            / "twocomms_django_theme"
            / "templates"
            / "pages"
            / "admin_panel.html"
        ).read_text(encoding="utf-8")
        row_partial = (
            template_root
            / "twocomms_django_theme"
            / "templates"
            / "partials"
            / "catalog_taxonomy_row.html"
        ).read_text(encoding="utf-8")
        stylesheet = (
            template_root
            / "twocomms_django_theme"
            / "static"
            / "css"
            / "styles.css"
        ).read_text(encoding="utf-8")

        self.assertIn('class="catalog-taxonomy-roots"', template)
        self.assertIn('class="catalog-taxonomy-details"', template)
        self.assertIn('data-taxonomy-children-root="{{ group.root.id }}"', template)
        self.assertIn('aria-expanded="false"', row_partial)
        self.assertIn('aria-label="Розгорнути {{ collection.name_uk }}"', row_partial)
        self.assertIn("collapseSiblingRootBranches", template)
        self.assertIn("refreshTreeVisibility();", template)
        self.assertRegex(
            stylesheet,
            r"\.catalog-taxonomy-children \{[^}]*grid-template-columns: repeat\(auto-fit, minmax\(240px, 1fr\)\);",
        )
        self.assertIn(".catalog-taxonomy-children[hidden]", stylesheet)
        self.assertIn(
            ".catalog-taxonomy-panel .catalog-taxonomy-kind { display: none; }",
            stylesheet,
        )
        self.assertIn(
            ".catalog-taxonomy-panel .catalog-taxonomy-toggle { height: 20px; min-width: 22px; }",
            stylesheet,
        )

    def test_archived_taxonomy_node_has_an_explicit_restore_path(self):
        self.parent.is_active = False
        self.parent.save(update_fields=("is_active", "updated_at"))
        partial = (
            Path(__file__).resolve().parents[2]
            / "twocomms_django_theme"
            / "templates"
            / "partials"
            / "catalog_taxonomy_row.html"
        ).read_text(encoding="utf-8")

        self.assertIn('data-restore-intent="1"', partial)
        self.assertIn('aria-label="Відновити {{ collection.name_uk }}"', partial)

    def test_archived_taxonomy_node_stays_visible_and_can_be_reactivated(self):
        self.parent.is_active = False
        self.parent.indexable = False
        self.parent.save(update_fields=("is_active", "indexable"))
        self.client.force_login(self.staff)

        response = self.client.get(reverse("admin_panel"), {"section": "catalogs"})

        self.assertEqual(response.status_code, 200)
        row = next(
            item
            for item in response.context["merch_collections_payload"]
            if item["id"] == self.parent.pk
        )
        self.assertFalse(row["is_active"])
        self.assertContains(response, f'data-collection-id="{self.parent.pk}"', html=False)

        saved = self.client.post(
            reverse("product_catalog_api_collection_save"),
            {
                "id": str(self.parent.pk),
                "slug": self.parent.slug,
                "kind": self.parent.kind,
                "name_uk": self.parent.name_uk,
                "is_active": "1",
            },
        )

        self.assertEqual(saved.status_code, 200, saved.content)
        self.parent.refresh_from_db()
        self.assertTrue(self.parent.is_active)

    def test_taxonomy_tree_exposes_real_expand_and_collapse_controls(self):
        template_root = Path(__file__).resolve().parents[2]
        template = (
            template_root
            / "twocomms_django_theme"
            / "templates"
            / "pages"
            / "admin_panel.html"
        ).read_text(encoding="utf-8")
        row_partial = (
            template_root
            / "twocomms_django_theme"
            / "templates"
            / "partials"
            / "catalog_taxonomy_row.html"
        ).read_text(encoding="utf-8")

        self.assertIn('data-taxonomy-action="toggle"', row_partial)
        self.assertIn("setBranchExpanded", template)
        self.assertIn("refreshTreeVisibility", template)

    def test_catalog_taxonomy_renders_exact_depth_for_future_descendants(self):
        child = MerchCollection.objects.create(
            slug=self.child_slug,
            kind=MerchCollection.Kind.BRIGADE,
            parent=self.parent,
            name_uk="225",
            order=20,
        )
        grandchild = MerchCollection.objects.create(
            slug=f"test-225-collab-{self.suffix}",
            kind=MerchCollection.Kind.COLLAB,
            parent=child,
            name_uk="Колаборація 225",
            order=30,
        )
        self.client.force_login(self.staff)

        response = self.client.get(reverse("admin_panel"), {"section": "catalogs"})

        self.assertEqual(response.status_code, 200)
        row = next(
            item
            for item in response.context["merch_collections_payload"]
            if item["id"] == grandchild.pk
        )
        self.assertEqual(row["depth"], 2)
        self.assertContains(
            response,
            f'data-collection-id="{grandchild.pk}" data-taxonomy-depth="2"',
            html=False,
        )
        self.assertContains(response, 'aria-level="3"', html=False)
