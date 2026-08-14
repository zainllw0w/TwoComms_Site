"""Deterministic, fail-closed policy for the optional Instagram follow CTA.

The service deliberately has no provider I/O.  It owns the local policy
boundary, immutable decision snapshots, the database-backed reservation, and
the receipt/ambiguous outcome accounting used by later delivery workers.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from difflib import SequenceMatcher
from typing import Iterable

from django.db import IntegrityError, transaction
from django.utils import timezone

from management.models import (
    IgClient,
    IgCommercialEpisode,
    IgConversationAnalysisSnapshot,
    IgFollowCtaDecision,
    IgFollowState,
    IgLifecycleEvent,
    IgPostSaleCase,
    InstagramBotMessage,
)
from management.services.ig_follow_state import effective_follow_state


POLICY_VERSION = "follow-v1"
COOLDOWN = timedelta(days=90)
ROLLING_YEAR = timedelta(days=365)
RESERVATION_LEASE = timedelta(minutes=5)
MIN_CANDIDATE_LENGTH = 24
MAX_CANDIDATE_LENGTH = 220
_SOFT_HESITATION = re.compile(
    r"\b(подума|думаю|подум|ще подума|порад|не впевн|maybe|think|consider|размыш)",
    re.IGNORECASE,
)
_URL = re.compile(r"(?:https?://|www\.|(?:[a-z0-9-]+\.)+(?:com|shop|ua|net|org)(?:/|\b))", re.I)
_PERCENT = re.compile(r"\d+\s*%")
_MARKDOWN = re.compile(r"[`*_#\[\]{}<>]|\]\(")
_CONTROL = re.compile(r"(?:\[/?(?:PAYLINK|FOLLOW|CTA|CONTROL|ORDER)[^\]]*\]|<[^>]+>)", re.I)
_DISCOUNT_WORDS = re.compile(
    r"(?:зниж|скид|промокод|promo|coupon|discount|stack|відсот|процент)", re.I
)
_URGENCY_WORDS = re.compile(
    r"(?:терміново|поспіш|сьогодні|зараз|лише|тільки|останн|last\s+chance|не\s+втрач)",
    re.I,
)
_GUILT_OR_SURVEILLANCE = re.compile(
    r"(?:ми\s+(?:бач|поміт|відстеж)|ви\s+не\s+підпис|я\s+знаю|ми\s+знаємо|перевір|контролю|стежимо|відслідков)",
    re.I,
)
_FALSE_PROMISE = re.compile(r"(?:гарант|обіця|обещ|безкоштов|free\s+gift)", re.I)
_PAYMENT_LINK = re.compile(r"(?:paylink|payment\s+link|посилання\s+на\s+оплат|ссылк\s+на\s+оплат)", re.I)
_UGC_OR_REVIEW = re.compile(
    r"(?:відгук|відміт|познач|репост|репостн|сторі|фото\s+в\s+одяз|ugc|review)", re.I
)
_RISK_WORDS = re.compile(
    r"(?:refund|refunded|повернен|обмін|обмен|exchange|скасув|отмен|reversal|chargeback|скарг|жалоб)",
    re.I,
)


@dataclass(frozen=True)
class FollowOpportunity:
    allowed: bool
    client_id: int
    opportunity: str
    episode_id: int | None
    source_message_id: int | None
    order_id: int | None
    lifecycle_event_id: int | None
    follow_state: str
    follow_state_revision: int
    conversation_watermark: int
    context_fingerprint: str
    base_text: str
    trigger_key: str
    reason_codes: tuple[str, ...] = ()
    analysis_id: int | None = None

    @property
    def suppression_reason(self) -> str:
        return self.reason_codes[0] if self.reason_codes else ""


@dataclass(frozen=True)
class AuthorizedFollowCta:
    decision_id: int
    text: str
    base_text: str
    final_text: str
    lease_token: str

    @property
    def candidate_text(self) -> str:
        return self.text


def _enum_value(value) -> str:
    return str(getattr(value, "value", value) or "")


def _fingerprint(*parts) -> str:
    encoded = json.dumps(parts, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _trigger_key(*, client, opportunity, episode=None, source_message=None, lifecycle_event=None) -> str:
    anchor = (
        f"message:{getattr(source_message, 'pk', '')}"
        if getattr(source_message, "pk", None)
        else f"lifecycle:{getattr(lifecycle_event, 'pk', '')}"
        if getattr(lifecycle_event, "pk", None)
        else f"episode:{getattr(episode, 'pk', '')}"
    )
    return f"{_enum_value(opportunity)}:{getattr(client, 'pk', 0)}:{anchor}"[:180]


def _source_text(source_message) -> str:
    return str(getattr(source_message, "text", "") or "")


def _latest_user_id(client_id: int) -> int:
    return int(
        InstagramBotMessage.objects.filter(
            client_id=client_id, role=InstagramBotMessage.Role.USER
        ).order_by("-pk").values_list("pk", flat=True).first()
        or 0
    )


def _timestamp_for_message(message):
    return getattr(message, "provider_created_at", None) or getattr(message, "created_at", None)


def _window_is_open(client, *, source_message=None, now) -> bool:
    if getattr(client, "delivery_status", "") == IgClient.DeliveryStatus.WINDOW_CLOSED:
        return False
    latest = getattr(client, "last_message_at", None)
    source_timestamp = _timestamp_for_message(source_message) if source_message is not None else None
    if latest is None or (source_timestamp is not None and source_timestamp > latest):
        latest = source_timestamp
    if latest is None:
        return False
    return latest >= now - timedelta(hours=24)


def _has_post_sale_risk(client, *, order=None, lifecycle_event=None) -> bool:
    active_statuses = {
        IgPostSaleCase.Status.NEEDS_DETAILS,
        IgPostSaleCase.Status.OPEN,
        IgPostSaleCase.Status.APPROVED,
        IgPostSaleCase.Status.IN_TRANSIT,
        IgPostSaleCase.Status.RECEIVED,
    }
    if IgPostSaleCase.objects.filter(client_id=client.pk, status__in=active_statuses).exists():
        return True
    if lifecycle_event is not None:
        kind = _enum_value(getattr(lifecycle_event, "kind", ""))
        payload = getattr(lifecycle_event, "payload", {}) or {}
        if kind in {"payment_recovery", "refund", "reversal", "cancellation", "return", "exchange"}:
            return True
    if _enum_value(getattr(client, "intent", "")) in {
        IgClient.Intent.SUPPORT,
        IgClient.Intent.SPAM,
    }:
        return True
    flags = getattr(client, "conversion_flags", {}) or {}
    if isinstance(flags, dict) and any(
        bool(flags.get(key)) for key in ("complaint", "support_complaint", "return", "exchange", "refund", "reversal", "cancelled")
    ):
        return True
        if isinstance(payload, dict) and any(
            str(payload.get(key) or "").lower() in {"return", "exchange", "refund", "reversal", "cancelled", "cancellation"}
            for key in ("kind", "event", "flow", "status", "case_type")
        ):
            return True
    for obj in (order, getattr(client, "current_commercial_episode", None)):
        values = " ".join(
            str(getattr(obj, name, "") or "")
            for name in ("status", "state", "cancellation_reason", "refund_status", "return_status", "exchange_status")
        )
        if _RISK_WORDS.search(values):
            return True
    return False


def _payment_recovery_active(client, *, source_message=None, lifecycle_event=None, base_text="") -> bool:
    context = getattr(client, "sales_context", {}) or {}
    if isinstance(context, dict) and any(
        bool(context.get(key)) for key in ("paylink_active", "payment_recovery", "payment_recovery_pending", "recovery_pending")
    ):
        return True
    event_payload = getattr(lifecycle_event, "payload", {}) or {}
    if isinstance(event_payload, dict) and any(
        bool(event_payload.get(key)) for key in ("paylink", "payment_recovery", "recovery")
    ):
        return True
    return bool(_PAYMENT_LINK.search(" ".join((_source_text(source_message), str(base_text or "")))))


def _growth_cta_present(text: str) -> bool:
    text = str(text or "")
    return bool(re.search(r"(?:підпис|подпис|follow|відгук|відміт|репост|промокод|зниж|скид)", text, re.I))


def _latest_hesitation_analysis(*, client, episode, source_message, now):
    if source_message is None or not _SOFT_HESITATION.search(_source_text(source_message)):
        return None
    allowed_bands = {
        IgConversationAnalysisSnapshot.Band.QUALIFIED,
        IgConversationAnalysisSnapshot.Band.HIGH_INTENT,
        IgConversationAnalysisSnapshot.Band.CHECKOUT,
    }
    analysis = (
        IgConversationAnalysisSnapshot.objects.filter(
            client_id=client.pk,
            score_band__in=allowed_bands,
            confidence__gte=Decimal("0.70"),
            analyzed_at__gte=now - timedelta(hours=24),
            analyzed_at__lte=now,
        )
        .order_by("-id")
        .first()
    )
    if analysis is None:
        return None
    if analysis.commercial_episode_id != getattr(episode, "pk", None):
        return None
    if not analysis.last_analyzed_message_id or analysis.last_analyzed_message_id < source_message.pk:
        return None
    if analysis.interaction_type in {
        IgConversationAnalysisSnapshot.InteractionType.SUPPORT_COMPLAINT,
        IgConversationAnalysisSnapshot.InteractionType.OPT_OUT,
        IgConversationAnalysisSnapshot.InteractionType.SPAM_ABUSE,
        IgConversationAnalysisSnapshot.InteractionType.EXPLICIT_NO_BUY,
    }:
        return None
    return analysis


def _suppression_codes(
    *,
    client,
    opportunity,
    episode,
    source_message,
    order,
    lifecycle_event,
    base_text,
    now,
    follow_view,
    conversation_watermark,
    include_history=True,
):
    reasons: list[str] = []
    if not follow_view.fresh or follow_view.state != IgFollowState.State.NOT_FOLLOWING:
        reasons.append("follow_state")
    if getattr(client, "hidden_at", None):
        reasons.append("hidden")
    if getattr(client, "is_blocked", False):
        reasons.append("blocked")
    if _enum_value(getattr(client, "stage", "")) == IgClient.Stage.SPAM:
        reasons.append("spam")
    if int(getattr(client, "spam_strikes", 0) or 0) > 0:
        reasons.append("spam")
    opted_out_at = getattr(client, "opted_out_at", None)
    opted_in_at = getattr(client, "opted_in_at", None)
    if opted_out_at and (not opted_in_at or opted_in_at <= opted_out_at):
        reasons.append("opted_out")
    if getattr(client, "bot_paused", False):
        reasons.append("paused")
    if getattr(client, "manager_takeover", False):
        reasons.append("takeover")
    if not _window_is_open(client, source_message=source_message, now=now):
        reasons.append("closed_window")
    if episode is None or getattr(episode, "state", "") in {
        IgCommercialEpisode.State.CANCELLED,
        IgCommercialEpisode.State.LOST,
    } or getattr(episode, "closed_at", None):
        reasons.append("stale_episode")
    current_episode_id = getattr(client, "current_commercial_episode_id", None)
    if current_episode_id and current_episode_id != getattr(episode, "pk", None):
        reasons.append("stale_episode")
    latest_user = _latest_user_id(client.pk)
    source_id = getattr(source_message, "pk", None)
    if latest_user > conversation_watermark and latest_user != source_id:
        reasons.append("new_inbound")
    if _has_post_sale_risk(client, order=order, lifecycle_event=lifecycle_event):
        reasons.append("post_sale_risk")
    if _payment_recovery_active(
        client, source_message=source_message, lifecycle_event=lifecycle_event, base_text=base_text
    ):
        reasons.append("payment_recovery")
    lifecycle_kind = _enum_value(getattr(lifecycle_event, "kind", ""))
    if (
        lifecycle_kind == IgLifecycleEvent.Kind.DELIVERED_REVIEW_REQUESTED
        or _UGC_OR_REVIEW.search(
        _source_text(source_message)
        )
    ):
        reasons.append("delivered_review_or_ugc")
    if _growth_cta_present(base_text):
        reasons.append("existing_cta")
    if _enum_value(opportunity) == IgFollowCtaDecision.Opportunity.HESITATION:
        analysis = _latest_hesitation_analysis(
            client=client, episode=episode, source_message=source_message, now=now
        )
        if analysis is None:
            reasons.append("analysis")
    else:
        analysis = None
    if include_history and episode is not None:
        active_states = {
            IgFollowCtaDecision.State.PREPARED,
            IgFollowCtaDecision.State.RESERVED,
            IgFollowCtaDecision.State.SENT,
            IgFollowCtaDecision.State.AMBIGUOUS,
        }
        if IgFollowCtaDecision.objects.filter(
            client_id=client.pk, commercial_episode_id=episode.pk, state__in=active_states
        ).exists():
            reasons.append("another_cta")
        happened = _delivery_timestamps(client.pk, now=now)
        if happened and now - max(happened) < COOLDOWN:
            reasons.append("cooldown")
        if len([stamp for stamp in happened if now - stamp < ROLLING_YEAR]) >= 2:
            reasons.append("annual_cap")
    return tuple(dict.fromkeys(reasons)), analysis


def _delivery_timestamps(client_id: int, *, now) -> list:
    rows = IgFollowCtaDecision.objects.filter(
        client_id=client_id,
        state__in=(IgFollowCtaDecision.State.SENT, IgFollowCtaDecision.State.AMBIGUOUS),
    ).only("completed_at", "provider_io_started_at", "updated_at", "created_at")
    result = []
    for row in rows:
        stamp = row.completed_at or row.provider_io_started_at or row.updated_at or row.created_at
        if stamp and stamp <= now:
            result.append(stamp)
    return result


def evaluate_follow_opportunity(
    *,
    client,
    opportunity,
    episode,
    source_message=None,
    order=None,
    lifecycle_event=None,
    base_text="",
    now=None,
) -> FollowOpportunity:
    now = now or timezone.now()
    opportunity_value = _enum_value(opportunity)
    follow_view = effective_follow_state(client, now=now)
    watermark = max(
        int(getattr(episode, "opened_watermark_message_id", 0) or 0),
        int(getattr(source_message, "pk", 0) or 0),
    )
    trigger_key = _trigger_key(
        client=client,
        opportunity=opportunity_value,
        episode=episode,
        source_message=source_message,
        lifecycle_event=lifecycle_event,
    )
    context_fingerprint = _fingerprint(
        POLICY_VERSION,
        getattr(client, "pk", None),
        getattr(episode, "pk", None),
        opportunity_value,
        getattr(source_message, "pk", None),
        getattr(order, "pk", None),
        getattr(lifecycle_event, "pk", None),
        follow_view.revision,
        watermark,
        str(base_text or "").strip(),
    )
    reasons, analysis = _suppression_codes(
        client=client,
        opportunity=opportunity_value,
        episode=episode,
        source_message=source_message,
        order=order,
        lifecycle_event=lifecycle_event,
        base_text=base_text,
        now=now,
        follow_view=follow_view,
        conversation_watermark=watermark,
    )
    return FollowOpportunity(
        allowed=not reasons,
        client_id=int(client.pk),
        opportunity=opportunity_value,
        episode_id=getattr(episode, "pk", None),
        source_message_id=getattr(source_message, "pk", None),
        order_id=getattr(order, "pk", None),
        lifecycle_event_id=getattr(lifecycle_event, "pk", None),
        follow_state=follow_view.state,
        follow_state_revision=int(follow_view.revision or 0),
        conversation_watermark=watermark,
        context_fingerprint=context_fingerprint,
        base_text=str(base_text or "").strip(),
        trigger_key=trigger_key,
        reason_codes=reasons,
        analysis_id=getattr(analysis, "pk", None),
    )


def _emoji_count(text: str) -> int:
    return sum(
        1
        for char in text
        if (0x1F000 <= ord(char) <= 0x1FAFF)
        or (0x2600 <= ord(char) <= 0x27BF)
    )


def _candidate_error(candidate: str, *, base_text: str, client=None) -> str:
    candidate = str(candidate or "").strip()
    if not (MIN_CANDIDATE_LENGTH <= len(candidate) <= MAX_CANDIDATE_LENGTH):
        return "candidate_length"
    if "\n" in candidate or "\r" in candidate:
        return "candidate_format"
    if _URL.search(candidate):
        return "candidate_url"
    if _MARKDOWN.search(candidate) or _CONTROL.search(candidate):
        return "candidate_control"
    if _PERCENT.search(candidate) or _DISCOUNT_WORDS.search(candidate):
        return "candidate_discount"
    if _URGENCY_WORDS.search(candidate):
        return "candidate_urgency"
    if _GUILT_OR_SURVEILLANCE.search(candidate):
        return "candidate_surveillance"
    if _FALSE_PROMISE.search(candidate):
        return "candidate_false_promise"
    punctuation = re.findall(r"[.!?。！？]", candidate)
    if len(punctuation) > 1 or candidate.count("?") > 1 or candidate.count("？") > 1:
        return "candidate_sentence_count"
    if _emoji_count(candidate) > 1:
        return "candidate_emoji"
    language = _enum_value(getattr(client, "language", "")) if client is not None else ""
    if language.startswith("uk") and not re.search(r"[А-Яа-яІіЇїЄєҐґ]", candidate):
        return "candidate_language"
    if language.startswith("en") and re.search(r"[А-Яа-яІіЇїЄєҐґ]", candidate):
        return "candidate_language"
    normalized_candidate = re.sub(r"\W+", " ", candidate.casefold()).strip()
    normalized_base = re.sub(r"\W+", " ", str(base_text or "").casefold()).strip()
    if normalized_candidate and (
        normalized_candidate in normalized_base
        or SequenceMatcher(None, normalized_candidate, normalized_base).ratio() >= 0.88
    ):
        return "candidate_similarity"
    try:
        from management.services.instagram_bot import _split_for_send

        if len(_split_for_send(f"{base_text.strip()} {candidate}")) != 1:
            return "candidate_chunk_limit"
    except Exception:
        return "candidate_chunk_limit"
    return ""


def _split_for_send(text: str, limit: int = 950, max_chunks: int = 4) -> list[str]:
    """Lazy public test/policy hook for the existing Instagram sender splitter."""
    from management.services.instagram_bot import _split_for_send as split_for_send

    return split_for_send(text, limit=limit, max_chunks=max_chunks)


def _safe_model_meta(model_meta) -> dict[str, str]:
    model_meta = model_meta if isinstance(model_meta, dict) else {}
    return {
        "model": str(model_meta.get("model") or model_meta.get("analysis_model") or "")[:80],
        "key_alias": str(model_meta.get("key_alias") or model_meta.get("model_key_alias") or "")[:80],
        "prompt_version": str(model_meta.get("prompt_version") or "")[:40],
    }


def prepare_follow_decision(
    opportunity: FollowOpportunity, *, candidate_text: str, model_meta=None
) -> IgFollowCtaDecision:
    existing = IgFollowCtaDecision.objects.filter(trigger_key=opportunity.trigger_key).first()
    if existing is not None:
        return existing
    from management.models import IgClient as _IgClient

    client = _IgClient.objects.filter(pk=opportunity.client_id).first()
    candidate_error = _candidate_error(candidate_text, base_text=opportunity.base_text, client=client)
    valid = bool(opportunity.allowed and not candidate_error)
    meta = _safe_model_meta(model_meta)
    reason_codes = list(opportunity.reason_codes)
    if candidate_error:
        reason_codes.extend(("invalid_candidate", candidate_error))
    state = IgFollowCtaDecision.State.PREPARED if valid else IgFollowCtaDecision.State.SUPPRESSED
    decision = IgFollowCtaDecision.objects.create(
        trigger_key=opportunity.trigger_key,
        client_id=opportunity.client_id,
        commercial_episode_id=opportunity.episode_id,
        order_id=opportunity.order_id,
        lifecycle_event_id=opportunity.lifecycle_event_id,
        source_message_id=opportunity.source_message_id,
        opportunity=opportunity.opportunity,
        policy_version=POLICY_VERSION,
        state=state,
        follow_state_revision=opportunity.follow_state_revision,
        conversation_watermark=opportunity.conversation_watermark,
        context_fingerprint=opportunity.context_fingerprint,
        base_text=opportunity.base_text,
        candidate_text=str(candidate_text or "").strip() if valid else "",
        candidate_hash=hashlib.sha256(str(candidate_text or "").strip().encode("utf-8")).hexdigest()
        if valid
        else "",
        suppression_reason=("invalid_candidate" if candidate_error else opportunity.suppression_reason)[:64],
        reason_codes=reason_codes,
        model=meta["model"],
        model_key_alias=meta["key_alias"],
        prompt_version=meta["prompt_version"],
    )
    return decision


def _current_opportunity_for_decision(decision, *, client, episode, now):
    source_message = (
        InstagramBotMessage.objects.filter(pk=decision.source_message_id).first()
        if decision.source_message_id
        else None
    )
    order = None
    if decision.order_id:
        try:
            from orders.models import Order

            order = Order.objects.filter(pk=decision.order_id).first()
        except Exception:
            order = None
    lifecycle_event = (
        IgLifecycleEvent.objects.filter(pk=decision.lifecycle_event_id).first()
        if decision.lifecycle_event_id
        else None
    )
    view = effective_follow_state(client, now=now)
    reasons, analysis = _suppression_codes(
        client=client,
        opportunity=decision.opportunity,
        episode=episode,
        source_message=source_message,
        order=order,
        lifecycle_event=lifecycle_event,
        base_text=decision.base_text,
        now=now,
        follow_view=view,
        conversation_watermark=decision.conversation_watermark,
        include_history=True,
    )
    # The decision itself is the current prepared row; its own episode slot is
    # nullable and therefore is not counted as another CTA here.
    reasons = tuple(code for code in reasons if code != "another_cta")
    return reasons, view, analysis


def authorize_follow_cta(
    decision_id, *, current_base_text: str, now=None
) -> AuthorizedFollowCta | None:
    now = now or timezone.now()
    try:
        with transaction.atomic():
            decision = (
                IgFollowCtaDecision.objects.select_for_update()
                .select_related("client", "commercial_episode")
                .filter(pk=decision_id)
                .first()
            )
            if decision is None or decision.state != IgFollowCtaDecision.State.PREPARED:
                return None
            if str(current_base_text or "").strip() != decision.base_text:
                return None
            client = IgClient.objects.select_for_update().get(pk=decision.client_id)
            episode = (
                IgCommercialEpisode.objects.filter(pk=decision.commercial_episode_id).first()
                if decision.commercial_episode_id
                else None
            )
            state = (
                IgFollowState.objects.select_for_update()
                .filter(client_id=decision.client_id)
                .first()
            )
            if state is None:
                return None
            reasons, view, _analysis = _current_opportunity_for_decision(
                decision, client=client, episode=episode, now=now
            )
            if reasons or view.revision != decision.follow_state_revision:
                return None
            source_message = (
                InstagramBotMessage.objects.filter(pk=decision.source_message_id).first()
                if decision.source_message_id
                else None
            )
            current_watermark = max(
                int(getattr(episode, "opened_watermark_message_id", 0) or 0),
                int(getattr(source_message, "pk", 0) or 0),
            )
            current_context = _fingerprint(
                POLICY_VERSION,
                client.pk,
                getattr(episode, "pk", None),
                decision.opportunity,
                getattr(source_message, "pk", None),
                decision.order_id,
                decision.lifecycle_event_id,
                view.revision,
                current_watermark,
                decision.base_text,
            )
            if current_context != decision.context_fingerprint:
                return None
            candidate_error = _candidate_error(
                decision.candidate_text, base_text=decision.base_text, client=client
            )
            if candidate_error:
                return None
            # The state projection is the serialization row for both episode
            # and cross-episode reservations.  The unique slots remain a
            # database-backed last line against incorrect application retries.
            episode_slot = f"ig-follow-episode:{decision.commercial_episode_id}" if decision.commercial_episode_id else None
            if episode_slot and IgFollowCtaDecision.objects.filter(
                commercial_episode_id=decision.commercial_episode_id,
                state__in=(
                    IgFollowCtaDecision.State.PREPARED,
                    IgFollowCtaDecision.State.RESERVED,
                    IgFollowCtaDecision.State.SENT,
                    IgFollowCtaDecision.State.AMBIGUOUS,
                ),
            ).exclude(pk=decision.pk).exists():
                return None
            history = _delivery_timestamps(decision.client_id, now=now)
            if history and now - max(history) < COOLDOWN:
                return None
            if len([stamp for stamp in history if now - stamp < ROLLING_YEAR]) >= 2:
                return None
            token = uuid.uuid4().hex
            decision.state = IgFollowCtaDecision.State.RESERVED
            decision.episode_slot_key = episode_slot
            decision.sent_scope_key = f"ig-follow-scope:{decision.client_id}:{token}"
            decision.lease_token = token
            decision.lease_expires_at = now + RESERVATION_LEASE
            decision.final_text = f"{decision.base_text} {decision.candidate_text}".strip()
            decision.save(
                update_fields=[
                    "state",
                    "episode_slot_key",
                    "sent_scope_key",
                    "lease_token",
                    "lease_expires_at",
                    "final_text",
                    "updated_at",
                ]
            )
            return AuthorizedFollowCta(
                decision_id=decision.pk,
                text=decision.candidate_text,
                base_text=decision.base_text,
                final_text=decision.final_text,
                lease_token=token,
            )
    except IntegrityError:
        return None


def finalize_follow_delivery(
    decision_id, *, outcome, provider_message_ids: Iterable[str] = (), now=None
) -> None:
    now = now or timezone.now()
    outcome_value = str(getattr(outcome, "value", outcome) or "").lower()
    with transaction.atomic():
        decision = IgFollowCtaDecision.objects.select_for_update().filter(pk=decision_id).first()
        if decision is None:
            return
        if decision.state in {
            IgFollowCtaDecision.State.SENT,
            IgFollowCtaDecision.State.AMBIGUOUS,
            IgFollowCtaDecision.State.CANCELLED,
            IgFollowCtaDecision.State.FAILED,
        }:
            return
        ids = [str(value)[:255] for value in (provider_message_ids or ()) if str(value).strip()]
        if outcome_value in {"provider_io_started", "sending", "started"}:
            decision.provider_io_started_at = decision.provider_io_started_at or now
            decision.save(update_fields=["provider_io_started_at", "updated_at"])
            return
        if outcome_value in {"sent", "receipt", "provider_receipt", "confirmed", "delivered"}:
            decision.state = IgFollowCtaDecision.State.SENT
            decision.provider_message_ids = ids
        elif outcome_value in {"ambiguous", "timeout_after_io", "unknown"}:
            decision.state = IgFollowCtaDecision.State.AMBIGUOUS
            decision.provider_message_ids = ids
        elif outcome_value in {"cancelled", "canceled", "cancelled_before_io"}:
            if decision.provider_io_started_at:
                # Once the non-idempotent provider boundary has started, a
                # local cancellation cannot prove that Meta rejected it.
                decision.state = IgFollowCtaDecision.State.AMBIGUOUS
                decision.provider_message_ids = ids
            else:
                decision.state = IgFollowCtaDecision.State.CANCELLED
                decision.episode_slot_key = None
                decision.sent_scope_key = None
        else:
            decision.state = IgFollowCtaDecision.State.AMBIGUOUS if decision.provider_io_started_at else IgFollowCtaDecision.State.FAILED
            if decision.state == IgFollowCtaDecision.State.FAILED:
                decision.episode_slot_key = None
                decision.sent_scope_key = None
        decision.completed_at = now
        decision.lease_token = ""
        decision.lease_expires_at = None
        decision.save(
            update_fields=[
                "state",
                "provider_message_ids",
                "episode_slot_key",
                "sent_scope_key",
                "completed_at",
                "lease_token",
                "lease_expires_at",
                "updated_at",
            ]
        )


__all__ = [
    "AuthorizedFollowCta",
    "FollowOpportunity",
    "authorize_follow_cta",
    "evaluate_follow_opportunity",
    "finalize_follow_delivery",
    "prepare_follow_decision",
]
