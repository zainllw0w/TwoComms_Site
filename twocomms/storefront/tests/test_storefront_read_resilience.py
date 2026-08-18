from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.db import OperationalError
from django.test import SimpleTestCase

from storefront.services.catalog_helpers import (
    build_color_preview_map,
    get_categories_cached,
)
from storefront.services.color_filter import build_available_colors


class StorefrontReadResilienceTests(SimpleTestCase):
    def test_color_preview_map_runs_inside_disconnect_retry_boundary(self):
        product = SimpleNamespace(id=7, final_price=100)
        retry = Mock(side_effect=lambda operation, **kwargs: operation())

        with patch(
            "storefront.services.catalog_helpers.retry_mysql_read",
            retry,
        ), patch(
            "storefront.services.catalog_helpers._load_product_color_variant_queryset",
            return_value=[],
        ):
            self.assertEqual(build_color_preview_map([product]), {})

        retry.assert_called_once()

    def test_color_preview_map_retries_a_real_mysql_disconnect(self):
        product = SimpleNamespace(id=7, final_price=100)
        loader = Mock(
            side_effect=[OperationalError(2006, "server has gone away"), []]
        )

        with patch(
            "storefront.services.catalog_helpers._load_product_color_variant_queryset",
            loader,
        ), patch("twocomms.db_resilience.connections") as connections:
            db = connections.__getitem__.return_value
            db.in_atomic_block = False
            self.assertEqual(build_color_preview_map([product]), {})

        self.assertEqual(loader.call_count, 2)
        db.close.assert_called_once_with()

    def test_available_colors_runs_inside_disconnect_retry_boundary(self):
        base_queryset = Mock()
        base_queryset.values_list.return_value = []
        retry = Mock(side_effect=lambda operation, **kwargs: operation())

        with patch("storefront.services.color_filter.retry_mysql_read", retry):
            self.assertEqual(
                build_available_colors(
                    base_queryset,
                    SimpleNamespace(GET={}),
                    [],
                ),
                [],
            )

        retry.assert_called_once()

    def test_categories_use_disconnect_retry_boundary(self):
        cache_backend = Mock()
        cache_backend.get.return_value = None
        retry = Mock(side_effect=lambda operation, **kwargs: operation())

        with patch(
            "storefront.services.catalog_helpers.retry_mysql_read",
            retry,
        ), patch(
            "storefront.services.catalog_helpers.apps.get_model",
            return_value=SimpleNamespace(
                objects=SimpleNamespace(
                    filter=lambda **kwargs: SimpleNamespace(
                        order_by=lambda *args: []
                    )
                )
            ),
        ):
            self.assertEqual(get_categories_cached(cache_backend), [])

        retry.assert_called_once()
