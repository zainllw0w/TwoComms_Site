import unittest
from pathlib import Path

from storefront.custom_print_config import build_custom_print_config


REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = REPO_ROOT / "twocomms/twocomms_django_theme/templates/pages/custom_print.html"
PREVIEW_JS = REPO_ROOT / "twocomms/twocomms_django_theme/static/js/custom-print-preview.js"
STUDIO_CSS = REPO_ROOT / "twocomms/twocomms_django_theme/static/css/custom-print-guided-studio.css"
ASSET_ROOT = REPO_ROOT / "twocomms/twocomms_django_theme/static/img/configurator/custom-ref"


class CustomPrintReferenceStageContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = build_custom_print_config(submit_url="/lead/", safe_exit_url="/exit/")
        cls.assets = cls.config["custom_ref_preview_assets"]

    def test_reference_matrix_matches_supplied_front_and_back_pairs(self):
        self.assertEqual(set(self.assets["tshirt:regular"]), {"black"})
        self.assertEqual(set(self.assets["tshirt:oversize"]), {"beige", "black", "white"})
        self.assertEqual(set(self.assets["hoodie:regular"]), {"black", "pink"})
        self.assertEqual(set(self.assets["hoodie:oversize"]), {"black", "pink"})

    def test_selectable_fit_colors_match_available_reference_renders(self):
        products = self.config["products"]
        fit_colors = {}
        for product in ("tshirt", "hoodie"):
            product_config = products[product]
            fit_colors[product] = {}
            for fit in ("regular", "oversize"):
                palette = product_config.get("fit_colors", {}).get(fit, product_config["colors"])
                fit_colors[product][fit] = {color["value"] for color in palette}

        self.assertEqual(fit_colors["tshirt"]["regular"], {"black"})
        self.assertEqual(fit_colors["tshirt"]["oversize"], {"black", "white", "coyote"})
        self.assertEqual(fit_colors["hoodie"]["regular"], {"black", "pink"})
        self.assertEqual(fit_colors["hoodie"]["oversize"], {"black", "pink"})

    def test_every_reference_has_decodable_avif_and_webp_paths(self):
        for profile, colors in self.assets.items():
            for color, sides in colors.items():
                self.assertEqual(set(sides), {"front", "back"}, (profile, color))
                for side, sources in sides.items():
                    self.assertEqual(set(sources), {"avif", "webp"})
                    for extension, url in sources.items():
                        self.assertTrue(url.endswith(f".{extension}"), (profile, color, side, url))
                        path = REPO_ROOT / "twocomms/twocomms_django_theme/static" / url.removeprefix("/static/")
                        self.assertTrue(path.is_file(), path)
                        self.assertGreater(path.stat().st_size, 0, path)

    def test_template_uses_picture_sources_in_both_previews_and_no_3d_module(self):
        template = TEMPLATE.read_text(encoding="utf-8")
        self.assertEqual(template.count("data-preview-picture"), 2)
        self.assertEqual(template.count("data-preview-avif"), 2)
        self.assertEqual(template.count("data-preview-webp"), 2)
        self.assertNotIn("custom-print-3d-viewer.js", template)

    def test_stage_has_no_legacy_yellow_floor_glow(self):
        source = STUDIO_CSS.read_text(encoding="utf-8")
        self.assertNotIn(".cp-stage-frame::after", source)
        self.assertNotIn(".cp-preview-dialog-canvas::after", source)
        self.assertNotIn("rgba(211, 157, 82, .24)", source)

    def test_preview_resolver_has_color_aliases_and_declared_fallback(self):
        source = PREVIEW_JS.read_text(encoding="utf-8")
        self.assertIn('coyote: "beige"', source)
        self.assertIn('thermo_pink: "pink"', source)
        self.assertIn("function resolveGarmentRender", source)
        self.assertIn("fallbackUsed: previewColor !== requestedRenderColor", source)
        self.assertIn("sources: profile[previewColor]", source)
        self.assertIn("render.sources[view] || render.sources.front", source)
        self.assertIn('preload.type = "image/avif"', source)
        self.assertIn('warmCurrentProfile(state)', source)

    def test_preview_preloads_current_side_and_defers_back_side(self):
        source = PREVIEW_JS.read_text(encoding="utf-8")
        self.assertIn("const render = resolveGarmentRender(profiles, profileKey(state), state.product.color);", source)
        self.assertIn("const variant = render?.sources;", source)
        self.assertIn('["front", "back"].forEach((side)', source)
        self.assertIn("if (side === view)", source)
        self.assertIn("scheduleBackWarmup(sources.avif)", source)
        self.assertNotIn('Object.values(profile).forEach((variant)', source)

    def test_desktop_stage_hides_duplicate_preview_action(self):
        source = STUDIO_CSS.read_text(encoding="utf-8")
        self.assertIn("@media (min-width: 1101px)", source)
        self.assertIn(".cp-stage-card .cp-preview-open { display: none; }", source)


if __name__ == "__main__":
    unittest.main()
