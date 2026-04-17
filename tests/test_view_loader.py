import unittest
from types import SimpleNamespace
from unittest.mock import patch

from storefront.view_loader import load_view_attr


class ViewLoaderTests(unittest.TestCase):
    def test_returns_attr_without_reload_when_present(self):
        handler = object()
        module = SimpleNamespace(admin_custom_print_lead_moderation=handler)

        with patch("storefront.view_loader.import_module", return_value=module) as import_mock:
            with patch("storefront.view_loader.reload") as reload_mock:
                resolved = load_view_attr(
                    "storefront.views.admin",
                    "admin_custom_print_lead_moderation",
                )

        self.assertIs(resolved, handler)
        import_mock.assert_called_once_with("storefront.views.admin")
        reload_mock.assert_not_called()

    def test_reloads_module_when_attr_is_missing_on_first_import(self):
        stale_module = SimpleNamespace()
        fresh_handler = object()
        fresh_module = SimpleNamespace(admin_custom_print_lead_moderation=fresh_handler)

        with patch("storefront.view_loader.import_module", return_value=stale_module) as import_mock:
            with patch("storefront.view_loader.reload", return_value=fresh_module) as reload_mock:
                resolved = load_view_attr(
                    "storefront.views.admin",
                    "admin_custom_print_lead_moderation",
                )

        self.assertIs(resolved, fresh_handler)
        import_mock.assert_called_once_with("storefront.views.admin")
        reload_mock.assert_called_once_with(stale_module)

    def test_raises_clear_error_when_attr_is_still_missing_after_reload(self):
        stale_module = SimpleNamespace()
        fresh_module = SimpleNamespace()

        with patch("storefront.view_loader.import_module", return_value=stale_module):
            with patch("storefront.view_loader.reload", return_value=fresh_module):
                with self.assertRaises(AttributeError) as ctx:
                    load_view_attr(
                        "storefront.views.admin",
                        "admin_custom_print_lead_moderation",
                    )

        self.assertIn("storefront.views.admin", str(ctx.exception))
        self.assertIn("admin_custom_print_lead_moderation", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
