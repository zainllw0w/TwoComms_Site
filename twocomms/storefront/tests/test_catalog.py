"""
Regression tests for storefront home/catalog/search endpoints.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache, caches
from django.test import TestCase
from django.urls import reverse

from productcolors.models import Color, ProductColorVariant
from storefront.models import Category, Product


class CatalogViewTestCase(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        caches["fragments"].clear()
        merchant_patcher = patch("storefront.signals.generate_google_merchant_feed_task.apply_async")
        indexnow_patcher = patch("storefront.signals.enqueue_indexnow_urls")
        self.addCleanup(merchant_patcher.stop)
        self.addCleanup(indexnow_patcher.stop)
        merchant_patcher.start()
        indexnow_patcher.start()
        self.category = Category.objects.create(
            name="Category 1",
            slug="category-1",
            is_active=True,
        )
        self.other_category = Category.objects.create(
            name="Category 2",
            slug="category-2",
            is_active=True,
        )

    def create_product(
        self,
        *,
        title: str,
        slug: str,
        category: Category | None = None,
        price: int = 100,
        description: str = "",
        status: str = "published",
        featured: bool = False,
    ) -> Product:
        return Product.objects.create(
            title=title,
            slug=slug,
            category=category or self.category,
            price=price,
            description=description,
            status=status,
            featured=featured,
        )


class HomeViewTests(CatalogViewTestCase):
    def test_home_page_loads_with_published_products_only(self):
        published = self.create_product(title="Published Product", slug="published-product", featured=True)
        self.create_product(title="Draft Product", slug="draft-product", status="draft")

        response = self.client.get(reverse("home"))
        product_titles = [product.title for product in response.context["products"]]

        self.assertEqual(response.status_code, 200)
        self.assertIn(published.title, product_titles)
        self.assertNotIn("Draft Product", product_titles)
        self.assertEqual(response.context["featured"].pk, published.pk)

    def test_home_page_caches_anonymous_response(self):
        self.create_product(title="Cached Product", slug="cached-product")

        first = self.client.get(reverse("home"))
        second = self.client.get(reverse("home"))

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.content, second.content)

    def test_home_page_renders_color_dropdown_inside_home_card(self):
        product = self.create_product(title="Color Product", slug="color-product")
        color = Color.objects.create(
            name="Deep Black",
            primary_hex="#000000",
            secondary_hex="#FFFFFF",
        )
        ProductColorVariant.objects.create(
            product=product,
            color=color,
            is_default=True,
            order=0,
        )

        response = self.client.get(reverse("home"))
        rendered_product = response.context["products"][0]
        html = response.content.decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(rendered_product.colors_preview_key.startswith("colors:1:"))
        self.assertContains(response, 'class="home-product-colors"')
        self.assertContains(response, 'class="home-color-dot color-dot active"')
        self.assertContains(response, 'aria-label="Колір Deep Black"')
        self.assertContains(response, "--c1: #000000; --c2: #FFFFFF;")
        self.assertNotIn('class="product-card-dots"', html)

    def test_home_card_image_area_links_to_product_detail_and_protects_image(self):
        product = self.create_product(title="Linked Product", slug="linked-product")
        product_url = reverse("product", kwargs={"slug": product.slug})

        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'href="{product_url}" class="home-product-media home-product-media-link"',
        )
        self.assertContains(response, 'data-product-card-link')
        self.assertContains(response, 'data-twc-image-protected="true"')
        self.assertContains(response, 'draggable="false"')

    def test_home_preloads_and_async_decodes_the_single_hero_logo(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            '<link rel="preload" as="image" href="/static/img/logo.svg" fetchpriority="high">',
        )
        self.assertContains(
            response,
            'class="hero-logo-image" loading="eager" fetchpriority="high" decoding="async"',
        )
        self.assertContains(response, 'width="600" height="600" class="hero-logo-image"')
        self.assertEqual(response.content.decode("utf-8").count('class="hero-logo-image"'), 1)


class CatalogViewTests(CatalogViewTestCase):
    def create_color_variant(self, product: Product, *, name: str, hex_value: str, stock: int = 3):
        color = Color.objects.create(name=name, primary_hex=hex_value)
        return ProductColorVariant.objects.create(
            product=product,
            color=color,
            is_default=True,
            stock=stock,
        )

    def test_global_mobile_shell_owns_header_cart_menu_and_bottom_navigation(self):
        self.create_product(title="Root Product", slug="root-product")

        response = self.client.get(reverse("catalog"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-mobile-site-shell="true"')
        self.assertContains(response, 'data-mobile-menu-panel')
        self.assertContains(response, 'id="cart-toggle-mobile"')
        self.assertContains(response, 'data-mobile-language-switcher')
        self.assertContains(response, 'data-bottom-nav-context="filters"')
        self.assertContains(response, 'data-mobile-open-filters')
        self.assertContains(response, "css/mobile-shell.css")
        self.assertNotContains(response, '>Кошик</span>')

        html = response.content.decode("utf-8")
        self.assertEqual(html.count('id="cart-toggle-mobile"'), 1)
        self.assertEqual(html.count('id="cart-count-mobile"'), 1)
        self.assertNotIn("data-catalog-reference-header", html)
        self.assertNotIn("catalog-mobile-reference__bottom-nav", html)
        self.assertNotIn("data-mobile-legacy-bottom-nav", html)

    def test_mobile_profile_dock_opens_existing_panel_and_exposes_avatar_contract(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="user-toggle-mobile"')
        self.assertContains(response, 'aria-controls="user-panel-mobile"')
        self.assertContains(response, 'aria-expanded="false"')
        self.assertContains(response, 'id="user-panel-mobile"')
        self.assertContains(response, 'aria-hidden="true"')
        self.assertContains(response, 'inert')

        header_template = (
            Path(__file__).resolve().parents[2]
            / "twocomms_django_theme"
            / "templates"
            / "partials"
            / "header.html"
        ).read_text(encoding="utf-8")
        self.assertIn("request.user.userprofile.avatar", header_template)
        self.assertIn("request.session.profile_avatar", header_template)
        self.assertIn('class="bottom-nav-avatar"', header_template)
        self.assertIn('class="bottom-nav-avatar-placeholder"', header_template)

    def test_mobile_profile_dock_renders_selected_avatar(self):
        user = User.objects.create_user(username="mobile-avatar-user", password="test-pass")
        user.userprofile.avatar.name = "avatars/mobile-selected.webp"
        user.userprofile.save(update_fields=["avatar"])
        self.client.force_login(user)

        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="bottom-nav-avatar"')
        self.assertContains(response, 'src="/media/avatars/mobile-selected.webp"')
        self.assertNotContains(response, 'class="bottom-nav-avatar-placeholder"')

    def test_mobile_cart_visibility_is_immediate_only_while_opening(self):
        shell_css = (
            Path(__file__).resolve().parents[2]
            / "twocomms_django_theme"
            / "static"
            / "css"
            / "mobile-shell.css"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "#mini-cart-panel-mobile.show {\n"
            "    transition: transform 240ms cubic-bezier(.2, .8, .2, 1), "
            "visibility 0s linear 0s !important;",
            shell_css,
        )
        self.assertIn(
            "transition: transform 240ms cubic-bezier(.2, .8, .2, 1), "
            "visibility 0s linear 240ms !important;",
            shell_css,
        )

    def test_mobile_panel_open_frame_is_cancelled_by_newer_operation(self):
        main_js = (
            Path(__file__).resolve().parents[2]
            / "twocomms_django_theme"
            / "static"
            / "js"
            / "main.js"
        ).read_text(encoding="utf-8")
        animated_panel_source = main_js[
            main_js.index("function showAnimatedPanel"):
            main_js.index("function setMobileCartExpanded")
        ]
        cart_open_source = main_js[
            main_js.index("function openMiniCart"):
            main_js.index("function closeMiniCart")
        ]

        self.assertIn("function showAnimatedPanel(panel, opId)", animated_panel_source)
        self.assertIn(
            "if (opId !== undefined && panel._opId !== opId) return;",
            animated_panel_source,
        )
        self.assertIn("up._opId = (up._opId || 0) + 1;", cart_open_source)
        self.assertIn("showAnimatedPanel(userPanelMobile, opId)", main_js)

    def test_mobile_panels_use_accessible_bottom_sheet_contract(self):
        static_root = Path(__file__).resolve().parents[2] / "twocomms_django_theme" / "static"
        shell_css = (static_root / "css" / "mobile-shell.css").read_text(encoding="utf-8")
        main_js = (static_root / "js" / "main.js").read_text(encoding="utf-8")
        base_template = (
            Path(__file__).resolve().parents[2]
            / "twocomms_django_theme"
            / "templates"
            / "base.html"
        ).read_text(encoding="utf-8")

        self.assertIn("position: fixed !important;", shell_css)
        self.assertIn("top: auto !important;", shell_css)
        self.assertIn("bottom: calc(var(--mobile-shell-dock-height) + 10px) !important;", shell_css)
        self.assertIn("padding: 0 0 env(safe-area-inset-bottom, 0px) !important;", shell_css)
        self.assertIn("transform: translateY(calc(100% +", shell_css)
        self.assertIn("transform: translateY(0)", shell_css)
        self.assertIn("100svh", shell_css)
        self.assertIn("100dvh", shell_css)
        self.assertIn("pointer-events: none !important;", shell_css)
        self.assertIn("prefers-reduced-motion: reduce", shell_css)

        self.assertNotIn("panel.classList.add('position-fixed', 'top-0'", main_js)
        self.assertIn("userToggleMobile.setAttribute('aria-expanded'", main_js)
        self.assertIn("cartToggleMobile.setAttribute('aria-expanded'", main_js)
        self.assertIn('aria-hidden="true" inert', base_template)

    def test_mobile_bottom_nav_uses_stable_full_state_transitions(self):
        static_root = Path(__file__).resolve().parents[2] / "twocomms_django_theme" / "static"
        shell_css = (static_root / "css" / "mobile-shell.css").read_text(encoding="utf-8")
        main_js = (static_root / "js" / "main.js").read_text(encoding="utf-8")

        self.assertIn("transition: transform 260ms cubic-bezier(.22, 1, .36, 1), opacity 180ms ease, visibility 0s linear 260ms !important;", shell_css)
        self.assertIn("will-change: transform, opacity;", shell_css)
        self.assertIn("padding: 5px max(8px, env(safe-area-inset-right, 0px)) max(6px, env(safe-area-inset-bottom, 0px)) max(8px, env(safe-area-inset-left, 0px));", shell_css)
        self.assertIn("HIDE_AFTER_DOWN_PX  = 36", main_js)
        self.assertIn("SHOW_AFTER_UP_PX    = 20", main_js)
        self.assertIn("const scrollDelta = Math.abs(dy);", main_js)
        self.assertIn("window.addEventListener('scroll', onWindowScroll, { passive: true });", main_js)
        self.assertIn("handleScroll(window.scrollY || document.documentElement.scrollTop || 0);", main_js)
        self.assertIn("if (inputFocused) return;", main_js)
        self.assertIn("resetAccumulators();\n        setHidden(false);\n        attachScrollListener();", main_js)
        self.assertIn("if (dy < 0) showHint();", main_js)
        self.assertIn("bottomNav.classList.toggle('bottom-nav--hidden', hidden);", main_js)
        self.assertNotIn("transform: scale", shell_css[shell_css.index(".bottom-nav {"):shell_css.index(".bottom-nav {") + 1800])

    def test_global_mobile_shell_uses_catalog_link_outside_catalog(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-bottom-nav-context="catalog"')
        self.assertContains(response, 'href="/catalog/"')

    def test_global_header_uses_explicit_desktop_and_mobile_brand_groups(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "class='navbar-brand navbar-brand--twocomms")
        self.assertContains(response, 'class="navbar-brand__name">TwoComms</span>')
        self.assertContains(response, 'class="mobile-site-shell__brand-name">TWOCOMMS</span>')

    def test_mobile_catalog_css_uses_stable_viewports_and_four_distinct_mark_paths(self):
        static_root = (
            Path(__file__).resolve().parents[2]
            / "twocomms_django_theme"
            / "static"
            / "css"
        )
        catalog_css = (static_root / "catalog-redesign.css").read_text(encoding="utf-8")
        shell_css = (static_root / "mobile-shell.css").read_text(encoding="utf-8")

        self.assertIn("100svh", catalog_css)
        self.assertIn("100dvh", catalog_css)
        self.assertIn("overflow: visible", catalog_css)
        self.assertIn(
            "animation: mobile-shell-mark-path-one 7.4s ease-in-out -1.2s infinite !important;",
            shell_css,
        )
        self.assertIn(
            'html[data-route-name="catalog"] .catalog-mobile-reference__floating-mark { animation: none !important;',
            shell_css,
        )
        for path_number in ("one", "two", "three", "four"):
            self.assertIn(f"@keyframes mobile-shell-mark-path-{path_number}", shell_css)
        self.assertNotIn("floating-mark--four { display: none;", shell_css)

    def test_root_results_mobile_grid_has_stable_tracks_and_single_card_span(self):
        shell_css = (
            Path(__file__).resolve().parents[2]
            / "twocomms_django_theme"
            / "static"
            / "css"
            / "catalog-redesign.css"
        ).read_text(encoding="utf-8")

        self.assertIn(
            ".catalog-redesign-shell--root-results .catalog-products-grid",
            shell_css,
        )
        self.assertIn("display: grid;", shell_css)
        self.assertIn("grid-template-columns: repeat(2, minmax(0, 1fr));", shell_css)
        self.assertIn(
            ".catalog-redesign-shell--root-results .catalog-products-grid > .product-card-wrap:only-child",
            shell_css,
        )
        self.assertIn("grid-column: 1 / -1;", shell_css)

    def test_mini_cart_template_exposes_stable_semantic_item_tracks(self):
        template = (
            Path(__file__).resolve().parents[2]
            / "twocomms_django_theme"
            / "templates"
            / "partials"
            / "mini_cart.html"
        ).read_text(encoding="utf-8")

        for class_name in (
            "mini-cart-row",
            "mini-cart-row__media",
            "mini-cart-row__copy",
            "mini-cart-row__title",
            "mini-cart-row__meta",
            "mini-cart-row__actions",
            "mini-cart-row__price",
            "mini-cart-row__remove",
        ):
            self.assertIn(class_name, template)

        shell_css = (
            Path(__file__).resolve().parents[2]
            / "twocomms_django_theme"
            / "static"
            / "css"
            / "mobile-shell.css"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "grid-template-columns: 48px minmax(0, 1fr) minmax(64px, auto);",
            shell_css,
        )
        self.assertIn("#mini-cart-panel-mobile .mini-cart-primary-cta", shell_css)
        self.assertIn("background: #f15a0b !important;", shell_css)
        self.assertIn("font-variant-numeric: tabular-nums;", shell_css)

    def test_mini_cart_uses_one_stable_responsive_visual_contract(self):
        theme_root = Path(__file__).resolve().parents[2] / "twocomms_django_theme"
        template_root = theme_root / "templates"
        base_template = (template_root / "base.html").read_text(encoding="utf-8")
        header_template = (template_root / "partials" / "header.html").read_text(
            encoding="utf-8"
        )
        mini_cart_template = (template_root / "partials" / "mini_cart.html").read_text(
            encoding="utf-8"
        )
        mini_cart_css_path = theme_root / "static" / "css" / "mini-cart.css"

        self.assertTrue(
            mini_cart_css_path.is_file(),
            "Dedicated css/mini-cart.css must own the responsive mini-cart contract",
        )
        mini_cart_css = mini_cart_css_path.read_text(encoding="utf-8")

        self.assertIn("css/mobile-shell.css", base_template)
        self.assertIn("css/mini-cart.css", base_template)
        self.assertLess(
            base_template.index("css/mobile-shell.css"),
            base_template.index("css/mini-cart.css"),
        )

        for panel_template in (header_template, base_template):
            for class_name in (
                "mini-cart-shell",
                "mini-cart-shell__header",
                "mini-cart-shell__content",
            ):
                self.assertIn(class_name, panel_template)
            self.assertNotIn("cart-sparks-container", panel_template)
            self.assertNotIn("cart-menu", panel_template)
            self.assertNotIn("cart-info", panel_template)

        for class_name in (
            "mini-cart-view",
            "mini-cart-list",
            "mini-cart-footer",
            "mini-cart-row__image",
            "mini-cart-secondary-action",
            "mini-cart-empty",
        ):
            self.assertIn(class_name, mini_cart_template)
        self.assertIn('width="56" height="56"', mini_cart_template)
        self.assertIn("data-mini-cart-continue", mini_cart_template)
        self.assertNotIn("w-100 h-100", mini_cart_template)
        self.assertNotIn('data-mono-checkout-trigger="mini"', mini_cart_template)
        self.assertNotIn("mini-cart-primary-cta__shine", mini_cart_template)
        self.assertNotIn("mini-cart-action-tile__icon-pulse", mini_cart_template)

        for contract in (
            "grid-template-columns: 56px minmax(0, 1fr) auto;",
            "grid-template-rows: minmax(0, 1fr) auto;",
            "width: 56px;",
            "height: 56px;",
            "overflow-y: auto;",
            "overscroll-behavior: contain;",
            "width: 420px;",
            "100dvh",
            "--mobile-shell-header-height",
            "--mobile-shell-dock-height",
            "@media (max-height: 680px)",
            "@media (prefers-reduced-motion: reduce)",
        ):
            self.assertIn(contract, mini_cart_css)

        remove_selector = (
            "#mini-cart-panel .mini-cart-row__remove,\n"
            "#mini-cart-panel-mobile .mini-cart-row__remove {"
        )
        self.assertIn(remove_selector, mini_cart_css)
        remove_rule = mini_cart_css.partition(remove_selector)[2].partition("}")[0]
        for touch_target_contract in (
            "width: 44px;",
            "height: 44px;",
            "min-width: 44px;",
            "min-height: 44px;",
        ):
            self.assertIn(touch_target_contract, remove_rule)

    def test_mini_cart_mobile_open_state_preserves_grid_against_inline_rule(self):
        theme_root = Path(__file__).resolve().parents[2] / "twocomms_django_theme"
        base_template = (theme_root / "templates" / "base.html").read_text(
            encoding="utf-8"
        )
        mini_cart_css = (theme_root / "static" / "css" / "mini-cart.css").read_text(
            encoding="utf-8"
        )

        inline_open_rule = (
            "#mini-cart-panel-mobile.show,\n"
            "    #user-panel-mobile.show {\n"
            "      display: block !important;"
        )
        self.assertIn(inline_open_rule, base_template)
        self.assertLess(
            base_template.index(inline_open_rule),
            base_template.index("css/mini-cart.css"),
        )

        responsive_open_rule = "#mini-cart-panel-mobile.show {"
        self.assertIn(responsive_open_rule, mini_cart_css)
        open_rule = mini_cart_css.partition(responsive_open_rule)[2].partition("}")[0]
        self.assertIn("display: grid !important;", open_rule)

    def test_mini_cart_desktop_surface_has_compact_reference_contract(self):
        mini_cart_css = (
            Path(__file__).resolve().parents[2]
            / "twocomms_django_theme"
            / "static"
            / "css"
            / "mini-cart.css"
        ).read_text(encoding="utf-8")

        for contract in (
            "@media (min-width: 992px) {\n  #mini-cart-panel.mini-cart-shell",
            "width: min(480px, calc(100vw - 32px)) !important;",
            "grid-template-rows: auto minmax(0, 1fr);",
            "min-height: 86px !important;",
            "min-height: 114px !important;",
            "height: 86px;",
            "color: #fff !important;",
            "background: linear-gradient(180deg, #ff7117 0%, #e84a05 50%, #ff6412 100%) !important;",
        ):
            self.assertIn(contract, mini_cart_css)

        desktop_layer = mini_cart_css[mini_cart_css.rfind("@media (min-width: 992px)"):]
        self.assertIn("#mini-cart-panel .mini-cart-shipping", desktop_layer)
        self.assertIn("#mini-cart-panel .mini-cart-row", desktop_layer)
        self.assertIn("#mini-cart-panel .mini-cart-primary-cta", desktop_layer)
        self.assertNotIn("#mini-cart-panel-mobile", desktop_layer)

    def test_mini_cart_checkout_action_uses_accessible_dark_ink(self):
        mini_cart_css = (
            Path(__file__).resolve().parents[2]
            / "twocomms_django_theme"
            / "static"
            / "css"
            / "mini-cart.css"
        ).read_text(encoding="utf-8")
        dark_ink = "#17110b"

        selectors = (
            (
                "#mini-cart-panel .mini-cart-primary-cta,\n"
                "#mini-cart-panel-mobile .mini-cart-primary-cta {"
            ),
            (
                "#mini-cart-panel .mini-cart-primary-cta:hover,\n"
                "#mini-cart-panel-mobile .mini-cart-primary-cta:hover {"
            ),
            ".mini-cart-primary-cta__icon,\n.mini-cart-primary-cta__arrow {",
            ".mini-cart-primary-cta__label {",
            ".mini-cart-primary-cta__hint {",
        )
        for selector in selectors:
            self.assertIn(selector, mini_cart_css)
            rule = mini_cart_css.partition(selector)[2].partition("}")[0]
            self.assertIn(f"color: {dark_ink};", rule)

        scoped_hint_selectors = (
            "#mini-cart-panel .mini-cart-primary-cta__hint,\n"
            "#mini-cart-panel-mobile .mini-cart-primary-cta__hint {",
        )
        for selector in scoped_hint_selectors:
            self.assertIn(selector, mini_cart_css)
            rule = mini_cart_css.partition(selector)[2].partition("}")[0]
            self.assertIn(f"color: {dark_ink};", rule)

        def relative_luminance(hex_color: str) -> float:
            channels = [int(hex_color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
            linear = [
                channel / 12.92
                if channel <= 0.04045
                else ((channel + 0.055) / 1.055) ** 2.4
                for channel in channels
            ]
            return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

        def contrast_ratio(first: str, second: str) -> float:
            light, dark = sorted(
                (relative_luminance(first), relative_luminance(second)), reverse=True
            )
            return (light + 0.05) / (dark + 0.05)

        for orange in ("#f15a0b", "#ff681b"):
            self.assertGreaterEqual(contrast_ratio(dark_ink, orange), 4.5)

    def test_reference_mini_cart_exposes_shipping_and_quantity_contract(self):
        theme_root = Path(__file__).resolve().parents[2] / "twocomms_django_theme"
        template = (theme_root / "templates" / "partials" / "mini_cart.html").read_text(
            encoding="utf-8"
        )
        css = (theme_root / "static" / "css" / "mini-cart.css").read_text(encoding="utf-8")
        for marker in (
            "mini-cart-shipping",
            "mini-cart-shipping__progress",
            "mini-cart-benefits",
            "mini-cart-quantity",
            "mini-cart-quantity__decrease",
            "mini-cart-quantity__increase",
            "mini-cart-summary__icon",
            "aria-label=\"{{ it.color_label|default:_('Колір') }}\"",
        ):
            self.assertIn(marker, template)
        self.assertNotIn("translate_color", template)
        for marker in (
            "border-radius: 28px 28px 0 0",
            "env(safe-area-inset-bottom",
            "transform: translateY(105%)",
            "mini-cart-shipping__bar",
            "mini-cart-benefits",
        ):
            self.assertIn(marker, css)

    def test_catalog_root_shows_published_products_and_category_cards(self):
        self.create_product(title="Root Product", slug="root-product")
        self.create_product(
            title="Other Product",
            slug="other-product",
            category=self.other_category,
        )
        self.create_product(title="Hidden Product", slug="hidden-product", status="draft")

        response = self.client.get(reverse("catalog"))
        product_titles = [product.title for product in response.context["products"]]

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["show_category_cards"])
        self.assertIn("Root Product", product_titles)
        self.assertIn("Other Product", product_titles)
        self.assertNotIn("Hidden Product", product_titles)

    def test_catalog_root_renders_accessible_aggregate_filter_sheet(self):
        tshirts = Category.objects.create(name="Футболки", slug="tshirts", is_active=True)
        Category.objects.create(name="Худі", slug="hoodie", is_active=True)
        Category.objects.create(name="Лонгсліви", slug="long-sleeve", is_active=True)
        product = self.create_product(title="Black Tee", slug="black-tee", category=tshirts)
        self.create_color_variant(product, name="Black", hex_value="#111111")

        response = self.client.get(reverse("catalog"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-catalog-root-filters')
        self.assertContains(response, 'id="catalog-root-filter-sheet"')
        self.assertContains(response, 'role="dialog"')
        self.assertContains(response, 'aria-modal="true"')
        self.assertContains(response, 'method="get"')
        for category_slug in ("tshirts", "hoodie", "long-sleeve"):
            self.assertContains(response, f'name="category" value="{category_slug}"')
        for size in ("XS", "S", "M", "L", "XL", "2XL"):
            self.assertContains(response, f'name="size" value="{size}"')
        self.assertContains(response, 'name="color" value="black"')
        self.assertContains(response, 'name="availability" value="in_stock"')
        self.assertContains(response, 'name="sort"')
        self.assertContains(response, 'data-catalog-root-filter-reset')
        self.assertContains(response, 'data-catalog-root-filter-apply')
        self.assertContains(response, 'data-root-active-count')

    def test_catalog_root_filters_multiple_categories_and_inventory(self):
        tshirts = Category.objects.create(name="Футболки", slug="tshirts", is_active=True)
        hoodie = Category.objects.create(name="Худі", slug="hoodie", is_active=True)
        long_sleeve = Category.objects.create(name="Лонгсліви", slug="long-sleeve", is_active=True)

        tee = self.create_product(title="Available Tee", slug="available-tee", category=tshirts)
        available_hoodie = self.create_product(
            title="Available Hoodie",
            slug="available-hoodie",
            category=hoodie,
        )
        unavailable_hoodie = self.create_product(
            title="Unavailable Hoodie",
            slug="unavailable-hoodie",
            category=hoodie,
        )
        unavailable_hoodie.is_dropship_available = False
        unavailable_hoodie.save(update_fields=["is_dropship_available"])
        excluded_long_sleeve = self.create_product(
            title="Excluded Long Sleeve",
            slug="excluded-long-sleeve",
            category=long_sleeve,
        )

        self.create_color_variant(tee, name="Tee Black", hex_value="#111111")
        self.create_color_variant(available_hoodie, name="Hoodie Black", hex_value="#121212")
        self.create_color_variant(unavailable_hoodie, name="Hoodie Gray", hex_value="#222222")
        self.create_color_variant(excluded_long_sleeve, name="Long Black", hex_value="#131313")

        response = self.client.get(
            f'{reverse("catalog")}?category=tshirts&category=hoodie&availability=in_stock'
        )
        product_titles = [product.title for product in response.context["products"]]

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["root_catalog_selected_categories"], ("tshirts", "hoodie"))
        self.assertEqual(response.context["root_catalog_facet_state"]["availability"], ("in_stock",))
        self.assertEqual(response.context["root_catalog_filter_active_count"], 3)
        self.assertFalse(response.context["show_category_cards"])
        self.assertIn("Available Tee", product_titles)
        self.assertIn("Available Hoodie", product_titles)
        self.assertNotIn("Unavailable Hoodie", product_titles)
        self.assertNotIn("Excluded Long Sleeve", product_titles)
        self.assertContains(response, "catalog-products-grid")
        self.assertContains(response, "home-product-card card product")

    def test_catalog_root_preserves_legacy_comma_separated_color_filter(self):
        tshirts = Category.objects.create(name="Футболки", slug="tshirts", is_active=True)
        product = self.create_product(title="Legacy Color Tee", slug="legacy-color-tee", category=tshirts)
        variant = self.create_color_variant(product, name="Black", hex_value="#111111")
        variant.slug = "black"
        variant.save(update_fields=["slug"])

        response = self.client.get(f'{reverse("catalog")}?color=black,red', follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["root_catalog_selected_color_slugs"], ("black",))
        self.assertFalse(response.context["show_category_cards"])
        self.assertIn("Legacy Color Tee", [product.title for product in response.context["products"]])

    def test_catalog_root_renders_print_zone_selector(self):
        self.create_product(title="Root Product", slug="root-product")

        response = self.client.get(reverse("catalog"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "catalog-print-panel")
        self.assertContains(response, "catalog-print-tool is-active")
        self.assertContains(response, 'data-print-mode="print"')
        self.assertContains(response, 'aria-pressed="true"')
        self.assertContains(response, "catalog-print-zone")
        self.assertContains(response, "catalog-print-zone__handle")
        self.assertContains(response, "Зона друку")
        self.assertContains(response, "js/catalog-redesign.js")

    def test_catalog_root_renders_mobile_reference_section_with_category_links(self):
        tshirts = Category.objects.create(name="Футболки", slug="tshirts", is_active=True)
        Category.objects.create(name="Худі", slug="hoodie", is_active=True)
        Category.objects.create(name="Лонгсліви", slug="long-sleeve", is_active=True)
        self.create_product(title="Root Product", slug="root-product", category=tshirts, price=790)
        response = self.client.get(reverse("catalog"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="catalog-mobile-reference"')
        self.assertContains(response, 'class="catalog-mobile-reference__hero"')
        self.assertContains(response, 'class="catalog-mobile-reference__categories"')
        self.assertContains(response, 'class="catalog-mobile-reference__custom-print"')
        self.assertContains(response, 'class="catalog-mobile-reference__benefits"')
        self.assertContains(response, 'href="/catalog/tshirts/"')
        self.assertContains(response, 'href="/catalog/hoodie/"')
        self.assertContains(response, 'href="/catalog/long-sleeve/"')
        self.assertContains(response, "Від 790 ₴")
        self.assertContains(response, "tshirt-bej-oversize.webp")
        self.assertContains(response, "catalog-longsleeve-cutout.avif")
        self.assertContains(response, "catalog-longsleeve-cutout.webp")
        self.assertContains(response, "catalog-custom-print.avif")
        self.assertContains(response, "catalog-custom-print.webp")

        html = response.content.decode("utf-8")
        self.assertLess(html.index('href="/catalog/tshirts/"'), html.index('href="/catalog/hoodie/"'))
        self.assertLess(html.index('href="/catalog/hoodie/"'), html.index('href="/catalog/long-sleeve/"'))

    def test_catalog_category_does_not_render_root_mobile_reference_section(self):
        self.create_product(title="Category Product", slug="category-product")
        response = self.client.get(reverse("catalog_by_cat", kwargs={"cat_slug": self.category.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'class="catalog-mobile-reference"')

    def test_catalog_by_category_limits_results_to_selected_category(self):
        in_category = self.create_product(title="Category Product", slug="category-product")
        self.create_product(
            title="Other Category Product",
            slug="other-category-product",
            category=self.other_category,
        )

        response = self.client.get(reverse("catalog_by_cat", kwargs={"cat_slug": self.category.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["category"].pk, self.category.pk)
        product_titles = [product.title for product in response.context["products"]]
        self.assertIn(in_category.title, product_titles)
        self.assertNotIn("Other Category Product", product_titles)

    def test_page_two_pagination_does_not_link_to_redirecting_page_one(self):
        for index in range(17):
            self.create_product(
                title=f"Paginated Product {index}",
                slug=f"paginated-product-{index}",
            )

        response = self.client.get(
            reverse("catalog_by_cat", kwargs={"cat_slug": self.category.slug})
            + "?page=2"
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "page=1")
        self.assertContains(response, "page=2")

    def test_catalog_category_uses_home_product_card_layout(self):
        product = self.create_product(title="Styled Product", slug="styled-product")
        product_url = reverse("product", kwargs={"slug": product.slug})

        response = self.client.get(reverse("catalog_by_cat", kwargs={"cat_slug": self.category.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "catalog-products-grid")
        self.assertContains(response, "home-products-grid")
        self.assertContains(response, "home-product-card card product")
        self.assertContains(response, "reveal-stagger stagger-item")
        self.assertContains(response, "home-product-media home-product-media-link")
        self.assertContains(response, "home-product-content")
        self.assertContains(response, f'href="{product_url}" class="home-product-media home-product-media-link"')
        self.assertContains(response, product.title)
        self.assertNotContains(response, 'class="card product h-100 hover-raise glass', html=False)

    def test_catalog_by_category_returns_404_for_inactive_category(self):
        self.category.is_active = False
        self.category.save(update_fields=["is_active"])

        response = self.client.get(reverse("catalog_by_cat", kwargs={"cat_slug": self.category.slug}))

        self.assertEqual(response.status_code, 404)

    def test_catalog_rejects_malformed_duplicate_and_out_of_range_pages(self):
        from unittest.mock import patch

        self.create_product(title="Page one", slug="page-one")
        self.create_product(title="Page two", slug="page-two")
        url = reverse("catalog_by_cat", kwargs={"cat_slug": self.category.slug})

        with patch("storefront.views.catalog.PRODUCTS_PER_PAGE", 1):
            for raw_page in ("abc", "0", "999", "2&page=2"):
                with self.subTest(raw_page=raw_page):
                    response = self.client.get(f"{url}?page={raw_page}")
                    self.assertEqual(response.status_code, 404)

    def test_catalog_keeps_valid_page_two_as_a_distinct_self_canonical_page(self):
        self.create_product(title="Page one", slug="page-one")
        self.create_product(title="Page two", slug="page-two")
        url = reverse("catalog_by_cat", kwargs={"cat_slug": self.category.slug})

        with patch("storefront.views.catalog.PRODUCTS_PER_PAGE", 1):
            page_one = self.client.get(url)
            response = self.client.get(f"{url}?page=2")

        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(
            [product.pk for product in response.context["products"]],
            [product.pk for product in page_one.context["products"]],
        )
        self.assertContains(response, 'content="index, follow')
        self.assertContains(response, f"{url}?page=2")

    def test_catalog_rejects_unknown_or_empty_facet_states(self):
        self.create_product(title="Facet product", slug="facet-product")
        url = reverse("catalog_by_cat", kwargs={"cat_slug": self.category.slug})

        for query in (
            "fit=not-a-fit",
            "size=3XL",
            "availability=preorder",
            "theme=not-a-theme",
            "fit=classic&fit=classic",
        ):
            with self.subTest(query=query):
                response = self.client.get(f"{url}?{query}")
                self.assertEqual(response.status_code, 404)

    def test_catalog_keeps_valid_empty_color_filter_as_a_noindex_ui_state(self):
        from productcolors.models import Color, ProductColorVariant

        other_category = Category.objects.create(
            name="Tshirts", slug="tshirts", is_active=True,
        )
        other_product = self.create_product(
            title="Black product elsewhere",
            slug="black-product-elsewhere",
            category=other_category,
        )
        black = Color.objects.create(name="Black", primary_hex="#000000")
        ProductColorVariant.objects.create(product=other_product, color=black)
        self.create_product(title="No color here", slug="no-color-here")

        url = reverse("catalog_by_cat", kwargs={"cat_slug": self.category.slug})
        response = self.client.get(f"{url}?color=black")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'content="noindex, follow')
        self.assertEqual(response.context["products"], [])

    def test_unowned_grey_and_olive_color_aliases_redirect_to_clean_category(self):
        self.create_product(title="Canonical color product", slug="canonical-color-product")
        url = reverse("catalog_by_cat", kwargs={"cat_slug": self.category.slug})

        for color_slug in ("grey", "olive"):
            with self.subTest(color_slug=color_slug):
                response = self.client.get(f"{url}?color={color_slug}")

                self.assertEqual(response.status_code, 301)
                self.assertEqual(response["Location"], url)


class SearchViewTests(CatalogViewTestCase):
    def test_search_finds_products_by_title_case_insensitively(self):
        self.create_product(title="Red T-Shirt", slug="red-t-shirt")
        self.create_product(title="Blue Jeans", slug="blue-jeans")

        response = self.client.get(reverse("search"), {"q": "RED"})
        product_titles = [product.title for product in response.context["products"]]

        self.assertEqual(response.status_code, 200)
        self.assertIn("Red T-Shirt", product_titles)
        self.assertNotIn("Blue Jeans", product_titles)
        self.assertEqual(response.context["results_count"], 1)

    def test_search_finds_products_by_description(self):
        self.create_product(
            title="Utility Hoodie",
            slug="utility-hoodie",
            description="Comfortable field-tested hoodie",
        )
        self.create_product(title="Plain Tee", slug="plain-tee", description="Minimal cotton tee")

        response = self.client.get(reverse("search"), {"q": "field-tested"})
        product_titles = [product.title for product in response.context["products"]]

        self.assertEqual(response.status_code, 200)
        self.assertIn("Utility Hoodie", product_titles)
        self.assertNotIn("Plain Tee", product_titles)

    def test_search_with_empty_query_returns_all_published_products(self):
        self.create_product(title="Published One", slug="published-one")
        self.create_product(title="Published Two", slug="published-two")
        self.create_product(title="Draft Product", slug="draft-product", status="draft")

        response = self.client.get(reverse("search"), {"q": ""})
        product_titles = [product.title for product in response.context["products"]]

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["results_count"], 2)
        self.assertIn("Published One", product_titles)
        self.assertIn("Published Two", product_titles)
        self.assertNotIn("Draft Product", product_titles)

    def test_search_results_are_paginated_and_keep_query_param(self):
        from storefront.views.utils import PRODUCTS_PER_PAGE

        for index in range(PRODUCTS_PER_PAGE + 3):
            self.create_product(
                title=f"Searchable Product {index:02d}",
                slug=f"searchable-product-{index:02d}",
            )

        response = self.client.get(reverse("search"), {"q": "Searchable"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["results_count"], PRODUCTS_PER_PAGE + 3)
        self.assertEqual(len(response.context["products"]), PRODUCTS_PER_PAGE)
        self.assertTrue(response.context["page_obj"].has_next())
        self.assertContains(response, "?q=Searchable&amp;page=2")


class LoadMoreProductsTests(CatalogViewTestCase):
    def test_load_more_returns_json_page_metadata(self):
        for index in range(9):
            self.create_product(
                title=f"Paged Product {index}",
                slug=f"paged-product-{index}",
            )

        response = self.client.get(reverse("load_more_products"), {"page": 2})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("html", payload)
        self.assertEqual(payload["current_page"], 2)
        self.assertFalse(payload["has_more"])
        self.assertEqual(payload["total_pages"], 2)

    def test_load_more_clamps_page_beyond_range_to_last_page(self):
        for index in range(9):
            self.create_product(
                title=f"Paged Product {index}",
                slug=f"paged-product-{index}",
            )

        response = self.client.get(reverse("load_more_products"), {"page": 99})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["current_page"], 2)
        self.assertFalse(payload["has_more"])

    def test_load_more_handles_invalid_page_as_first_page(self):
        for index in range(9):
            self.create_product(
                title=f"Invalid Page Product {index}",
                slug=f"invalid-page-product-{index}",
            )

        response = self.client.get(reverse("load_more_products"), {"page": "bad"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["current_page"], 1)
        self.assertTrue(payload["has_more"])
