from django.test import SimpleTestCase

from twocomms.storefront import views
from twocomms.storefront.views import monobank as monobank_views


class ViewExportsTests(SimpleTestCase):
    """Ensure storefront.views re-exports functions from modular packages."""

    def test_monobank_create_invoice_points_to_new_module(self):
        """monobank_create_invoice из нового модуля не должен переопределяться старым views.py."""
        self.assertIs(
            views.monobank_create_invoice,
            monobank_views.monobank_create_invoice,
            msg="monobank_create_invoice должен ссылаться на реализацию из views.monobank"
        )
