from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase


class SendUtmReportEmailPolicyTests(SimpleTestCase):
    @patch("storefront.management.commands.send_utm_report.EmailMessage")
    @patch(
        "storefront.management.commands.send_utm_report.Command._generate_html_report",
        return_value="<p>report</p>",
    )
    @patch(
        "storefront.management.commands.send_utm_report.get_repeat_purchase_rate",
        return_value={},
    )
    @patch(
        "storefront.management.commands.send_utm_report.get_source_ltv_comparison",
        return_value=[],
    )
    @patch("storefront.management.commands.send_utm_report.compare_periods", return_value={})
    @patch("storefront.management.commands.send_utm_report.get_geo_stats", return_value=[])
    @patch("storefront.management.commands.send_utm_report.get_funnel_stats", return_value={})
    @patch("storefront.management.commands.send_utm_report.get_campaigns_stats", return_value=[])
    @patch("storefront.management.commands.send_utm_report.get_sources_stats", return_value=[])
    @patch("storefront.management.commands.send_utm_report.get_general_stats", return_value={})
    def test_smtp_failure_is_logged_and_raised_as_command_error(
        self,
        _general,
        _sources,
        _campaigns,
        _funnel,
        _geo,
        _comparison,
        _ltv,
        _repeat,
        _render,
        email_class,
    ):
        email_class.return_value.send.side_effect = OSError("SMTP unavailable")

        with self.assertLogs(
            "storefront.management.commands.send_utm_report", level="ERROR"
        ) as logs, self.assertRaisesMessage(CommandError, "SMTP unavailable"):
            call_command(
                "send_utm_report",
                period="week",
                recipients="ops@example.com",
                format="html",
                attach_csv=False,
                dry_run=False,
            )

        self.assertIn("Ошибка при отправке UTM отчета", "\n".join(logs.output))
        email_class.return_value.send.assert_called_once_with(using="reports")
