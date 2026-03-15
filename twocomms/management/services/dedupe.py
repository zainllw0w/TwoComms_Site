from dataclasses import dataclass
import re
from urllib.parse import urlsplit

from django.utils import timezone

from management.models import (
    Client,
    DuplicateReview,
    ManagementLead,
    build_phone_last7,
    normalize_name_for_match,
    normalize_phone,
)
from .client_entry import candidate_owner_display


class DedupeZone:
    AUTO_BLOCK = "auto_block"
    REVIEW = "review"
    SUGGESTION = "suggestion"
    CLEAR = "clear"


@dataclass
class DedupeDecision:
    zone: str
    candidates: list[dict]


PARTIAL_PHONE_MATCH_SCORE = 0.2


def _candidate_score(*, name_match_score: float, phone_match_score: float, owner_match_score: float, source_link_score: float) -> float:
    return (
        0.45 * name_match_score
        + 0.35 * phone_match_score
        + 0.10 * owner_match_score
        + 0.10 * source_link_score
    )


def normalize_website_for_match(raw_url: str) -> str:
    value = (raw_url or "").strip().lower()
    if not value:
        return ""
    parsed = urlsplit(value if "://" in value else f"https://{value}")
    host = (parsed.netloc or parsed.path).lower()
    path = parsed.path if parsed.netloc else ""
    path = re.sub(r"/+$", "", path or "")
    if host.startswith("www."):
        host = host[4:]
    combined = f"{host}{path}"
    return combined.strip("/")


def _format_dt(dt_value) -> str:
    if not dt_value:
        return "—"
    try:
        return timezone.localtime(dt_value).strftime("%d.%m.%Y %H:%M")
    except Exception:
        return "—"


def _client_candidate_payload(client: Client, *, score: float, exact_phone: bool, is_shared_phone: bool) -> dict:
    return {
        "kind": "client",
        "id": client.id,
        "shop_name": client.shop_name,
        "phone": client.phone,
        "website_url": client.website_url or "",
        "score": round(score, 4),
        "is_shared_phone": bool(is_shared_phone),
        "exact_phone": bool(exact_phone),
        "owner_display": candidate_owner_display(client.owner),
        "created_at_display": _format_dt(client.created_at),
        "last_contact_display": _format_dt(client.updated_at or client.created_at),
        "last_result_display": client.get_call_result_display(),
        "verdict_display": client.call_result_details or client.get_call_result_display(),
        "next_call_display": _format_dt(client.next_call_at),
    }


def _lead_candidate_payload(lead: ManagementLead, *, score: float, exact_phone: bool, is_shared_phone: bool) -> dict:
    return {
        "kind": "lead",
        "id": lead.id,
        "shop_name": lead.shop_name,
        "phone": lead.phone,
        "website_url": lead.website_url or "",
        "score": round(score, 4),
        "is_shared_phone": bool(is_shared_phone),
        "exact_phone": bool(exact_phone),
        "owner_display": candidate_owner_display(lead.added_by),
        "created_at_display": _format_dt(lead.created_at),
        "last_contact_display": _format_dt(lead.updated_at or lead.created_at),
        "last_result_display": lead.get_status_display(),
        "verdict_display": lead.rejection_reason or lead.comments or lead.get_status_display(),
        "next_call_display": "—",
    }


def _collect_candidates(
    *,
    shop_name: str,
    phone: str,
    website_url: str,
    owner,
    exclude_client_ids: list[int] | None = None,
    exclude_lead_ids: list[int] | None = None,
) -> list[dict]:
    phone_normalized = normalize_phone(phone)
    phone_last7 = build_phone_last7(phone_normalized or phone)
    name_key = normalize_name_for_match(shop_name)
    website_key = normalize_website_for_match(website_url)
    candidates: list[dict] = []
    exclude_client_ids = exclude_client_ids or []
    exclude_lead_ids = exclude_lead_ids or []

    for client in Client.objects.exclude(id__in=exclude_client_ids).select_related("owner"):
        name_score = 1.0 if client.normalized_name_match_key and client.normalized_name_match_key == name_key else 0.0
        phone_score = (
            1.0
            if client.phone_normalized and client.phone_normalized == phone_normalized
            else PARTIAL_PHONE_MATCH_SCORE if client.phone_last7 and client.phone_last7 == phone_last7 else 0.0
        )
        owner_score = 1.0 if owner and client.owner_id == getattr(owner, "id", None) else 0.0
        source_score = 1.0 if website_key and normalize_website_for_match(client.website_url) == website_key else 0.0
        score = _candidate_score(
            name_match_score=name_score,
            phone_match_score=phone_score,
            owner_match_score=owner_score,
            source_link_score=source_score,
        )
        if score <= 0:
            continue
        candidates.append(_client_candidate_payload(
            client,
            score=score,
            is_shared_phone=bool(client.is_shared_phone),
            exact_phone=bool(client.phone_normalized and client.phone_normalized == phone_normalized),
        ))

    for lead in (
        ManagementLead.objects.exclude(status=ManagementLead.Status.REJECTED)
        .exclude(id__in=exclude_lead_ids)
        .select_related("added_by")
    ):
        name_score = 1.0 if lead.normalized_name_match_key and lead.normalized_name_match_key == name_key else 0.0
        phone_score = (
            1.0
            if lead.phone_normalized and lead.phone_normalized == phone_normalized
            else PARTIAL_PHONE_MATCH_SCORE if lead.phone_last7 and lead.phone_last7 == phone_last7 else 0.0
        )
        owner_score = 1.0 if owner and lead.added_by_id == getattr(owner, "id", None) else 0.0
        source_score = 1.0 if website_key and normalize_website_for_match(lead.website_url) == website_key else 0.0
        score = _candidate_score(
            name_match_score=name_score,
            phone_match_score=phone_score,
            owner_match_score=owner_score,
            source_link_score=source_score,
        )
        if score <= 0:
            continue
        candidates.append(_lead_candidate_payload(
            lead,
            score=score,
            is_shared_phone=bool(lead.is_shared_phone),
            exact_phone=bool(lead.phone_normalized and lead.phone_normalized == phone_normalized),
        ))

    candidates.sort(key=lambda item: (item["exact_phone"], item["score"]), reverse=True)
    return candidates


def evaluate_duplicate_zone(
    *,
    shop_name: str,
    phone: str,
    website_url: str,
    owner,
    exclude_client_ids: list[int] | None = None,
    exclude_lead_ids: list[int] | None = None,
) -> DedupeDecision:
    candidates = _collect_candidates(
        shop_name=shop_name,
        phone=phone,
        website_url=website_url,
        owner=owner,
        exclude_client_ids=exclude_client_ids,
        exclude_lead_ids=exclude_lead_ids,
    )
    if not candidates:
        return DedupeDecision(zone=DedupeZone.CLEAR, candidates=[])

    strongest = candidates[0]
    if strongest["exact_phone"]:
        zone = DedupeZone.REVIEW if strongest["is_shared_phone"] else DedupeZone.AUTO_BLOCK
    elif strongest["score"] >= 0.75:
        zone = DedupeZone.REVIEW
    elif strongest["score"] >= 0.45:
        zone = DedupeZone.SUGGESTION
    else:
        zone = DedupeZone.CLEAR
    return DedupeDecision(zone=zone, candidates=candidates[:5])


def create_duplicate_review(*, owner, zone: str, shop_name: str, phone: str, payload: dict, candidates: list[dict]) -> DuplicateReview:
    return DuplicateReview.objects.create(
        owner=owner,
        zone=zone,
        incoming_shop_name=shop_name,
        incoming_phone=phone,
        incoming_payload=payload,
        candidate_summary=candidates,
    )


def resolve_duplicate_review_override(
    *,
    owner,
    decision: DedupeDecision,
    shop_name: str,
    phone: str,
    payload: dict,
    override_reason: str,
) -> DuplicateReview:
    review = create_duplicate_review(
        owner=owner,
        zone=decision.zone,
        shop_name=shop_name,
        phone=phone,
        payload={
            **payload,
            "override_reason": override_reason,
        },
        candidates=decision.candidates,
    )
    review.status = DuplicateReview.Status.RESOLVED
    review.resolution_note = override_reason
    review.resolved_by = owner
    review.resolved_at = timezone.now()
    review.save(update_fields=["status", "resolution_note", "resolved_by", "resolved_at"])
    return review


def build_duplicate_conflict_payload(
    *,
    owner,
    decision: DedupeDecision,
    shop_name: str,
    phone: str,
    payload: dict,
    auto_block_error: str,
    review_error: str,
) -> dict:
    duplicate_review = None
    if decision.zone == DedupeZone.REVIEW:
        duplicate_review = create_duplicate_review(
            owner=owner,
            zone=decision.zone,
            shop_name=shop_name,
            phone=phone,
            payload=payload,
            candidates=decision.candidates,
        )
    return {
        "success": False,
        "error": auto_block_error if decision.zone == DedupeZone.AUTO_BLOCK else review_error,
        "zone": decision.zone,
        "candidates": decision.candidates,
        "duplicate_review_id": duplicate_review.id if duplicate_review else None,
    }


def build_duplicate_preview_payload(*, decision: DedupeDecision) -> dict:
    return {
        "success": True,
        "zone": decision.zone,
        "has_warning": decision.zone != DedupeZone.CLEAR,
        "candidates": decision.candidates,
    }
