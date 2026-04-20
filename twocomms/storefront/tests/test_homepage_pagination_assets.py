import re
from pathlib import Path

from django.test import SimpleTestCase


class HomepagePaginationCssTests(SimpleTestCase):
    def test_home_pagination_has_single_mobile_safe_base_ruleset(self):
        css_path = (
            Path(__file__).resolve().parents[2]
            / "twocomms_django_theme"
            / "static"
            / "css"
            / "home.css"
        )
        css = css_path.read_text(encoding="utf-8")

        rail_blocks = re.findall(r"^\.pagination-rail\s*\{([^}]*)\}", css, re.S | re.M)
        showcase_blocks = re.findall(r"^\.pagination-showcase\s*\{([^}]*)\}", css, re.S | re.M)

        self.assertEqual(
            len(showcase_blocks),
            1,
            "Homepage pagination showcase should have a single base ruleset to avoid cascade regressions.",
        )
        self.assertEqual(
            len(rail_blocks),
            1,
            "Homepage pagination rail should have a single base ruleset so mobile-safe overflow rules are not overridden later.",
        )
        self.assertIn("box-sizing: border-box;", rail_blocks[0])
        self.assertIn("max-width: 100%;", rail_blocks[0])
        self.assertIn("justify-content: flex-start;", rail_blocks[0])
        self.assertIn("overflow-x: auto;", rail_blocks[0])
        self.assertIn("scroll-padding-inline:", rail_blocks[0])

    def test_home_pagination_keeps_not_scrollable_centering_desktop_only(self):
        css_path = (
            Path(__file__).resolve().parents[2]
            / "twocomms_django_theme"
            / "static"
            / "css"
            / "home.css"
        )
        css = css_path.read_text(encoding="utf-8")

        self.assertRegex(css, r"@media\s*\(min-width:\s*769px\)")
        self.assertRegex(
            css,
            r"@media\s*\(min-width:\s*769px\)\s*\{[\s\S]*?\.pagination-rail:not\(\.is-scrollable\)\s*\{[\s\S]*?justify-content:\s*center;[\s\S]*?overflow-x:\s*visible;",
        )

    def test_home_pagination_has_mobile_scale_hook(self):
        css_path = (
            Path(__file__).resolve().parents[2]
            / "twocomms_django_theme"
            / "static"
            / "css"
            / "home.css"
        )
        js_path = (
            Path(__file__).resolve().parents[2]
            / "twocomms_django_theme"
            / "static"
            / "js"
            / "modules"
            / "homepage.js"
        )
        css = css_path.read_text(encoding="utf-8")
        js = js_path.read_text(encoding="utf-8")

        self.assertRegex(
            css,
            r"@media\s*\(max-width:\s*768px\)\s*\{[\s\S]*?\.pagination-rail\.is-scaled\s*\{[\s\S]*?overflow-x:\s*hidden;",
        )
        self.assertIn(
            "transform: translateX(var(--pagination-mobile-offset, 0px)) scale(var(--pagination-mobile-scale, 1));",
            css,
        )
        self.assertIn("transform-origin: left top;", css)
        self.assertIn("window.matchMedia('(max-width: 768px)')", js)
        self.assertIn("--pagination-mobile-scale", js)
        self.assertIn("--pagination-mobile-offset", js)
        self.assertIn("scrollContainer.classList.add('is-scaled');", js)

    def test_home_template_has_no_raw_survey_comment_text(self):
        template_path = (
            Path(__file__).resolve().parents[2]
            / "twocomms_django_theme"
            / "templates"
            / "pages"
            / "index.html"
        )
        template = template_path.read_text(encoding="utf-8")

        self.assertNotIn("Survey-модалка упакована в <template>", template)

    def test_home_template_uses_pagination_partial_shell(self):
        template_path = (
            Path(__file__).resolve().parents[2]
            / "twocomms_django_theme"
            / "templates"
            / "pages"
            / "index.html"
        )
        template = template_path.read_text(encoding="utf-8")

        self.assertIn('id="home-pagination-shell"', template)
        self.assertIn('{% include "partials/home_pagination.html"', template)
        self.assertNotIn("{% for num in paginator.page_range %}", template)

    def test_home_pagination_js_swaps_server_rendered_html(self):
        js_path = (
            Path(__file__).resolve().parents[2]
            / "twocomms_django_theme"
            / "static"
            / "js"
            / "modules"
            / "homepage.js"
        )
        js = js_path.read_text(encoding="utf-8")

        self.assertIn("pagination_html", js)
        self.assertIn("home-pagination-shell", js)
        self.assertRegex(js, r"getPaginationNav\s*=\s*\(\)\s*=>")
        self.assertIn("const mobileVisualInset = isMobilePaginationViewport() ? 16 : 0;", js)
        self.assertIn("scrollContainer.clientWidth - railPaddingX - mobileVisualInset", js)
        self.assertIn("const scaledWidth = naturalWidth * scale;", js)
        self.assertIn(
            "showcase.style.setProperty('--pagination-mobile-offset', `${Math.max(0, Math.floor((availableWidth - scaledWidth) / 2))}px`);",
            js,
        )

    def test_home_pagination_has_ellipsis_style(self):
        css_path = (
            Path(__file__).resolve().parents[2]
            / "twocomms_django_theme"
            / "static"
            / "css"
            / "home.css"
        )
        css = css_path.read_text(encoding="utf-8")

        self.assertRegex(
            css,
            r"\.pagination-premium \.page-item-ellipsis \.page-link\s*\{[\s\S]*?pointer-events:\s*none;",
        )

    def test_home_pagination_mobile_reserves_edge_gutter(self):
        css_path = (
            Path(__file__).resolve().parents[2]
            / "twocomms_django_theme"
            / "static"
            / "css"
            / "home.css"
        )
        css = css_path.read_text(encoding="utf-8")

        self.assertRegex(
            css,
            r"@media\s*\(max-width:\s*768px\)\s*\{[\s\S]*?\.pagination-showcase\s*\{[\s\S]*?padding-inline:\s*clamp\(0\.55rem,\s*3vw,\s*0\.85rem\);",
        )
        self.assertNotRegex(
            css,
            r"@media\s*\(max-width:\s*768px\)\s*\{[\s\S]*?\.pagination-rail\s*\{[\s\S]*?max-width:",
        )
