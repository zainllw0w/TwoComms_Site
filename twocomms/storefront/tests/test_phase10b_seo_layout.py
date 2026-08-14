"""
Phase 10b — tabs layout, pricing table, intro section, seed migration.

Covers:
  * ``get_category_seo_layout`` — splits blocks into ``tab_blocks`` (in
    canonical order) and ``best_prices``, drops empty entries, exposes
    ``has_any``.
  * Catalog template — renders intro section above grid, tabs component
    below grid, pricing table when ``best_prices`` has items.
  * Seed migration — populated SEO copy + structured blocks for
    ``hoodie``/``tshirts``/``long-sleeve`` if categories exist (smoke
    test using fixtures created in setUp).
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import re
import tempfile
from unittest.mock import patch

from django.core.cache import cache, caches
from django.core.cache.backends.filebased import FileBasedCache
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import translation

from productcolors.models import Color, ProductColorVariant

from storefront.models import (
    Category,
    CategoryColorLanding,
    CategorySeoBlock,
    CategorySeoBlockItem,
    Product,
)
from storefront.services.category_seo_blocks import (
    TAB_BLOCK_TYPES,
    get_category_seo_blocks,
    get_category_seo_layout,
)
from storefront.services.catalog_helpers import (
    PUBLIC_CATEGORY_COLOR_LANDING_VERSION_CACHE_KEY,
    bump_public_category_color_landing_version,
)
from storefront.views.catalog import (
    _catalog_cache_prefix,
    catalog,
    thematic_landing,
)
from storefront.views.utils import _build_anon_cache_key


class _BasePhase10bTests(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        caches["fragments"].clear()
        merchant_patcher = patch(
            "storefront.signals.generate_google_merchant_feed_task.apply_async"
        )
        indexnow_patcher = patch("storefront.signals.enqueue_indexnow_urls")
        self.addCleanup(merchant_patcher.stop)
        self.addCleanup(indexnow_patcher.stop)
        merchant_patcher.start()
        indexnow_patcher.start()

        self.category = Category.objects.create(
            name="Худі", slug="hoodie", is_active=True,
        )
        self.product = Product.objects.create(
            title="Худі ZSU", slug="hoodi-zsu",
            category=self.category, price=1490, status="published",
            priority=10,
        )
        self.black = Color.objects.create(name="Чорний", primary_hex="#111111")

    def _landing(self, **overrides):
        payload = {
            "category": self.category,
            "color": self.black,
            "color_slug": "black",
            "seo_title": "Чорні худі",
            "seo_h1": "Чорні худі TwoComms",
            "seo_description": "Добірка чорних худі TwoComms.",
            "editorial_html": "x" * CategoryColorLanding.MIN_EDITORIAL_LENGTH,
            "is_published": True,
            "order": 0,
        }
        payload.update(overrides)
        return CategoryColorLanding.objects.create(**payload)

    def _publish_black_variant(self, *, product=None, stock=0):
        return ProductColorVariant.objects.create(
            product=product or self.product,
            color=self.black,
            is_default=True,
            stock=stock,
        )


class CategorySeoLayoutServiceTests(_BasePhase10bTests):
    def _block(self, btype, items, **kwargs):
        block = CategorySeoBlock.objects.create(
            category=self.category, block_type=btype,
            title=kwargs.get("title", btype),
            is_active=kwargs.get("is_active", True),
            order=kwargs.get("order", 0),
        )
        for idx, payload in enumerate(items):
            CategorySeoBlockItem.objects.create(
                block=block,
                label=payload["label"],
                url=payload.get("url", ""),
                extra=payload.get("extra") or {},
                order=idx,
            )
        return block

    def test_layout_excludes_stored_query_rails_and_preserves_owned_blocks(self):
        # Insert blocks in REVERSE canonical order with random ``order`` values.
        self._block("top_cards",
                    [{"label": "card", "extra": {"product_id": self.product.id}}],
                    order=5)
        self._block("top_queries", [{"label": "q", "url": "/catalog/hoodie/"}],
                    order=1)
        self._block("top_filters", [{"label": "f", "url": "/catalog/hoodie/"}],
                    order=99)
        self._block("top_menu", [{"label": "m", "url": "/catalog/hoodie/"}],
                    order=10)

        layout = get_category_seo_layout(self.category)
        types = [e["block"].block_type for e in layout["tab_blocks"]]
        self.assertEqual(types, ["top_menu", "top_cards"])
        self.assertEqual(tuple(TAB_BLOCK_TYPES), ("top_menu", "color_landings", "top_cards"))
        self.assertTrue(
            CategorySeoBlock.objects.filter(
                category=self.category,
                block_type="top_filters",
            ).exists()
        )
        self.assertTrue(
            CategorySeoBlock.objects.filter(
                category=self.category,
                block_type="top_queries",
            ).exists()
        )
        self.assertTrue(layout["has_any"])

    def test_scoped_block_loader_hides_legacy_rails_without_deleting_rows(self):
        self._block(
            "top_filters",
            [{"label": "legacy filter", "url": "/catalog/hoodie/"}],
        )
        self._block(
            "top_queries",
            [{"label": "legacy query", "url": "/catalog/hoodie/"}],
        )
        self._block(
            "top_cards",
            [{"label": "owned card", "extra": {"product_id": self.product.id}}],
        )

        scoped = get_category_seo_blocks(
            self.category,
            block_types=("top_menu", "top_cards", "best_prices"),
        )

        self.assertEqual(
            [entry["block"].block_type for entry in scoped],
            ["top_cards"],
        )
        self.assertTrue(
            CategorySeoBlock.objects.filter(
                category=self.category,
                block_type__in=("top_filters", "top_queries"),
            ).count() == 2
        )

    def test_uk_layout_adds_only_published_color_owner_with_inventory(self):
        self._publish_black_variant()
        self._landing(
            seo_h1="Дуже довгий SEO H1, який не повинен дублюватися у навігації",
        )

        with translation.override("uk"):
            layout = get_category_seo_layout(self.category)

        rail = next(
            entry
            for entry in layout["tab_blocks"]
            if entry["block"].block_type == "color_landings"
        )
        self.assertEqual([item.label for item in rail["items"]], [self.black.name])
        self.assertEqual(
            [item.url for item in rail["items"]],
            [reverse(
                "catalog_by_cat_color",
                kwargs={"cat_slug": self.category.slug, "color_slug": "black"},
            )],
        )

    def test_stored_color_landing_block_cannot_override_uk_owner_rail(self):
        self._block(
            "color_landings",
            [{"label": "Injected owner", "url": "https://example.com/injected"}],
        )
        self._publish_black_variant()
        self._landing()

        with translation.override("uk"):
            layout = get_category_seo_layout(self.category)

        rail = next(
            entry
            for entry in layout["tab_blocks"]
            if entry["block"].block_type == "color_landings"
        )
        self.assertEqual(
            [(item.label, item.url) for item in rail["items"]],
            [(
                self.black.name,
                reverse(
                    "catalog_by_cat_color",
                    kwargs={
                        "cat_slug": self.category.slug,
                        "color_slug": "black",
                    },
                ),
            )],
        )

    def test_stored_color_landing_block_is_hidden_outside_uk(self):
        self._block(
            "color_landings",
            [{"label": "Injected owner", "url": "/catalog/hoodie/injected/"}],
        )

        for language in ("ru", "en"):
            with self.subTest(language=language), translation.override(language):
                layout = get_category_seo_layout(self.category)
                self.assertNotIn(
                    "color_landings",
                    [entry["block"].block_type for entry in layout["tab_blocks"]],
                )

    def test_color_owner_rail_excludes_unpublished_empty_wrong_color_and_foreign_landings(self):
        self._landing(is_published=False)
        empty_color = Color.objects.create(name="Кайот", primary_hex="#A98463")
        self._landing(
            color=empty_color,
            color_slug="coyote",
            seo_title="Худі кольору кайот",
            seo_h1="Худі кольору кайот",
            order=1,
        )
        wrong_color = Color.objects.create(name="Білий", primary_hex="#FFFFFF")
        ProductColorVariant.objects.create(
            product=self.product,
            color=wrong_color,
            is_default=True,
            stock=5,
        )
        wrong_landing_color = Color.objects.create(name="Зелений", primary_hex="#008000")
        self._landing(
            color=wrong_landing_color,
            color_slug="green",
            seo_title="Зелені худі",
            seo_h1="Зелені худі",
            order=2,
        )
        foreign_category = Category.objects.create(
            name="Футболки",
            slug="tshirts-rail",
            is_active=True,
        )
        foreign_product = Product.objects.create(
            title="Foreign T-shirt",
            slug="foreign-tshirt-rail",
            category=foreign_category,
            price=900,
            status="published",
        )
        ProductColorVariant.objects.create(
            product=foreign_product,
            color=self.black,
            is_default=True,
            stock=5,
        )
        self._landing(
            category=foreign_category,
            seo_title="Чорні футболки",
            seo_h1="Чорні футболки",
        )

        with translation.override("uk"):
            layout = get_category_seo_layout(self.category)

        self.assertNotIn(
            "color_landings",
            [entry["block"].block_type for entry in layout["tab_blocks"]],
        )

    def test_color_owner_rail_requires_published_status_but_not_stock(self):
        self._landing()
        for status in ("draft", "archived"):
            product = Product.objects.create(
                title=f"{status.title()} hoodie",
                slug=f"{status}-hoodie-rail",
                category=self.category,
                price=1490,
                status=status,
            )
            self._publish_black_variant(product=product, stock=7)

        with translation.override("uk"):
            hidden_layout = get_category_seo_layout(self.category)

        self.assertNotIn(
            "color_landings",
            [entry["block"].block_type for entry in hidden_layout["tab_blocks"]],
        )

        self._publish_black_variant(stock=0)
        with translation.override("uk"):
            visible_layout = get_category_seo_layout(self.category)

        rail = next(
            entry
            for entry in visible_layout["tab_blocks"]
            if entry["block"].block_type == "color_landings"
        )
        self.assertEqual([item.label for item in rail["items"]], [self.black.name])

    def test_color_owner_rail_requires_active_current_category(self):
        self._publish_black_variant()
        self._landing()
        self.category.is_active = False
        self.category.save(update_fields=["is_active"])

        with translation.override("uk"):
            layout = get_category_seo_layout(self.category)

        self.assertNotIn(
            "color_landings",
            [entry["block"].block_type for entry in layout["tab_blocks"]],
        )

    def test_color_owner_rail_is_deterministic_and_uses_short_color_names(self):
        coyote = Color.objects.create(name="Кайот", primary_hex="#A98463")
        ProductColorVariant.objects.create(
            product=self.product,
            color=coyote,
            is_default=True,
        )
        self._publish_black_variant()
        later = self._landing(order=20)
        earlier = self._landing(
            color=coyote,
            color_slug="coyote",
            seo_title="Худі кольору кайот",
            seo_h1="",
            order=10,
        )

        with translation.override("uk"):
            layout = get_category_seo_layout(self.category)

        rail = next(
            entry
            for entry in layout["tab_blocks"]
            if entry["block"].block_type == "color_landings"
        )
        self.assertEqual(
            [(item.label, item.url) for item in rail["items"]],
            [
                (coyote.name, f"/catalog/{self.category.slug}/coyote/"),
                (self.black.name, f"/catalog/{self.category.slug}/black/"),
            ],
        )

    def test_color_owner_rail_publishes_only_first_owner_per_color(self):
        self._publish_black_variant()
        first_owner = self._landing(color_slug="black-primary", order=10)
        self._landing(color_slug="black-alias", order=20)

        with translation.override("uk"):
            layout = get_category_seo_layout(self.category)

        rail = next(
            entry
            for entry in layout["tab_blocks"]
            if entry["block"].block_type == "color_landings"
        )
        self.assertEqual(
            [(item.label, item.url) for item in rail["items"]],
            [(
                self.black.name,
                reverse(
                    "catalog_by_cat_color",
                    kwargs={
                        "cat_slug": self.category.slug,
                        "color_slug": first_owner.color_slug,
                    },
                ),
            )],
        )

    def test_ru_and_en_layouts_do_not_publish_uk_color_owner(self):
        self._publish_black_variant()
        self._landing()

        for language in ("ru", "en"):
            with self.subTest(language=language), translation.override(language):
                layout = get_category_seo_layout(self.category)
                self.assertNotIn(
                    "color_landings",
                    [entry["block"].block_type for entry in layout["tab_blocks"]],
                )

    def test_best_prices_returned_separately_from_tabs(self):
        self._block("best_prices",
                    [{"label": "Худі", "extra": {"product_id": self.product.id, "price": 1490}}])
        self._block("top_filters",
                    [{"label": "Чорний", "url": "/catalog/hoodie/?color=black"}])
        layout = get_category_seo_layout(self.category)
        # ``best_prices`` is NEVER in tab_blocks.
        self.assertNotIn(
            "best_prices",
            [e["block"].block_type for e in layout["tab_blocks"]],
        )
        self.assertIsNotNone(layout["best_prices"])
        self.assertEqual(layout["best_prices"]["block"].block_type, "best_prices")

    def test_empty_blocks_and_pricing_with_no_items_dropped(self):
        # top_filters with NO items at all → service drops the block.
        CategorySeoBlock.objects.create(
            category=self.category, block_type="top_filters",
            title="filters", is_active=True,
        )
        # best_prices with NO items at all → layout returns None.
        CategorySeoBlock.objects.create(
            category=self.category, block_type="best_prices",
            title="prices", is_active=True,
        )
        layout = get_category_seo_layout(self.category)
        self.assertEqual(
            [entry["block"].block_type for entry in layout["tab_blocks"]],
            ["top_menu"],
        )
        self.assertIsNone(layout["best_prices"])
        self.assertTrue(layout["has_any"])

    def test_layout_for_none_category(self):
        layout = get_category_seo_layout(None)
        self.assertEqual(layout, {"tab_blocks": [], "best_prices": None, "has_any": False})


class CategoryColorLandingCatalogCacheTests(_BasePhase10bTests):
    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()
        self.catalog_request = self.factory.get("/catalog/hoodie/")
        self.thematic_request = self.factory.get("/catalog/theme/streetwear/")

    def _prefixes(self):
        return (
            _catalog_cache_prefix(self.catalog_request, catalog),
            _catalog_cache_prefix(self.thematic_request, thematic_landing),
        )

    def _assert_only_catalog_prefix_changed(self, before):
        after = self._prefixes()
        self.assertNotEqual(after[0], before[0])
        self.assertEqual(after[1], before[1])

    def test_create_color_landing_invalidates_only_catalog_page_cache(self):
        before = self._prefixes()

        with self.captureOnCommitCallbacks(execute=True):
            self._landing()

        self._assert_only_catalog_prefix_changed(before)

    def test_color_landing_save_invalidates_only_catalog_page_cache(self):
        landing = self._landing(is_published=False)
        before = self._prefixes()

        with self.captureOnCommitCallbacks(execute=True):
            landing.is_published = True
            landing.save(update_fields=["is_published"])

        self._assert_only_catalog_prefix_changed(before)

    def test_delete_color_landing_invalidates_only_catalog_page_cache(self):
        landing = self._landing()
        before = self._prefixes()

        with self.captureOnCommitCallbacks(execute=True):
            landing.delete()

        self._assert_only_catalog_prefix_changed(before)

    def test_color_landing_generation_is_unique_under_concurrent_file_cache_bumps(self):
        with tempfile.TemporaryDirectory() as cache_dir:
            backend = FileBasedCache(cache_dir, {"OPTIONS": {}})
            key = PUBLIC_CATEGORY_COLOR_LANDING_VERSION_CACHE_KEY
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [
                    pool.submit(
                        bump_public_category_color_landing_version,
                        backend,
                    )
                    for _ in range(2)
                ]
                returned = [future.result(timeout=10) for future in futures]

            self.assertEqual(len(set(returned)), 2)
            self.assertIn(backend.get(key), returned)

    def test_catalog_page_cache_key_keeps_full_token_within_backend_limit(self):
        token = "f" * 32
        with patch(
            "storefront.views.catalog.get_public_category_color_landing_version",
            return_value=token,
        ):
            prefix = _catalog_cache_prefix(self.catalog_request, catalog)

        raw_key = _build_anon_cache_key(
            self.catalog_request,
            catalog,
            key_prefix=prefix,
            query_string="",
        )
        backend_key = cache.make_key(raw_key)

        self.assertIn(f":cl:{token}:", backend_key)
        self.assertLessEqual(len(backend_key.encode("utf-8")), 250)


class CatalogIntegrationLayoutTests(_BasePhase10bTests):
    def test_intro_section_rendered_above_products_when_set(self):
        self.category.seo_intro_html = (
            '<p>Patriotic <strong>hoodie</strong> intro</p>'
            '<details><summary>Що таке худі?</summary><p>Hoodies info.</p></details>'
        )
        self.category.save(update_fields=["seo_intro_html"])
        response = self.client.get(reverse("catalog_by_cat",
                                           kwargs={"cat_slug": self.category.slug}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "catalog-category-intro")
        self.assertContains(response, "Patriotic")
        self.assertContains(response, "Що таке худі?")

    def test_intro_section_skipped_when_empty(self):
        self.assertEqual(self.category.seo_intro_html, "")
        response = self.client.get(reverse("catalog_by_cat",
                                           kwargs={"cat_slug": self.category.slug}))
        self.assertNotContains(response, "catalog-category-intro")

    def test_page_two_keeps_products_but_omits_page_one_editorial_sections(self):
        self.category.seo_intro_html = "PAGE_ONE_INTRO_ONLY"
        self.category.description = "PAGE_ONE_DESCRIPTION_ONLY"
        self.category.save(update_fields=["seo_intro_html", "description"])
        block = CategorySeoBlock.objects.create(
            category=self.category,
            block_type="top_cards",
            title="PAGE_ONE_SEO_TABS_ONLY",
            is_active=True,
        )
        CategorySeoBlockItem.objects.create(
            block=block,
            label="PAGE_ONE_SEO_LINK_ONLY",
            url="/catalog/hoodie/",
        )
        Product.objects.create(
            title="Second hoodie",
            slug="second-hoodie",
            category=self.category,
            price=1500,
            status="published",
        )

        with patch("storefront.views.catalog.PRODUCTS_PER_PAGE", 1):
            page_one = self.client.get(
                reverse("catalog_by_cat", kwargs={"cat_slug": self.category.slug})
            )
            page_two = self.client.get(
                reverse("catalog_by_cat", kwargs={"cat_slug": self.category.slug})
                + "?page=2"
            )

        self.assertContains(page_one, "PAGE_ONE_INTRO_ONLY")
        self.assertContains(page_one, "PAGE_ONE_DESCRIPTION_ONLY")
        self.assertContains(page_one, "PAGE_ONE_SEO_TABS_ONLY")
        self.assertContains(page_one, "PAGE_ONE_SEO_LINK_ONLY")
        self.assertEqual(page_two.status_code, 200)
        self.assertContains(page_two, "Second hoodie")
        self.assertContains(page_two, "?page=2")
        self.assertNotContains(page_two, "PAGE_ONE_INTRO_ONLY")
        self.assertNotContains(page_two, "PAGE_ONE_DESCRIPTION_ONLY")
        self.assertNotContains(page_two, "PAGE_ONE_SEO_TABS_ONLY")
        self.assertNotContains(page_two, "PAGE_ONE_SEO_LINK_ONLY")

        # The legacy catalog branch must obey the same page-1 editorial rule.
        with patch("storefront.views.catalog.SMART_SELECTOR_CATEGORY_SLUGS", ()):
            non_smart_page_two = self.client.get(
                reverse("catalog_by_cat", kwargs={"cat_slug": self.category.slug})
                + "?page=2"
            )
        self.assertEqual(non_smart_page_two.status_code, 200)
        self.assertContains(non_smart_page_two, "Second hoodie")
        self.assertContains(non_smart_page_two, "?page=2")
        self.assertNotContains(non_smart_page_two, "PAGE_ONE_INTRO_ONLY")
        self.assertNotContains(non_smart_page_two, "PAGE_ONE_DESCRIPTION_ONLY")
        self.assertNotContains(non_smart_page_two, "PAGE_ONE_SEO_TABS_ONLY")
        self.assertNotContains(non_smart_page_two, "PAGE_ONE_SEO_LINK_ONLY")

    def test_tabs_component_renders_only_owned_public_rails(self):
        self._publish_black_variant()
        self._landing(
            seo_h1="Дуже довгий SEO H1, який не повинен дублюватися у навігації",
        )
        for btype, label in (
            ("top_filters", "Чорний худі"),
            ("top_menu", "Усі худі"),
            ("top_queries", "Купити ЗСУ худі"),
        ):
            block = CategorySeoBlock.objects.create(
                category=self.category, block_type=btype,
                title=btype, is_active=True,
            )
            CategorySeoBlockItem.objects.create(
                block=block, label=label, url="/catalog/hoodie/",
            )
            if btype == "top_menu":
                CategorySeoBlockItem.objects.create(
                    block=block,
                    label="Кастомний друк",
                    url="/custom-print/",
                    order=1,
                )
        with translation.override("uk"):
            response = self.client.get(reverse(
                "catalog_by_cat",
                kwargs={"cat_slug": self.category.slug},
            ))
        self.assertContains(response, 'data-seo-tab-trigger="top_menu"')
        self.assertContains(response, 'data-seo-tab-trigger="color_landings"')
        self.assertNotContains(response, 'data-seo-tab-trigger="top_filters"')
        self.assertNotContains(response, 'data-seo-tab-trigger="top_queries"')
        self.assertContains(response, f'href="/catalog/{self.category.slug}/black/"')
        self.assertContains(
            response,
            f'<a class="seo-tab-link" href="/catalog/{self.category.slug}/black/">Чорний</a>',
            html=False,
        )
        self.assertNotContains(
            response,
            "Дуже довгий SEO H1, який не повинен дублюватися у навігації",
        )
        self.assertContains(response, 'href="/custom-print/"')
        # Smart Selector stays interactive; its UI-state query URL is not part
        # of the editorial SEO rail and must remain available to users.
        self.assertContains(
            response,
            '<fieldset data-smart-filter-section="color">',
            html=False,
        )
        color_fieldset = re.search(
            r'<fieldset data-smart-filter-section="color">.*?</fieldset>',
            response.content.decode(),
            flags=re.DOTALL,
        )
        self.assertIsNotNone(color_fieldset)
        self.assertIn(
            f'href="/catalog/{self.category.slug}/?color=black"',
            color_fieldset.group(),
        )
        # First tab in canonical order (``top_menu``) should be the active one.
        self.assertContains(response, 'data-seo-tab-panel="top_menu"')

    def test_category_view_loads_stored_seo_blocks_once(self):
        with (
            patch(
                "storefront.views.catalog.get_category_seo_blocks",
                wraps=get_category_seo_blocks,
            ) as view_loader,
            patch(
                "storefront.services.category_seo_blocks.get_category_seo_blocks",
                wraps=get_category_seo_blocks,
            ) as layout_loader,
        ):
            response = self.client.get(reverse(
                "catalog_by_cat",
                kwargs={"cat_slug": self.category.slug},
            ))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(view_loader.call_count + layout_loader.call_count, 1)
        view_loader.assert_called_once_with(
            self.category,
            block_types=("top_menu", "top_cards", "best_prices"),
        )

    def test_ru_and_en_category_html_do_not_link_uk_color_owner(self):
        self._publish_black_variant()
        self._landing()

        for language in ("ru", "en"):
            with self.subTest(language=language), translation.override(language):
                url = reverse(
                    "catalog_by_cat",
                    kwargs={"cat_slug": self.category.slug},
                )
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(
                    response,
                    'data-seo-tab-trigger="color_landings"',
                )
                self.assertNotContains(
                    response,
                    f'href="/catalog/{self.category.slug}/black/"',
                )

    def test_pricing_table_renders_with_price_label(self):
        block = CategorySeoBlock.objects.create(
            category=self.category, block_type="best_prices",
            title="Найкращі ціни", is_active=True,
        )
        CategorySeoBlockItem.objects.create(
            block=block, label="Худі ZSU patriot", url="/product/x/",
            extra={"product_id": self.product.id, "price": 1490},
        )
        response = self.client.get(reverse("catalog_by_cat",
                                           kwargs={"cat_slug": self.category.slug}))
        self.assertContains(response, "seo-pricing__table")
        self.assertContains(response, "1490")
        self.assertContains(response, "грн")

    def test_layout_context_present_on_category_root_with_no_blocks(self):
        response = self.client.get(reverse("catalog_by_cat",
                                           kwargs={"cat_slug": self.category.slug}))
        layout = response.context["category_seo_layout"]
        self.assertEqual(
            [entry["block"].block_type for entry in layout["tab_blocks"]],
            ["top_menu"],
        )
        self.assertIsNone(layout["best_prices"])
        self.assertTrue(layout["has_any"])


class SeedMigrationSmokeTests(TestCase):
    """Phase 10b — re-run the seed function in a fresh transaction and
    assert it populated copy + blocks for the live category slugs."""

    def setUp(self):
        super().setUp()
        cache.clear()
        caches["fragments"].clear()
        merchant_patcher = patch(
            "storefront.signals.generate_google_merchant_feed_task.apply_async"
        )
        indexnow_patcher = patch("storefront.signals.enqueue_indexnow_urls")
        self.addCleanup(merchant_patcher.stop)
        self.addCleanup(indexnow_patcher.stop)
        merchant_patcher.start()
        indexnow_patcher.start()

        # Build empty-stub categories matching the production slugs so
        # the seed function has something to write to.
        self.cats = {}
        for slug, name in (
            ("hoodie", "Худі"),
            ("tshirts", "Футболки"),
            ("long-sleeve", "Лонгсліви"),
        ):
            self.cats[slug] = Category.objects.create(
                name=name, slug=slug, is_active=True,
            )

    def test_seed_populates_copy_and_blocks(self):
        # Re-import the function — it's not part of public API but stable.
        from importlib import import_module
        seed = import_module(
            "storefront.migrations.0053_phase10b_seed_category_seo"
        )
        from django.apps import apps

        seed.seed_seo_copy(apps, schema_editor=None)

        for slug in ("hoodie", "tshirts", "long-sleeve"):
            cat = Category.objects.get(slug=slug)
            self.assertTrue(cat.seo_intro_html.strip(),
                            msg=f"intro empty for {slug}")
            self.assertTrue(cat.description.strip(),
                            msg=f"description empty for {slug}")
            self.assertTrue(cat.seo_text_title.strip(),
                            msg=f"seo_text_title empty for {slug}")
            block_types = set(
                CategorySeoBlock.objects.filter(category=cat, is_active=True)
                .values_list("block_type", flat=True)
            )
            # best_prices is conditional on having Products; the others
            # must always seed.
            self.assertTrue({"top_menu", "top_filters", "top_queries"} <= block_types,
                            msg=f"missing tab blocks for {slug}: {block_types}")

    def test_seed_idempotent_on_second_run(self):
        from importlib import import_module
        seed = import_module(
            "storefront.migrations.0053_phase10b_seed_category_seo"
        )
        from django.apps import apps
        seed.seed_seo_copy(apps, schema_editor=None)
        before_count = CategorySeoBlock.objects.count()
        # Manually edit a description — second run must NOT overwrite.
        cat = Category.objects.get(slug="hoodie")
        cat.description = "<p>Manual edit</p>"
        cat.save(update_fields=["description"])

        seed.seed_seo_copy(apps, schema_editor=None)
        cat.refresh_from_db()
        self.assertIn("Manual edit", cat.description)
        self.assertEqual(CategorySeoBlock.objects.count(), before_count,
                         msg="seed re-run should not duplicate blocks")
