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
            ["standard", "premium"],
        )
        self.assertEqual(
            [item["value"] for item in config["products"]["tshirt"]["fabrics"]["oversize"]],
            ["standard", "premium", "thermo"],
        )
        self.assertEqual(config["products"]["tshirt"]["fabrics"]["oversize"][2]["price_delta"], 500)
        self.assertIn("stage_profiles", config)
        self.assertIn("hoodie", config["stage_profiles"])
        self.assertIn("regular", config["stage_profiles"]["hoodie"])
        self.assertIn("oversize", config["stage_profiles"]["hoodie"])

    def test_config_exposes_clean_hoodie_fabric_labels_and_premium_info(self):
        config = build_custom_print_config(
            submit_url="https://twocomms.shop/custom-print/lead/",
            safe_exit_url="https://twocomms.shop/custom-print/safe-exit/",
            add_to_cart_url="https://twocomms.shop/custom-print/add-to-cart/",
        )

        oversize_fabrics = config["products"]["hoodie"]["fabrics"]["oversize"]
        self.assertEqual(
            [item["value"] for item in oversize_fabrics],
            ["standard", "premium"],
        )
        self.assertEqual(oversize_fabrics[0]["label"], "Стандарт")
        self.assertEqual(oversize_fabrics[1]["label"], "Преміум")
        self.assertEqual(oversize_fabrics[1]["price_delta"], 250)
        self.assertEqual(oversize_fabrics[1]["info_theme"], "premium")
        self.assertIn("вищу щільність", oversize_fabrics[1]["info_desc"])

    def test_stage_profiles_expose_distinct_back_presets_for_a4_a3_a2(self):
        config = build_custom_print_config(
            submit_url="https://twocomms.shop/custom-print/lead/",
            safe_exit_url="https://twocomms.shop/custom-print/safe-exit/",
            add_to_cart_url="https://twocomms.shop/custom-print/add-to-cart/",
        )

        back_presets = (
            config["stage_profiles"]["hoodie"]["regular"]["back"]["anchors"]["back"]["presets"]
        )
        a4 = back_presets["A4"]
        a3 = back_presets["A3"]
        a2 = back_presets["A2"]

        self.assertLess(a4["width"], a3["width"])
        self.assertLess(a3["width"], a2["width"])
        self.assertLess(a4["height"], a3["height"])
        self.assertLess(a3["height"], a2["height"])
        self.assertGreater(a2["y"], a3["y"])

    def test_normalize_snapshot_preserves_zone_sizes_sleeves_and_legacy_lacing(self):
        normalized = normalize_custom_print_snapshot(
            {
                "product": {
                    "type": "hoodie",
                    "fit": "oversize",
                    "fabric": "premium",
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
        self.assertEqual(normalized["product"]["fabric"], "premium")
        self.assertEqual(normalized["print"]["add_ons"], ["lacing"])
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
        self.assertTrue(specs[0]["requires_artwork_file"])
        self.assertEqual(specs[0]["file_index"], 0)
        self.assertEqual(specs[1]["zone"], "back")
        self.assertEqual(specs[1]["size_preset"], "A2")
        self.assertTrue(specs[1]["requires_artwork_file"])
        self.assertEqual(specs[1]["file_index"], 1)
        self.assertEqual(specs[2]["placement_key"], "sleeve_left")
        self.assertEqual(specs[2]["mode"], "full_text")
        self.assertEqual(specs[2]["text"], "LEFT TEXT")
        self.assertFalse(specs[2]["requires_artwork_file"])
        self.assertNotIn("file_index", specs[2])
        self.assertEqual(specs[3]["placement_key"], "sleeve_right")
        self.assertEqual(specs[3]["mode"], "a6")
        self.assertTrue(specs[3]["requires_artwork_file"])
        self.assertEqual(specs[3]["file_index"], 2)

    def test_build_placement_specs_text_only_sleeve_does_not_require_file(self):
        specs = build_placement_specs(
            {
                "print": {
                    "zones": ["sleeve"],
                    "zone_options": {
                        "sleeve": {
                            "left_enabled": True,
                            "right_enabled": False,
                            "left_mode": "full_text",
                            "left_text": "TWOCOMMS",
                        },
                    },
                }
            }
        )

        self.assertEqual(len(specs), 1)
        self.assertEqual(specs[0]["placement_key"], "sleeve_left")
        self.assertFalse(specs[0]["requires_artwork_file"])
        self.assertNotIn("file_index", specs[0])


if __name__ == "__main__":
    unittest.main()
