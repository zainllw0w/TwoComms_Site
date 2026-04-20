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

        rail_blocks = re.findall(r"\.pagination-rail\s*\{([^}]*)\}", css, re.S)
        showcase_blocks = re.findall(r"\.pagination-showcase\s*\{([^}]*)\}", css, re.S)

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
