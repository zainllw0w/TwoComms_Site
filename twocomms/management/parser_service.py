from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import os
from typing import Any
from urllib.parse import urlparse

import requests
from django.db.models import Q
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


class ParsingServiceError(Exception):
    pass


@dataclass(slots=True)
class ParsingCounters:
    moderation: int
    base: int
    converted: int
    rejected: int
    unprocessed: int


def parse_keywords(raw_keywords: str) -> list[str]:
    return split_terms(raw_keywords)


def parse_cities(raw_cities: str) -> list[str]:
    raw = (raw_cities or "").strip()
    if not raw:
        return []
    if any(sep in raw for sep in ["\n", ",", ";"]):
        return split_terms(raw)
    return [raw]


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


def _duplicate_state(phone_normalized: str, place_id: str) -> str | None:
    lead_qs = ManagementLead.objects.all()
    query = Q()
    if phone_normalized:
        query |= Q(phone_normalized=phone_normalized)
    if place_id:
        query |= Q(google_place_id=place_id)
    if query:
        lead_qs = lead_qs.filter(query)
    else:
        lead_qs = lead_qs.none()

    if lead_qs.filter(status=ManagementLead.Status.REJECTED).exists():
        return "rejected"
    if lead_qs.exists():
        return "duplicate"
    if phone_normalized and Client.objects.filter(phone_normalized=phone_normalized).exists():
        return "duplicate"
    return None


def create_parsing_job(*, user, keywords_raw: str, cities_raw: str, request_limit: int) -> LeadParsingJob:
    keywords = parse_keywords(keywords_raw)
    cities = parse_cities(cities_raw)
    if not keywords:
        raise ParsingServiceError("Вкажіть хоча б одне ключове слово.")
    if not cities:
        raise ParsingServiceError("Вкажіть хоча б одне місто.")
    if request_limit < 1:
        raise ParsingServiceError("Ліміт запитів має бути >= 1.")

    return LeadParsingJob.objects.create(
        created_by=user,
        status=LeadParsingJob.Status.RUNNING,
        keywords_raw=keywords_raw,
        cities_raw=cities_raw,
        keywords=keywords,
        cities=cities,
        request_limit=min(request_limit, 5000),
    )


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
    if status in {LeadParsingJob.Status.COMPLETED, LeadParsingJob.Status.STOPPED, LeadParsingJob.Status.FAILED}:
        job.finished_at = timezone.now()


def parser_run_step(job: LeadParsingJob) -> LeadParsingJob:
    if job.status != LeadParsingJob.Status.RUNNING:
        return job

    if job.request_count >= job.request_limit:
        _finalize_job(job, LeadParsingJob.Status.COMPLETED)
        job.save(update_fields=["status", "finished_at", "updated_at"])
        return job

    keywords = job.keywords or []
    cities = job.cities or []
    if not keywords or not cities or job.current_city_index >= len(cities):
        _finalize_job(job, LeadParsingJob.Status.COMPLETED)
        job.save(update_fields=["status", "finished_at", "updated_at"])
        return job

    keyword = str(keywords[job.current_keyword_index]).strip()
    city = str(cities[job.current_city_index]).strip()
    query = f"{keyword} {city}".strip()
    job.current_query = query

    try:
        api_key = get_maps_api_key()
        places, next_page_token = _places_search_text(api_key, query, city, job.next_page_token or "")
    except ParsingServiceError as exc:
        if job.next_page_token and "page token" in str(exc).lower():
            job.last_error = str(exc)
            job.save(update_fields=["last_error", "updated_at"])
            return job
        job.last_error = str(exc)
        _finalize_job(job, LeadParsingJob.Status.FAILED)
        job.save(update_fields=["status", "last_error", "finished_at", "updated_at", "current_query", "next_page_token"])
        return job

    for place in places:
        place_id = str(place.get("id") or "").strip()
        place_name = _place_display_name(place)
        phone = _place_phone(place)
        phone_normalized = normalize_phone(phone)
        website_url = str(place.get("websiteUri") or "").strip()
        maps_url = str(place.get("googleMapsUri") or "").strip()
        job.total_found += 1

        if not phone_normalized:
            job.no_phone_skipped += 1
            LeadParsingResult.objects.create(
                job=job,
                keyword=keyword,
                city=city,
                query=query,
                place_id=place_id,
                place_name=place_name,
                phone=phone,
                website_url=website_url,
                maps_url=maps_url,
                status=LeadParsingResult.ResultStatus.NO_PHONE,
                reason="Контактний номер не знайдено",
                payload=place,
            )
            continue

        duplicate_state = _duplicate_state(phone_normalized, place_id)
        if duplicate_state == "rejected":
            job.already_rejected_skipped += 1
            LeadParsingResult.objects.create(
                job=job,
                keyword=keyword,
                city=city,
                query=query,
                place_id=place_id,
                place_name=place_name,
                phone=phone_normalized,
                website_url=website_url,
                maps_url=maps_url,
                status=LeadParsingResult.ResultStatus.REJECTED,
                reason="Вже відхилено раніше",
                payload=place,
            )
            continue
        if duplicate_state == "duplicate":
            job.duplicate_skipped += 1
            LeadParsingResult.objects.create(
                job=job,
                keyword=keyword,
                city=city,
                query=query,
                place_id=place_id,
                place_name=place_name,
                phone=phone_normalized,
                website_url=website_url,
                maps_url=maps_url,
                status=LeadParsingResult.ResultStatus.DUPLICATE,
                reason="Дубль у базі/модерації/клієнтах",
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
        )
        job.added_to_moderation += 1
        LeadParsingResult.objects.create(
            job=job,
            lead=lead,
            keyword=keyword,
            city=city,
            query=query,
            place_id=place_id,
            place_name=lead.shop_name,
            phone=lead.phone,
            website_url=lead.website_url,
            maps_url=lead.google_maps_url,
            status=LeadParsingResult.ResultStatus.ADDED,
            reason="Успішно додано в модерацію",
            payload=place,
        )

    job.last_error = ""
    job.request_count += 1
    job.next_page_token = next_page_token or ""
    has_next = True
    if not job.next_page_token:
        has_next = _advance_position(job)
    if not has_next or job.request_count >= job.request_limit:
        job.next_page_token = ""
        _finalize_job(job, LeadParsingJob.Status.COMPLETED)
    job.save()
    return job


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
