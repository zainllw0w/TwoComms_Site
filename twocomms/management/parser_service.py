from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import hashlib
import os
from typing import Any
from urllib.parse import urlparse

import requests
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from .lead_services import split_terms
from .models import (
    Client,
    LeadParsingJob,
    LeadParsingQueryState,
    LeadParsingResult,
    LeadParsingRuntimeLock,
    ManagementLead,
    normalize_phone,
)
from .parser_usage import CURRENT_FIELD_MASK_VERSION

PLACES_TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
PLACES_FIELD_MASK = ",".join(
    [
        "places.id",
        "places.displayName",
        "places.formattedAddress",
        "places.internationalPhoneNumber",
        "places.nationalPhoneNumber",
        "places.websiteUri",
        "places.googleMapsUri",
        "places.types",
        "nextPageToken",
    ]
)
PLACES_PAGE_SIZE = 20
PLACE_SEARCH_RADIUS_METERS = 22000.0
GEOCODE_CACHE_TTL_SECONDS = 60 * 60 * 24
GEOCODE_NEGATIVE_CACHE_TTL_SECONDS = 60 * 10
GEOCODE_NEGATIVE_SENTINEL = {"__geocode_negative__": True}

DEFAULT_REQUESTS_PER_MINUTE = 10
MAX_REQUESTS_PER_MINUTE = 20
DEFAULT_HISTORY_LOOKBACK_DAYS = 30
MAX_HISTORY_LOOKBACK_DAYS = 3650
MAX_TARGET_LEADS_LIMIT = 5000
PAGE_TOKEN_RETRY_LIMIT = 2
TRANSIENT_RETRY_LIMIT = 2
PAGE_TOKEN_DELAY_SECONDS = 2
STEP_LOCK_STALE_AFTER = timedelta(seconds=60)
SESSION_STALE_AFTER = timedelta(minutes=5)
QUERY_EMPTY_PAGE_LOOP_LIMIT = 2
QUERY_PAGE_FINGERPRINT_LIMIT = 6
QUERY_PAGE_HARD_CAP = 5
MAX_RESULT_REASON_LENGTH = 255
MAX_QUERY_EXHAUSTED_MESSAGE_LENGTH = 255
RUNTIME_LOCK_KEY = 1
ACTIVE_STATUSES = {LeadParsingJob.Status.RUNNING, LeadParsingJob.Status.PAUSED}
FINAL_STATUSES = {
    LeadParsingJob.Status.COMPLETED,
    LeadParsingJob.Status.STOPPED,
    LeadParsingJob.Status.FAILED,
}
PLACES_INCLUDED_TYPE_CHOICES = (
    ("", "Без фільтра"),
    ("clothing_store", "Магазини одягу"),
    ("shoe_store", "Взуття"),
    ("store", "Загальний магазин"),
    ("shopping_mall", "ТЦ / торгова площа"),
    ("sporting_goods_store", "Спорттовари"),
    ("market", "Ринок / базар"),
    ("department_store", "Універмаг"),
    ("discount_store", "Дисконт"),
)
ALLOWED_PLACES_INCLUDED_TYPES = {value for value, _label in PLACES_INCLUDED_TYPE_CHOICES if value}
PLACES_INCLUDED_TYPE_LABELS = dict(PLACES_INCLUDED_TYPE_CHOICES)


class ParsingServiceError(Exception):
    pass


@dataclass(slots=True)
class ParsingCounters:
    moderation: int
    base: int
    converted: int
    rejected: int
    unprocessed: int


@dataclass(slots=True)
class ParserDuplicateDecision:
    state: str | None = None
    reason: str = ""
    reason_code: str = ""
    result_status: str = LeadParsingResult.ResultStatus.DUPLICATE
    count_as_duplicate: bool = True


@dataclass(slots=True)
class PreparedPlace:
    payload: dict[str, Any]
    place_id: str
    place_name: str
    raw_phone: str
    phone_normalized: str
    website_url: str
    maps_url: str


@dataclass(slots=True)
class DuplicateBatchState:
    job_place_ids: set[str]
    job_phones: set[str]
    recent_client_phones: set[str]
    recent_active_lead_phones: set[str]
    recent_rejected_phones: set[str]
    recent_place_ids: set[str]


@dataclass(slots=True)
class QueryStateTransition:
    status: str = LeadParsingQueryState.Status.ACTIVE
    reason: str = ""
    reason_code: str = ""
    page_fingerprint: str = ""
    token_hash: str = ""


def _dedupe_case_insensitive(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        cleaned = str(value or "").strip()
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(cleaned)
    return deduped


def parse_keywords(raw_keywords: str) -> list[str]:
    return _dedupe_case_insensitive(split_terms(raw_keywords))


def parse_cities(raw_cities: str) -> list[str]:
    return _dedupe_case_insensitive(split_terms(raw_cities))


def sanitize_requests_per_minute(raw_value: int | str | None) -> int:
    try:
        value = int(str(raw_value or DEFAULT_REQUESTS_PER_MINUTE).strip())
    except (TypeError, ValueError):
        value = DEFAULT_REQUESTS_PER_MINUTE
    return max(1, min(value, MAX_REQUESTS_PER_MINUTE))


def sanitize_history_lookback_days(raw_value: int | str | None) -> int:
    try:
        value = int(str(raw_value or DEFAULT_HISTORY_LOOKBACK_DAYS).strip())
    except (TypeError, ValueError):
        value = DEFAULT_HISTORY_LOOKBACK_DAYS
    return max(0, min(value, MAX_HISTORY_LOOKBACK_DAYS))


def sanitize_target_leads_limit(raw_value: int | str | None) -> int:
    try:
        value = int(str(raw_value or "0").strip())
    except (TypeError, ValueError):
        value = 0
    return max(0, min(value, MAX_TARGET_LEADS_LIMIT))


def _coerce_flag(raw_value: Any) -> bool:
    if isinstance(raw_value, bool):
        return raw_value
    value = str(raw_value or "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def sanitize_places_included_type(raw_value: Any) -> str:
    value = str(raw_value or "").strip()
    return value if value in ALLOWED_PLACES_INCLUDED_TYPES else ""


def sanitize_places_included_types(raw_values: Any) -> list[str]:
    if raw_values is None:
        return []
    if isinstance(raw_values, str):
        iterable = [raw_values]
    elif isinstance(raw_values, (list, tuple, set)):
        iterable = list(raw_values)
    else:
        iterable = [raw_values]

    sanitized: list[str] = []
    for value in iterable:
        normalized = sanitize_places_included_type(value)
        if normalized and normalized not in sanitized:
            sanitized.append(normalized)
    return sanitized


def places_included_type_label(raw_value: Any) -> str:
    normalized = sanitize_places_included_type(raw_value)
    if not normalized:
        return PLACES_INCLUDED_TYPE_LABELS.get("", "Без фільтра")
    return PLACES_INCLUDED_TYPE_LABELS.get(normalized, normalized)


def parser_selected_included_types(job: LeadParsingJob) -> list[str]:
    selected = sanitize_places_included_types(job.included_types)
    if selected:
        return selected
    single = sanitize_places_included_type(job.included_type)
    return [single] if single else []


def _request_type_sequence(job: LeadParsingJob) -> list[str]:
    selected = parser_selected_included_types(job)
    return selected or [""]


def _normalize_job_type_state(job: LeadParsingJob):
    selected = parser_selected_included_types(job)
    sequence = selected or [""]
    max_index = len(sequence) - 1
    if int(job.current_type_index or 0) > max_index:
        job.current_type_index = 0
    active_type = sequence[int(job.current_type_index or 0)]
    job.included_types = selected
    job.included_type = active_type


def _current_included_type(job: LeadParsingJob) -> str:
    _normalize_job_type_state(job)
    return str(job.included_type or "").strip()


def _current_keyword(job: LeadParsingJob) -> str:
    keywords = job.keywords or []
    if not keywords or job.current_keyword_index >= len(keywords):
        return ""
    return str(keywords[job.current_keyword_index]).strip()


def _current_city(job: LeadParsingJob) -> str:
    cities = job.cities or []
    if not cities or job.current_city_index >= len(cities):
        return ""
    return str(cities[job.current_city_index]).strip()


def current_parser_query(job: LeadParsingJob) -> str:
    request_spec = job.current_request_spec or {}
    if request_spec.get("text_query"):
        return str(request_spec.get("text_query") or "").strip()
    keyword = _current_keyword(job)
    city = _current_city(job)
    return f"{keyword} {city}".strip()


def effective_added_lead_count(job: LeadParsingJob) -> int:
    return int(job.added_to_moderation or 0) + int(job.saved_no_phone_to_moderation or 0)


def _fit_charfield(value: str, max_length: int) -> str:
    text = str(value or "").strip()
    if len(text) <= max_length:
        return text
    if max_length <= 3:
        return text[:max_length]
    return f"{text[: max_length - 3].rstrip()}..."


def _request_identity(job: LeadParsingJob, request_spec: dict[str, Any] | None = None) -> dict[str, str]:
    request_spec = dict(request_spec or {})
    keyword = str(request_spec.get("keyword") or _current_keyword(job)).strip()
    city = str(request_spec.get("city") or _current_city(job)).strip()
    included_type = sanitize_places_included_type(request_spec.get("included_type") or _current_included_type(job))
    text_query = str(request_spec.get("text_query") or f"{keyword} {city}".strip()).strip()
    return {
        "keyword": keyword,
        "city": city,
        "included_type": included_type,
        "text_query": text_query,
    }


def _hash_token(raw_value: str) -> str:
    value = str(raw_value or "").strip()
    if not value:
        return ""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _page_fingerprint(prepared_places: list[PreparedPlace], next_page_token: str) -> str:
    items: list[str] = []
    for prepared in prepared_places:
        if prepared.place_id:
            items.append(f"id:{prepared.place_id}")
            continue
        fallback = "|".join(
            [
                prepared.place_name.strip().casefold(),
                (prepared.phone_normalized or prepared.raw_phone).strip(),
                prepared.website_url.strip().casefold(),
            ]
        ).strip("|")
        if fallback:
            items.append(f"fallback:{fallback}")
    items.sort()
    # Fingerprint the actual page content, not the pagination token.
    # Google may rotate nextPageToken while still looping over the same places.
    raw = "||".join(items)
    if not raw:
        raw = f"empty::{bool(str(next_page_token or '').strip())}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _get_or_create_query_state(job: LeadParsingJob, request_spec: dict[str, Any] | None = None) -> LeadParsingQueryState:
    identity = _request_identity(job, request_spec)
    query_state, created = LeadParsingQueryState.objects.get_or_create(
        job=job,
        keyword=identity["keyword"],
        city=identity["city"],
        included_type=identity["included_type"],
        defaults={"text_query": identity["text_query"]},
    )
    if created or query_state.text_query != identity["text_query"]:
        query_state.text_query = identity["text_query"]
        query_state.save(update_fields=["text_query", "updated_at"])
    return query_state


def parser_current_query_state_payload(job: LeadParsingJob | None) -> dict[str, Any] | None:
    if not job:
        return None
    identity = _request_identity(job, job.current_request_spec or None)
    if not identity["keyword"] and not identity["city"] and not identity["text_query"]:
        return None
    query_state = (
        LeadParsingQueryState.objects.filter(
            job=job,
            keyword=identity["keyword"],
            city=identity["city"],
            included_type=identity["included_type"],
        )
        .order_by("-updated_at", "-id")
        .first()
    )
    if not query_state:
        return None
    return {
        "status": query_state.status,
        "status_display": query_state.get_status_display(),
        "keyword": query_state.keyword,
        "city": query_state.city,
        "included_type": query_state.included_type,
        "text_query": query_state.text_query,
        "pages_fetched": query_state.pages_fetched,
        "api_requests_sent": query_state.api_requests_sent,
        "places_seen_count": query_state.places_seen_count,
        "places_added_count": query_state.places_added_count,
        "exhausted_reason_code": query_state.exhausted_reason_code,
        "exhausted_message": query_state.exhausted_message,
    }


def get_maps_api_key() -> str:
    from django.conf import settings

    key = (getattr(settings, "GMapsAPI", None) or "").strip()
    if key:
        return key

    key = (os.environ.get("GMapsAPI") or "").strip()
    if not key:
        raise ParsingServiceError("Не знайдено GMapsAPI у змінних середовища.")
    return key


def get_maps_request_referer() -> str:
    from django.conf import settings

    referer = (
        getattr(settings, "GMAPS_REQUEST_REFERER", None)
        or os.environ.get("GMAPS_REQUEST_REFERER")
        or "https://management.twocomms.shop/"
    )
    referer = str(referer or "").strip()
    if referer and not referer.endswith("/"):
        referer += "/"
    return referer


def _google_context_headers() -> dict[str, str]:
    referer = get_maps_request_referer()
    if not referer:
        return {}
    headers = {"Referer": referer}
    parsed = urlparse(referer)
    if parsed.scheme and parsed.netloc:
        headers["Origin"] = f"{parsed.scheme}://{parsed.netloc}"
    return headers


def geocode_city_center(city: str, api_key: str) -> dict[str, Any] | None:
    normalized_city = " ".join(str(city or "").strip().casefold().split())
    if not normalized_city:
        return None

    cache_key = f"management:parser:geocode:v1:{normalized_city}"
    cached = cache.get(cache_key)
    if cached is not None:
        return None if cached == GEOCODE_NEGATIVE_SENTINEL else cached

    params = {"address": city, "key": api_key}
    try:
        resp = requests.get(GEOCODE_URL, params=params, headers=_google_context_headers(), timeout=12)
        if resp.status_code != 200:
            cache.set(cache_key, GEOCODE_NEGATIVE_SENTINEL, GEOCODE_NEGATIVE_CACHE_TTL_SECONDS)
            return None
        payload = resp.json() or {}
        if payload.get("status") != "OK":
            cache.set(cache_key, GEOCODE_NEGATIVE_SENTINEL, GEOCODE_NEGATIVE_CACHE_TTL_SECONDS)
            return None
        results = payload.get("results") or []
        if not results:
            cache.set(cache_key, GEOCODE_NEGATIVE_SENTINEL, GEOCODE_NEGATIVE_CACHE_TTL_SECONDS)
            return None
        geometry = results[0].get("geometry", {}) or {}
        location = geometry.get("location") or {}
        lat = location.get("lat")
        lng = location.get("lng")
        if lat is None or lng is None:
            cache.set(cache_key, GEOCODE_NEGATIVE_SENTINEL, GEOCODE_NEGATIVE_CACHE_TTL_SECONDS)
            return None
        result: dict[str, Any] = {
            "latitude": float(lat),
            "longitude": float(lng),
        }

        viewport = geometry.get("viewport") or geometry.get("bounds") or {}
        southwest = viewport.get("southwest") or {}
        northeast = viewport.get("northeast") or {}
        if all(key in southwest for key in ("lat", "lng")) and all(key in northeast for key in ("lat", "lng")):
            result["viewport"] = {
                "low": {
                    "latitude": float(southwest["lat"]),
                    "longitude": float(southwest["lng"]),
                },
                "high": {
                    "latitude": float(northeast["lat"]),
                    "longitude": float(northeast["lng"]),
                },
            }
        cache.set(cache_key, result, GEOCODE_CACHE_TTL_SECONDS)
        return result
    except requests.RequestException:
        cache.set(cache_key, GEOCODE_NEGATIVE_SENTINEL, GEOCODE_NEGATIVE_CACHE_TTL_SECONDS)
        return None


def _location_payload_from_context(city_context: dict[str, Any] | None) -> dict[str, Any]:
    if city_context and city_context.get("viewport"):
        return {
            "geo_mode": "viewport_restriction",
            "locationRestriction": {
                "rectangle": city_context["viewport"],
            },
        }
    if city_context and city_context.get("latitude") is not None and city_context.get("longitude") is not None:
        return {
            "geo_mode": "circle_bias",
            "locationBias": {
                "circle": {
                    "center": {
                        "latitude": float(city_context["latitude"]),
                        "longitude": float(city_context["longitude"]),
                    },
                    "radius": PLACE_SEARCH_RADIUS_METERS,
                }
            },
        }
    return {"geo_mode": "none"}


def _build_request_spec(job: LeadParsingJob, api_key: str) -> dict[str, Any]:
    _normalize_job_type_state(job)
    keyword = _current_keyword(job)
    city = _current_city(job)
    query = f"{keyword} {city}".strip()
    city_context = geocode_city_center(city, api_key)
    location_payload = _location_payload_from_context(city_context)
    geo_mode = str(location_payload.pop("geo_mode", "none"))
    selected_types = parser_selected_included_types(job)
    active_type = _current_included_type(job)
    spec = {
        "keyword": keyword,
        "city": city,
        "text_query": query,
        "page_index": 0,
        "field_mask_version": CURRENT_FIELD_MASK_VERSION,
        "geo_mode": geo_mode,
        "region_code": "UA",
        "included_type": active_type,
        "included_type_label": places_included_type_label(active_type),
        "included_types": selected_types,
        "current_type_index": int(job.current_type_index or 0),
        "type_ordinal": int(job.current_type_index or 0) + 1,
        "types_total": len(selected_types) or 1,
        "strict_type_filtering": bool(selected_types and job.strict_type_filtering),
    }
    if location_payload:
        spec["location_payload"] = location_payload
    return spec


def _coerce_request_spec(job: LeadParsingJob, api_key: str) -> dict[str, Any]:
    keyword = _current_keyword(job)
    city = _current_city(job)
    current_spec = dict(job.current_request_spec or {})
    _normalize_job_type_state(job)
    if (
        job.next_page_token
        and current_spec
        and str(current_spec.get("keyword") or "") == keyword
        and str(current_spec.get("city") or "") == city
    ):
        current_spec.setdefault("text_query", f"{keyword} {city}".strip())
        current_spec.setdefault("page_index", 0)
        current_spec["field_mask_version"] = CURRENT_FIELD_MASK_VERSION
        current_spec.setdefault("geo_mode", "none")
        current_spec["region_code"] = "UA"
        current_spec.setdefault("included_type", _current_included_type(job))
        current_spec["included_type_label"] = places_included_type_label(current_spec.get("included_type"))
        current_spec["included_types"] = parser_selected_included_types(job)
        current_spec["current_type_index"] = int(job.current_type_index or 0)
        current_spec["type_ordinal"] = int(job.current_type_index or 0) + 1
        current_spec["types_total"] = len(parser_selected_included_types(job)) or 1
        current_spec["strict_type_filtering"] = bool(parser_selected_included_types(job) and job.strict_type_filtering)
        return current_spec
    return _build_request_spec(job, api_key)


def _places_search_text(
    api_key: str,
    text_query: str,
    city: str,
    page_token: str = "",
    request_spec: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], str]:
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": PLACES_FIELD_MASK,
    }
    headers.update(_google_context_headers())

    spec = dict(request_spec or {})
    body: dict[str, Any] = {
        "textQuery": str(spec.get("text_query") or text_query).strip(),
        "languageCode": "uk",
        "regionCode": str(spec.get("region_code") or "UA"),
        "pageSize": PLACES_PAGE_SIZE,
    }
    included_type = sanitize_places_included_type(spec.get("included_type"))
    if included_type:
        body["includedType"] = included_type
        if _coerce_flag(spec.get("strict_type_filtering")):
            body["strictTypeFiltering"] = True

    location_payload = dict(spec.get("location_payload") or {})
    if not location_payload:
        city_context = geocode_city_center(city, api_key)
        location_payload = _location_payload_from_context(city_context)
        location_payload.pop("geo_mode", None)
    body.update(location_payload)

    if page_token:
        body["pageToken"] = page_token

    try:
        resp = requests.post(PLACES_TEXT_SEARCH_URL, json=body, headers=headers, timeout=20)
    except requests.RequestException as exc:
        raise ParsingServiceError(f"Помилка HTTP запиту до Google Places: {exc}") from exc

    if resp.status_code >= 400:
        detail = ""
        try:
            detail = (resp.json() or {}).get("error", {}).get("message", "")
        except Exception:
            detail = resp.text[:400]
        raise ParsingServiceError(f"Google Places API помилка ({resp.status_code}): {detail or 'невідома помилка'}")

    payload = resp.json() or {}
    return payload.get("places") or [], str(payload.get("nextPageToken") or "")


def _place_display_name(place: dict[str, Any]) -> str:
    display_name = place.get("displayName")
    if isinstance(display_name, dict):
        return str(display_name.get("text") or "").strip()
    return str(display_name or "").strip()


def _place_phone(place: dict[str, Any]) -> str:
    return str(place.get("internationalPhoneNumber") or place.get("nationalPhoneNumber") or "").strip()


def _place_details_blob(place: dict[str, Any]) -> str:
    chunks: list[str] = []
    address = str(place.get("formattedAddress") or "").strip()
    if address:
        chunks.append(f"Адреса: {address}")
    place_types = [str(item or "").strip() for item in (place.get("types") or []) if str(item or "").strip()]
    if place_types:
        chunks.append(f"Google Places types: {', '.join(place_types)}")
    website = str(place.get("websiteUri") or "").strip()
    if website:
        chunks.append(f"Сайт: {website}")
    maps_uri = str(place.get("googleMapsUri") or "").strip()
    if maps_uri:
        chunks.append(f"Google Maps: {maps_uri}")
    return "\n".join(chunks)


def _prepare_places(places: list[dict[str, Any]]) -> list[PreparedPlace]:
    prepared: list[PreparedPlace] = []
    for place in places:
        raw_phone = _place_phone(place)
        prepared.append(
            PreparedPlace(
                payload=place,
                place_id=str(place.get("id") or "").strip(),
                place_name=_place_display_name(place),
                raw_phone=raw_phone,
                phone_normalized=normalize_phone(raw_phone),
                website_url=str(place.get("websiteUri") or "").strip(),
                maps_url=str(place.get("googleMapsUri") or "").strip(),
            )
        )
    return prepared


def _analyze_query_transition(
    query_state: LeadParsingQueryState,
    prepared_places: list[PreparedPlace],
    next_page_token: str,
) -> QueryStateTransition:
    next_pages_fetched = int(query_state.pages_fetched or 0) + 1
    page_fingerprint = _page_fingerprint(prepared_places, next_page_token)
    token_hash = _hash_token(next_page_token)
    seen_fingerprints = list(query_state.seen_page_fingerprints or [])
    next_empty_pages = int(query_state.consecutive_empty_pages or 0) + (1 if not prepared_places else 0)

    if next_pages_fetched > QUERY_PAGE_HARD_CAP:
        return QueryStateTransition(
            status=LeadParsingQueryState.Status.ANOMALY,
            reason="Google Places повернув підозріло довгу пагінацію для одного query; job зупинено як захист від циклу.",
            reason_code="query_page_cap_exceeded",
            page_fingerprint=page_fingerprint,
            token_hash=token_hash,
        )

    if page_fingerprint and page_fingerprint in seen_fingerprints:
        return QueryStateTransition(
            status=LeadParsingQueryState.Status.ANOMALY,
            reason="Google Places повторив ту саму сторінку для поточного query; job зупинено як захист від циклу.",
            reason_code="query_exhausted_repeated_page",
            page_fingerprint=page_fingerprint,
            token_hash=token_hash,
        )

    if token_hash and query_state.last_next_page_token_hash and token_hash == query_state.last_next_page_token_hash:
        return QueryStateTransition(
            status=LeadParsingQueryState.Status.ANOMALY,
            reason="Google Places повторив той самий page token без прогресу; job зупинено як захист від циклу.",
            reason_code="query_exhausted_repeated_token",
            page_fingerprint=page_fingerprint,
            token_hash=token_hash,
        )

    if not prepared_places and next_page_token and next_empty_pages >= QUERY_EMPTY_PAGE_LOOP_LIMIT:
        return QueryStateTransition(
            status=LeadParsingQueryState.Status.ANOMALY,
            reason="Google Places кілька разів повернув порожню сторінку з продовженням пагінації; job зупинено як захист від циклу.",
            reason_code="query_exhausted_empty_page_loop",
            page_fingerprint=page_fingerprint,
            token_hash=token_hash,
        )

    if not next_page_token:
        return QueryStateTransition(
            status=LeadParsingQueryState.Status.EXHAUSTED,
            reason="Результати за цим запитом закінчилися.",
            reason_code="query_exhausted_no_more_results",
            page_fingerprint=page_fingerprint,
            token_hash=token_hash,
        )

    return QueryStateTransition(
        status=LeadParsingQueryState.Status.ACTIVE,
        page_fingerprint=page_fingerprint,
        token_hash=token_hash,
    )


def _persist_query_state_progress(
    *,
    query_state: LeadParsingQueryState,
    transition: QueryStateTransition,
    prepared_places: list[PreparedPlace],
    added_count: int,
    step_finished_at,
):
    seen_fingerprints = list(query_state.seen_page_fingerprints or [])
    if transition.page_fingerprint and transition.page_fingerprint not in seen_fingerprints:
        seen_fingerprints.append(transition.page_fingerprint)
        seen_fingerprints = seen_fingerprints[-QUERY_PAGE_FINGERPRINT_LIMIT:]

    query_state.pages_fetched = int(query_state.pages_fetched or 0) + 1
    query_state.api_requests_sent = int(query_state.api_requests_sent or 0) + 1
    query_state.places_seen_count = int(query_state.places_seen_count or 0) + len(prepared_places)
    query_state.places_added_count = int(query_state.places_added_count or 0) + added_count
    query_state.consecutive_empty_pages = int(query_state.consecutive_empty_pages or 0) + (1 if not prepared_places else 0)
    if prepared_places:
        query_state.consecutive_empty_pages = 0
    if transition.status == LeadParsingQueryState.Status.ANOMALY:
        query_state.consecutive_repeated_pages = int(query_state.consecutive_repeated_pages or 0) + 1
    else:
        query_state.consecutive_repeated_pages = 0
    query_state.last_next_page_token_hash = transition.token_hash
    query_state.seen_page_fingerprints = seen_fingerprints
    if prepared_places or added_count or transition.status != LeadParsingQueryState.Status.ACTIVE:
        query_state.last_progress_at = step_finished_at
    query_state.status = transition.status
    if transition.status in {LeadParsingQueryState.Status.EXHAUSTED, LeadParsingQueryState.Status.ANOMALY}:
        query_state.exhausted_reason_code = transition.reason_code
        query_state.exhausted_message = _fit_charfield(transition.reason, MAX_QUERY_EXHAUSTED_MESSAGE_LENGTH)
    query_state.save()


def _recent_history_cutoff(job: LeadParsingJob):
    if int(job.history_lookback_days or 0) <= 0:
        return None
    return timezone.now() - timedelta(days=int(job.history_lookback_days))


def _build_duplicate_batch_state(job: LeadParsingJob, prepared_places: list[PreparedPlace]) -> DuplicateBatchState:
    place_ids = {place.place_id for place in prepared_places if place.place_id}
    phones = {place.phone_normalized for place in prepared_places if place.phone_normalized}

    job_place_ids = set()
    job_phones = set()
    if place_ids:
        job_place_ids = set(
            LeadParsingResult.objects.filter(job=job, place_id__in=place_ids)
            .exclude(place_id="")
            .values_list("place_id", flat=True)
        )
    if phones:
        job_phones = set(
            LeadParsingResult.objects.filter(job=job, phone__in=phones)
            .exclude(phone="")
            .values_list("phone", flat=True)
        )

    cutoff = _recent_history_cutoff(job)
    recent_client_phones: set[str] = set()
    recent_active_lead_phones: set[str] = set()
    recent_rejected_phones: set[str] = set()
    recent_place_ids: set[str] = set()

    if cutoff:
        if phones:
            recent_client_phones = set(
                Client.objects.filter(phone_normalized__in=phones, created_at__gte=cutoff).values_list("phone_normalized", flat=True)
            )
            lead_base = ManagementLead.objects.filter(phone_normalized__in=phones, created_at__gte=cutoff)
            recent_active_lead_phones = set(
                lead_base.exclude(status=ManagementLead.Status.REJECTED).values_list("phone_normalized", flat=True)
            )
            recent_rejected_phones = set(
                lead_base.filter(status=ManagementLead.Status.REJECTED).values_list("phone_normalized", flat=True)
            )
        if place_ids:
            recent_place_ids = set(
                ManagementLead.objects.filter(
                    google_place_id__in=place_ids,
                    created_at__gte=cutoff,
                )
                .exclude(google_place_id="")
                .values_list("google_place_id", flat=True)
            )

    return DuplicateBatchState(
        job_place_ids=job_place_ids,
        job_phones=job_phones,
        recent_client_phones=recent_client_phones,
        recent_active_lead_phones=recent_active_lead_phones,
        recent_rejected_phones=recent_rejected_phones,
        recent_place_ids=recent_place_ids,
    )


def _parser_duplicate_state(
    job: LeadParsingJob,
    prepared: PreparedPlace,
    batch: DuplicateBatchState,
    seen_job_phones: set[str],
    seen_job_place_ids: set[str],
) -> ParserDuplicateDecision:
    if prepared.place_id and prepared.place_id in seen_job_place_ids:
        return ParserDuplicateDecision(
            state="job_place",
            reason="Повторний Place ID у поточному парсингу",
            reason_code="duplicate_job_place",
        )

    if prepared.phone_normalized and prepared.phone_normalized in seen_job_phones:
        return ParserDuplicateDecision(
            state="job_phone",
            reason="Повторний номер у поточному парсингу",
            reason_code="duplicate_job_phone",
        )

    if int(job.history_lookback_days or 0) <= 0:
        return ParserDuplicateDecision()

    if prepared.phone_normalized:
        if prepared.phone_normalized in batch.recent_client_phones:
            return ParserDuplicateDecision(
                state="existing_client",
                reason=f"Номер вже є у клієнтах за останні {job.history_lookback_days} дн.",
                reason_code="recent_history_phone",
            )
        if prepared.phone_normalized in batch.recent_active_lead_phones:
            return ParserDuplicateDecision(
                state="existing_lead",
                reason=f"Номер вже оброблявся у лідах за останні {job.history_lookback_days} дн.",
                reason_code="recent_history_phone",
            )
        if prepared.phone_normalized in batch.recent_rejected_phones:
            return ParserDuplicateDecision(
                state="rejected_history",
                reason=f"Номер вже відхиляли за останні {job.history_lookback_days} дн.",
                reason_code="recent_history_phone",
                result_status=LeadParsingResult.ResultStatus.REJECTED,
                count_as_duplicate=False,
            )

    if prepared.place_id and prepared.place_id in batch.recent_place_ids:
        return ParserDuplicateDecision(
            state="recent_history_place",
            reason=f"Place ID вже зустрічався за останні {job.history_lookback_days} дн.",
            reason_code="recent_history_place",
        )

    return ParserDuplicateDecision()


def _mark_seen(prepared: PreparedPlace, seen_job_phones: set[str], seen_job_place_ids: set[str]):
    if prepared.place_id:
        seen_job_place_ids.add(prepared.place_id)
    if prepared.phone_normalized:
        seen_job_phones.add(prepared.phone_normalized)


def _advance_position(job: LeadParsingJob) -> bool:
    keywords = job.keywords or []
    cities = job.cities or []
    type_sequence = _request_type_sequence(job)
    job.current_request_spec = {}
    job.next_page_token = ""
    if not keywords or not cities:
        return False
    if job.current_type_index + 1 < len(type_sequence):
        job.current_type_index += 1
        job.included_type = type_sequence[job.current_type_index]
        return True
    job.current_type_index = 0
    job.included_type = type_sequence[0] if type_sequence else ""
    if job.current_keyword_index + 1 < len(keywords):
        job.current_keyword_index += 1
        return True
    job.current_keyword_index = 0
    job.current_city_index += 1
    return job.current_city_index < len(cities)


def _finalize_job(job: LeadParsingJob, status: str, *, finished_at=None, stop_reason_code: str = ""):
    finished_at = finished_at or timezone.now()
    job.status = status
    job.next_step_not_before = None
    job.retry_state = {}
    if status in FINAL_STATUSES:
        job.finished_at = finished_at
        job.current_request_spec = {}
        job.next_page_token = ""
        if stop_reason_code:
            job.stop_reason_code = stop_reason_code


def _rate_interval(job: LeadParsingJob) -> timedelta:
    rpm = sanitize_requests_per_minute(job.requests_per_minute)
    return timedelta(seconds=60 / rpm)


def _backoff_delay(kind: str, count: int) -> timedelta:
    if kind == "page_token":
        return timedelta(seconds=min(2 ** count, 8))
    return timedelta(seconds=min(3 * count, 12))


def _is_page_token_error(message: str, has_page_token: bool) -> bool:
    if not has_page_token:
        return False
    lowered = (message or "").lower()
    return "page token" in lowered or "pagetoken" in lowered or "invalid_request" in lowered


def _is_transient_google_error(message: str) -> bool:
    lowered = (message or "").lower()
    return (
        "http запиту" in lowered
        or "http request" in lowered
        or "(429)" in lowered
        or "(500)" in lowered
        or "(502)" in lowered
        or "(503)" in lowered
        or "(504)" in lowered
        or "timed out" in lowered
        or "timeout" in lowered
    )


def _set_step_finish(job: LeadParsingJob, *, started_at, finished_at):
    job.is_step_in_progress = False
    job.last_step_finished_at = finished_at
    job.heartbeat_at = finished_at
    if started_at:
        job.last_step_duration_ms = max(0, int((finished_at - started_at).total_seconds() * 1000))
    else:
        job.last_step_duration_ms = 0


def _reset_runtime_state(job: LeadParsingJob):
    job.next_page_token = ""
    job.current_request_spec = {}
    job.next_step_not_before = None
    job.retry_state = {}
    job.is_step_in_progress = False


def _mark_job_stopped(job: LeadParsingJob, *, reason_code: str, finished_at):
    _reset_runtime_state(job)
    job.status = LeadParsingJob.Status.STOPPED
    job.stop_reason_code = reason_code
    job.finished_at = finished_at
    job.heartbeat_at = finished_at


def _job_heartbeat_reference(job: LeadParsingJob):
    return job.heartbeat_at or job.last_step_started_at or job.last_step_finished_at or job.started_at


def _job_is_stale(job: LeadParsingJob, now) -> bool:
    if job.status != LeadParsingJob.Status.RUNNING:
        return False
    heartbeat = _job_heartbeat_reference(job)
    return bool(heartbeat and heartbeat <= now - SESSION_STALE_AFTER)


def _runtime_lock_for_update() -> LeadParsingRuntimeLock:
    lock, _ = LeadParsingRuntimeLock.objects.select_for_update().get_or_create(singleton_key=RUNTIME_LOCK_KEY)
    return lock


def _sync_runtime_lock(lock: LeadParsingRuntimeLock, job: LeadParsingJob | None):
    lock.active_job = job if job and job.status in ACTIVE_STATUSES else None
    lock.save(update_fields=["active_job", "updated_at"])


def _normalize_active_jobs_locked(lock: LeadParsingRuntimeLock, *, now=None) -> LeadParsingJob | None:
    now = now or timezone.now()
    active_jobs = list(
        LeadParsingJob.objects.select_for_update()
        .filter(status__in=ACTIVE_STATUSES)
        .order_by("-started_at", "-id")
    )

    canonical: LeadParsingJob | None = None
    if lock.active_job_id:
        canonical = next((job for job in active_jobs if job.id == lock.active_job_id), None)
    if canonical is None and active_jobs:
        canonical = active_jobs[0]

    for job in active_jobs:
        if canonical and job.id == canonical.id:
            continue
        _mark_job_stopped(job, reason_code="session_superseded", finished_at=now)
        job.save()

    if canonical and _job_is_stale(canonical, now):
        _mark_job_stopped(canonical, reason_code="session_stale_stopped", finished_at=now)
        canonical.save()
        canonical = None

    _sync_runtime_lock(lock, canonical)
    return canonical


def _create_result(
    *,
    job: LeadParsingJob,
    keyword: str,
    city: str,
    query: str,
    status: str,
    reason: str,
    reason_code: str,
    place_id: str = "",
    place_name: str = "",
    phone: str = "",
    website_url: str = "",
    maps_url: str = "",
    payload: dict[str, Any] | None = None,
    lead: ManagementLead | None = None,
):
    LeadParsingResult.objects.create(
        job=job,
        lead=lead,
        keyword=keyword,
        city=city,
        query=query,
        place_id=place_id,
        place_name=place_name,
        phone=phone,
        website_url=website_url,
        maps_url=maps_url,
        status=status,
        reason=_fit_charfield(reason, MAX_RESULT_REASON_LENGTH),
        reason_code=reason_code,
        payload=payload or {},
    )


def _apply_duplicate_counters(job: LeadParsingJob, decision: ParserDuplicateDecision):
    if decision.count_as_duplicate:
        job.duplicate_skipped += 1
    if decision.state == "job_place":
        job.duplicate_same_job_place_skipped += 1
    elif decision.state == "job_phone":
        job.duplicate_same_job_phone_skipped += 1
    elif decision.state == "existing_client":
        job.duplicate_existing_client_skipped += 1
        if decision.reason_code == "recent_history_phone":
            job.recent_history_phone_skipped += 1
    elif decision.state == "existing_lead":
        job.duplicate_existing_lead_skipped += 1
        if decision.reason_code == "recent_history_phone":
            job.recent_history_phone_skipped += 1
    elif decision.state == "rejected_history":
        job.already_rejected_skipped += 1
        if decision.reason_code == "recent_history_phone":
            job.recent_history_phone_skipped += 1
    elif decision.state == "recent_history_place":
        job.recent_history_place_skipped += 1


def _apply_query_state_skip(
    *,
    job: LeadParsingJob,
    request_spec: dict[str, Any],
    query_state: LeadParsingQueryState,
    step_started_at,
    step_finished_at,
) -> LeadParsingJob:
    keyword = str(request_spec.get("keyword") or _current_keyword(job)).strip()
    city = str(request_spec.get("city") or _current_city(job)).strip()
    query = str(request_spec.get("text_query") or f"{keyword} {city}".strip()).strip()
    reason_code = "query_exhausted_cached_skip"
    if query_state.status == LeadParsingQueryState.Status.ANOMALY:
        reason_code = "query_anomaly_cached_skip"
    _create_result(
        job=job,
        keyword=keyword,
        city=city,
        query=query,
        status=LeadParsingResult.ResultStatus.NOTICE,
        reason=query_state.exhausted_message or "Запит уже був завершений раніше; повторний API виклик пропущено.",
        reason_code=reason_code,
        payload={"query_state_id": query_state.id, "query_state_status": query_state.status},
    )
    if job.status == LeadParsingJob.Status.RUNNING:
        has_next = _advance_position(job)
        if not has_next:
            _finalize_job(job, LeadParsingJob.Status.COMPLETED, finished_at=step_finished_at)
        else:
            job.next_step_not_before = step_finished_at
            job.current_query = current_parser_query(job)
    _set_step_finish(job, started_at=step_started_at, finished_at=step_finished_at)
    job.save()
    return job


def _apply_places_success(
    *,
    job: LeadParsingJob,
    places: list[dict[str, Any]],
    next_page_token: str,
    request_spec: dict[str, Any],
    step_started_at,
    step_finished_at,
) -> LeadParsingJob:
    keyword = str(request_spec.get("keyword") or _current_keyword(job)).strip()
    city = str(request_spec.get("city") or _current_city(job)).strip()
    query = str(request_spec.get("text_query") or f"{keyword} {city}".strip()).strip()

    query_state, _ = LeadParsingQueryState.objects.select_for_update().get_or_create(
        job=job,
        keyword=keyword,
        city=city,
        included_type=sanitize_places_included_type(request_spec.get("included_type")),
        defaults={"text_query": query},
    )
    if query_state.text_query != query:
        query_state.text_query = query

    job.request_count += 1
    job.request_success_count += 1
    job.last_error = ""
    job.retry_state = {}
    job.stop_reason_code = ""
    job.current_query = query

    prepared_places = _prepare_places(places)
    transition = _analyze_query_transition(query_state, prepared_places, next_page_token)
    if transition.status == LeadParsingQueryState.Status.ANOMALY:
        if query_state.status != LeadParsingQueryState.Status.ANOMALY:
            job.queries_exhausted_anomaly += 1
        _persist_query_state_progress(
            query_state=query_state,
            transition=transition,
            prepared_places=prepared_places,
            added_count=0,
            step_finished_at=step_finished_at,
        )
        _create_result(
            job=job,
            keyword=keyword,
            city=city,
            query=query,
            status=LeadParsingResult.ResultStatus.ERROR,
            reason=transition.reason,
            reason_code=transition.reason_code,
            payload={
                "query_state_id": query_state.id,
                "pages_fetched": query_state.pages_fetched,
                "next_page_token_present": bool(next_page_token),
            },
        )
        _mark_job_stopped(job, reason_code=transition.reason_code or "worker_stalled", finished_at=step_finished_at)
        _set_step_finish(job, started_at=step_started_at, finished_at=step_finished_at)
        job.save()
        return job

    batch = _build_duplicate_batch_state(job, prepared_places)
    seen_job_place_ids = set(batch.job_place_ids)
    seen_job_phones = set(batch.job_phones)
    added_count = 0

    for prepared in prepared_places:
        job.total_found += 1
        decision = _parser_duplicate_state(job, prepared, batch, seen_job_phones, seen_job_place_ids)
        if decision.state:
            _apply_duplicate_counters(job, decision)
            _create_result(
                job=job,
                keyword=keyword,
                city=city,
                query=query,
                status=decision.result_status,
                reason=decision.reason,
                reason_code=decision.reason_code,
                place_id=prepared.place_id,
                place_name=prepared.place_name,
                phone=prepared.phone_normalized or prepared.raw_phone,
                website_url=prepared.website_url,
                maps_url=prepared.maps_url,
                payload=prepared.payload,
            )
            _mark_seen(prepared, seen_job_phones, seen_job_place_ids)
            continue

        if not prepared.phone_normalized:
            if job.save_no_phone_leads and prepared.website_url:
                lead = ManagementLead.objects.create(
                    shop_name=prepared.place_name or f"{keyword} / {city}",
                    phone="",
                    full_name="",
                    role=Client.Role.OTHER,
                    source="Google Карти",
                    website_url=prepared.website_url,
                    city=city,
                    parser_keyword=keyword,
                    parser_query=query,
                    google_place_id=prepared.place_id,
                    google_maps_url=prepared.maps_url,
                    details=_place_details_blob(prepared.payload),
                    comments="Парсинг з Google Карт",
                    extra_data=prepared.payload,
                    status=ManagementLead.Status.MODERATION,
                    lead_source=ManagementLead.LeadSource.PARSER,
                    niche_status=ManagementLead.NicheStatus.MAYBE,
                    requires_phone_completion=True,
                    parser_job=job,
                    added_by=job.created_by,
                )
                job.saved_no_phone_to_moderation += 1
                _create_result(
                    job=job,
                    lead=lead,
                    keyword=keyword,
                    city=city,
                    query=query,
                    status=LeadParsingResult.ResultStatus.ADDED_NO_PHONE,
                    reason="Додано в модерацію без телефону; потрібне дозаповнення",
                    reason_code="added_no_phone_to_moderation",
                    place_id=prepared.place_id,
                    place_name=lead.shop_name,
                    phone="",
                    website_url=lead.website_url,
                    maps_url=lead.google_maps_url,
                    payload=prepared.payload,
                )
                added_count += 1
            else:
                job.no_phone_skipped += 1
                _create_result(
                    job=job,
                    keyword=keyword,
                    city=city,
                    query=query,
                    status=LeadParsingResult.ResultStatus.NO_PHONE,
                    reason="Контактний номер не знайдено",
                    reason_code="missing_phone",
                    place_id=prepared.place_id,
                    place_name=prepared.place_name,
                    phone=prepared.raw_phone,
                    website_url=prepared.website_url,
                    maps_url=prepared.maps_url,
                    payload=prepared.payload,
                )
            _mark_seen(prepared, seen_job_phones, seen_job_place_ids)
            continue

        lead = ManagementLead.objects.create(
            shop_name=prepared.place_name or f"{keyword} / {city}",
            phone=prepared.phone_normalized,
            full_name="",
            role=Client.Role.OTHER,
            source="Google Карти",
            website_url=prepared.website_url,
            city=city,
            parser_keyword=keyword,
            parser_query=query,
            google_place_id=prepared.place_id,
            google_maps_url=prepared.maps_url,
            details=_place_details_blob(prepared.payload),
            comments="Парсинг з Google Карт",
            extra_data=prepared.payload,
            status=ManagementLead.Status.MODERATION,
            lead_source=ManagementLead.LeadSource.PARSER,
            niche_status=ManagementLead.NicheStatus.MAYBE,
            parser_job=job,
            added_by=job.created_by,
        )
        job.added_to_moderation += 1
        _create_result(
            job=job,
            lead=lead,
            keyword=keyword,
            city=city,
            query=query,
            status=LeadParsingResult.ResultStatus.ADDED,
            reason="Успішно додано в модерацію",
            reason_code="added_to_moderation",
            place_id=prepared.place_id,
            place_name=lead.shop_name,
            phone=lead.phone,
            website_url=lead.website_url,
            maps_url=lead.google_maps_url,
            payload=prepared.payload,
        )
        added_count += 1
        _mark_seen(prepared, seen_job_phones, seen_job_place_ids)

    if transition.status == LeadParsingQueryState.Status.EXHAUSTED and query_state.status != LeadParsingQueryState.Status.EXHAUSTED:
        job.queries_exhausted_normal += 1
    _persist_query_state_progress(
        query_state=query_state,
        transition=transition,
        prepared_places=prepared_places,
        added_count=added_count,
        step_finished_at=step_finished_at,
    )

    if transition.status == LeadParsingQueryState.Status.EXHAUSTED:
        _create_result(
            job=job,
            keyword=keyword,
            city=city,
            query=query,
            status=LeadParsingResult.ResultStatus.NOTICE,
            reason=f"{query or 'Поточний запит'}: результати закінчилися.",
            reason_code=transition.reason_code,
            payload={"query_state_id": query_state.id, "included_type": query_state.included_type},
        )

    if job.status in ACTIVE_STATUSES:
        if job.status == LeadParsingJob.Status.RUNNING and int(job.target_leads_limit or 0) > 0 and effective_added_lead_count(job) >= int(job.target_leads_limit or 0):
            _create_result(
                job=job,
                keyword=keyword,
                city=city,
                query=query,
                status=LeadParsingResult.ResultStatus.NOTICE,
                reason=f"Досягнуто цілі по лідах: {effective_added_lead_count(job)}/{job.target_leads_limit}.",
                reason_code="target_leads_reached",
                payload={"effective_added_count": effective_added_lead_count(job), "target_leads_limit": job.target_leads_limit},
            )
            _finalize_job(
                job,
                LeadParsingJob.Status.COMPLETED,
                finished_at=step_finished_at,
                stop_reason_code="target_leads_reached",
            )
        elif job.status == LeadParsingJob.Status.RUNNING:
            job.next_page_token = next_page_token or ""
        if job.status == LeadParsingJob.Status.RUNNING and job.next_page_token:
            job.current_request_spec = {
                **request_spec,
                "page_index": int(request_spec.get("page_index") or 0) + 1,
            }
        elif job.status == LeadParsingJob.Status.RUNNING:
            has_next = _advance_position(job)
            if not has_next:
                _finalize_job(job, LeadParsingJob.Status.COMPLETED, finished_at=step_finished_at)
            else:
                job.current_query = current_parser_query(job)

        if job.status == LeadParsingJob.Status.RUNNING and job.request_count >= job.request_limit:
            _finalize_job(job, LeadParsingJob.Status.COMPLETED, finished_at=step_finished_at)
        elif job.status == LeadParsingJob.Status.RUNNING:
            delay = _rate_interval(job)
            if job.next_page_token:
                delay = max(delay, timedelta(seconds=PAGE_TOKEN_DELAY_SECONDS))
            job.next_step_not_before = step_finished_at + delay
            job.current_query = current_parser_query(job)
        elif job.status == LeadParsingJob.Status.PAUSED:
            job.next_step_not_before = None
            job.current_query = current_parser_query(job)
    else:
        _reset_runtime_state(job)

    _set_step_finish(job, started_at=step_started_at, finished_at=step_finished_at)
    job.save()
    return job


def _apply_internal_step_error(job: LeadParsingJob, *, error_message: str, step_started_at, step_finished_at) -> LeadParsingJob:
    job.last_error = error_message
    job.current_query = current_parser_query(job)
    if job.status == LeadParsingJob.Status.RUNNING:
        _finalize_job(job, LeadParsingJob.Status.FAILED, finished_at=step_finished_at)
    _set_step_finish(job, started_at=step_started_at, finished_at=step_finished_at)
    job.save()
    return job


def _apply_discarded_request(
    job: LeadParsingJob,
    *,
    request_spec: dict[str, Any],
    was_success: bool,
    error_message: str = "",
    step_started_at,
    step_finished_at,
) -> LeadParsingJob:
    job.request_count += 1
    if was_success:
        job.request_success_count += 1
        job.last_error = ""
    else:
        job.request_error_count += 1
        job.last_error = error_message
    job.current_query = str(request_spec.get("text_query") or current_parser_query(job)).strip()
    _reset_runtime_state(job)
    _set_step_finish(job, started_at=step_started_at, finished_at=step_finished_at)
    job.save()
    return job


def _apply_step_error(
    job: LeadParsingJob,
    *,
    request_spec: dict[str, Any],
    error_message: str,
    step_started_at,
    step_finished_at,
) -> LeadParsingJob:
    keyword = str(request_spec.get("keyword") or _current_keyword(job)).strip()
    city = str(request_spec.get("city") or _current_city(job)).strip()
    query = str(request_spec.get("text_query") or f"{keyword} {city}".strip()).strip()

    job.request_count += 1
    job.request_error_count += 1
    job.current_query = query
    job.current_request_spec = request_spec
    job.last_error = error_message

    retry_kind = None
    retry_limit = 0
    if _is_page_token_error(error_message, bool(job.next_page_token)):
        retry_kind = "page_token"
        retry_limit = PAGE_TOKEN_RETRY_LIMIT
    elif _is_transient_google_error(error_message):
        retry_kind = "transient"
        retry_limit = TRANSIENT_RETRY_LIMIT

    previous_kind = str((job.retry_state or {}).get("kind") or "")
    previous_count = int((job.retry_state or {}).get("count") or 0)
    retry_count = previous_count + 1 if retry_kind and previous_kind == retry_kind else 1

    if job.status == LeadParsingJob.Status.RUNNING and retry_kind and retry_count <= retry_limit:
        job.retry_state = {"kind": retry_kind, "count": retry_count, "message": error_message}
        job.next_step_not_before = step_finished_at + _backoff_delay(retry_kind, retry_count)
        _create_result(
            job=job,
            keyword=keyword,
            city=city,
            query=query,
            status=LeadParsingResult.ResultStatus.ERROR,
            reason=f"Тимчасова помилка Google, повтор {retry_count}/{retry_limit}",
            reason_code=f"{retry_kind}_retry",
            payload={"error": error_message, "next_page_token": job.next_page_token},
        )
        _set_step_finish(job, started_at=step_started_at, finished_at=step_finished_at)
        job.save()
        return job

    job.retry_state = {}

    if retry_kind == "page_token":
        _create_result(
            job=job,
            keyword=keyword,
            city=city,
            query=query,
            status=LeadParsingResult.ResultStatus.ERROR,
            reason="Page token не вдалося обробити після повторів",
            reason_code="page_token_exhausted",
            payload={"error": error_message, "next_page_token": job.next_page_token},
        )
        job.next_page_token = ""
        job.current_request_spec = {}
        if job.status == LeadParsingJob.Status.RUNNING:
            has_next = _advance_position(job)
            if not has_next or job.request_count >= job.request_limit:
                _finalize_job(job, LeadParsingJob.Status.COMPLETED, finished_at=step_finished_at)
            else:
                job.next_step_not_before = step_finished_at + _rate_interval(job)
                job.current_query = current_parser_query(job)
    else:
        _create_result(
            job=job,
            keyword=keyword,
            city=city,
            query=query,
            status=LeadParsingResult.ResultStatus.ERROR,
            reason=error_message,
            reason_code="places_api_error",
            payload={"error": error_message, "next_page_token": job.next_page_token},
        )
        if job.status == LeadParsingJob.Status.RUNNING:
            _finalize_job(job, LeadParsingJob.Status.FAILED, finished_at=step_finished_at)

    _set_step_finish(job, started_at=step_started_at, finished_at=step_finished_at)
    job.save()
    return job


def parser_dashboard_job(job_id: int | str | None = None) -> LeadParsingJob | None:
    now = timezone.now()
    with transaction.atomic():
        lock = _runtime_lock_for_update()
        active_job = _normalize_active_jobs_locked(lock, now=now)
        if job_id:
            return LeadParsingJob.objects.filter(id=job_id).first()
    if active_job:
        return active_job
    return LeadParsingJob.objects.order_by("-started_at", "-id").first()


def create_parsing_job(
    *,
    user,
    keywords_raw: str,
    cities_raw: str,
    request_limit: int,
    target_leads_limit: int | str | None = 0,
    requests_per_minute: int | str | None = DEFAULT_REQUESTS_PER_MINUTE,
    history_lookback_days: int | str | None = DEFAULT_HISTORY_LOOKBACK_DAYS,
    save_no_phone_leads: bool | str | None = False,
    included_types: list[str] | tuple[str, ...] | None = None,
    included_type: str | None = "",
    strict_type_filtering: bool | str | None = False,
) -> LeadParsingJob:
    keywords = parse_keywords(keywords_raw)
    cities = parse_cities(cities_raw)
    if not keywords:
        raise ParsingServiceError("Вкажіть хоча б одне ключове слово.")
    if not cities:
        raise ParsingServiceError("Вкажіть хоча б одне місто.")
    if request_limit < 1:
        raise ParsingServiceError("Ліміт запитів має бути >= 1.")

    now = timezone.now()
    sanitized_included_types = sanitize_places_included_types(included_types)
    if not sanitized_included_types:
        single_type = sanitize_places_included_type(included_type)
        if single_type:
            sanitized_included_types = [single_type]
    active_included_type = sanitized_included_types[0] if sanitized_included_types else ""
    with transaction.atomic():
        lock = _runtime_lock_for_update()
        active_job = _normalize_active_jobs_locked(lock, now=now)
        if active_job:
            raise ParsingServiceError("Вже є активна сесія парсингу. Зупиніть або відновіть її перед новим запуском.")

        job = LeadParsingJob.objects.create(
            created_by=user,
            status=LeadParsingJob.Status.RUNNING,
            keywords_raw=keywords_raw,
            cities_raw=cities_raw,
            keywords=keywords,
            cities=cities,
            request_limit=min(request_limit, 5000),
            target_leads_limit=sanitize_target_leads_limit(target_leads_limit),
            requests_per_minute=sanitize_requests_per_minute(requests_per_minute),
            history_lookback_days=sanitize_history_lookback_days(history_lookback_days),
            save_no_phone_leads=_coerce_flag(save_no_phone_leads),
            included_type=active_included_type,
            included_types=sanitized_included_types,
            current_type_index=0,
            strict_type_filtering=bool(sanitized_included_types and _coerce_flag(strict_type_filtering)),
            current_query=f"{keywords[0]} {cities[0]}".strip(),
            heartbeat_at=now,
        )
        _sync_runtime_lock(lock, job)
        return job


def parser_pause_job(job_id: int | str) -> LeadParsingJob:
    now = timezone.now()
    with transaction.atomic():
        lock = _runtime_lock_for_update()
        _normalize_active_jobs_locked(lock, now=now)
        job = LeadParsingJob.objects.select_for_update().get(id=job_id)
        if job.status == LeadParsingJob.Status.RUNNING:
            job.status = LeadParsingJob.Status.PAUSED
            job.next_step_not_before = None
            job.heartbeat_at = now
            job.stop_reason_code = ""
            job.save(update_fields=["status", "next_step_not_before", "heartbeat_at", "stop_reason_code", "updated_at"])
        _sync_runtime_lock(lock, job if job.status in ACTIVE_STATUSES else None)
        return job


def parser_resume_job(job_id: int | str) -> LeadParsingJob:
    now = timezone.now()
    with transaction.atomic():
        lock = _runtime_lock_for_update()
        active_job = _normalize_active_jobs_locked(lock, now=now)
        job = LeadParsingJob.objects.select_for_update().get(id=job_id)
        if active_job and active_job.id != job.id:
            raise ParsingServiceError("Вже є активна сесія парсингу. Спочатку завершіть або зупиніть її.")
        if job.status in {LeadParsingJob.Status.PAUSED, LeadParsingJob.Status.FAILED}:
            job.status = LeadParsingJob.Status.RUNNING
            job.last_error = ""
            job.retry_state = {}
            job.next_step_not_before = None
            job.heartbeat_at = now
            job.stop_reason_code = ""
            job.save(
                update_fields=[
                    "status",
                    "last_error",
                    "retry_state",
                    "next_step_not_before",
                    "heartbeat_at",
                    "stop_reason_code",
                    "updated_at",
                ]
            )
        _sync_runtime_lock(lock, job if job.status in ACTIVE_STATUSES else None)
        return job


def parser_stop_job(job_id: int | str, *, reason_code: str = "user_stop") -> LeadParsingJob:
    now = timezone.now()
    with transaction.atomic():
        lock = _runtime_lock_for_update()
        _normalize_active_jobs_locked(lock, now=now)
        job = LeadParsingJob.objects.select_for_update().get(id=job_id)
        if job.status in ACTIVE_STATUSES:
            _mark_job_stopped(job, reason_code=reason_code, finished_at=now)
            job.save()
        _sync_runtime_lock(lock, None if lock.active_job_id == job.id else lock.active_job)
        return job


def parser_run_step(job: LeadParsingJob) -> LeadParsingJob:
    step_started_at = timezone.now()
    request_spec: dict[str, Any] | None = None

    with transaction.atomic():
        lock = _runtime_lock_for_update()
        active_job = _normalize_active_jobs_locked(lock, now=step_started_at)
        locked_job = LeadParsingJob.objects.select_for_update().get(id=job.id)
        now = timezone.now()

        if locked_job.is_step_in_progress and locked_job.last_step_started_at and locked_job.last_step_started_at <= now - STEP_LOCK_STALE_AFTER:
            locked_job.is_step_in_progress = False
            locked_job.retry_state = {}

        if not active_job or active_job.id != locked_job.id:
            if locked_job.is_step_in_progress:
                _set_step_finish(locked_job, started_at=locked_job.last_step_started_at, finished_at=now)
                locked_job.save(update_fields=["is_step_in_progress", "last_step_finished_at", "last_step_duration_ms", "heartbeat_at", "updated_at"])
            return locked_job

        if locked_job.status != LeadParsingJob.Status.RUNNING:
            if locked_job.is_step_in_progress:
                _set_step_finish(locked_job, started_at=locked_job.last_step_started_at, finished_at=now)
                locked_job.save(update_fields=["is_step_in_progress", "last_step_finished_at", "last_step_duration_ms", "heartbeat_at", "updated_at"])
            return locked_job

        if locked_job.request_count >= locked_job.request_limit:
            _finalize_job(locked_job, LeadParsingJob.Status.COMPLETED, finished_at=now)
            _set_step_finish(locked_job, started_at=locked_job.last_step_started_at, finished_at=now)
            locked_job.save()
            _sync_runtime_lock(lock, None)
            return locked_job

        keywords = locked_job.keywords or []
        cities = locked_job.cities or []
        if not keywords or not cities or locked_job.current_city_index >= len(cities):
            _finalize_job(locked_job, LeadParsingJob.Status.COMPLETED, finished_at=now)
            _set_step_finish(locked_job, started_at=locked_job.last_step_started_at, finished_at=now)
            locked_job.save()
            _sync_runtime_lock(lock, None)
            return locked_job

        if locked_job.next_step_not_before and now < locked_job.next_step_not_before:
            return locked_job

        if locked_job.is_step_in_progress:
            return locked_job

        locked_job.is_step_in_progress = True
        locked_job.last_step_started_at = step_started_at
        locked_job.current_query = current_parser_query(locked_job)
        locked_job.heartbeat_at = step_started_at
        locked_job.save(update_fields=["is_step_in_progress", "last_step_started_at", "current_query", "heartbeat_at", "updated_at"])

    request_was_sent = False
    try:
        api_key = get_maps_api_key()
        request_spec = _coerce_request_spec(job=locked_job, api_key=api_key)
        query_state = _get_or_create_query_state(locked_job, request_spec)
        if query_state.status in {LeadParsingQueryState.Status.EXHAUSTED, LeadParsingQueryState.Status.ANOMALY}:
            with transaction.atomic():
                lock = _runtime_lock_for_update()
                locked_job = LeadParsingJob.objects.select_for_update().get(id=job.id)
                locked_query_state = LeadParsingQueryState.objects.select_for_update().get(id=query_state.id)
                updated_job = _apply_query_state_skip(
                    job=locked_job,
                    request_spec=request_spec,
                    query_state=locked_query_state,
                    step_started_at=locked_job.last_step_started_at or step_started_at,
                    step_finished_at=timezone.now(),
                )
                _sync_runtime_lock(lock, updated_job if updated_job.status in ACTIVE_STATUSES else None)
                return updated_job
        query = str(request_spec.get("text_query") or "").strip()
        city = str(request_spec.get("city") or _current_city(locked_job)).strip()
        next_page_token = locked_job.next_page_token or ""
        request_was_sent = True
        places, returned_next_page_token = _places_search_text(
            api_key,
            query,
            city,
            next_page_token,
            request_spec=request_spec,
        )

        with transaction.atomic():
            lock = _runtime_lock_for_update()
            locked_job = LeadParsingJob.objects.select_for_update().get(id=job.id)
            if locked_job.status == LeadParsingJob.Status.STOPPED:
                updated_job = _apply_discarded_request(
                    locked_job,
                    request_spec=request_spec,
                    was_success=True,
                    step_started_at=locked_job.last_step_started_at or step_started_at,
                    step_finished_at=timezone.now(),
                )
            else:
                updated_job = _apply_places_success(
                    job=locked_job,
                    places=places,
                    next_page_token=returned_next_page_token,
                    request_spec=request_spec,
                    step_started_at=locked_job.last_step_started_at or step_started_at,
                    step_finished_at=timezone.now(),
                )
            _sync_runtime_lock(lock, updated_job if updated_job.status in ACTIVE_STATUSES else None)
            return updated_job
    except ParsingServiceError as exc:
        with transaction.atomic():
            lock = _runtime_lock_for_update()
            locked_job = LeadParsingJob.objects.select_for_update().get(id=job.id)
            if request_was_sent:
                if locked_job.status == LeadParsingJob.Status.STOPPED:
                    updated_job = _apply_discarded_request(
                        locked_job,
                        request_spec=request_spec or {},
                        was_success=False,
                        error_message=str(exc),
                        step_started_at=locked_job.last_step_started_at or step_started_at,
                        step_finished_at=timezone.now(),
                    )
                else:
                    updated_job = _apply_step_error(
                        locked_job,
                        request_spec=request_spec or {},
                        error_message=str(exc),
                        step_started_at=locked_job.last_step_started_at or step_started_at,
                        step_finished_at=timezone.now(),
                    )
            else:
                updated_job = _apply_internal_step_error(
                    locked_job,
                    error_message=str(exc),
                    step_started_at=locked_job.last_step_started_at or step_started_at,
                    step_finished_at=timezone.now(),
                )
            _sync_runtime_lock(lock, updated_job if updated_job.status in ACTIVE_STATUSES else None)
            return updated_job
    except Exception as exc:
        with transaction.atomic():
            lock = _runtime_lock_for_update()
            locked_job = LeadParsingJob.objects.select_for_update().get(id=job.id)
            if request_was_sent:
                if locked_job.status == LeadParsingJob.Status.STOPPED:
                    updated_job = _apply_discarded_request(
                        locked_job,
                        request_spec=request_spec or {},
                        was_success=False,
                        error_message=f"Непередбачена помилка парсингу: {exc}",
                        step_started_at=locked_job.last_step_started_at or step_started_at,
                        step_finished_at=timezone.now(),
                    )
                else:
                    updated_job = _apply_step_error(
                        locked_job,
                        request_spec=request_spec or {},
                        error_message=f"Непередбачена помилка парсингу: {exc}",
                        step_started_at=locked_job.last_step_started_at or step_started_at,
                        step_finished_at=timezone.now(),
                    )
            else:
                updated_job = _apply_internal_step_error(
                    locked_job,
                    error_message=f"Непередбачена помилка парсингу: {exc}",
                    step_started_at=locked_job.last_step_started_at or step_started_at,
                    step_finished_at=timezone.now(),
                )
            _sync_runtime_lock(lock, updated_job if updated_job.status in ACTIVE_STATUSES else None)
            return updated_job


def parser_global_counters() -> ParsingCounters:
    moderation = ManagementLead.objects.filter(status=ManagementLead.Status.MODERATION).count()
    base = ManagementLead.objects.filter(status=ManagementLead.Status.BASE).count()
    converted = ManagementLead.objects.filter(status=ManagementLead.Status.CONVERTED).count()
    rejected = ManagementLead.objects.filter(status=ManagementLead.Status.REJECTED).count()
    return ParsingCounters(
        moderation=moderation,
        base=base,
        converted=converted,
        rejected=rejected,
        unprocessed=base,
    )
