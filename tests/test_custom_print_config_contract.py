import unittest

from storefront.custom_print_config import (
    build_custom_print_config,
    build_placement_specs,
    normalize_custom_print_snapshot,
)


class CustomPrintConfigContractTests(unittest.TestCase):
    def test_config_exposes_progress_steps_and_front_size_presets(self):
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
        self.assertEqual(config["front_size_default"], "A4")
        self.assertEqual(config["artwork_services"][1]["price_delta"], 150)
        self.assertEqual(config["artwork_services"][2]["price_delta"], 300)
        self.assertEqual(config["products"]["hoodie"]["add_ons"][0]["price_delta"], 150)

    def test_normalize_snapshot_preserves_front_size_and_legacy_lacing(self):
        normalized = normalize_custom_print_snapshot(
            {
                "product": {
                    "type": "hoodie",
                    "fit": "oversize",
                    "fabric": "standard",
                    "color": "graphite",
                },
                "print": {
                    "zones": ["front", "back"],
                    "add_ons": ["grommets"],
                    "zone_options": {
                        "front": {
                            "size_preset": "A4",
                        }
                    },
                },
            }
        )

        self.assertEqual(normalized["product"]["fabric"], "premium")
        self.assertEqual(normalized["print"]["add_ons"], ["lacing"])
        self.assertEqual(normalized["print"]["zone_options"]["front"]["size_preset"], "A4")

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

    def test_build_placement_specs_carries_front_size_preset(self):
        specs = build_placement_specs(
            {
                "print": {
                    "zones": ["front", "back"],
                    "zone_options": {
                        "front": {
                            "size_preset": "A5",
                        }
                    },
                }
            }
        )

        self.assertEqual(specs[0]["zone"], "front")
        self.assertEqual(specs[0]["size_preset"], "A5")
        self.assertEqual(specs[1]["zone"], "back")
        self.assertNotIn("size_preset", specs[1])


if __name__ == "__main__":
    unittest.main()
