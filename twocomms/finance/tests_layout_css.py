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
