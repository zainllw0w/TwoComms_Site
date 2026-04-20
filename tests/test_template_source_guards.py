import re
import unittest
from pathlib import Path


BASE_TEMPLATE = Path(
    "/Users/zainllw0w/TwoComms/site/twocomms/twocomms_django_theme/templates/base.html"
)
HOME_TEMPLATE = Path(
    "/Users/zainllw0w/TwoComms/site/twocomms/twocomms_django_theme/templates/pages/index.html"
)
SETTINGS_FILE = Path(
    "/Users/zainllw0w/TwoComms/site/twocomms/twocomms/settings.py"
)
CATALOG_VIEWS_FILE = Path(
    "/Users/zainllw0w/TwoComms/site/twocomms/storefront/views/catalog.py"
)
DTF_ANIMATIONS_FILE = Path(
    "/Users/zainllw0w/TwoComms/site/twocomms/dtf/static/dtf/css/components/animations.css"
)
ANALYTICS_LOADER_FILE = Path(
    "/Users/zainllw0w/TwoComms/site/twocomms/twocomms_django_theme/static/js/analytics-loader.js"
)


class BaseTemplateSourceGuardsTests(unittest.TestCase):
    def _multiline_hash_comments(self, template_path: Path):
        content = template_path.read_text(encoding="utf-8")
        multiline_comments = []
        cursor = 0

        while True:
            start = content.find("{#", cursor)
            if start == -1:
                break
            end = content.find("#}", start + 2)
            if end == -1:
                break

            comment = content[start : end + 2]
            if "\n" in comment:
                multiline_comments.append(comment)
            cursor = end + 2

        return multiline_comments

    def test_base_template_avoids_multiline_django_hash_comments(self):
        multiline_comments = self._multiline_hash_comments(BASE_TEMPLATE)

        self.assertEqual(
            multiline_comments,
            [],
            "base.html must not use multiline {# ... #} comments because they leak into rendered HTML",
        )

    def test_home_template_avoids_multiline_django_hash_comments(self):
        multiline_comments = self._multiline_hash_comments(HOME_TEMPLATE)

        self.assertEqual(
            multiline_comments,
            [],
            "index.html must not use multiline {# ... #} comments because they leak into rendered HTML",
        )

    def test_base_template_keeps_homepage_footer_and_rum_assets(self):
        content = BASE_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn("css/support-hub.css", content)
        self.assertIn("js/rum.js", content)
        self.assertIn("js/ui-fallback.js", content)
        self.assertNotIn("css/fonts.css", content)
        self.assertIn("js/analytics-loader.js' %}?v=5", content)

    def test_base_template_does_not_embed_server_generated_csrf_token(self):
        content = BASE_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn('<meta name="csrf-token" content="">', content)
        self.assertNotIn('content="{{ csrf_token }}"', content)
        self.assertIn("getCookie('csrftoken')", content)

    def test_base_template_uses_client_side_sync_hints(self):
        content = BASE_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn("readSyncHint('twc-sync-cart')", content)
        self.assertIn("readSyncHint('twc-sync-favs')", content)
        self.assertNotIn("sync_cart_badge|yesno", content)
        self.assertNotIn("sync_favorites_badge|yesno", content)

    def test_base_template_inlines_all_inter_weights_to_prevent_duplicate_font_fetches(self):
        content = BASE_TEMPLATE.read_text(encoding="utf-8")

        for weight in ("400", "500", "600", "700"):
            self.assertIn(f"font-weight: {weight};", content)

    def test_base_template_enables_effects_lite_for_mid_devices(self):
        content = BASE_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn("} else if (deviceClass === 'mid') {", content)
        self.assertIn("docEl.classList.add('effects-lite');", content)
        self.assertIn("docEl.classList.remove('effects-high', 'perf-lite');", content)

    def test_settings_drop_session_sync_context_processor(self):
        settings_source = SETTINGS_FILE.read_text(encoding="utf-8")

        self.assertNotIn("storefront.context_processors.user_state_hint", settings_source)

    def test_catalog_views_keep_csrf_cookie_on_cached_catalog_pages(self):
        source = CATALOG_VIEWS_FILE.read_text(encoding="utf-8")

        self.assertRegex(
            source,
            r"@ensure_csrf_cookie\s+@cache_page_for_anon\(600\)[^\n]*\ndef catalog",
        )

    def test_dtf_mobile_dock_animation_keeps_horizontal_centering(self):
        source = DTF_ANIMATIONS_FILE.read_text(encoding="utf-8")

        self.assertIn("transform: translateX(-50%) translateY(120%);", source)
        self.assertIn("transform: translateX(-50%) translateY(0);", source)

    def test_analytics_loader_keeps_clarity_off_home_idle_path(self):
        source = ANALYTICS_LOADER_FILE.read_text(encoding="utf-8")

        self.assertIn("if (!isLowDevice && routeName !== 'home') {", source)
        self.assertIn("if (!isLowDevice && routeName === 'home') {", source)
        self.assertIn("loadClarityOnFirstInteraction();", source)


if __name__ == "__main__":
    unittest.main()
