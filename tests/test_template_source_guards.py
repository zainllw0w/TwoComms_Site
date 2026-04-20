import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BASE_TEMPLATE = REPO_ROOT / "twocomms" / "twocomms_django_theme" / "templates" / "base.html"
HOME_TEMPLATE = REPO_ROOT / "twocomms" / "twocomms_django_theme" / "templates" / "pages" / "index.html"
SETTINGS_FILE = REPO_ROOT / "twocomms" / "twocomms" / "settings.py"
CATALOG_VIEWS_FILE = REPO_ROOT / "twocomms" / "storefront" / "views" / "catalog.py"
DTF_ANIMATIONS_FILE = REPO_ROOT / "twocomms" / "dtf" / "static" / "dtf" / "css" / "components" / "animations.css"
ANALYTICS_LOADER_FILE = REPO_ROOT / "twocomms" / "twocomms_django_theme" / "static" / "js" / "analytics-loader.js"
HOME_CSS_FILE = REPO_ROOT / "twocomms" / "twocomms_django_theme" / "static" / "css" / "home.css"
HOME_BOOTSTRAP_SUBSET_FILE = (
    REPO_ROOT / "twocomms" / "twocomms_django_theme" / "static" / "css" / "bootstrap-home-subset.css"
)
MAIN_JS_FILE = REPO_ROOT / "twocomms" / "twocomms_django_theme" / "static" / "js" / "main.js"
STYLES_CSS_FILE = REPO_ROOT / "twocomms" / "twocomms_django_theme" / "static" / "css" / "styles.css"


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
        self.assertIn("js/main.js' %}?v=44", content)

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

    def test_base_template_keeps_ahrefs_homepage_interaction_only(self):
        content = BASE_TEMPLATE.read_text(encoding="utf-8")

        self.assertRegex(
            content,
            r"var fallbackDelay = routeName === 'home'\s*\?\s*null\s*:\s*\(deviceClass === 'low'",
        )
        self.assertIn("if (fallbackDelay !== null)", content)

    def test_base_template_uses_local_bootstrap_subset_on_home(self):
        content = BASE_TEMPLATE.read_text(encoding="utf-8")

        self.assertRegex(
            content,
            re.compile(
                r"{% if request\.resolver_match\.url_name == 'home' %}[\s\S]+css/bootstrap-home-subset\.css"
                r"[\s\S]+{% else %}[\s\S]+bootstrap@5\.3\.3/dist/css/bootstrap\.min\.css",
            ),
        )

    def test_home_css_no_longer_carries_hand_maintained_bootstrap_subset(self):
        source = HOME_CSS_FILE.read_text(encoding="utf-8")

        self.assertNotIn(".navbar-toggler-icon {", source)

    def test_home_bootstrap_subset_keeps_required_selectors(self):
        source = HOME_BOOTSTRAP_SUBSET_FILE.read_text(encoding="utf-8")

        for needle in (
            ".container-xxl{",
            ".border-bottom{",
            ".navbar-toggler-icon{",
            ".collapse:not(.show){",
            ".form-control{",
            ".modal-backdrop{",
            ".row-cols-2>*{",
            ".visually-hidden{",
            ".modal.show .modal-dialog{",
            ".disabled>.page-link",
        ):
            self.assertIn(needle, source)

    def test_main_js_keeps_bottom_nav_static_on_small_screens(self):
        source = MAIN_JS_FILE.read_text(encoding="utf-8")

        self.assertIn("const isSmallScreen = window.matchMedia('(max-width: 768px)').matches;", source)
        self.assertIn("const scrollAdaptiveEnabled = !isSmallScreen && bottomNavDeviceClass === 'high';", source)

    def test_main_js_no_longer_mutates_backdrop_filter_on_scroll(self):
        source = MAIN_JS_FILE.read_text(encoding="utf-8")

        self.assertNotIn("setProperty('backdrop-filter'", source)
        self.assertNotIn("removeProperty('backdrop-filter'", source)
        self.assertIn("setProperty('animation-play-state', 'paused', 'important');", source)

    def test_styles_css_simplifies_mobile_bottom_nav_motion(self):
        source = STYLES_CSS_FILE.read_text(encoding="utf-8")

        for needle in (
            "backdrop-filter: none !important;",
            "-webkit-backdrop-filter: none !important;",
            ".bottom-nav.bottom-nav--hidden {",
            "transform: translateX(-50%) !important;",
            ".bottom-nav-item.active .bottom-nav-icon::before {",
            "filter: none !important;",
        ):
            self.assertIn(needle, source)


if __name__ == "__main__":
    unittest.main()
