"""Optional external analytics connectors for the admin dashboard."""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable

import requests
from django.core.cache import cache

logger = logging.getLogger(__name__)

GA4_SCOPES = ["https://www.googleapis.com/auth/analytics.readonly"]
GA4_CACHE_TTL = 60 * 5
CLARITY_CACHE_TTL = 60 * 5


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


def _cache_get_or_set(prefix: str, payload: dict[str, Any], ttl: int, builder):
    key = _cache_key(prefix, payload)
    cached = cache.get(key)
    if cached is not None:
        return cached
    result = builder()
    cache.set(key, result, ttl)
    return result


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


def _build_ga4_client():
    deps = _load_ga4_dependencies()
    client_class = deps["client_class"]
    service_account = deps["service_account"]
    google_default_credentials = deps["google_default_credentials"]

    credentials_file = _env_first(
        "GA4_SERVICE_ACCOUNT_FILE",
        "GOOGLE_APPLICATION_CREDENTIALS",
    )
    credentials_json = _env_first(
        "GA4_SERVICE_ACCOUNT_JSON",
        "GOOGLE_SERVICE_ACCOUNT_JSON",
    )

    if credentials_json and service_account is not None:
        info = json.loads(credentials_json)
        credentials = service_account.Credentials.from_service_account_info(info, scopes=GA4_SCOPES)
        return client_class(credentials=credentials), "service_account_json"

    if credentials_file and service_account is not None:
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
            message="Google Analytics Data API залежності не встановлені.",
            details={"property_id": property_id, "configured": True, "dependency_error": str(exc)},
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
        return ConnectorStatus(
            key="ga4",
            label="GA4 Data API",
            status="healthy",
            message="З’єднання з GA4 успішне.",
            details=details,
        ).as_dict()
    except Exception as exc:
        details["connection_error"] = str(exc)
        return ConnectorStatus(
            key="ga4",
            label="GA4 Data API",
            status="error",
            message="Не вдалося отримати тестовий звіт з GA4.",
            details=details,
        ).as_dict()


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
    token = _clarity_token()
    if not token:
        return ConnectorStatus(
            key="clarity",
            label="Microsoft Clarity",
            status="warning",
            message="API token для Clarity не налаштований.",
            details={"configured": False},
        ).as_dict()

    details = {"configured": True}
    if not test_connection:
        return ConnectorStatus(
            key="clarity",
            label="Microsoft Clarity",
            status="healthy",
            message="Clarity live-insights конектор готовий.",
            details=details,
        ).as_dict()

    try:
        _clarity_request(num_of_days=1, use_cache=False)
        return ConnectorStatus(
            key="clarity",
            label="Microsoft Clarity",
            status="healthy",
            message="З’єднання з Clarity успішне.",
            details=details,
        ).as_dict()
    except Exception as exc:
        if isinstance(exc, requests.HTTPError) and exc.response is not None:
            details["http_status"] = exc.response.status_code
        details["connection_error"] = str(exc)
        return ConnectorStatus(
            key="clarity",
            label="Microsoft Clarity",
            status="error",
            message="Не вдалося отримати live insights з Clarity.",
            details=details,
        ).as_dict()


def _clarity_request(
    *,
    num_of_days: int = 1,
    dimension1: str = "",
    dimension2: str = "",
    dimension3: str = "",
    use_cache: bool = True,
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
        params = {"numOfDays": max(1, min(int(num_of_days), 3))}
        if dimension1:
            params["dimension1"] = dimension1
        if dimension2:
            params["dimension2"] = dimension2
        if dimension3:
            params["dimension3"] = dimension3

        response = requests.get(
            "https://www.clarity.ms/export-data/api/v1/project-live-insights",
            params=params,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, list):
            raise RuntimeError("Unexpected Clarity response shape")
        return data

    if not use_cache:
        return _builder()
    return _cache_get_or_set("clarity_live_insights", payload, CLARITY_CACHE_TTL, _builder)


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
