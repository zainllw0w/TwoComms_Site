from __future__ import annotations

from datetime import timedelta
from math import floor
from typing import Any

from django.db.models import Case, F, IntegerField, Q, Sum, Value, When
from django.utils import timezone

from management.constants import POINTS as LEGACY_POINTS
from management.models import Client, ClientInteractionAttempt, ManagementLead
from management.services.outcomes import RESULTS_REQUIRING_REASON


VISIBLE_POINTS_POLICY_VERSION = "visible-points-v2"

BASE_OUTCOME_POINTS = {
    Client.CallResult.NO_ANSWER: 1,
    Client.CallResult.INVALID_NUMBER: 2,
    Client.CallResult.NOT_INTERESTED: 2,
    Client.CallResult.EXPENSIVE: 2,
    Client.CallResult.OTHER: 2,
    Client.CallResult.WROTE_IG: 2,
    Client.CallResult.THINKING: 3,
    Client.CallResult.SENT_MESSENGER: 4,
    Client.CallResult.SENT_EMAIL: 5,
    Client.CallResult.XML_CONNECTED: 8,
    Client.CallResult.WAITING_PREPAYMENT: 10,
    Client.CallResult.WAITING_PAYMENT: 12,
    Client.CallResult.TEST_BATCH: 20,
    Client.CallResult.ORDER: 32,
}

EARLY_MID_FUNNEL_RESULTS = {
    Client.CallResult.NO_ANSWER,
    Client.CallResult.INVALID_NUMBER,
    Client.CallResult.NOT_INTERESTED,
    Client.CallResult.EXPENSIVE,
    Client.CallResult.OTHER,
    Client.CallResult.WROTE_IG,
    Client.CallResult.THINKING,
    Client.CallResult.SENT_MESSENGER,
    Client.CallResult.SENT_EMAIL,
}

PROGRESS_RESULTS = {
    Client.CallResult.XML_CONNECTED,
    Client.CallResult.WAITING_PREPAYMENT,
    Client.CallResult.WAITING_PAYMENT,
}

CONVERSION_RESULTS = {
    Client.CallResult.TEST_BATCH,
    Client.CallResult.ORDER,
}

PROMISE_RESULTS = {
    Client.CallResult.THINKING,
    Client.CallResult.WAITING_PREPAYMENT,
    Client.CallResult.WAITING_PAYMENT,
    Client.CallResult.TEST_BATCH,
}

NEGATIVE_RESULTS_CAP_TO_ONE_WITHOUT_CONTEXT = {
    Client.CallResult.INVALID_NUMBER,
    Client.CallResult.NOT_INTERESTED,
    Client.CallResult.EXPENSIVE,
    Client.CallResult.OTHER,
}

CHEAP_REPEAT_RESULTS = EARLY_MID_FUNNEL_RESULTS

DAILY_CAPS = {
    Client.CallResult.NO_ANSWER: 6,
    Client.CallResult.WROTE_IG: 12,
}

THINKING_NO_FOLLOWUP_CAP = 15
PROMISE_NARROW_WINDOW_HOURS = 72
DETAIL_TEXT_MIN_LEN = 8


def legacy_points_value_for_result(call_result: str) -> int:
    return int(LEGACY_POINTS.get(call_result, 0))


def client_visible_points_value(client: Client) -> int:
    if client.points_override is not None:
        return int(client.points_override)
    context = client.call_result_context or {}
    if context.get("points_policy_version") == VISIBLE_POINTS_POLICY_VERSION:
        return compute_visible_points(client)
    return legacy_points_value_for_result(client.call_result)


def visible_points_sum_expr() -> Sum:
    legacy_case = Case(
        *[When(call_result=key, then=Value(int(value))) for key, value in LEGACY_POINTS.items()],
        default=Value(0),
        output_field=IntegerField(),
    )
    return Sum(
        Case(
            When(points_override__isnull=False, then=F("points_override")),
            When(call_result_context__points_policy_version=VISIBLE_POINTS_POLICY_VERSION, then=Value(0)),
            default=legacy_case,
            output_field=IntegerField(),
        )
    )


def classify_points_source_bucket(client: Client, *, source_lead: ManagementLead | None = None) -> str:
    lead = source_lead or _resolve_source_lead(client)
    if lead and lead.lead_source == ManagementLead.LeadSource.PARSER:
        return "parser_assigned_base"
    return "manual_origin"


def compute_visible_points(
    client: Client,
    interaction: ClientInteractionAttempt | None = None,
    *,
    source_lead: ManagementLead | None = None,
) -> int:
    return int(build_visible_points_breakdown(client, interaction=interaction, source_lead=source_lead)["final_points"])


def build_visible_points_breakdown(
    client: Client,
    interaction: ClientInteractionAttempt | None = None,
    *,
    source_lead: ManagementLead | None = None,
) -> dict[str, Any]:
    interaction = interaction or _latest_interaction(client)
    context = client.call_result_context or {}
    call_result = str(client.call_result or "")
    source_bucket = classify_points_source_bucket(client, source_lead=source_lead)
    flags: list[str] = []

    base_points = int(BASE_OUTCOME_POINTS.get(call_result, 0))
    has_evidence = _has_linked_evidence(client, interaction)
    has_next_step = bool(client.next_call_at)
    has_meaningful_detail = _has_meaningful_detail(client, interaction)

    structure_bonus = 0
    if call_result in RESULTS_REQUIRING_REASON:
        if (interaction.reason_code if interaction else "") or client.call_result_reason_code:
            structure_bonus += 1
    elif has_evidence or has_next_step or has_meaningful_detail:
        structure_bonus += 1

    if has_meaningful_detail:
        structure_bonus += 1

    evidence_bonus = 0
    if call_result not in CONVERSION_RESULTS and has_evidence:
        evidence_bonus = 2

    next_step_bonus = 0
    if has_next_step:
        if call_result in PROMISE_RESULTS and _is_narrow_window_followup(client, interaction):
            next_step_bonus = 4
        else:
            next_step_bonus = 2

    source_weight = _source_weight_for(call_result, source_bucket)
    repeat_multiplier = _repeat_multiplier(client)
    if repeat_multiplier < 1.0:
        flags.append("repeat_decay")
    if repeat_multiplier == 0.0:
        flags.append("repeat_exhausted")

    abuse_multiplier = 0.5 if _has_duplicate_override(client, interaction) else 1.0
    if abuse_multiplier < 1.0:
        flags.append("duplicate_override_penalty")

    raw_points = floor((base_points + structure_bonus + evidence_bonus + next_step_bonus) * source_weight * repeat_multiplier * abuse_multiplier)
    raw_points = max(0, int(raw_points))

    negative_cap_triggered = False
    if call_result in NEGATIVE_RESULTS_CAP_TO_ONE_WITHOUT_CONTEXT:
        has_reason = bool((interaction.reason_code if interaction else "") or client.call_result_reason_code)
        has_note = bool((interaction.reason_note if interaction else "") or client.call_result_reason_note or _safe_text(context.get("note")) or _safe_text(client.manager_note))
        if not has_reason and not has_note:
            raw_points = min(raw_points or 1, 1)
            negative_cap_triggered = True
            flags.append("negative_missing_context_cap")

    cap_category = _daily_cap_category(client)
    prior_capped_points = _prior_capped_points_sum(client, cap_category)
    final_points = raw_points
    daily_cap = _daily_cap_value(cap_category)
    if daily_cap is not None:
        remaining = max(0, int(daily_cap) - int(prior_capped_points))
        if final_points > remaining:
            final_points = remaining
            flags.append("daily_cap_applied")
        if remaining <= 0:
            flags.append("daily_cap_exhausted")
    else:
        remaining = None

    return {
        "policy_version": VISIBLE_POINTS_POLICY_VERSION,
        "call_result": call_result,
        "base_outcome_points": base_points,
        "structure_bonus": structure_bonus,
        "evidence_bonus": evidence_bonus,
        "next_step_bonus": next_step_bonus,
        "source_weight": source_weight,
        "repeat_multiplier": repeat_multiplier,
        "abuse_multiplier": abuse_multiplier,
        "pre_cap_points": raw_points,
        "final_points": max(0, int(final_points)),
        "points_source_bucket": source_bucket,
        "cap_category": cap_category or "",
        "daily_cap": daily_cap,
        "daily_cap_remaining_before_current": remaining if daily_cap is not None else None,
        "flags": sorted(set(flags)),
        "negative_cap_triggered": negative_cap_triggered,
    }


def sync_client_visible_points(
    client: Client,
    interaction: ClientInteractionAttempt | None = None,
    *,
    source_lead: ManagementLead | None = None,
) -> int:
    breakdown = build_visible_points_breakdown(client, interaction=interaction, source_lead=source_lead)
    context = dict(client.call_result_context or {})
    context["points_policy_version"] = VISIBLE_POINTS_POLICY_VERSION
    context["points_breakdown"] = breakdown
    context["points_source_bucket"] = breakdown["points_source_bucket"]
    context["points_flags"] = breakdown["flags"]

    client.points_override = int(breakdown["final_points"])
    client.call_result_context = context
    client.save(update_fields=["points_override", "call_result_context", "updated_at"])
    return int(client.points_override or 0)


def _latest_interaction(client: Client) -> ClientInteractionAttempt | None:
    if not client.pk:
        return None
    return client.interaction_attempts.order_by("-created_at", "-id").first()


def _resolve_source_lead(client: Client) -> ManagementLead | None:
    if not client.pk:
        return None
    try:
        return client.source_lead
    except ManagementLead.DoesNotExist:
        pass

    root_id = client.phase_root_id or client.id
    family_ids = list(
        Client.objects.filter(Q(id=root_id) | Q(phase_root_id=root_id)).values_list("id", flat=True)
    )
    if not family_ids:
        family_ids = [client.id]
    return (
        ManagementLead.objects.filter(converted_client_id__in=family_ids)
        .order_by("id")
        .first()
    )


def _source_weight_for(call_result: str, source_bucket: str) -> float:
    if source_bucket != "parser_assigned_base":
        return 1.0
    if call_result in CONVERSION_RESULTS:
        return 0.90
    if call_result in PROGRESS_RESULTS:
        return 0.60
    return 0.35


def _has_linked_evidence(client: Client, interaction: ClientInteractionAttempt | None) -> bool:
    context = client.call_result_context or {}
    return any(
        (
            getattr(interaction, "cp_log_id", None),
            getattr(interaction, "linked_shop_id", None),
            _safe_text(getattr(interaction, "xml_resource_url", "")),
            _safe_text(getattr(interaction, "messenger_target_value", "")),
            context.get("cp_log_id"),
            context.get("linked_shop_id"),
            _safe_text(context.get("xml_resource_url")),
            _safe_text(context.get("messenger_target_value")),
        )
    )


def _has_duplicate_override(client: Client, interaction: ClientInteractionAttempt | None) -> bool:
    context = client.call_result_context or {}
    return bool(
        _safe_text(getattr(interaction, "duplicate_override_reason", ""))
        or _safe_text(context.get("duplicate_override_reason"))
    )


def _has_meaningful_detail(client: Client, interaction: ClientInteractionAttempt | None) -> bool:
    context = client.call_result_context or {}
    candidates = [
        getattr(interaction, "reason_note", ""),
        getattr(interaction, "details", ""),
        client.call_result_reason_note,
        client.call_result_details,
        client.manager_note,
        context.get("note", ""),
    ]
    return any(len(_safe_text(value)) >= DETAIL_TEXT_MIN_LEN for value in candidates)


def _is_narrow_window_followup(client: Client, interaction: ClientInteractionAttempt | None) -> bool:
    if not client.next_call_at:
        return False
    anchor = getattr(interaction, "created_at", None) or client.created_at or timezone.now()
    try:
        delta = client.next_call_at - anchor
    except Exception:
        return False
    return delta <= timedelta(hours=PROMISE_NARROW_WINDOW_HOURS)


def _same_day_prior_qs(client: Client):
    if not client.owner_id or not client.created_at:
        return Client.objects.none()
    day_start, day_end = _local_day_bounds(client.created_at)
    qs = Client.objects.filter(owner_id=client.owner_id, created_at__gte=day_start, created_at__lt=day_end).exclude(pk=client.pk)
    return qs.filter(Q(created_at__lt=client.created_at) | Q(created_at=client.created_at, id__lt=client.id))


def _repeat_multiplier(client: Client) -> float:
    if client.call_result not in CHEAP_REPEAT_RESULTS:
        return 1.0
    prior_count = _same_day_prior_qs(client).filter(_identity_filter(client), call_result__in=CHEAP_REPEAT_RESULTS).count()
    if client.call_result == Client.CallResult.NO_ANSWER:
        return 1.0 if prior_count == 0 else 0.0
    if prior_count == 0:
        return 1.0
    if prior_count == 1:
        return 0.5
    return 0.0


def _identity_filter(client: Client) -> Q:
    root_id = client.phase_root_id or client.id
    query = Q(id=root_id) | Q(phase_root_id=root_id)
    if client.phone_normalized:
        query |= Q(phone_normalized=client.phone_normalized)
    elif client.phone_last7:
        query |= Q(phone_last7=client.phone_last7)
    if client.website_match_key:
        query |= Q(website_match_key=client.website_match_key)
    if client.normalized_name_match_key:
        query |= Q(normalized_name_match_key=client.normalized_name_match_key)
    return query


def _daily_cap_category(client: Client) -> str | None:
    if client.call_result in DAILY_CAPS:
        return client.call_result
    if client.call_result == Client.CallResult.THINKING and not client.next_call_at:
        return "thinking_no_followup"
    return None


def _daily_cap_value(cap_category: str | None) -> int | None:
    if not cap_category:
        return None
    if cap_category == "thinking_no_followup":
        return THINKING_NO_FOLLOWUP_CAP
    return DAILY_CAPS.get(cap_category)


def _prior_capped_points_sum(client: Client, cap_category: str | None) -> int:
    if not cap_category:
        return 0
    total = 0
    qs = _same_day_prior_qs(client)
    if cap_category == "thinking_no_followup":
        qs = qs.filter(call_result=Client.CallResult.THINKING)
    elif cap_category in DAILY_CAPS:
        qs = qs.filter(call_result=cap_category)
    for row in qs.only("points_override", "call_result_context", "next_call_at", "call_result"):
        if (row.call_result_context or {}).get("points_policy_version") != VISIBLE_POINTS_POLICY_VERSION:
            continue
        if _daily_cap_category(row) != cap_category:
            continue
        total += int(row.points_override or 0)
    return total


def _local_day_bounds(dt_value):
    local_dt = timezone.localtime(dt_value)
    start = local_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return start, end


def _safe_text(value: Any) -> str:
    return str(value or "").strip()
