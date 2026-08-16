from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.test import TestCase
from django.utils import timezone

from management import checker_views, network_views, parsing_views, shop_views, views
from management.models import LeadNetwork, ManagementLead, Shop


class ManagementPaginationOrderingTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username="pagination-admin",
            is_staff=True,
        )
        self.tie_at = timezone.now().replace(microsecond=0)

    def assert_tie_boundary(self, queryset, expected_ids):
        self.assertTrue(queryset.totally_ordered)
        paginator = Paginator(queryset, 2)
        actual_ids = [
            obj.pk
            for page_number in paginator.page_range
            for obj in paginator.page(page_number).object_list
        ]
        self.assertEqual(actual_ids, expected_ids)
        self.assertEqual(len(actual_ids), len(set(actual_ids)))

    def create_tied_shops(self):
        shops = [Shop.objects.create(name=f"Shop {index}") for index in range(3)]
        Shop.objects.filter(pk__in=[shop.pk for shop in shops]).update(created_at=self.tie_at)
        return shops

    def test_admin_shop_cards_are_totally_ordered_across_tie_boundary(self):
        shops = self.create_tied_shops()
        builder = getattr(views, "_admin_shops_queryset", None)

        self.assertIsNotNone(builder)
        queryset = builder()
        self.assertEqual(queryset.query.order_by, ("-created_at", "-id"))
        self.assert_tie_boundary(queryset, [shop.pk for shop in reversed(shops)])

    def test_shop_page_is_totally_ordered_across_tie_boundary(self):
        shops = self.create_tied_shops()
        builder = getattr(shop_views, "_shops_queryset", None)

        self.assertIsNotNone(builder)
        queryset = builder(self.staff)
        self.assertEqual(queryset.query.order_by, ("-created_at", "-id"))
        self.assert_tie_boundary(queryset, [shop.pk for shop in reversed(shops)])

    def test_network_api_is_totally_ordered_across_tie_boundary(self):
        networks = [
            LeadNetwork.objects.create(
                canonical_name=f"Network {index}",
                slug=f"network-{index}",
                members_count=7,
            )
            for index in range(3)
        ]
        LeadNetwork.objects.filter(pk__in=[network.pk for network in networks]).update(
            updated_at=self.tie_at
        )

        queryset = network_views._networks_queryset(q="", policy="", state="all")

        self.assertEqual(
            queryset.query.order_by,
            ("-members_count", "-updated_at", "-id"),
        )
        self.assert_tie_boundary(queryset, [network.pk for network in reversed(networks)])

    def test_checker_api_is_totally_ordered_across_tie_boundary(self):
        leads = [
            ManagementLead.objects.create(
                shop_name=f"Checked {index}",
                phone=f"+380000000{index:03d}",
                lead_source=ManagementLead.LeadSource.PARSER,
                ai_score=80,
                ai_checked_at=self.tie_at,
            )
            for index in range(3)
        ]

        queryset = checker_views._results_queryset("all", "", "", "")

        self.assertEqual(
            queryset.query.order_by,
            ("-ai_score", "-ai_checked_at", "-id"),
        )
        self.assert_tie_boundary(queryset, [lead.pk for lead in reversed(leads)])

    def test_moderation_api_is_totally_ordered_across_tie_boundary(self):
        leads = [
            ManagementLead.objects.create(
                shop_name=f"Moderation {index}",
                phone=f"+380111111{index:03d}",
                status=ManagementLead.Status.MODERATION,
            )
            for index in range(3)
        ]
        ManagementLead.objects.filter(pk__in=[lead.pk for lead in leads]).update(
            created_at=self.tie_at
        )

        queryset = parsing_views._moderation_queryset()

        self.assertEqual(queryset.query.order_by, ("-created_at", "-id"))
        self.assert_tie_boundary(queryset, [lead.pk for lead in reversed(leads)])
