"""WSGI integration contract for the guarded image middleware."""

from unittest.mock import patch

from django.core.handlers.wsgi import WSGIHandler
from django.test import SimpleTestCase


class ImageOptimizationMiddlewareWSGIGuardTests(SimpleTestCase):
    def test_wsgi_handler_skips_guarded_middleware_before_runtime_side_effects(self):
        with (
            patch("twocomms.image_middleware.ThreadPoolExecutor") as executor,
            patch("twocomms.image_middleware.os.makedirs") as makedirs,
        ):
            handler = WSGIHandler()

        self.assertIsNotNone(handler._middleware_chain)
        executor.assert_not_called()
        makedirs.assert_not_called()
