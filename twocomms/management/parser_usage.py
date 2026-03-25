from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import os

from django.db.models import Sum
from django.utils import timezone

from .models import LeadParsingJob


CURRENT_PLACES_SKU = "Text Search Enterprise"
CURRENT_FIELD_MASK_VERSION = "text_search_enterprise_contacts_v4_types_region_ua"
ENTERPRISE_FREE_MONTHLY_CALLS = 1000


@dataclass(slots=True)
class ParserUsageSnapshot:
    provider_status: str
    sku: str
    field_mask_version: str
    free_monthly_calls: int
    local_30d_usage: int
    current_billing_month_usage: int
    google_project_usage: int | None


class LocalParserUsageProvider:
    status = "not_connected"

    def fetch(self) -> ParserUsageSnapshot:
        now = timezone.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        local_30d_usage = (
            LeadParsingJob.objects.filter(started_at__gte=now - timedelta(days=30)).aggregate(total=Sum("request_count")).get("total")
            or 0
        )
        current_billing_month_usage = (
            LeadParsingJob.objects.filter(started_at__gte=month_start).aggregate(total=Sum("request_count")).get("total")
            or 0
        )
        return ParserUsageSnapshot(
            provider_status=self.status,
            sku=CURRENT_PLACES_SKU,
            field_mask_version=CURRENT_FIELD_MASK_VERSION,
            free_monthly_calls=ENTERPRISE_FREE_MONTHLY_CALLS,
            local_30d_usage=int(local_30d_usage),
            current_billing_month_usage=int(current_billing_month_usage),
            google_project_usage=None,
        )


class GoogleProjectUsageProvider:
    status = "not_connected"

    def is_configured(self) -> bool:
        return bool((os.environ.get("GOOGLE_CLOUD_PROJECT") or "").strip())

    def fetch(self) -> ParserUsageSnapshot | None:
        if not self.is_configured():
            return None
        return None


def parser_usage_snapshot() -> ParserUsageSnapshot:
    google_provider = GoogleProjectUsageProvider()
    google_snapshot = google_provider.fetch()
    if google_snapshot is not None:
        return google_snapshot
    return LocalParserUsageProvider().fetch()
