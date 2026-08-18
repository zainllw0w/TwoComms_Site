"""Fail-closed contracts for the request-path image optimizer."""

from unittest.mock import patch

from django.core.exceptions import MiddlewareNotUsed
from django.test import SimpleTestCase, override_settings

from .image_middleware import ImageOptimizationMiddleware


class ImageOptimizationMiddlewareGuardTests(SimpleTestCase):
    def _assert_disabled_without_runtime_side_effects(self):
        with (
            patch("twocomms.image_middleware.ThreadPoolExecutor") as executor,
            patch("twocomms.image_middleware.os.makedirs") as makedirs,
            self.assertRaisesRegex(
                MiddlewareNotUsed,
                r"DJ6-BG-010.*worker.*atomic media.*browser asset",
            ),
        ):
            ImageOptimizationMiddleware(lambda request: None)

        executor.assert_not_called()
        makedirs.assert_not_called()

    @override_settings(
        IMAGE_OPTIMIZATION_MIDDLEWARE_ENABLED=False,
        IMAGE_OPTIMIZATION_ALLOW_ON_DEMAND=False,
    )
    def test_default_configuration_disables_middleware_before_side_effects(self):
        self._assert_disabled_without_runtime_side_effects()

    @override_settings(
        IMAGE_OPTIMIZATION_MIDDLEWARE_ENABLED=True,
        IMAGE_OPTIMIZATION_ALLOW_ON_DEMAND=True,
    )
    def test_legacy_flags_cannot_bypass_missing_runtime_proof(self):
        self._assert_disabled_without_runtime_side_effects()
