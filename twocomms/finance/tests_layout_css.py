"""Regression tests for the finance shell responsive layout CSS."""
from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class FinanceSidebarLayoutCssTests(SimpleTestCase):
    css_paths = (
        "twocomms_django_theme/static/css/finance.css",
        "static/css/finance-fixes.css",
    )

    def _read_css(self, relative_path: str) -> str:
        return (Path(settings.BASE_DIR) / relative_path).read_text(encoding="utf-8")

    def _desktop_sidebar_rules(self, css: str) -> list[str]:
        rules: list[str] = []
        for section in css.split("@media (min-width: 901px)")[1:]:
            match = re.search(r"\.fin-sidebar\s*\{(?P<body>.*?)\n\s*\}", section, re.S)
            if match:
                rules.append(match.group("body"))
        return rules

    def _rule(self, css: str, selector: str) -> str:
        match = re.search(rf"{re.escape(selector)}\s*\{{(?P<body>.*?)\n\}}", css, re.S)
        self.assertIsNotNone(match, f"{selector} rule must exist")
        return match.group("body")

    def test_desktop_sidebar_sticks_below_header_without_clipping(self):
        for relative_path in self.css_paths:
            with self.subTest(css=relative_path):
                rules = self._desktop_sidebar_rules(self._read_css(relative_path))
                self.assertTrue(rules, f"{relative_path} must define desktop sidebar rules")
                for rule in rules:
                    self.assertIn("top: var(--fin-header-h);", rule)
                    self.assertNotIn("top: 0;", rule)
                    self.assertRegex(
                        rule,
                        r"height:\s*calc\(100(?:dvh|svh|vh) - var\(--fin-header-h\)\);",
                    )

    def test_mobile_landscape_sidebar_override_is_scoped_to_mobile_widths(self):
        css = self._read_css("twocomms_django_theme/static/css/finance.css")
        self.assertIn(
            "@media (max-width: 900px) and (max-height: 500px) and (orientation: landscape)",
            css,
        )
        self.assertNotIn("@media (max-height: 500px) and (orientation: landscape)", css)

    def test_sticky_shell_ancestors_do_not_create_scroll_containers(self):
        css = self._read_css("twocomms_django_theme/static/css/finance.css")
        for selector in ("html, body", ".fin-body", ".fin-workspace"):
            with self.subTest(selector=selector):
                rule = self._rule(css, selector)
                self.assertIn("overflow-x: clip;", rule)


class FinanceMobileDrawerStructureTests(SimpleTestCase):
    def _read(self, relative_path: str) -> str:
        return (Path(settings.BASE_DIR) / relative_path).read_text(encoding="utf-8")

    def _between(self, source: str, start: str, end: str) -> str:
        start_index = source.index(start)
        end_index = source.index(end, start_index)
        return source[start_index:end_index]

    def test_mobile_navigation_lives_in_right_settings_drawer_not_left_stats_drawer(self):
        template = self._read("finance/templates/finance/base.html")
        sidebar = self._between(template, 'id="fin-sidebar"', 'id="fin-sidebar-backdrop"')
        settings = self._between(template, 'id="fin-settings-panel"', '<span class="fin-version">')

        self.assertNotIn("fin-mobile-nav", sidebar)
        self.assertIn("fin-settings-nav", settings)
        self.assertLess(settings.index("fin-settings-nav"), settings.index("fin-settings-section--push"))
        self.assertIn('aria-controls="fin-sidebar"', template)
        self.assertIn('aria-controls="fin-settings-panel"', template)

    def test_push_settings_are_collapsed_behind_a_disclosure(self):
        template = self._read("finance/templates/finance/base.html")

        self.assertIn('id="fin-push-disclosure"', template)
        self.assertIn('aria-controls="fin-push-settings-content"', template)
        self.assertIn('id="fin-push-settings-content" hidden', template)
        self.assertIn('id="push-settings-content" hidden', template)

    def test_finance_js_uses_edge_swipes_for_left_and_right_drawers(self):
        js = self._read("twocomms_django_theme/static/js/finance.js")

        self.assertIn("EDGE_SWIPE_WIDTH", js)
        self.assertIn("MIN_SWIPE_DISTANCE", js)
        self.assertIn("touchstart", js)
        self.assertIn("touchmove", js)
        self.assertIn("touchend", js)
        self.assertIn("passive: false", js)
        self.assertIn("window.FinanceSettings.open()", js)
        self.assertIn("Math.abs(deltaX) <= Math.abs(deltaY)", js)

    def test_settings_js_exposes_panel_api_and_push_disclosure(self):
        js = self._read("twocomms_django_theme/static/js/finance-pwa.js")

        self.assertIn("window.FinanceSettings", js)
        self.assertIn("fin-push-disclosure", js)
        self.assertIn("fin-push-settings-content", js)

    def test_settings_sections_do_not_shrink_over_expanded_push_content(self):
        css = self._read("twocomms_django_theme/static/css/finance.css")

        self.assertRegex(
            css,
            r"\.fin-settings-panel__body\s*>\s*\.fin-settings-section\s*\{[^}]*flex:\s*0\s+0\s+auto;",
        )
        self.assertIn("grid-template-columns: repeat(auto-fit, minmax(126px, 1fr));", css)
