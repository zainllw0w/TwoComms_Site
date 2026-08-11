import json
from pathlib import Path
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from product_catalog.models import MerchCollection


class TaxonomyAdminApiTests(TestCase):
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
                "icon": SimpleUploadedFile(
                    "225.png",
                    b"\x89PNG\r\n\x1a\n",
                    content_type="image/png",
                ),
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
        self.assertIn(".catalog-index-button", purged_stylesheet)
