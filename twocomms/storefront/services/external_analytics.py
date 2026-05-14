"""Optional external analytics connectors for the admin dashboard.

This module is intentionally defensive: GA4 and Clarity are *secondary*
data sources, the dashboard MUST stay usable even when both providers are
down for days at a time. The caching layer therefore implements
stale-while-revalidate with very long fallback windows and per-provider
retry / quota policies so a Microsoft outage does not torch our daily
rate-limit budget.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Iterable

import requests
from django.core.cache import cache

logger = logging.getLogger(__name__)

GA4_SCOPES = ["https://www.googleapis.com/auth/analytics.readonly"]
# GA4 default per-property quotas are generous, but each dashboard render
# fires multiple reports (channel groups / sources / devices / countries /
# landing pages). 30 min cache reduces that to ~50 calls per dimension per
# day even with active staff usage.
GA4_CACHE_TTL = 60 * 30
# Microsoft Clarity caps the Data Export API at 10 requests/project/day.
# We issue 2 different dimension calls per dashboard load, so we need at
# least a 4-hour TTL to stay safely under the limit even with two admins
# refreshing throughout the day. Status pings are cached separately.
CLARITY_CACHE_TTL = 60 * 60 * 4
# Hard daily ceiling enforced in-process (matches the API's published cap).
CLARITY_DAILY_BUDGET = 10
# Soft reserve so manual probes / status pings always have headroom.
CLARITY_BUDGET_RESERVE = 2

# Resilience tunables. Once a remote API has failed we keep its last good
# response in cache for ``STALE_TTL`` seconds and refuse to retry the live
# call for ``FAILURE_TTL`` seconds. This prevents the dashboard from melting
# down with a long retry loop if GA4/Clarity are degraded.
STALE_TTL = 60 * 60 * 24 * 30  # serve last good payload for 30 days
FAILURE_TTL = 60 * 60          # backoff window during outages (1h)
STATUS_CACHE_TTL = 60 * 60 * 6  # cache successful status pings for 6h
STATUS_FAILURE_CACHE_TTL = 60 * 30
HTTP_RETRY_STATUSES_DEFAULT = {500, 502, 503, 504}
HTTP_RETRY_MAX = 2  # i.e. 3 attempts total
HTTP_RETRY_BACKOFF = 0.4  # seconds, exponential

# Clarity-specific: never retry server errors. A 500 from Clarity is almost
# always a Microsoft-side issue that won't resolve in the next 0.8 seconds,
# and each retry burns one of our 10 daily quota slots.
CLARITY_RETRY_STATUSES: set[int] = set()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class ConnectorStatus:
    key: str
    label: str
    status: str
    message: str
    details: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "status": self.status,
            "message": self.message,
            "details": self.details,
        }


def _cache_key(prefix: str, payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, default=str)
    digest = hashlib.sha1(serialized.encode("utf-8")).hexdigest()
    return f"external_analytics:{prefix}:{digest}"


def _stale_key(key: str) -> str:
    return f"{key}:stale"


def _failure_key(key: str) -> str:
    return f"{key}:fail"


def _meta_key(key: str) -> str:
    """Key for storing metadata (timestamp / source) alongside cached data."""
    return f"{key}:meta"


def _read_cache_meta(prefix: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Return metadata for the latest successful fetch, if any."""
    key = _cache_key(prefix, payload)
    meta = cache.get(_meta_key(key)) or {}
    failure = cache.get(_failure_key(key))
    if failure:
        meta = dict(meta)
        meta["last_error"] = failure
    return meta


def _cache_get_or_set(
    prefix: str,
    payload: dict[str, Any],
    ttl: int,
    builder,
    *,
    failure_ttl: int = FAILURE_TTL,
    stale_ttl: int = STALE_TTL,
):
    """
    Cache wrapper that survives transient API failures.

    Behaviour:
    - return live cache if fresh;
    - if a recent failure was recorded (``failure_ttl`` window), serve stale
      data and avoid retrying the API;
    - otherwise call the builder, persisting both fresh and stale copies on
      success and recording the failure on exception.

    Raises only when there is no cached fallback so callers can decide.
    """
    key = _cache_key(prefix, payload)
    cached = cache.get(key)
    if cached is not None:
        return cached

    stale_key = _stale_key(key)
    failure_key = _failure_key(key)
    meta_key = _meta_key(key)

    failure_marker = cache.get(failure_key)
    if failure_marker:
        stale = cache.get(stale_key)
        if stale is not None:
            return stale
        raise RuntimeError(failure_marker)

    try:
        result = builder()
    except Exception as exc:
        cache.set(failure_key, str(exc) or exc.__class__.__name__, failure_ttl)
        existing_meta = cache.get(meta_key) or {}
        cache.set(
            meta_key,
            {
                **existing_meta,
                "last_error_at": _now_iso(),
                "last_error": str(exc) or exc.__class__.__name__,
            },
            stale_ttl,
        )
        stale = cache.get(stale_key)
        if stale is not None:
            logger.warning("%s call failed, serving stale data: %s", prefix, exc)
            return stale
        raise

    cache.set(key, result, ttl)
    cache.set(stale_key, result, stale_ttl)
    cache.set(
        meta_key,
        {
            "last_success_at": _now_iso(),
            "ttl": ttl,
        },
        stale_ttl,
    )
    cache.delete(failure_key)
    return result


def _http_get_with_retry(
    url: str,
    *,
    params: dict,
    headers: dict,
    timeout: int,
    retry_statuses: set[int] | None = None,
) -> requests.Response:
    """GET with exponential backoff for transient HTTP errors.

    ``retry_statuses`` can be an empty set to disable status-based retries
    entirely (e.g. for Clarity, where 5xx burns daily quota).
    """
    retry_statuses = retry_statuses if retry_statuses is not None else HTTP_RETRY_STATUSES_DEFAULT
    last_exc: Exception | None = None
    for attempt in range(HTTP_RETRY_MAX + 1):
        try:
            response = requests.get(url, params=params, headers=headers, timeout=timeout)
        except (requests.ConnectionError, requests.Timeout) as exc:
            last_exc = exc
            if attempt >= HTTP_RETRY_MAX:
                raise
            time.sleep(HTTP_RETRY_BACKOFF * (2 ** attempt))
            continue

        if response.status_code in retry_statuses and attempt < HTTP_RETRY_MAX:
            time.sleep(HTTP_RETRY_BACKOFF * (2 ** attempt))
            continue
        return response

    if last_exc is not None:
        raise last_exc
    raise RuntimeError("HTTP retry loop exhausted without response")


# ---------------------------------------------------------------------------
# Clarity daily quota tracker
# ---------------------------------------------------------------------------

def _clarity_quota_key() -> str:
    """Per-UTC-day Redis counter that mirrors Clarity's published cap."""
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"external_analytics:clarity:quota:{today}"


def get_clarity_quota_state() -> dict[str, int]:
    """Return ``{used, remaining, limit}`` for the current UTC day."""
    used = int(cache.get(_clarity_quota_key()) or 0)
    return {
        "used": used,
        "remaining": max(0, CLARITY_DAILY_BUDGET - used),
        "limit": CLARITY_DAILY_BUDGET,
        "reserve": CLARITY_BUDGET_RESERVE,
    }


def _clarity_budget_allows_call(*, allow_reserve: bool = False) -> bool:
    """
    Check if we still have budget to call Clarity.

    Normal callers must leave the reserve untouched (so manual status pings
    can always succeed); pass ``allow_reserve=True`` for those probes.
    """
    state = get_clarity_quota_state()
    floor = 0 if allow_reserve else CLARITY_BUDGET_RESERVE
    return state["used"] < (CLARITY_DAILY_BUDGET - floor)


def _record_clarity_call() -> int:
    """Atomically increment the daily counter. Returns the new total."""
    key = _clarity_quota_key()
    # ``Django.core.cache`` may not implement ``incr`` for all backends. The
    # Redis backend used in production does. Fall back to set-after-get for
    # local/test environments.
    try:
        # Initialize if missing.
        cache.add(key, 0, 60 * 60 * 26)  # 26h so we comfortably cross UTC midnight
        return cache.incr(key, 1)
    except (ValueError, NotImplementedError):
        current = int(cache.get(key) or 0) + 1
        cache.set(key, current, 60 * 60 * 26)
        return current


def _env_first(*names: str) -> str:
    for name in names:
        value = (os.environ.get(name) or "").strip()
        if value:
            return value
    return ""


def _load_ga4_dependencies():
    from google.analytics.data_v1beta import BetaAnalyticsDataClient
    from google.analytics.data_v1beta.types import (
        DateRange,
        Dimension,
        Filter,
        FilterExpression,
        FilterExpressionList,
        Metric,
        RunReportRequest,
    )

    try:
        from google.oauth2 import service_account  # type: ignore
    except Exception:
        service_account = None

    try:
        from google.auth import default as google_default_credentials  # type: ignore
    except Exception:
        google_default_credentials = None

    return {
        "client_class": BetaAnalyticsDataClient,
        "date_range": DateRange,
        "dimension": Dimension,
        "filter": Filter,
        "filter_expression": FilterExpression,
        "filter_expression_list": FilterExpressionList,
        "metric": Metric,
        "request": RunReportRequest,
        "service_account": service_account,
        "google_default_credentials": google_default_credentials,
    }


def _ga4_property_id_raw() -> str:
    return _env_first(
        "GA4_PROPERTY_ID",
        "GA4_PROPERTY_NUMERIC_ID",
        "GOOGLE_ANALYTICS_PROPERTY_ID",
        "GOOGLE_ANALYTICS_4_PROPERTY_ID",
    )


def _ga4_property_id() -> str:
    raw_value = _ga4_property_id_raw()
    if not raw_value:
        return ""
    normalized = raw_value.strip()
    if normalized.startswith("properties/"):
        normalized = normalized.split("/", 1)[1].strip()
    return normalized if normalized.isdigit() else ""


def _resolve_ga4_credentials_file() -> str:
    """
    Return an existing service-account JSON path or empty string.

    Order of resolution:
    1. ``GA4_SERVICE_ACCOUNT_FILE`` env var (verbatim if file exists).
    2. ``GOOGLE_APPLICATION_CREDENTIALS`` env var.
    3. Auto-discovery: any ``*service*account*.json`` or
       ``gen-lang-client-*.json`` file under ``BASE_DIR/Anl`` or
       ``BASE_DIR.parent/Anl``. Useful when the env var path is stale and
       the file moved between deploys.
    """
    explicit = _env_first("GA4_SERVICE_ACCOUNT_FILE", "GOOGLE_APPLICATION_CREDENTIALS")
    if explicit and os.path.isfile(explicit):
        return explicit

    try:
        from django.conf import settings as _django_settings

        base_dir = getattr(_django_settings, "BASE_DIR", None)
    except Exception:
        base_dir = None

    candidates: list[str] = []
    if base_dir is not None:
        for parent in (str(base_dir), os.path.dirname(str(base_dir))):
            candidates.append(os.path.join(parent, "Anl"))
            candidates.append(os.path.join(parent, "credentials"))

    for directory in candidates:
        if not os.path.isdir(directory):
            continue
        try:
            entries = os.listdir(directory)
        except OSError:
            continue
        for name in entries:
            if not name.endswith(".json"):
                continue
            lower = name.lower()
            if (
                "gen-lang-client" in lower
                or "service-account" in lower
                or "service_account" in lower
                or "google-credentials" in lower
            ):
                full = os.path.join(directory, name)
                if os.path.isfile(full):
                    return full
    return explicit if explicit else ""


def _build_ga4_client():
    deps = _load_ga4_dependencies()
    client_class = deps["client_class"]
    service_account = deps["service_account"]
    google_default_credentials = deps["google_default_credentials"]

    credentials_file = _resolve_ga4_credentials_file()
    credentials_json = _env_first(
        "GA4_SERVICE_ACCOUNT_JSON",
        "GOOGLE_SERVICE_ACCOUNT_JSON",
    )

    if credentials_json and service_account is not None:
        info = json.loads(credentials_json)
        credentials = service_account.Credentials.from_service_account_info(info, scopes=GA4_SCOPES)
        return client_class(credentials=credentials), "service_account_json"

    if credentials_file and service_account is not None:
        if not os.path.isfile(credentials_file):
            raise FileNotFoundError(
                f"GA4 service account file not found at {credentials_file}"
            )
        credentials = service_account.Credentials.from_service_account_file(
            credentials_file,
            scopes=GA4_SCOPES,
        )
        return client_class(credentials=credentials), "service_account_file"

    if google_default_credentials is not None:
        credentials, _ = google_default_credentials(scopes=GA4_SCOPES)
        return client_class(credentials=credentials), "application_default"

    return client_class(), "application_default"


def get_ga4_status(test_connection: bool = False) -> dict[str, Any]:
    """Return health status for GA4. Caches successful test_connection results."""
    if test_connection:
        cache_key = "external_analytics:ga4:status:test"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
    raw_property_id = _ga4_property_id_raw()
    property_id = _ga4_property_id()
    if not raw_property_id:
        return ConnectorStatus(
            key="ga4",
            label="GA4 Data API",
            status="warning",
            message="Не заданий numeric property ID для backend-запитів.",
            details={"property_id": "", "configured": False},
        ).as_dict()
    if not property_id:
        return ConnectorStatus(
            key="ga4",
            label="GA4 Data API",
            status="warning",
            message="GA4 property ID має бути numeric (наприклад, 504296337).",
            details={"property_id": raw_property_id, "configured": False},
        ).as_dict()

    try:
        client, auth_mode = _build_ga4_client()
    except ImportError as exc:
        return ConnectorStatus(
            key="ga4",
            label="GA4 Data API",
            status="warning",
            message="Google Analytics Data API залежності не встановлені (pip install google-analytics-data google-auth).",
            details={"property_id": property_id, "configured": True, "dependency_error": str(exc)},
        ).as_dict()
    except FileNotFoundError as exc:
        return ConnectorStatus(
            key="ga4",
            label="GA4 Data API",
            status="warning",
            message="Service-account JSON для GA4 не знайдено. Завантажте файл у /Anl або задайте GA4_SERVICE_ACCOUNT_JSON.",
            details={"property_id": property_id, "configured": True, "error": str(exc)},
        ).as_dict()
    except Exception as exc:
        return ConnectorStatus(
            key="ga4",
            label="GA4 Data API",
            status="error",
            message="Не вдалося ініціалізувати GA4 клієнт.",
            details={"property_id": property_id, "configured": True, "error": str(exc)},
        ).as_dict()

    details: dict[str, Any] = {
        "property_id": property_id,
        "configured": True,
        "auth_mode": auth_mode,
    }

    if not test_connection:
        return ConnectorStatus(
            key="ga4",
            label="GA4 Data API",
            status="healthy",
            message="Конектор готовий до запитів.",
            details=details,
        ).as_dict()

    try:
        deps = _load_ga4_dependencies()
        request = deps["request"](
            property=f"properties/{property_id}",
            dimensions=[deps["dimension"](name="date")],
            metrics=[deps["metric"](name="sessions")],
            date_ranges=[deps["date_range"](start_date="7daysAgo", end_date="yesterday")],
            limit=1,
            return_property_quota=True,
        )
        response = client.run_report(request)
        quota = getattr(response, "property_quota", None)
        details["quota"] = str(quota) if quota else ""
        result = ConnectorStatus(
            key="ga4",
            label="GA4 Data API",
            status="healthy",
            message="З’єднання з GA4 успішне.",
            details=details,
        ).as_dict()
        cache.set("external_analytics:ga4:status:test", result, STATUS_CACHE_TTL)
        return result
    except Exception as exc:
        details["connection_error"] = str(exc)
        result = ConnectorStatus(
            key="ga4",
            label="GA4 Data API",
            status="error",
            message="Не вдалося отримати тестовий звіт з GA4.",
            details=details,
        ).as_dict()
        cache.set("external_analytics:ga4:status:test", result, STATUS_FAILURE_CACHE_TTL)
        return result


def _build_ga4_dimension_filter(
    *,
    device_type: str = "",
    utm_source: str = "",
    utm_medium: str = "",
    campaign: str = "",
):
    deps = _load_ga4_dependencies()
    filter_items = []
    if device_type:
        filter_items.append(
            deps["filter_expression"](
                filter=deps["filter"](
                    field_name="deviceCategory",
                    string_filter=deps["filter"].StringFilter(value=device_type),
                )
            )
        )
    if utm_source:
        filter_items.append(
            deps["filter_expression"](
                filter=deps["filter"](
                    field_name="sessionSource",
                    string_filter=deps["filter"].StringFilter(value=utm_source),
                )
            )
        )
    if utm_medium:
        filter_items.append(
            deps["filter_expression"](
                filter=deps["filter"](
                    field_name="sessionMedium",
                    string_filter=deps["filter"].StringFilter(value=utm_medium),
                )
            )
        )
    if campaign:
        filter_items.append(
            deps["filter_expression"](
                filter=deps["filter"](
                    field_name="sessionCampaignName",
                    string_filter=deps["filter"].StringFilter(value=campaign),
                )
            )
        )
    if not filter_items:
        return None
    if len(filter_items) == 1:
        return filter_items[0]
    return deps["filter_expression"](
        and_group=deps["filter_expression_list"](expressions=filter_items)
    )


def _serialize_ga4_rows(rows: Iterable[Any], dimensions: list[str], metrics: list[str]) -> list[dict[str, Any]]:
    data: list[dict[str, Any]] = []
    for row in rows:
        item: dict[str, Any] = {}
        for index, dimension_name in enumerate(dimensions):
            try:
                item[dimension_name] = row.dimension_values[index].value
            except Exception:
                item[dimension_name] = ""
        for index, metric_name in enumerate(metrics):
            raw_value = ""
            try:
                raw_value = row.metric_values[index].value
            except Exception:
                raw_value = ""
            try:
                number = float(raw_value)
                item[metric_name] = int(number) if number.is_integer() else number
            except Exception:
                item[metric_name] = raw_value
        data.append(item)
    return data


def run_ga4_report(
    *,
    dimensions: list[str],
    metrics: list[str],
    start_date: date,
    end_date: date,
    device_type: str = "",
    utm_source: str = "",
    utm_medium: str = "",
    campaign: str = "",
    limit: int = 1000,
) -> dict[str, Any]:
    property_id = _ga4_property_id()
    if not property_id:
        raise RuntimeError("GA4 property ID is missing or invalid")

    payload = {
        "property_id": property_id,
        "dimensions": dimensions,
        "metrics": metrics,
        "start_date": str(start_date),
        "end_date": str(end_date),
        "device_type": device_type,
        "utm_source": utm_source,
        "utm_medium": utm_medium,
        "campaign": campaign,
        "limit": limit,
    }

    def _builder():
        deps = _load_ga4_dependencies()
        client, _ = _build_ga4_client()
        request = deps["request"](
            property=f"properties/{property_id}",
            dimensions=[deps["dimension"](name=name) for name in dimensions],
            metrics=[deps["metric"](name=name) for name in metrics],
            date_ranges=[
                deps["date_range"](
                    start_date=start_date.isoformat(),
                    end_date=end_date.isoformat(),
                )
            ],
            dimension_filter=_build_ga4_dimension_filter(
                device_type=device_type,
                utm_source=utm_source,
                utm_medium=utm_medium,
                campaign=campaign,
            ),
            limit=limit,
            return_property_quota=True,
        )
        response = client.run_report(request)
        return {
            "rows": _serialize_ga4_rows(response.rows, dimensions, metrics),
            "row_count": getattr(response, "row_count", 0),
            "quota": str(getattr(response, "property_quota", "")),
        }

    return _cache_get_or_set("ga4_report", payload, GA4_CACHE_TTL, _builder)


def fetch_ga4_acquisition_snapshot(
    *,
    start_date: date,
    end_date: date,
    device_type: str = "",
    utm_source: str = "",
    utm_medium: str = "",
    campaign: str = "",
) -> dict[str, Any]:
    try:
        return {
            "channel_groups": run_ga4_report(
                dimensions=["sessionDefaultChannelGroup"],
                metrics=["sessions", "activeUsers", "engagementRate"],
                start_date=start_date,
                end_date=end_date,
                device_type=device_type,
                utm_source=utm_source,
                utm_medium=utm_medium,
                campaign=campaign,
                limit=20,
            ),
            "sources": run_ga4_report(
                dimensions=["sessionSource", "sessionMedium"],
                metrics=["sessions", "activeUsers", "engagementRate"],
                start_date=start_date,
                end_date=end_date,
                device_type=device_type,
                utm_source=utm_source,
                utm_medium=utm_medium,
                campaign=campaign,
                limit=25,
            ),
            "devices": run_ga4_report(
                dimensions=["deviceCategory", "browser"],
                metrics=["sessions", "activeUsers", "engagementRate"],
                start_date=start_date,
                end_date=end_date,
                device_type=device_type,
                utm_source=utm_source,
                utm_medium=utm_medium,
                campaign=campaign,
                limit=15,
            ),
            "countries": run_ga4_report(
                dimensions=["country"],
                metrics=["sessions", "activeUsers", "engagementRate"],
                start_date=start_date,
                end_date=end_date,
                device_type=device_type,
                utm_source=utm_source,
                utm_medium=utm_medium,
                campaign=campaign,
                limit=15,
            ),
            "landing_pages": run_ga4_report(
                dimensions=["landingPagePlusQueryString"],
                metrics=["sessions", "activeUsers", "engagementRate"],
                start_date=start_date,
                end_date=end_date,
                device_type=device_type,
                utm_source=utm_source,
                utm_medium=utm_medium,
                campaign=campaign,
                limit=15,
            ),
        }
    except Exception as exc:
        logger.warning("GA4 acquisition snapshot failed: %s", exc, exc_info=True)
        return {"error": str(exc)}


def _clarity_token() -> str:
    return _env_first(
        "CLARITY_API_TOKEN",
        "MICROSOFT_CLARITY_API_TOKEN",
    )


def get_clarity_status(test_connection: bool = False) -> dict[str, Any]:
    """Return health status for Clarity. Caches successful test pings."""
    if test_connection:
        cache_key = "external_analytics:clarity:status:test"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
    token = _clarity_token()
    if not token:
        return ConnectorStatus(
            key="clarity",
            label="Microsoft Clarity",
            status="warning",
            message="API token для Clarity не налаштований.",
            details={"configured": False},
        ).as_dict()

    # Pull metadata about the latest successful overview fetch so admins can
    # see "data from 2h ago" even when the live ping is failing.
    overview_meta = _read_cache_meta(
        "clarity_live_insights",
        {"num_of_days": 1, "dimension1": "", "dimension2": "", "dimension3": ""},
    )
    quota = get_clarity_quota_state()
    details: dict[str, Any] = {
        "configured": True,
        "last_success_at": overview_meta.get("last_success_at", ""),
        "last_error_at": overview_meta.get("last_error_at", ""),
        "daily_quota_used": quota["used"],
        "daily_quota_remaining": quota["remaining"],
        "daily_quota_limit": quota["limit"],
    }

    if not test_connection:
        # Cheap path: trust whatever the cache+DB knows, no live call.
        if overview_meta.get("last_success_at"):
            return ConnectorStatus(
                key="clarity",
                label="Microsoft Clarity",
                status="healthy",
                message=f"Останнє оновлення: {overview_meta['last_success_at']}.",
                details=details,
            ).as_dict()
        return ConnectorStatus(
            key="clarity",
            label="Microsoft Clarity",
            status="healthy",
            message="Clarity live-insights конектор готовий.",
            details=details,
        ).as_dict()

    # If quota is exhausted, do not attempt a live ping; surface the cached
    # state to the admin instead.
    if not _clarity_budget_allows_call(allow_reserve=True):
        result = ConnectorStatus(
            key="clarity",
            label="Microsoft Clarity",
            status="warning",
            message=(
                f"Clarity API: добова квота вичерпана ({quota['used']}/{quota['limit']}). "
                "Лічильник скидається о 00:00 UTC."
            ),
            details=details,
        ).as_dict()
        cache.set("external_analytics:clarity:status:test", result, STATUS_FAILURE_CACHE_TTL)
        return result

    try:
        _clarity_request(num_of_days=1, use_cache=False, allow_reserve=True)
        quota = get_clarity_quota_state()
        details["daily_quota_used"] = quota["used"]
        details["daily_quota_remaining"] = quota["remaining"]
        details["last_success_at"] = _now_iso()
        result = ConnectorStatus(
            key="clarity",
            label="Microsoft Clarity",
            status="healthy",
            message=(
                f"З'єднання з Clarity успішне. Квота: {quota['used']}/{quota['limit']} за добу."
            ),
            details=details,
        ).as_dict()
        cache.set("external_analytics:clarity:status:test", result, STATUS_CACHE_TTL)
        return result
    except ClarityQuotaExhausted as exc:
        details["connection_error"] = str(exc)
        result = ConnectorStatus(
            key="clarity",
            label="Microsoft Clarity",
            status="warning",
            message=f"Clarity API: добова квота вичерпана ({quota['used']}/{quota['limit']}).",
            details=details,
        ).as_dict()
        cache.set("external_analytics:clarity:status:test", result, STATUS_FAILURE_CACHE_TTL)
        return result
    except Exception as exc:
        http_status = None
        if isinstance(exc, requests.HTTPError) and exc.response is not None:
            http_status = exc.response.status_code
            details["http_status"] = http_status
        details["connection_error"] = str(exc)
        # Refresh quota snapshot in case the failed call still consumed a slot
        quota = get_clarity_quota_state()
        details["daily_quota_used"] = quota["used"]
        details["daily_quota_remaining"] = quota["remaining"]

        # Customise the message based on the failure mode so admins see what
        # action is actually required.
        if http_status == 429:
            message = "Clarity API: добова квота 10 запитів вичерпана (HTTP 429)."
            status = "warning"
        elif http_status in (401, 403):
            message = (
                "Clarity API token відхилено (HTTP "
                f"{http_status}). Перегенеруйте токен у Clarity → Settings → Data Export."
            )
            status = "error"
        elif http_status is not None and 500 <= http_status < 600:
            message = (
                f"Microsoft Clarity тимчасово недоступний (HTTP {http_status}). "
                "Дані оновляться автоматично, коли сервіс відновиться."
            )
            status = "warning"
        else:
            message = (
                "Не вдалося отримати live insights з Clarity "
                f"({exc.__class__.__name__}). Перевірте токен та мережу."
            )
            status = "error"

        # Annotate with "last good" timestamp so the warning still feels
        # useful while Clarity is degraded.
        if overview_meta.get("last_success_at"):
            message = f"{message} Останнє успішне оновлення: {overview_meta['last_success_at']}."

        result = ConnectorStatus(
            key="clarity",
            label="Microsoft Clarity",
            status=status,
            message=message,
            details=details,
        ).as_dict()
        cache.set("external_analytics:clarity:status:test", result, STATUS_FAILURE_CACHE_TTL)
        return result


class ClarityQuotaExhausted(RuntimeError):
    """Raised when the daily 10-call Clarity budget is depleted."""


def _clarity_request(
    *,
    num_of_days: int = 1,
    dimension1: str = "",
    dimension2: str = "",
    dimension3: str = "",
    use_cache: bool = True,
    allow_reserve: bool = False,
) -> list[dict[str, Any]]:
    token = _clarity_token()
    if not token:
        raise RuntimeError("Clarity API token is not configured")

    payload = {
        "num_of_days": num_of_days,
        "dimension1": dimension1,
        "dimension2": dimension2,
        "dimension3": dimension3,
    }

    def _builder():
        # Pre-flight: never make a call that would push us past the daily cap.
        if not _clarity_budget_allows_call(allow_reserve=allow_reserve):
            state = get_clarity_quota_state()
            raise ClarityQuotaExhausted(
                f"Clarity daily budget exhausted ({state['used']}/{state['limit']})"
            )

        params = {"numOfDays": max(1, min(int(num_of_days), 3))}
        if dimension1:
            params["dimension1"] = dimension1
        if dimension2:
            params["dimension2"] = dimension2
        if dimension3:
            params["dimension3"] = dimension3

        # Increment counter BEFORE the call so even network errors count
        # against quota (each attempt hits Clarity infra once).
        _record_clarity_call()

        response = _http_get_with_retry(
            "https://www.clarity.ms/export-data/api/v1/project-live-insights",
            params=params,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            timeout=20,
            retry_statuses=CLARITY_RETRY_STATUSES,  # never retry 5xx (saves quota)
        )
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, list):
            raise RuntimeError("Unexpected Clarity response shape")
        return data

    if not use_cache:
        return _builder()
    return _cache_get_or_set(
        "clarity_live_insights",
        payload,
        CLARITY_CACHE_TTL,
        _builder,
    )


def fetch_clarity_overview(*, num_of_days: int = 1) -> dict[str, Any]:
    metrics = _clarity_request(num_of_days=num_of_days)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for block in metrics:
        metric_name = str(block.get("metricName") or "")
        info = block.get("information")
        if metric_name and isinstance(info, list):
            grouped[metric_name] = info
    return grouped


def fetch_clarity_problem_urls(*, num_of_days: int = 1) -> list[dict[str, Any]]:
    data = _clarity_request(num_of_days=num_of_days, dimension1="URL")
    merged: dict[str, dict[str, Any]] = {}
    metric_key_map = {
        "Rage Click Count": "rage_clicks",
        "Dead Click Count": "dead_clicks",
        "Quickback Click": "quickbacks",
        "Script Error Count": "script_errors",
        "Error Click Count": "error_clicks",
        "Engagement Time": "engagement_time",
        "Traffic": "sessions",
        "Popular Pages": "popular_pages",
    }

    for block in data:
        metric_name = str(block.get("metricName") or "")
        metric_key = metric_key_map.get(metric_name)
        if not metric_key:
            continue
        for row in block.get("information") or []:
            url = str(row.get("URL") or row.get("Url") or row.get("url") or "").strip()
            if not url:
                continue
            item = merged.setdefault(
                url,
                {
                    "url": url,
                    "sessions": 0,
                    "rage_clicks": 0,
                    "dead_clicks": 0,
                    "quickbacks": 0,
                    "script_errors": 0,
                    "error_clicks": 0,
                    "engagement_time": 0,
                },
            )
            raw_value = (
                row.get(metric_key)
                or row.get("value")
                or row.get("count")
                or row.get("totalSessionCount")
            )
            try:
                item[metric_key] = float(raw_value or 0)
            except Exception:
                item[metric_key] = 0
            if metric_key == "sessions":
                try:
                    item["sessions"] = int(row.get("totalSessionCount") or raw_value or 0)
                except Exception:
                    item["sessions"] = 0

    ranked = sorted(
        merged.values(),
        key=lambda row: (
            row.get("rage_clicks", 0)
            + row.get("dead_clicks", 0)
            + row.get("quickbacks", 0)
            + row.get("script_errors", 0)
        ),
        reverse=True,
    )
    return ranked[:20]
