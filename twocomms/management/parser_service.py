from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from functools import lru_cache
import os
from typing import Any
from urllib.parse import urlparse

import requests
from django.db import transaction
from django.utils import timezone

from .lead_services import split_terms
from .models import Client, LeadParsingJob, LeadParsingResult, ManagementLead, normalize_phone

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
        "places.rating",
        "places.userRatingCount",
        "places.businessStatus",
        "nextPageToken",
    ]
)

DEFAULT_REQUESTS_PER_MINUTE = 20
MAX_REQUESTS_PER_MINUTE = 30
PAGE_TOKEN_RETRY_LIMIT = 2
TRANSIENT_RETRY_LIMIT = 2
PAGE_TOKEN_DELAY_SECONDS = 2
STEP_LOCK_STALE_AFTER = timedelta(seconds=60)


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


def parse_keywords(raw_keywords: str) -> list[str]:
    return split_terms(raw_keywords)


def parse_cities(raw_cities: str) -> list[str]:
    raw = (raw_cities or "").strip()
    if not raw:
        return []
    if any(sep in raw for sep in ["\n", ",", ";"]):
        return split_terms(raw)
    return [raw]


def sanitize_requests_per_minute(raw_value: int | str | None) -> int:
    try:
        value = int(str(raw_value or DEFAULT_REQUESTS_PER_MINUTE).strip())
    except (TypeError, ValueError):
        value = DEFAULT_REQUESTS_PER_MINUTE
    return max(1, min(value, MAX_REQUESTS_PER_MINUTE))


def current_parser_query(job: LeadParsingJob) -> str:
    keywords = job.keywords or []
    cities = job.cities or []
    if not keywords or not cities or job.current_city_index >= len(cities):
        return ""
    keyword = str(keywords[job.current_keyword_index]).strip()
    city = str(cities[job.current_city_index]).strip()
    return f"{keyword} {city}".strip()


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


@lru_cache(maxsize=256)
def geocode_city_center(city: str, api_key: str) -> dict[str, float] | None:
    params = {"address": city, "key": api_key}
    try:
        resp = requests.get(GEOCODE_URL, params=params, headers=_google_context_headers(), timeout=12)
        if resp.status_code != 200:
            return None
        payload = resp.json() or {}
        if payload.get("status") != "OK":
            return None
        results = payload.get("results") or []
        if not results:
            return None
        location = results[0].get("geometry", {}).get("location", {})
        lat = location.get("lat")
        lng = location.get("lng")
        if lat is None or lng is None:
            return None
        return {"latitude": float(lat), "longitude": float(lng)}
    except requests.RequestException:
        return None


def _places_search_text(api_key: str, text_query: str, city: str, page_token: str = "") -> tuple[list[dict[str, Any]], str]:
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": PLACES_FIELD_MASK,
    }
    headers.update(_google_context_headers())
    body: dict[str, Any] = {
        "textQuery": text_query,
        "languageCode": "uk",
        "pageSize": 20,
    }
    center = geocode_city_center(city, api_key)
    if center:
        body["locationBias"] = {
            "circle": {
                "center": center,
                "radius": 22000.0,
            }
        }
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
    dn = place.get("displayName")
    if isinstance(dn, dict):
        return str(dn.get("text") or "").strip()
    return str(dn or "").strip()


def _place_phone(place: dict[str, Any]) -> str:
    return str(place.get("internationalPhoneNumber") or place.get("nationalPhoneNumber") or "").strip()


def _place_details_blob(place: dict[str, Any]) -> str:
    chunks: list[str] = []
    address = str(place.get("formattedAddress") or "").strip()
    if address:
        chunks.append(f"Адреса: {address}")
    types = place.get("types") or []
    if types:
        chunks.append(f"Types: {', '.join(types)}")
    rating = place.get("rating")
    if rating is not None:
        chunks.append(f"Рейтинг: {rating}")
    rating_count = place.get("userRatingCount")
    if rating_count is not None:
        chunks.append(f"Кількість відгуків: {rating_count}")
    business_status = str(place.get("businessStatus") or "").strip()
    if business_status:
        chunks.append(f"Business status: {business_status}")
    maps_uri = str(place.get("googleMapsUri") or "").strip()
    if maps_uri:
        chunks.append(f"Google Maps: {maps_uri}")
    return "\n".join(chunks)


def _advance_position(job: LeadParsingJob) -> bool:
    keywords = job.keywords or []
    cities = job.cities or []
    if not keywords or not cities:
        return False
    if job.current_keyword_index + 1 < len(keywords):
        job.current_keyword_index += 1
        return True
    job.current_keyword_index = 0
    job.current_city_index += 1
    return job.current_city_index < len(cities)


def _finalize_job(job: LeadParsingJob, status: str):
    job.status = status
    job.next_step_not_before = None
    job.retry_state = {}
    if status in {LeadParsingJob.Status.COMPLETED, LeadParsingJob.Status.STOPPED, LeadParsingJob.Status.FAILED}:
        job.finished_at = timezone.now()


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
    if started_at:
        job.last_step_duration_ms = max(0, int((finished_at - started_at).total_seconds() * 1000))
    else:
        job.last_step_duration_ms = 0


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
        reason=reason,
        reason_code=reason_code,
        payload=payload or {},
    )


def _parser_duplicate_state(job: LeadParsingJob, phone_normalized: str, place_id: str) -> ParserDuplicateDecision:
    if place_id and LeadParsingResult.objects.filter(job=job, place_id=place_id).exists():
        return ParserDuplicateDecision(
            state="job_place",
            reason="Повторний Place ID у поточному парсингу",
            reason_code="duplicate_job_place",
        )

    if phone_normalized and LeadParsingResult.objects.filter(job=job, phone=phone_normalized).exists():
        return ParserDuplicateDecision(
            state="job_phone",
            reason="Повторний номер у поточному парсингу",
            reason_code="duplicate_job_phone",
        )

    if not phone_normalized:
        return ParserDuplicateDecision()

    if Client.objects.filter(phone_normalized=phone_normalized).exists():
        return ParserDuplicateDecision(
            state="existing_client",
            reason="Номер вже є у клієнтах",
            reason_code="duplicate_existing_client",
        )

    active_lead_qs = ManagementLead.objects.filter(phone_normalized=phone_normalized).exclude(status=ManagementLead.Status.REJECTED)
    if active_lead_qs.exists():
        return ParserDuplicateDecision(
            state="existing_lead",
            reason="Номер вже є у лідах або вже оброблявся",
            reason_code="duplicate_existing_lead",
        )

    if ManagementLead.objects.filter(phone_normalized=phone_normalized, status=ManagementLead.Status.REJECTED).exists():
        return ParserDuplicateDecision(
            state="rejected_history",
            reason="Номер вже відхиляли раніше",
            reason_code="duplicate_rejected_history",
            result_status=LeadParsingResult.ResultStatus.REJECTED,
        )

    return ParserDuplicateDecision()


def _apply_duplicate_counters(job: LeadParsingJob, decision: ParserDuplicateDecision):
    if decision.state == "job_place":
        job.duplicate_skipped += 1
        job.duplicate_same_job_place_skipped += 1
    elif decision.state == "job_phone":
        job.duplicate_skipped += 1
        job.duplicate_same_job_phone_skipped += 1
    elif decision.state == "existing_client":
        job.duplicate_skipped += 1
        job.duplicate_existing_client_skipped += 1
    elif decision.state == "existing_lead":
        job.duplicate_skipped += 1
        job.duplicate_existing_lead_skipped += 1
    elif decision.state == "rejected_history":
        job.already_rejected_skipped += 1


def _apply_places_success(
    *,
    job: LeadParsingJob,
    places: list[dict[str, Any]],
    next_page_token: str,
    step_started_at,
    step_finished_at,
) -> LeadParsingJob:
    keyword = str((job.keywords or [])[job.current_keyword_index]).strip()
    city = str((job.cities or [])[job.current_city_index]).strip()
    query = current_parser_query(job)

    job.request_count += 1
    job.request_success_count += 1
    job.last_error = ""
    job.retry_state = {}
    job.current_query = query

    for place in places:
        place_id = str(place.get("id") or "").strip()
        place_name = _place_display_name(place)
        raw_phone = _place_phone(place)
        phone_normalized = normalize_phone(raw_phone)
        website_url = str(place.get("websiteUri") or "").strip()
        maps_url = str(place.get("googleMapsUri") or "").strip()
        job.total_found += 1

        if not phone_normalized:
            if place_id and LeadParsingResult.objects.filter(job=job, place_id=place_id).exists():
                decision = ParserDuplicateDecision(
                    state="job_place",
                    reason="Повторний Place ID у поточному парсингу",
                    reason_code="duplicate_job_place",
                )
                _apply_duplicate_counters(job, decision)
                _create_result(
                    job=job,
                    keyword=keyword,
                    city=city,
                    query=query,
                    status=LeadParsingResult.ResultStatus.DUPLICATE,
                    reason=decision.reason,
                    reason_code=decision.reason_code,
                    place_id=place_id,
                    place_name=place_name,
                    phone=raw_phone,
                    website_url=website_url,
                    maps_url=maps_url,
                    payload=place,
                )
                continue

            job.no_phone_skipped += 1
            _create_result(
                job=job,
                keyword=keyword,
                city=city,
                query=query,
                status=LeadParsingResult.ResultStatus.NO_PHONE,
                reason="Контактний номер не знайдено",
                reason_code="missing_phone",
                place_id=place_id,
                place_name=place_name,
                phone=raw_phone,
                website_url=website_url,
                maps_url=maps_url,
                payload=place,
            )
            continue

        decision = _parser_duplicate_state(job, phone_normalized, place_id)
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
                place_id=place_id,
                place_name=place_name,
                phone=phone_normalized,
                website_url=website_url,
                maps_url=maps_url,
                payload=place,
            )
            continue

        lead = ManagementLead.objects.create(
            shop_name=place_name or f"{keyword} / {city}",
            phone=phone_normalized,
            full_name="",
            role=Client.Role.OTHER,
            source="Google Карти",
            website_url=website_url,
            city=city,
            parser_keyword=keyword,
            parser_query=query,
            google_place_id=place_id,
            google_maps_url=maps_url,
            details=_place_details_blob(place),
            comments="Парсинг з Google Карт",
            extra_data=place,
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
            place_id=place_id,
            place_name=lead.shop_name,
            phone=lead.phone,
            website_url=lead.website_url,
            maps_url=lead.google_maps_url,
            payload=place,
        )

    if job.status in {LeadParsingJob.Status.RUNNING, LeadParsingJob.Status.PAUSED}:
        job.next_page_token = next_page_token or ""
        has_next = True
        if not job.next_page_token:
            has_next = _advance_position(job)
        if job.status == LeadParsingJob.Status.RUNNING and (not has_next or job.request_count >= job.request_limit):
            job.next_page_token = ""
            _finalize_job(job, LeadParsingJob.Status.COMPLETED)
        elif job.status == LeadParsingJob.Status.RUNNING:
            delay = _rate_interval(job)
            if job.next_page_token:
                delay = max(delay, timedelta(seconds=PAGE_TOKEN_DELAY_SECONDS))
            job.next_step_not_before = step_finished_at + delay
        else:
            job.next_step_not_before = None
    elif job.status == LeadParsingJob.Status.STOPPED:
        job.next_page_token = ""
        job.next_step_not_before = None

    _set_step_finish(job, started_at=step_started_at, finished_at=step_finished_at)
    job.save()
    return job


def _apply_step_error(job: LeadParsingJob, *, error_message: str, step_started_at, step_finished_at) -> LeadParsingJob:
    keyword = str((job.keywords or [])[job.current_keyword_index]).strip() if job.keywords else ""
    city = str((job.cities or [])[job.current_city_index]).strip() if job.cities and job.current_city_index < len(job.cities) else ""
    query = current_parser_query(job)

    job.request_count += 1
    job.request_error_count += 1
    job.current_query = query
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
            phone="",
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
        if job.status == LeadParsingJob.Status.RUNNING:
            has_next = _advance_position(job)
            if not has_next or job.request_count >= job.request_limit:
                _finalize_job(job, LeadParsingJob.Status.COMPLETED)
            else:
                job.next_step_not_before = step_finished_at + _rate_interval(job)
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
            _finalize_job(job, LeadParsingJob.Status.FAILED)

    _set_step_finish(job, started_at=step_started_at, finished_at=step_finished_at)
    job.save()
    return job


def create_parsing_job(
    *,
    user,
    keywords_raw: str,
    cities_raw: str,
    request_limit: int,
    requests_per_minute: int | str | None = DEFAULT_REQUESTS_PER_MINUTE,
) -> LeadParsingJob:
    keywords = parse_keywords(keywords_raw)
    cities = parse_cities(cities_raw)
    if not keywords:
        raise ParsingServiceError("Вкажіть хоча б одне ключове слово.")
    if not cities:
        raise ParsingServiceError("Вкажіть хоча б одне місто.")
    if request_limit < 1:
        raise ParsingServiceError("Ліміт запитів має бути >= 1.")
    if LeadParsingJob.objects.filter(status__in=[LeadParsingJob.Status.RUNNING, LeadParsingJob.Status.PAUSED]).exists():
        raise ParsingServiceError("Вже є активна сесія парсингу. Зупиніть або відновіть її перед новим запуском.")

    return LeadParsingJob.objects.create(
        created_by=user,
        status=LeadParsingJob.Status.RUNNING,
        keywords_raw=keywords_raw,
        cities_raw=cities_raw,
        keywords=keywords,
        cities=cities,
        request_limit=min(request_limit, 5000),
        requests_per_minute=sanitize_requests_per_minute(requests_per_minute),
    )


def parser_run_step(job: LeadParsingJob) -> LeadParsingJob:
    step_started_at = timezone.now()

    with transaction.atomic():
        locked_job = LeadParsingJob.objects.select_for_update().get(id=job.id)
        now = timezone.now()

        if locked_job.is_step_in_progress and locked_job.last_step_started_at and locked_job.last_step_started_at <= now - STEP_LOCK_STALE_AFTER:
            locked_job.is_step_in_progress = False
            locked_job.retry_state = {}

        if locked_job.status != LeadParsingJob.Status.RUNNING:
            if locked_job.is_step_in_progress:
                _set_step_finish(locked_job, started_at=locked_job.last_step_started_at, finished_at=now)
                locked_job.save(update_fields=["is_step_in_progress", "last_step_finished_at", "last_step_duration_ms", "updated_at"])
            return locked_job

        if locked_job.request_count >= locked_job.request_limit:
            _finalize_job(locked_job, LeadParsingJob.Status.COMPLETED)
            _set_step_finish(locked_job, started_at=locked_job.last_step_started_at, finished_at=now)
            locked_job.save()
            return locked_job

        keywords = locked_job.keywords or []
        cities = locked_job.cities or []
        if not keywords or not cities or locked_job.current_city_index >= len(cities):
            _finalize_job(locked_job, LeadParsingJob.Status.COMPLETED)
            _set_step_finish(locked_job, started_at=locked_job.last_step_started_at, finished_at=now)
            locked_job.save()
            return locked_job

        if locked_job.next_step_not_before and now < locked_job.next_step_not_before:
            return locked_job

        if not locked_job.is_step_in_progress:
            locked_job.is_step_in_progress = True
            locked_job.last_step_started_at = step_started_at

        locked_job.current_query = current_parser_query(locked_job)
        locked_job.save(update_fields=["is_step_in_progress", "last_step_started_at", "current_query", "updated_at"])

        query = locked_job.current_query
        city = str(cities[locked_job.current_city_index]).strip()
        next_page_token = locked_job.next_page_token or ""

    try:
        api_key = get_maps_api_key()
        places, returned_next_page_token = _places_search_text(api_key, query, city, next_page_token)

        with transaction.atomic():
            locked_job = LeadParsingJob.objects.select_for_update().get(id=job.id)
            return _apply_places_success(
                job=locked_job,
                places=places,
                next_page_token=returned_next_page_token,
                step_started_at=locked_job.last_step_started_at or step_started_at,
                step_finished_at=timezone.now(),
            )
    except ParsingServiceError as exc:
        with transaction.atomic():
            locked_job = LeadParsingJob.objects.select_for_update().get(id=job.id)
            return _apply_step_error(
                locked_job,
                error_message=str(exc),
                step_started_at=locked_job.last_step_started_at or step_started_at,
                step_finished_at=timezone.now(),
            )
    except Exception as exc:
        with transaction.atomic():
            locked_job = LeadParsingJob.objects.select_for_update().get(id=job.id)
            return _apply_step_error(
                locked_job,
                error_message=f"Непередбачена помилка парсингу: {exc}",
                step_started_at=locked_job.last_step_started_at or step_started_at,
                step_finished_at=timezone.now(),
            )


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
