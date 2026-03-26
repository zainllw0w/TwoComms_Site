from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta, timezone as dt_timezone
import base64
import json
import os
import time

from django.conf import settings
from django.core.cache import cache
from django.db.models import Sum
from django.utils import timezone

import jwt
import requests

from .models import LeadParsingJob


CURRENT_PLACES_SKU = "Text Search Enterprise"
CURRENT_FIELD_MASK_VERSION = "text_search_enterprise_contacts_v4_types_region_ua"
ENTERPRISE_FREE_MONTHLY_CALLS = 1000
LOCAL_USAGE_CACHE_TTL_SECONDS = 30
GOOGLE_USAGE_CACHE_TTL_SECONDS = 300
GOOGLE_USAGE_ERROR_CACHE_TTL_SECONDS = 60
GOOGLE_TOKEN_CACHE_SKEW_SECONDS = 60
GOOGLE_MONITORING_SCOPE = "https://www.googleapis.com/auth/cloud-platform"
GOOGLE_OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_MONITORING_TIMESERIES_URL = "https://monitoring.googleapis.com/v3/projects/{project_id}/timeSeries"
GOOGLE_MONITORING_USAGE_FILTER = (
    'metric.type = "maps.googleapis.com/service/v2/request_count" '
    'AND resource.type = "maps.googleapis.com/Api" '
    'AND metric.labels.platform_type = "PLATFORM_TYPE_WEBSERVICE"'
)


@dataclass(slots=True)
class ParserUsageSnapshot:
    provider_status: str
    sku: str
    field_mask_version: str
    free_monthly_calls: int
    local_30d_usage: int
    current_billing_month_usage: int
    google_project_usage: int | None


def _int_value(raw_value, default=0) -> int:
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return default


def _base_snapshot(*, provider_status: str, google_project_usage: int | None = None) -> ParserUsageSnapshot:
    cache_key = "management:parser:local-usage:v1"
    cached = cache.get(cache_key)
    if cached is None:
        now = timezone.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        cached = {
            "local_30d_usage": int(
                LeadParsingJob.objects.filter(started_at__gte=now - timedelta(days=30)).aggregate(total=Sum("request_count")).get("total")
                or 0
            ),
            "current_billing_month_usage": int(
                LeadParsingJob.objects.filter(started_at__gte=month_start).aggregate(total=Sum("request_count")).get("total")
                or 0
            ),
        }
        cache.set(cache_key, cached, LOCAL_USAGE_CACHE_TTL_SECONDS)
    return ParserUsageSnapshot(
        provider_status=provider_status,
        sku=CURRENT_PLACES_SKU,
        field_mask_version=CURRENT_FIELD_MASK_VERSION,
        free_monthly_calls=ENTERPRISE_FREE_MONTHLY_CALLS,
        local_30d_usage=int(cached.get("local_30d_usage") or 0),
        current_billing_month_usage=int(cached.get("current_billing_month_usage") or 0),
        google_project_usage=google_project_usage,
    )


def _utc_rfc3339(value) -> str:
    return value.astimezone(dt_timezone.utc).isoformat().replace("+00:00", "Z")


def _service_account_info_from_env_or_file() -> dict | None:
    raw_json = (
        getattr(settings, "GOOGLE_SERVICE_ACCOUNT_JSON", None)
        or os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
        or ""
    ).strip()
    if raw_json:
        return json.loads(raw_json)

    raw_json_b64 = (
        getattr(settings, "GOOGLE_SERVICE_ACCOUNT_JSON_B64", None)
        or os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON_B64")
        or ""
    ).strip()
    if raw_json_b64:
        decoded = base64.b64decode(raw_json_b64).decode("utf-8")
        return json.loads(decoded)

    path = (
        getattr(settings, "GOOGLE_APPLICATION_CREDENTIALS", None)
        or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        or ""
    ).strip()
    if not path:
        return None
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


class GoogleProjectUsageProvider:
    def project_id(self) -> str:
        project_id = (
            getattr(settings, "GOOGLE_CLOUD_PROJECT", None)
            or os.environ.get("GOOGLE_CLOUD_PROJECT")
            or os.environ.get("GCLOUD_PROJECT")
            or ""
        ).strip()
        if project_id:
            return project_id
        try:
            info = _service_account_info_from_env_or_file() or {}
        except Exception:
            info = {}
        return str(info.get("project_id") or "").strip()

    def _usage_cache_key(self, project_id: str) -> str:
        return f"management:parser:usage:v3:{project_id or 'local'}"

    def _token_cache_key(self, client_email: str) -> str:
        normalized = "".join(client_email.strip().split()).lower()
        return f"management:parser:google-token:v1:{normalized}"

    def _monitoring_access_token(self) -> tuple[str | None, str]:
        direct_token = (
            getattr(settings, "GOOGLE_MONITORING_ACCESS_TOKEN", None)
            or os.environ.get("GOOGLE_MONITORING_ACCESS_TOKEN")
            or os.environ.get("GOOGLE_CLOUD_ACCESS_TOKEN")
            or ""
        ).strip()
        if direct_token:
            return direct_token, "connected via Cloud Monitoring token"

        try:
            info = _service_account_info_from_env_or_file()
        except Exception as exc:
            return None, f"local only · invalid Google credentials ({exc})"
        if not info:
            return None, "local only · Google Cloud credentials missing"

        client_email = str(info.get("client_email") or "").strip()
        private_key = str(info.get("private_key") or "").strip()
        token_uri = str(info.get("token_uri") or GOOGLE_OAUTH_TOKEN_URL).strip() or GOOGLE_OAUTH_TOKEN_URL
        if not client_email or not private_key:
            return None, "local only · invalid Google service account payload"

        cache_key = self._token_cache_key(client_email)
        cached = cache.get(cache_key)
        if cached:
            return str(cached), "connected via Cloud Monitoring"

        now_ts = int(time.time())
        assertion = jwt.encode(
            {
                "iss": client_email,
                "scope": GOOGLE_MONITORING_SCOPE,
                "aud": token_uri,
                "iat": now_ts,
                "exp": now_ts + 3600,
            },
            private_key,
            algorithm="RS256",
        )
        response = requests.post(
            token_uri,
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": assertion,
            },
            timeout=15,
        )
        if response.status_code >= 400:
            detail = ""
            try:
                payload = response.json() or {}
                detail = payload.get("error_description") or payload.get("error") or ""
            except Exception:
                detail = response.text[:200]
            return None, f"local only · token exchange failed ({response.status_code}) {detail}".strip()

        payload = response.json() or {}
        access_token = str(payload.get("access_token") or "").strip()
        expires_in = max(60, _int_value(payload.get("expires_in"), default=3600) - GOOGLE_TOKEN_CACHE_SKEW_SECONDS)
        if not access_token:
            return None, "local only · Google token exchange returned no access token"
        cache.set(cache_key, access_token, expires_in)
        return access_token, "connected via Cloud Monitoring"

    def _fetch_google_project_usage(self, *, project_id: str, access_token: str) -> int:
        now = timezone.now()
        start = now - timedelta(days=30)
        interval_seconds = max(3600, int((now - start).total_seconds()))
        response = requests.get(
            GOOGLE_MONITORING_TIMESERIES_URL.format(project_id=project_id),
            headers={"Authorization": f"Bearer {access_token}"},
            params={
                "filter": GOOGLE_MONITORING_USAGE_FILTER,
                "interval.startTime": _utc_rfc3339(start),
                "interval.endTime": _utc_rfc3339(now),
                "aggregation.alignmentPeriod": f"{interval_seconds}s",
                "aggregation.perSeriesAligner": "ALIGN_SUM",
                "aggregation.crossSeriesReducer": "REDUCE_SUM",
                "view": "FULL",
            },
            timeout=20,
        )
        if response.status_code >= 400:
            detail = ""
            try:
                payload = response.json() or {}
                detail = (payload.get("error") or {}).get("message") or ""
            except Exception:
                detail = response.text[:200]
            raise RuntimeError(f"Cloud Monitoring API error ({response.status_code}): {detail or 'unknown error'}")

        payload = response.json() or {}
        total = 0
        for series in payload.get("timeSeries") or []:
            for point in series.get("points") or []:
                value = point.get("value") or {}
                if "int64Value" in value:
                    total += _int_value(value.get("int64Value"))
                elif "doubleValue" in value:
                    total += int(float(value.get("doubleValue") or 0))
        return total

    def fetch_google_project_usage(self) -> tuple[str, int | None]:
        project_id = self.project_id()
        if not project_id:
            return "local only · GOOGLE_CLOUD_PROJECT missing", None

        cache_key = self._usage_cache_key(project_id)
        cached = cache.get(cache_key)
        if cached is not None:
            return str(cached.get("status") or "local only"), cached.get("usage")

        access_token, status = self._monitoring_access_token()
        if not access_token:
            cache.set(cache_key, {"status": status, "usage": None}, GOOGLE_USAGE_ERROR_CACHE_TTL_SECONDS)
            return status, None

        try:
            usage = self._fetch_google_project_usage(project_id=project_id, access_token=access_token)
        except Exception as exc:
            status = f"local only · {str(exc).strip()}"
            cache.set(cache_key, {"status": status, "usage": None}, GOOGLE_USAGE_ERROR_CACHE_TTL_SECONDS)
            return status, None

        status = "connected via Cloud Monitoring"
        cache.set(cache_key, {"status": status, "usage": usage}, GOOGLE_USAGE_CACHE_TTL_SECONDS)
        return status, usage


def parser_usage_snapshot() -> ParserUsageSnapshot:
    provider_status, google_project_usage = GoogleProjectUsageProvider().fetch_google_project_usage()
    return _base_snapshot(provider_status=provider_status, google_project_usage=google_project_usage)
