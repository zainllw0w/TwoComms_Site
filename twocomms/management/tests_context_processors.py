from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase, override_settings

from management import context_processors


class ManagementShellContextTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @override_settings(ROOT_URLCONF="twocomms.urls")
    def test_main_site_skips_management_shell_context_for_staff_user(self):
        request = self.factory.get("/", HTTP_HOST="twocomms.shop")
        request.user = SimpleNamespace(
            is_authenticated=True,
            is_staff=True,
        )

        with patch.object(
            context_processors,
            "build_management_shell_metrics",
            side_effect=AssertionError("management shell metrics should not load on main site"),
        ):
            context = context_processors.management_shell_context(request)

        self.assertEqual(context, {})

    @override_settings(ROOT_URLCONF="twocomms.urls_management")
    def test_management_site_keeps_management_shell_context_for_staff_user(self):
        request = self.factory.get("/", HTTP_HOST="management.twocomms.shop")
        request.user = SimpleNamespace(
            is_authenticated=True,
            is_staff=True,
        )

        metrics = {
            "management_shell_payout_url": "/payouts/",
            "management_shell_payout_available": 0,
            "management_shell_has_active_payout_request": False,
        }

        with patch.object(context_processors, "build_management_shell_metrics", return_value=metrics) as mocked_build:
            context = context_processors.management_shell_context(request)

        mocked_build.assert_called_once_with(request.user, None)
        self.assertEqual(context["management_shell_role_label"], "Адміністратор")
        self.assertEqual(context["management_shell_stats_url"], "/stats/admin/")
        self.assertEqual(context["management_shell_payout_url"], "/payouts/")
