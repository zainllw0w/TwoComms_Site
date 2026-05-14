"""
Pre-warm GA4 + Clarity caches outside of dashboard requests.

Run from cron every few hours so that admins always see fresh data without
paying the latency of a live API call (and without burning Clarity's tiny
10-request/day quota on user-facing pageloads).

Example crontab entry (every 4 hours):

    0 */4 * * * cd /home/qlknpodo/TWC/TwoComms_Site/twocomms && \
        /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.14/bin/python \
        manage.py refresh_external_analytics >> /tmp/refresh_external.log 2>&1
"""

from __future__ import annotations

import logging
import sys
from datetime import date, timedelta

from django.core.management.base import BaseCommand

from storefront.services import external_analytics as ext

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Refresh GA4 + Clarity caches from cron (stale-while-revalidate prefetch)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-ga4",
            action="store_true",
            help="Do not refresh GA4 (e.g. when running with a limited service account).",
        )
        parser.add_argument(
            "--skip-clarity",
            action="store_true",
            help="Do not refresh Clarity (useful when quota is exhausted).",
        )

    def handle(self, *args, **options):
        exit_code = 0

        if not options["skip_ga4"]:
            try:
                self._refresh_ga4()
            except Exception as exc:  # noqa: BLE001
                self.stderr.write(self.style.ERROR(f"GA4 refresh failed: {exc}"))
                logger.exception("GA4 refresh failed")
                exit_code = 1

        if not options["skip_clarity"]:
            try:
                self._refresh_clarity()
            except Exception as exc:  # noqa: BLE001
                self.stderr.write(self.style.ERROR(f"Clarity refresh failed: {exc}"))
                logger.exception("Clarity refresh failed")
                exit_code = 1

        sys.exit(exit_code)

    # ------------------------------------------------------------------
    # GA4
    # ------------------------------------------------------------------
    def _refresh_ga4(self) -> None:
        status = ext.get_ga4_status(test_connection=True)
        self.stdout.write(f"GA4 status: {status['status']} — {status['message']}")
        if status["status"] != "healthy":
            self.stdout.write(self.style.WARNING("Skipping GA4 prefetch (status != healthy)."))
            return

        # Match the default window used by the admin overview tab so the
        # prefetched cache hits the same key.
        end_date = date.today()
        start_date = end_date - timedelta(days=7)
        try:
            ext.fetch_ga4_acquisition_snapshot(start_date=start_date, end_date=end_date)
            self.stdout.write(self.style.SUCCESS("GA4 acquisition snapshot refreshed."))
        except Exception as exc:  # noqa: BLE001
            self.stdout.write(self.style.WARNING(f"GA4 acquisition snapshot: {exc}"))

    # ------------------------------------------------------------------
    # Clarity
    # ------------------------------------------------------------------
    def _refresh_clarity(self) -> None:
        token = ext._clarity_token()
        if not token:
            self.stdout.write(self.style.WARNING("Clarity token not configured — skipping."))
            return

        quota = ext.get_clarity_quota_state()
        self.stdout.write(
            f"Clarity quota before refresh: {quota['used']}/{quota['limit']} "
            f"(remaining {quota['remaining']})."
        )
        if not ext._clarity_budget_allows_call():
            self.stdout.write(
                self.style.WARNING(
                    "Clarity daily budget already at reserve — skipping prefetch."
                )
            )
            return

        # Overview (no dimension) + URL breakdown = 2 calls per run.
        # At 6 calls/day max (3 cron runs) we stay well under the 10/day cap
        # and still leave 4 slots for manual probes and dashboard reload pings.
        try:
            ext.fetch_clarity_overview(num_of_days=1)
            self.stdout.write(self.style.SUCCESS("Clarity overview snapshot refreshed."))
        except ext.ClarityQuotaExhausted as exc:
            self.stdout.write(self.style.WARNING(f"Clarity overview: {exc}"))
            return
        except Exception as exc:  # noqa: BLE001
            self.stdout.write(self.style.WARNING(f"Clarity overview: {exc}"))

        if not ext._clarity_budget_allows_call():
            self.stdout.write(
                self.style.WARNING(
                    "Skipping problem-URL prefetch to preserve quota reserve."
                )
            )
            return

        try:
            ext.fetch_clarity_problem_urls(num_of_days=1)
            self.stdout.write(self.style.SUCCESS("Clarity problem URLs snapshot refreshed."))
        except Exception as exc:  # noqa: BLE001
            self.stdout.write(self.style.WARNING(f"Clarity problem URLs: {exc}"))

        final_quota = ext.get_clarity_quota_state()
        self.stdout.write(
            f"Clarity quota after refresh: {final_quota['used']}/{final_quota['limit']}."
        )
