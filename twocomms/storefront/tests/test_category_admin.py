from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import Resolver404, resolve, reverse

from storefront.forms import CategoryForm
from storefront.models import Category, Product


class CategoryAdminTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username="category-staff",
            password="secret",
            is_staff=True,
        )
        self.customer = get_user_model().objects.create_user(
            username="category-customer",
            password="secret",
        )
        self.category = Category.objects.create(
            name="Футболки",
            slug="tshirts",
            is_active=False,
            is_featured=True,
        )

    def test_category_editor_uses_canonical_catalog_routes_and_removes_public_duplicate(self):
        self.assertEqual(
            reverse("admin_category_new"),
            "/admin-panel/catalog/categories/new/",
        )
        self.assertEqual(
            reverse("admin_category_edit", args=[self.category.pk]),
            f"/admin-panel/catalog/categories/{self.category.pk}/edit/",
        )
        with self.assertRaises(Resolver404):
            resolve("/add-category/")
        with self.assertRaises(Resolver404):
            resolve("/admin-panel/category/new/")

    def test_category_editor_is_staff_only(self):
        self.client.force_login(self.customer)

        self.assertEqual(self.client.get(reverse("admin_category_new")).status_code, 302)
        self.assertEqual(
            self.client.get(reverse("admin_category_edit", args=[self.category.pk])).status_code,
            302,
        )

    def test_category_form_exposes_seo_and_status_without_overwriting_existing_flags(self):
        expected = {
            "name",
            "slug",
            "icon",
            "cover",
            "order",
            "description",
            "is_active",
            "is_featured",
            "seo_title",
            "seo_h1",
            "seo_description",
            "seo_text_title",
            "seo_intro_html",
        }
        form = CategoryForm(instance=self.category)
        self.assertTrue(expected.issubset(form.fields))

        form = CategoryForm(
            data={
                "name": self.category.name,
                "slug": self.category.slug,
                "order": self.category.order,
                "description": "Оновлений опис",
                "is_featured": "on",
            },
            instance=self.category,
        )
        self.assertTrue(form.is_valid(), form.errors)
        updated = form.save()
        self.assertFalse(updated.is_active)
        self.assertTrue(updated.is_featured)

    def test_category_form_reports_duplicate_slug(self):
        form = CategoryForm(
            data={"name": "Інша категорія", "slug": self.category.slug, "order": 20}
        )

        self.assertFalse(form.is_valid())
        self.assertIn("вже існує", form.errors["slug"][0])

    def test_staff_category_form_is_structured_and_returns_to_catalog_admin(self):
        self.client.force_login(self.staff)

        response = self.client.get(reverse("admin_category_edit", args=[self.category.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="catalog-category-editor"', html=False)
        self.assertContains(response, 'data-category-section="seo"', html=False)
        self.assertContains(response, 'data-category-media-preview="icon"', html=False)
        self.assertNotContains(response, "form.as_p")
        self.assertContains(response, '/admin-panel/?section=catalogs', html=False)

    def test_category_delete_is_post_only_and_refuses_nonempty_category(self):
        self.client.force_login(self.staff)
        delete_url = reverse("admin_category_delete", args=[self.category.pk])

        self.assertEqual(self.client.get(delete_url).status_code, 405)
        Product.objects.create(
            title="Товар категорії",
            slug="category-product",
            category=self.category,
            price=1000,
        )
        response = self.client.post(delete_url)
        self.assertEqual(response.status_code, 409)
        self.assertTrue(Category.objects.filter(pk=self.category.pk).exists())

    def test_catalog_template_posts_category_delete_and_uses_canonical_create_route(self):
        template = (
            Path(__file__).resolve().parents[2]
            / "twocomms_django_theme"
            / "templates"
            / "pages"
            / "admin_panel.html"
        ).read_text(encoding="utf-8")

        self.assertIn("{% url 'admin_category_new' %}", template)
        self.assertIn("data-delete-endpoint=\"{% url 'admin_category_delete' category.id %}\"", template)
        self.assertIn('data-action="indexnow-submit" data-index-state="idle" data-target-type="all"', template)
        self.assertIn('data-action="google-indexing-submit" data-index-state="idle" data-target-type="all"', template)
        self.assertIn('id="catalog-index-live"', template)
        self.assertIn('role="status" aria-live="polite"', template)
        self.assertIn('role="treeitem"', template)
        self.assertIn('aria-expanded=', template)
        self.assertIn('title="{{ category.name }}"', template)
        self.assertIn('title="{{ product.title }}"', template)
        self.assertIn("method: 'POST'", template)
