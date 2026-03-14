from dataclasses import dataclass

from management.models import (
    Client,
    DuplicateReview,
    ManagementLead,
    build_phone_last7,
    normalize_name_for_match,
    normalize_phone,
)


class DedupeZone:
    AUTO_BLOCK = "auto_block"
    REVIEW = "review"
    SUGGESTION = "suggestion"
    CLEAR = "clear"


@dataclass
class DedupeDecision:
    zone: str
    candidates: list[dict]


def _candidate_score(*, name_match_score: float, phone_match_score: float, owner_match_score: float, source_link_score: float) -> float:
    return (
        0.45 * name_match_score
        + 0.35 * phone_match_score
        + 0.10 * owner_match_score
        + 0.10 * source_link_score
    )


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
    candidates: list[dict] = []
    exclude_client_ids = exclude_client_ids or []
    exclude_lead_ids = exclude_lead_ids or []

    for client in Client.objects.exclude(id__in=exclude_client_ids).select_related("owner"):
        name_score = 1.0 if client.normalized_name_match_key and client.normalized_name_match_key == name_key else 0.0
        phone_score = 1.0 if client.phone_normalized and client.phone_normalized == phone_normalized else 0.75 if client.phone_last7 and client.phone_last7 == phone_last7 else 0.0
        owner_score = 1.0 if owner and client.owner_id == getattr(owner, "id", None) else 0.0
        source_score = 1.0 if website_url and client.website_url and client.website_url.strip() == website_url.strip() else 0.0
        score = _candidate_score(
            name_match_score=name_score,
            phone_match_score=phone_score,
            owner_match_score=owner_score,
            source_link_score=source_score,
        )
        if score <= 0:
            continue
        candidates.append(
            {
                "kind": "client",
                "id": client.id,
                "shop_name": client.shop_name,
                "phone": client.phone,
                "score": round(score, 4),
                "is_shared_phone": bool(client.is_shared_phone),
                "exact_phone": bool(client.phone_normalized and client.phone_normalized == phone_normalized),
            }
        )

    for lead in (
        ManagementLead.objects.exclude(status=ManagementLead.Status.REJECTED)
        .exclude(id__in=exclude_lead_ids)
        .select_related("added_by")
    ):
        name_score = 1.0 if lead.normalized_name_match_key and lead.normalized_name_match_key == name_key else 0.0
        phone_score = 1.0 if lead.phone_normalized and lead.phone_normalized == phone_normalized else 0.75 if lead.phone_last7 and lead.phone_last7 == phone_last7 else 0.0
        owner_score = 1.0 if owner and lead.added_by_id == getattr(owner, "id", None) else 0.0
        source_score = 1.0 if website_url and lead.website_url and lead.website_url.strip() == website_url.strip() else 0.0
        score = _candidate_score(
            name_match_score=name_score,
            phone_match_score=phone_score,
            owner_match_score=owner_score,
            source_link_score=source_score,
        )
        if score <= 0:
            continue
        candidates.append(
            {
                "kind": "lead",
                "id": lead.id,
                "shop_name": lead.shop_name,
                "phone": lead.phone,
                "score": round(score, 4),
                "is_shared_phone": bool(lead.is_shared_phone),
                "exact_phone": bool(lead.phone_normalized and lead.phone_normalized == phone_normalized),
            }
        )

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
