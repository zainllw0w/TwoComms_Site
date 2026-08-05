from django.contrib.admin.sites import AdminSite
from django.test import SimpleTestCase

from warehouse.admin import StockItemAdmin
from warehouse.models import StockItem


class StockItemAdminTests(SimpleTestCase):
    def test_quantity_is_read_only(self):
        model_admin = StockItemAdmin(StockItem, AdminSite())

        self.assertIn("quantity", model_admin.get_readonly_fields(request=None))
