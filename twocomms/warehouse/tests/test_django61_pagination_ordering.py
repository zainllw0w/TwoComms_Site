from django.contrib.contenttypes.models import ContentType
from django.core.paginator import Paginator
from django.test import TestCase
from django.utils import timezone

from warehouse.models import StockMovement
from warehouse.views import history


class WarehousePaginationOrderingTests(TestCase):
    def test_history_is_totally_ordered_across_tie_boundary(self):
        content_type = ContentType.objects.get_for_model(StockMovement)
        movements = [
            StockMovement.objects.create(
                content_type=content_type,
                object_id=index + 1,
                delta=1,
                quantity_after=index + 1,
            )
            for index in range(3)
        ]
        tie_at = timezone.now().replace(microsecond=0)
        StockMovement.objects.filter(pk__in=[movement.pk for movement in movements]).update(
            created_at=tie_at
        )
        builder = getattr(history, "_history_queryset", None)

        self.assertIsNotNone(builder)
        queryset = builder()
        self.assertEqual(queryset.query.order_by, ("-created_at", "-id"))
        self.assertTrue(queryset.totally_ordered)

        paginator = Paginator(queryset, 2)
        actual_ids = [
            movement.pk
            for page_number in paginator.page_range
            for movement in paginator.page(page_number).object_list
        ]
        self.assertEqual(actual_ids, [movement.pk for movement in reversed(movements)])
        self.assertEqual(len(actual_ids), len(set(actual_ids)))
