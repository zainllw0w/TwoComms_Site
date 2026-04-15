import unittest

from storefront.custom_print_config import (
    build_custom_print_config,
    build_placement_specs,
    normalize_custom_print_snapshot,
)


class CustomPrintConfigContractTests(unittest.TestCase):
    def test_config_exposes_progress_steps_tshirt_rules_and_zone_presets(self):
        config = build_custom_print_config(
            submit_url="https://twocomms.shop/custom-print/lead/",
            safe_exit_url="https://twocomms.shop/custom-print/safe-exit/",
            add_to_cart_url="https://twocomms.shop/custom-print/add-to-cart/",
        )

        self.assertEqual(
            [item["value"] for item in config["progress_steps"]],
            ["mode", "product", "config", "zones", "artwork", "quantity", "gift", "contact"],
        )
        self.assertEqual(
            [item["value"] for item in config["front_size_presets"]],
            ["A6", "A5", "A4"],
        )
        self.assertEqual(
            [item["value"] for item in config["back_size_presets"]],
            ["A4", "A3", "A2"],
        )
        self.assertEqual(
            [item["value"] for item in config["sleeve_mode_options"]],
            ["a6", "full_text"],
        )
        self.assertEqual(config["front_size_default"], "A4")
        self.assertEqual(config["back_size_default"], "A4")
        self.assertEqual(config["artwork_services"][1]["price_delta"], 150)
        self.assertEqual(config["artwork_services"][2]["price_delta"], 300)
        self.assertEqual(config["products"]["hoodie"]["add_ons"][0]["price_delta"], 150)
        self.assertEqual(
            [item["value"] for item in config["products"]["tshirt"]["fits"]],
            ["regular", "oversize"],
        )
        self.assertEqual(
            [item["value"] for item in config["products"]["tshirt"]["fabrics"]["regular"]],
            ["premium", "thermo"],
        )
        self.assertEqual(config["products"]["tshirt"]["fabrics"]["regular"][1]["price_delta"], 500)

    def test_normalize_snapshot_preserves_zone_sizes_sleeves_and_legacy_lacing(self):
        normalized = normalize_custom_print_snapshot(
            {
                "product": {
                    "type": "tshirt",
                    "fit": "oversize",
                    "fabric": "thermo",
                    "color": "graphite",
                },
                "print": {
                    "zones": ["front", "back", "sleeve"],
                    "add_ons": ["grommets"],
                    "zone_options": {
                        "front": {
                            "size_preset": "A4",
                        },
                        "back": {
                            "size_preset": "A2",
                        },
                        "sleeve": {
                            "left_enabled": True,
                            "right_enabled": True,
                            "left_mode": "full_text",
                            "left_text": "TWOCOMMS",
                            "right_mode": "a6",
                        },
                    },
                },
            }
        )

        self.assertEqual(normalized["product"]["fit"], "oversize")
        self.assertEqual(normalized["product"]["fabric"], "thermo")
        self.assertEqual(normalized["print"]["add_ons"], [])
        self.assertEqual(normalized["print"]["zone_options"]["front"]["size_preset"], "A4")
        self.assertEqual(normalized["print"]["zone_options"]["back"]["size_preset"], "A2")
        self.assertTrue(normalized["print"]["zone_options"]["sleeve"]["left_enabled"])
        self.assertTrue(normalized["print"]["zone_options"]["sleeve"]["right_enabled"])
        self.assertEqual(normalized["print"]["zone_options"]["sleeve"]["left_mode"], "full_text")
        self.assertEqual(normalized["print"]["zone_options"]["sleeve"]["left_text"], "TWOCOMMS")

    def test_normalize_snapshot_defaults_front_size_when_front_is_selected(self):
        normalized = normalize_custom_print_snapshot(
            {
                "product": {
                    "type": "tshirt",
                    "color": "black",
                },
                "print": {
                    "zones": ["front"],
                },
            }
        )

        self.assertEqual(normalized["print"]["zone_options"]["front"]["size_preset"], "A4")

    def test_build_placement_specs_expand_back_and_both_sleeves(self):
        specs = build_placement_specs(
            {
                "print": {
                    "zones": ["front", "back", "sleeve"],
                    "zone_options": {
                        "front": {
                            "size_preset": "A5",
                        },
                        "back": {
                            "size_preset": "A2",
                        },
                        "sleeve": {
                            "left_enabled": True,
                            "right_enabled": True,
                            "left_mode": "full_text",
                            "left_text": "LEFT TEXT",
                            "right_mode": "a6",
                        },
                    },
                }
            }
        )

        self.assertEqual(specs[0]["zone"], "front")
        self.assertEqual(specs[0]["size_preset"], "A5")
        self.assertEqual(specs[1]["zone"], "back")
        self.assertEqual(specs[1]["size_preset"], "A2")
        self.assertEqual(specs[2]["placement_key"], "sleeve_left")
        self.assertEqual(specs[2]["mode"], "full_text")
        self.assertEqual(specs[2]["text"], "LEFT TEXT")
        self.assertEqual(specs[3]["placement_key"], "sleeve_right")
        self.assertEqual(specs[3]["mode"], "a6")


if __name__ == "__main__":
    unittest.main()
