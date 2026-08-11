"""Durable, reply-independent high-reasoning analysis for Instagram CRM."""
from __future__ import annotations

import hashlib
import json
import re
import secrets
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.db import IntegrityError, transaction
from django.db.models import (
    Case,
    CharField,
    F,
    Max,
    PositiveSmallIntegerField,
    Q,
    Value,
    When,
)
from django.db.models.functions import Coalesce
from django.utils import timezone

from management.models import (
    IgClient,
    IgConversationAnalysisJob,
    IgConversationAnalysisSnapshot,
    InstagramBotMessage,
    InstagramBotSettings,
)
from management.services.bot_payment_truth import client_has_confirmed_purchase
from management.services.call_ai_analysis import gemini_generate_json
from management.services.ig_funnel_reset import current_message_floor


DEBOUNCE_SECONDS = 30
LEASE_SECONDS = 180
MAX_ATTEMPTS = 5
MAX_MESSAGES = 160
MAX_TRANSCRIPT_CHARS = 30_000
ANALYSIS_PROMPT_VERSION = "2026-07-30.crm.episode-potential.v3"
RETRY_DELAYS = (60, 180, 600, 1800, 3600)
HISTORICAL_ANALYSIS_TRIGGERS = frozenset({
    "reconcile",
    "poll_history",
    "poll_backfill",
    "manual_refresh",
})
REPLY_PROCESSING_GRACE_SECONDS = 300

EXPLICIT_REPEAT_RE = re.compile(
    r"(?:\b(?:хочу|візьму|возьму|замов\w*|закаж\w*)\b.{0,50}\b(?:ще|еще)\b|"
    r"\b(?:ще|еще)\s+(?:одн\w*|так\w*)\b|"
    r"\b(?:повторн\w*|знову|снова)\b.{0,50}\b(?:замов\w*|заказ\w*|куп\w*)\b|"
    r"\b(?:another\s+one|one\s+more|reorder)\b)",
    re.I,
)

# A received-item request can itself contain "ще одну" (for example, replacing
# one shirt with another size).  In a mixed service + purchase message, accept
# repeat intent only when a separate additive clause contains a purchase verb.
ADDITIVE_REPEAT_PURCHASE_RE = re.compile(
    r"(?:\+|[,;.]|\b(?:і|й|та|и|а|також|также|плюс|окремо|отдельно|"
    r"додатково|дополнительно)\b).{0,50}?"
    r"(?:\b(?:хочу|візьм\w*|возьм\w*|замов\w*|закаж\w*|куп\w*|"
    r"придба\w*)\b.{0,50}\b(?:ще|еще)\b|"
    r"\b(?:ще|еще)\b.{0,50}\b(?:хочу|візьм\w*|возьм\w*|замов\w*|"
    r"закаж\w*|куп\w*|придба\w*)\b)",
    re.I,
)


def _has_explicit_repeat_evidence(text: str) -> bool:
    value = str(text or "")
    if not EXPLICIT_REPEAT_RE.search(value):
        return False
    from management.services.ig_post_sale import detect_post_sale_type

    return bool(
        not detect_post_sale_type(value)
        or ADDITIVE_REPEAT_PURCHASE_RE.search(value)
    )

SYSTEM_PROMPT = """Ти аналізуєш Instagram-діалог для внутрішньої CRM TwoComms.
Поверни лише JSON. Відокремлюй намір купити від факту оплати. Навіть підтверджена
оплата не підвищує purchase_probability і confidence: вони описують лише намір,
видимий у повідомленнях клієнта. Обіцянка,
скриншот, посилання або слова менеджера не є оплатою. Не роби висновків про
платоспроможність з мови, національності, граматики, стилю чи манери письма.
Повідомлення менеджера є контекстом, але не доказом наміру клієнта.
У кожному `media` розділяй `product` (питання/інтерес/кандидат покупки),
`receipt` (доказ для ручної перевірки, але не provider-paid), `custom_reference`
та `other`. Не перетворюй невідоме зображення на товар каталогу. `product_id`
можна використовувати лише якщо його прямо підтверджено catalog match context.
`truth_state` є авторитетним системним контекстом оплати, угоди та доставки;
не перетворюй службовий статус замовлення на висловлений намір клієнта.

Поля JSON:
- interaction_type: unknown|reaction_only|information_only|product_interest|
  size_fit_question|custom_print|price_objection|high_intent|payment_pending|
  paid_order_waiting|no_reply|explicit_no_buy|opt_out|spam_abuse|manager_observation|
  collaboration|wholesale_b2b|support_complaint|exchange_request|return_request|
  community_casual;
  Обмін чи повернення вже купленого товару — це exchange_request/return_request,
  а не support_complaint. support_complaint лишається для реальної проблеми:
  посилка не дійшла, брак, не той принт.
- score_band: cold|exploring|qualified|high_intent|checkout|lost|opted_out;
- purchase_probability і confidence: числа 0..1;
- evidence: масив {message_id, quote, claim}; quote має бути дослівним коротким
  фрагментом саме цього повідомлення;
- uncertainties: масив коротких рядків.
- repeat_intent: порожній об'єкт або {kind, confidence, evidence_message_ids}, де
  kind є explicit_more|reorder|gift|another_recipient, confidence >= 0.70, а
  evidence_message_ids містить лише повідомлення клієнта з явним повторним наміром.
Не давай порад клієнту і не генеруй відповідь для відправлення."""


def _job_covers_exact_state(
    job: IgConversationAnalysisJob,
    *,
    watermark: int,
    required_state_fingerprint: str,
) -> bool:
    if (
        int(job.watermark_message_id or 0) != int(watermark or 0)
        or job.required_state_fingerprint != required_state_fingerprint
    ):
        return False
    if job.status in {
        IgConversationAnalysisJob.Status.PENDING,
        IgConversationAnalysisJob.Status.PROCESSING,
        IgConversationAnalysisJob.Status.FAILED,
    }:
        return int(job.revision or 0) > int(job.analyzed_revision or 0)
    return bool(
        job.status in {
            IgConversationAnalysisJob.Status.DONE,
            IgConversationAnalysisJob.Status.SKIPPED,
        }
        and int(job.analyzed_watermark_message_id or 0) >= watermark
        and int(job.analyzed_revision or 0) >= int(job.revision or 0)
    )


def schedule_analysis(
    client: IgClient,
    message: InstagramBotMessage,
    *,
    trigger: str = "message",
    now=None,
    delay_seconds: int = DEBOUNCE_SECONDS,
) -> IgConversationAnalysisJob | None:
    """Coalesce a changed conversation into one per-client durable job."""
    if (
        not client
        or not getattr(client, "pk", None)
        or not getattr(message, "pk", None)
        or client.hidden_at
        or client.is_blocked
        or client.stage == IgClient.Stage.SPAM
    ):
        return None
    now = now or timezone.now()
    due_at = now + timedelta(seconds=max(0, min(int(delay_seconds), 3600)))
    provisional_fingerprint = _required_state_fingerprint(client, message.pk)
    trigger_value = (trigger or "message")[:32]
    incoming_historical = False
    if trigger_value in HISTORICAL_ANALYSIS_TRIGGERS:
        settings_obj = InstagramBotSettings.load()
        event_at = message.provider_created_at or message.created_at
        incoming_historical = bool(
            not _historical_backfill_allowed(settings_obj)
            and event_at
            and event_at < settings_obj.analysis_reconcile_after
        )
    for attempt in range(2):
        try:
            with transaction.atomic():
                job, created = IgConversationAnalysisJob.objects.get_or_create(
                    client_id=client.pk,
                    defaults={
                        "watermark_message_id": message.pk,
                        "due_at": due_at,
                        "next_attempt_at": due_at,
                        "trigger": trigger_value,
                        "required_state_fingerprint": provisional_fingerprint,
                    },
                )
                job = IgConversationAnalysisJob.objects.select_for_update().get(pk=job.pk)
                if (
                    not created
                    and incoming_historical
                    and job.trigger not in HISTORICAL_ANALYSIS_TRIGGERS
                    and job.status in {
                        IgConversationAnalysisJob.Status.PENDING,
                        IgConversationAnalysisJob.Status.PROCESSING,
                        IgConversationAnalysisJob.Status.FAILED,
                    }
                ):
                    return job
                watermark = max(int(job.watermark_message_id or 0), message.pk)
                required_state_fingerprint = _required_state_fingerprint(client, watermark)
                if _job_covers_exact_state(
                    job,
                    watermark=watermark,
                    required_state_fingerprint=required_state_fingerprint,
                ):
                    return job
                job.watermark_message_id = watermark
                job.revision = int(job.revision or 0) + 1
                job.due_at = due_at
                job.trigger = trigger_value
                job.required_state_fingerprint = required_state_fingerprint
                job.attempts = 0
                fields = [
                    "watermark_message_id", "revision", "due_at", "trigger",
                    "required_state_fingerprint", "attempts", "updated_at",
                ]
                if job.status != IgConversationAnalysisJob.Status.PROCESSING:
                    job.status = IgConversationAnalysisJob.Status.PENDING
                    job.next_attempt_at = due_at
                    job.attempts = 0
                    job.lease_token = ""
                    job.lease_until = None
                    job.claimed_watermark_message_id = 0
                    job.claimed_revision = 0
                    job.last_error = ""
                    job.skip_reason = ""
                    fields.extend([
                        "status", "next_attempt_at", "attempts", "lease_token",
                        "lease_until", "claimed_watermark_message_id",
                        "claimed_revision", "last_error", "skip_reason",
                    ])
                job.save(update_fields=fields)
                return job
        except IntegrityError:
            if attempt:
                raise
    return None


def schedule_client_truth_analysis(
    client: IgClient,
    *,
    trigger: str,
    now=None,
) -> IgConversationAnalysisJob | None:
    """Reanalyze the same message watermark after payment/order truth changes."""
    if not client or not getattr(client, "pk", None):
        return None
    message = (
        InstagramBotMessage.objects.filter(
            client_id=client.pk,
            role__in=[InstagramBotMessage.Role.USER, InstagramBotMessage.Role.MANAGER],
        )
        .order_by("-id")
        .first()
    )
    if not message:
        return None
    return schedule_analysis(
        client,
        message,
        trigger=trigger,
        now=now,
        delay_seconds=0,
    )


def _reclaim_stale(now) -> int:
    return IgConversationAnalysisJob.objects.filter(
        status=IgConversationAnalysisJob.Status.PROCESSING,
        lease_until__lt=now,
    ).update(
        status=Case(
            When(
                revision__gt=F("claimed_revision"),
                then=Value(IgConversationAnalysisJob.Status.PENDING),
            ),
            When(
                attempts__gte=MAX_ATTEMPTS,
                then=Value(IgConversationAnalysisJob.Status.FAILED),
            ),
            default=Value(IgConversationAnalysisJob.Status.PENDING),
            output_field=CharField(max_length=16),
        ),
        lease_token="",
        lease_until=None,
        next_attempt_at=now,
        attempts=Case(
            When(revision__gt=F("claimed_revision"), then=Value(0)),
            default=F("attempts"),
            output_field=PositiveSmallIntegerField(),
        ),
        last_error=Case(
            When(
                revision__gt=F("claimed_revision"),
                then=Value("stale_lease_recovered"),
            ),
            When(
                attempts__gte=MAX_ATTEMPTS,
                then=Value("stale_lease_retry_exhausted"),
            ),
            default=Value("stale_lease_recovered"),
            output_field=CharField(max_length=1000),
        ),
        claimed_watermark_message_id=0,
        claimed_revision=0,
    )


def _claim_due(now) -> tuple[IgConversationAnalysisJob, int, int, str] | None:
    for _unused in range(5):
        candidate = (
            IgConversationAnalysisJob.objects.filter(
                status=IgConversationAnalysisJob.Status.PENDING,
                attempts__lt=MAX_ATTEMPTS,
                due_at__lte=now,
                next_attempt_at__lte=now,
                client__hidden_at__isnull=True,
                client__is_blocked=False,
            ).exclude(
                client__stage=IgClient.Stage.SPAM,
            )
            .order_by("due_at", "id")
            .first()
        )
        if not candidate:
            return None
        token = secrets.token_hex(16)
        lease_until = now + timedelta(seconds=LEASE_SECONDS)
        claimed = IgConversationAnalysisJob.objects.filter(
            pk=candidate.pk,
            status=IgConversationAnalysisJob.Status.PENDING,
            attempts__lt=MAX_ATTEMPTS,
            watermark_message_id=candidate.watermark_message_id,
            revision=candidate.revision,
            due_at__lte=now,
            next_attempt_at__lte=now,
        ).update(
            status=IgConversationAnalysisJob.Status.PROCESSING,
            lease_token=token,
            lease_until=lease_until,
            claimed_watermark_message_id=candidate.watermark_message_id,
            claimed_revision=candidate.revision,
            attempts=candidate.attempts + 1,
            last_error="",
            skip_reason="",
            media_phase=IgConversationAnalysisJob.MediaPhase.NOT_STARTED,
            media_error_kind="",
            media_started_at=None,
            media_completed_at=None,
            media_item_count=0,
        )
        if claimed:
            candidate.refresh_from_db()
            return (
                candidate,
                int(candidate.watermark_message_id or 0),
                int(candidate.revision or 0),
                token,
            )
    return None


def _required_truth_state(client: IgClient) -> dict:
    """Return the canonical, non-secret payment/order context for analysis."""
    from management.services.ig_commercial_episodes import (
        _client_order_queryset,
        client_payment_truth_state,
    )

    order_truth = []
    for order in _client_order_queryset(client).prefetch_related("ig_deals").order_by("pk"):
        deals = list(order.ig_deals.all())
        order_truth.append({
            "order_id": order.pk,
            "order_number": order.order_number,
            "status": order.status,
            "payment_status": order.payment_status,
            "tracking_number": order.tracking_number or "",
            "shipment_status": order.shipment_status or "",
            "deal_ids": sorted(deal.pk for deal in deals),
            "shipped_notified_at": max(
                (deal.shipped_notified_at for deal in deals if deal.shipped_notified_at),
                default=None,
            ),
        })
    return {
        # CRM truth (provider OR source-qualified manager confirmation). The
        # per-source provider/manager amounts stay available below through
        # ``client_payment_truth_state``, so nothing is hidden from the model.
        "verified_payment": client_has_confirmed_purchase(client),
        "order_truth": order_truth,
        **client_payment_truth_state(client),
    }


def _analysis_message_rows(client_id: int, watermark: int):
    floor = current_message_floor(client_id)
    rows = list(
        InstagramBotMessage.objects.filter(
            client_id=client_id,
            id__gte=floor,
            id__lte=watermark,
        )
        .exclude(status=InstagramBotMessage.Status.FAILED)
        .annotate(event_at=Coalesce("provider_created_at", "created_at"))
        .order_by("-event_at", "-id")[:MAX_MESSAGES]
    )
    rows.reverse()
    return rows


def _message_state_for_fingerprint(client_id: int, watermark: int) -> list[dict]:
    return [
        {
            "id": row.pk,
            "role": row.role,
            "status": row.status,
            "source": row.source,
            "text": row.text or "",
            "attachments": row.attachments or "",
            "event_at": (row.provider_created_at or row.created_at).isoformat(),
        }
        for row in _analysis_message_rows(client_id, watermark)
    ]


def _fingerprint_for_truth(client_id: int, watermark: int, truth_state: dict) -> str:
    payload = {
        "client_id": client_id,
        "watermark": int(watermark or 0),
        "prompt_version": ANALYSIS_PROMPT_VERSION,
        "truth_state": truth_state,
        "message_state": _message_state_for_fingerprint(client_id, watermark),
    }
    encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True, default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _required_state_fingerprint(client: IgClient, watermark: int) -> str:
    """Hash only durable, non-secret inputs that require a fresh analysis."""
    return _fingerprint_for_truth(
        client.pk,
        watermark,
        _required_truth_state(client),
    )


def _lease_is_owned(job: IgConversationAnalysisJob, *, token: str, now) -> bool:
    return bool(
        job.status == IgConversationAnalysisJob.Status.PROCESSING
        and job.lease_token == token
        and job.lease_until
        and job.lease_until > now
    )


def _claim_is_current(
    job: IgConversationAnalysisJob,
    *,
    token: str,
    claimed_watermark: int,
    claimed_revision: int,
    now,
) -> bool:
    """Return whether this exact worker still owns an unexpired claim."""
    return bool(
        _lease_is_owned(job, token=token, now=now)
        and int(job.watermark_message_id or 0) == claimed_watermark
        and int(job.revision or 0) == claimed_revision
        and int(job.claimed_watermark_message_id or 0) == claimed_watermark
        and int(job.claimed_revision or 0) == claimed_revision
    )


def _job_covers_required_analysis(
    job: IgConversationAnalysisJob | None,
    *,
    watermark: int,
    required_state_fingerprint: str,
) -> bool:
    """Protect an already queued/in-flight revision and its retry backoff."""
    return bool(
        job
        and job.status in {
            IgConversationAnalysisJob.Status.PENDING,
            IgConversationAnalysisJob.Status.PROCESSING,
            IgConversationAnalysisJob.Status.FAILED,
        }
        and int(job.watermark_message_id or 0) >= watermark
        and int(job.revision or 0) > int(job.analyzed_revision or 0)
        and job.required_state_fingerprint == required_state_fingerprint
    )


def _reconcile_candidate_is_eligible(
    *,
    cutoff,
    latest_message_at,
    job_created_at=None,
    truth_changed_at=None,
    include_history: bool = False,
) -> bool:
    """Keep automatic repair post-rollout unless history was explicitly allowed."""
    if include_history:
        return True
    # A recovery job can be created today for a years-old imported message.
    # Its creation time is therefore not business evidence and must not unlock
    # historical Gemini work. Only a post-cutoff conversation event or an
    # explicit payment/order truth change may do that.
    return any(
        value is not None and value >= cutoff
        for value in (latest_message_at, truth_changed_at)
    )


def _historical_backfill_allowed(settings_obj: InstagramBotSettings) -> bool:
    if not settings_obj.analysis_backfill_enabled:
        return False
    from management.services.gemini_keys import ALL_KEYS, key_project_groups

    mapping = key_project_groups()
    return bool(ALL_KEYS) and all(alias in mapping for alias in ALL_KEYS)


def _historical_reconcile_job(job: IgConversationAnalysisJob, watermark: int) -> bool:
    """Return whether a queued reconcile job is old recovery data, not live work."""
    if job.trigger not in HISTORICAL_ANALYSIS_TRIGGERS:
        return False
    settings_obj = InstagramBotSettings.load()
    if _historical_backfill_allowed(settings_obj):
        return False
    outstanding_events = list(
        InstagramBotMessage.objects.filter(
            client_id=job.client_id,
            id__gt=max(0, int(job.analyzed_watermark_message_id or 0)),
            id__lte=max(0, int(watermark or 0)),
            role__in=[
                InstagramBotMessage.Role.USER,
                InstagramBotMessage.Role.MANAGER,
            ],
        )
        .exclude(status=InstagramBotMessage.Status.FAILED)
        .annotate(event_at=Coalesce("provider_created_at", "created_at"))
        .values_list("event_at", flat=True)
    )
    if not outstanding_events and watermark:
        anchor_event = (
            InstagramBotMessage.objects.filter(
                client_id=job.client_id,
                pk=watermark,
                role__in=[
                    InstagramBotMessage.Role.USER,
                    InstagramBotMessage.Role.MANAGER,
                ],
            )
            .annotate(event_at=Coalesce("provider_created_at", "created_at"))
            .values_list("event_at", flat=True)
            .first()
        )
        if anchor_event is not None:
            outstanding_events = [anchor_event]
    if any(
        event_at is None or event_at >= settings_obj.analysis_reconcile_after
        for event_at in outstanding_events
    ):
        return False
    truth_changed_at = _latest_truth_change(job.client)
    return not (
        truth_changed_at
        and truth_changed_at >= settings_obj.analysis_reconcile_after
    )


def _latest_truth_change(client: IgClient):
    deal_times = client.deals.aggregate(
        payment_truth_updated_at=Max("payment_truth_updated_at"),
        order_truth_updated_at=Max("order_truth_updated_at"),
    )
    projection_updated_at = client.payment_projections.aggregate(
        updated_at=Max("updated_at")
    )["updated_at"]
    manager_decision_created_at = client.payment_review_decisions.aggregate(
        created_at=Max("created_at")
    )["created_at"]
    episode_updated_at = client.commercial_episodes.aggregate(
        updated_at=Max("updated_at")
    )["updated_at"]
    values = [
        deal_times["payment_truth_updated_at"],
        deal_times["order_truth_updated_at"],
        projection_updated_at,
        manager_decision_created_at,
        episode_updated_at,
    ]
    return max((value for value in values if value is not None), default=None)


def _rules_window_skip_reason(
    client: IgClient,
    *,
    watermark: int,
    analyzed_watermark: int,
) -> str:
    changed_message_ids = list(
        InstagramBotMessage.objects.filter(
            client_id=client.pk,
            id__gt=max(0, int(analyzed_watermark or 0)),
            id__lte=max(0, int(watermark or 0)),
            role__in=[
                InstagramBotMessage.Role.USER,
                InstagramBotMessage.Role.MANAGER,
            ],
        )
        .exclude(status=InstagramBotMessage.Status.FAILED)
        .values_list("id", flat=True)
    )
    if not changed_message_ids:
        return ""
    latest_by_message = {}
    for message_id, interaction_type in (
        client.analysis_snapshots.filter(
            analysis_model="rules",
            last_analyzed_message_id__in=changed_message_ids,
        )
        .order_by("id")
        .values_list("last_analyzed_message_id", "interaction_type")
    ):
        latest_by_message[int(message_id)] = interaction_type
    if latest_by_message.get(changed_message_ids[-1]) == (
        IgConversationAnalysisSnapshot.InteractionType.OPT_OUT
    ):
        return "opt_out"
    if len(latest_by_message) == len(changed_message_ids) and all(
        latest_by_message.get(message_id)
        == IgConversationAnalysisSnapshot.InteractionType.REACTION_ONLY
        for message_id in changed_message_ids
    ):
        return "reaction_only"
    return ""


def _skip_reason(
    client: IgClient,
    *,
    watermark: int = 0,
    analyzed_watermark: int = 0,
) -> str:
    if client.hidden_at:
        return "hidden"
    if client.is_blocked or client.stage == IgClient.Stage.SPAM:
        return "spam_or_blocked"
    if client.opted_out_at and (
        not client.opted_in_at or client.opted_in_at < client.opted_out_at
    ):
        return "opt_out"
    return _rules_window_skip_reason(
        client,
        watermark=watermark,
        analyzed_watermark=analyzed_watermark,
    )


def _conversation(
    client_id: int,
    watermark: int,
    *,
    on_media_progress=None,
) -> tuple[list[dict], dict[int, dict], list[dict]]:
    rows = _analysis_message_rows(client_id, watermark)
    from management.services.instagram_bot import _capture_message_media

    # Keep media acquisition bounded by the same eight-image provider budget;
    # an old client can contain many webhook rows and must not consume the
    # entire analysis lease before Gemini is reached.
    capture_budget = 8
    for row in reversed(rows):
        if capture_budget <= 0:
            break
        entries = row.attachment_media or []
        needs_capture = (
            not entries and row.source == "webhook"
        ) or any(
            isinstance(item, dict)
            and item.get("provenance") == "live_webhook"
            and item.get("status") != "owned"
            for item in entries
        )
        if not needs_capture:
            continue
        before_attempts = sum(
            int(item.get("capture_attempts") or 0)
            for item in entries
            if isinstance(item, dict)
        )
        _capture_message_media(
            row,
            limit=capture_budget,
            on_progress=on_media_progress,
        )
        row.refresh_from_db(fields=["attachment_media"])
        after_attempts = sum(
            int(item.get("capture_attempts") or 0)
            for item in (row.attachment_media or [])
            if isinstance(item, dict)
        )
        capture_budget -= max(0, after_attempts - before_attempts)
    total = 0
    classify_media_items = None
    media_expected = any(
        bool(row.attachments or row.attachment_media)
        for row in rows
    )
    media_error_kind = ""
    try:
        from management.services.ig_payment_review import (
            _augment_messages_with_raw_media,
            classify_media_items,
        )

        client = IgClient.objects.get(pk=client_id)
        raw_rows = [
            {
                "id": row.pk,
                "mid": row.mid or "",
                "text": row.text or "",
                "attachments": row.attachments or "",
                "attachment_media": row.attachment_media or [],
                "source": row.source or "",
                "role": row.role,
                "created_at": row.created_at,
            }
            for row in rows
        ]
        augmented_by_id = {
            int(item.get("id")): item
            for item in _augment_messages_with_raw_media(client, raw_rows)
            if str(item.get("id") or "").isdigit()
        }
    except Exception:
        augmented_by_id = {}
        if media_expected:
            media_error_kind = "media_recovery_exception"
    rendered: list[dict] = []
    by_id: dict[int, dict] = {}
    media_sources: list[dict] = []
    for row in reversed(rows):
        text = " ".join((row.text or "").split())
        augmented = augmented_by_id.get(row.pk) or {}
        raw_media = augmented.get("media") if isinstance(augmented.get("media"), list) else []
        if not text and not row.attachments and not raw_media:
            continue
        remaining = MAX_TRANSCRIPT_CHARS - total
        if remaining <= 0:
            break
        text = text[:remaining]
        role = {
            InstagramBotMessage.Role.USER: "user",
            InstagramBotMessage.Role.MODEL: "model",
            InstagramBotMessage.Role.MANAGER: "manager",
        }.get(row.role, "system")
        item = {"message_id": row.pk, "role": role, "text": text}
        if raw_media:
            try:
                if classify_media_items is None:
                    raise RuntimeError("media_classifier_unavailable")
                semantic_media = classify_media_items(
                    text,
                    raw_media,
                    payment_context=bool(re.search(
                        r"\b(оплат\w*|платіж\w*|платеж\w*|чек\w*|квитанц\w*|receipt|paid)\b",
                        text,
                        re.IGNORECASE,
                    )),
                )
            except Exception:
                semantic_media = []
                media_error_kind = media_error_kind or "media_classifier_exception"
            if semantic_media:
                manager_media = role == "manager"
                item["media"] = []
                for media_index, media in enumerate(semantic_media[:8]):
                    if media.get("url"):
                        media_sources.append({
                            "url": str(media.get("url") or "")[:1200],
                            "message_id": row.pk,
                            "media_index": media_index,
                            "provenance": str(media.get("provenance") or "")[:32],
                            "status": str(media.get("status") or "")[:32],
                            "storage_name": str(media.get("storage_name") or "")[:500],
                            "local_url": str(media.get("local_url") or "")[:1200],
                            "mime": str(media.get("mime") or "")[:64],
                            "error_kind": str(media.get("error_kind") or "")[:64],
                        })
                    item["media"].append({
                        "role": "manager_reference" if manager_media else str(media.get("role") or "other")[:32],
                        "intent": "manager_reference" if manager_media else str(media.get("intent") or "unknown")[:40],
                        "actionable": False if manager_media else bool(media.get("actionable")),
                        "payment_evidence": False if manager_media else bool(media.get("payment_evidence")),
                        "catalog_match_allowed": False if manager_media else bool(media.get("catalog_match_allowed")),
                        "source_media_id": str(media.get("ig_post_media_id") or "")[:80],
                    })
        rendered.append(item)
        by_id[row.pk] = item
        total += len(text)
    rendered.reverse()
    bounded_sources = media_sources[:8]
    if media_error_kind:
        bounded_sources.append({"media_error_kind": media_error_kind})
    return rendered, by_id, bounded_sources


def _decimal_01(value, default: str) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        parsed = Decimal(default)
    return max(Decimal("0"), min(Decimal("1"), parsed)).quantize(Decimal("0.0001"))


def _normalize(parsed: dict, by_id: dict[int, dict], *, verified_payment: bool) -> dict:
    parsed = parsed if isinstance(parsed, dict) else {}
    valid_types = {value for value, _label in IgConversationAnalysisSnapshot.InteractionType.choices}
    valid_bands = {value for value, _label in IgConversationAnalysisSnapshot.Band.choices}
    interaction_type = str(parsed.get("interaction_type") or "unknown")
    band = str(parsed.get("score_band") or "cold")
    if interaction_type not in valid_types:
        interaction_type = IgConversationAnalysisSnapshot.InteractionType.UNKNOWN
    if band not in valid_bands:
        band = IgConversationAnalysisSnapshot.Band.COLD
    probability = _decimal_01(parsed.get("purchase_probability"), "0")
    confidence = _decimal_01(parsed.get("confidence"), "0")
    raw_repeat = parsed.get("repeat_intent")
    repeat_intent = {}
    if isinstance(raw_repeat, dict):
        repeat_kind = str(raw_repeat.get("kind") or "").strip()[:32]
        repeat_confidence = _decimal_01(raw_repeat.get("confidence"), "0")
        valid_repeat_kinds = {"explicit_more", "reorder", "gift", "another_recipient"}
        repeat_evidence_ids = []
        for value in raw_repeat.get("evidence_message_ids") or []:
            try:
                message_id = int(value)
            except (TypeError, ValueError):
                continue
            source = by_id.get(message_id)
            source_text = str((source or {}).get("text") or "")
            if (
                source
                and source.get("role") == "user"
                and _has_explicit_repeat_evidence(source_text)
                and message_id not in repeat_evidence_ids
            ):
                repeat_evidence_ids.append(message_id)
        if (
            repeat_kind in valid_repeat_kinds
            and repeat_confidence >= Decimal("0.7000")
            and repeat_evidence_ids
        ):
            repeat_intent = {
                "kind": repeat_kind,
                "confidence": repeat_confidence,
                "evidence_message_ids": repeat_evidence_ids[:20],
            }
    uncertainties = [str(value)[:160] for value in (parsed.get("uncertainties") or []) if str(value).strip()][:20]
    if interaction_type == IgConversationAnalysisSnapshot.InteractionType.CUSTOM_PRINT:
        from management.services.bot_sales_classifier import is_explicit_custom_print_request

        has_user_custom_evidence = any(
            source.get("role") == "user"
            and is_explicit_custom_print_request(source.get("text") or "")
            for source in by_id.values()
            if isinstance(source, dict)
        )
        if not has_user_custom_evidence:
            interaction_type = IgConversationAnalysisSnapshot.InteractionType.INFORMATION_ONLY
            uncertainties.append("custom_print_user_evidence_missing")

    if (
        band == IgConversationAnalysisSnapshot.Band.PAID
        or interaction_type
        == IgConversationAnalysisSnapshot.InteractionType.PAID_ORDER_WAITING
    ):
        # F-SCORE-003: понижение имеет смысл, пока «оплачено» — это утверждение
        # модели: слова клиента деньгами не являются. Но когда факт оплаты
        # подтверждён самой системой, понижать нечего — мы затирали бы
        # собственную истину, и клиент навсегда оставался «в процессі оплати».
        # На проде это и наблюдалось: `score_band='paid'` — 0 записей из 1792.
        if verified_payment:
            band = IgConversationAnalysisSnapshot.Band.PAID
            # Only a claim about the payment itself is replaced. A more specific
            # type the model already resolved — an exchange, a return, a real
            # complaint — carries strictly more information than
            # «оплачено / очікує товар» and must survive (IMP-015).
            if interaction_type in {
                IgConversationAnalysisSnapshot.InteractionType.UNKNOWN,
                IgConversationAnalysisSnapshot.InteractionType.PAYMENT_PENDING,
                IgConversationAnalysisSnapshot.InteractionType.PAID_ORDER_WAITING,
            }:
                interaction_type = (
                    IgConversationAnalysisSnapshot.InteractionType.PAID_ORDER_WAITING
                )
        else:
            band = IgConversationAnalysisSnapshot.Band.CHECKOUT
            interaction_type = (
                IgConversationAnalysisSnapshot.InteractionType.PAYMENT_PENDING
            )
            probability = min(probability, Decimal("0.9500"))
            uncertainties.append("payment_unverified")

    evidence = []
    for raw in parsed.get("evidence") or []:
        if not isinstance(raw, dict):
            continue
        try:
            message_id = int(raw.get("message_id"))
        except (TypeError, ValueError):
            continue
        source = by_id.get(message_id)
        quote = " ".join(str(raw.get("quote") or "").split())[:300]
        if not source or not quote or quote.casefold() not in source["text"].casefold():
            continue
        evidence.append({
            "message_id": message_id,
            "source_role": source["role"],
            "quote": quote,
            "claim": str(raw.get("claim") or "")[:300],
        })
        if len(evidence) >= 20:
            break
    if not evidence:
        uncertainties.append("evidence_unverified")
    return {
        "interaction_type": interaction_type,
        "score_band": band,
        "purchase_probability": probability,
        "confidence": confidence,
        "evidence": evidence,
        "uncertainties": list(dict.fromkeys(uncertainties))[:20],
        "repeat_intent": repeat_intent,
    }


def _finish_skip(
    job_id: int,
    token: str,
    watermark: int,
    claimed_revision: int,
    reason: str,
    now,
) -> str:
    with transaction.atomic():
        job = IgConversationAnalysisJob.objects.select_for_update().filter(
            pk=job_id,
            status=IgConversationAnalysisJob.Status.PROCESSING,
            lease_token=token,
        ).first()
        finalized_at = timezone.now()
        if not job or not _lease_is_owned(job, token=token, now=finalized_at):
            return "superseded"
        if (
            int(job.claimed_watermark_message_id or 0) != watermark
            or int(job.claimed_revision or 0) != claimed_revision
        ):
            return "superseded"
        if (
            int(job.watermark_message_id or 0) != watermark
            or int(job.revision or 0) != claimed_revision
        ):
            job.status = IgConversationAnalysisJob.Status.PENDING
            job.lease_token = ""
            job.lease_until = None
            job.claimed_watermark_message_id = 0
            job.claimed_revision = 0
            job.attempts = 0
            job.next_attempt_at = max(job.due_at, finalized_at)
            job.save(update_fields=[
                "status", "lease_token", "lease_until",
                "claimed_watermark_message_id", "claimed_revision", "attempts",
                "next_attempt_at", "updated_at",
            ])
            return "superseded"
        job.analyzed_watermark_message_id = max(
            int(job.analyzed_watermark_message_id or 0), watermark
        )
        job.analyzed_revision = max(int(job.analyzed_revision or 0), claimed_revision)
        job.lease_token = ""
        job.lease_until = None
        job.claimed_watermark_message_id = 0
        job.claimed_revision = 0
        job.skip_reason = reason
        job.status = IgConversationAnalysisJob.Status.SKIPPED
        job.save(update_fields=[
            "analyzed_watermark_message_id", "analyzed_revision", "lease_token",
            "lease_until", "claimed_watermark_message_id", "claimed_revision",
            "skip_reason", "status", "next_attempt_at", "updated_at",
        ])
        return "skipped"


def _finish_failure(
    job: IgConversationAnalysisJob,
    token: str,
    claimed_watermark: int,
    claimed_revision: int,
    exc: Exception,
    now,
) -> None:
    with transaction.atomic():
        current = IgConversationAnalysisJob.objects.select_for_update().filter(
            pk=job.pk,
            status=IgConversationAnalysisJob.Status.PROCESSING,
            lease_token=token,
        ).first()
        if not current or not _lease_is_owned(current, token=token, now=now):
            return
        if (
            int(current.claimed_watermark_message_id or 0) != claimed_watermark
            or int(current.claimed_revision or 0) != claimed_revision
        ):
            return
        current.lease_token = ""
        current.lease_until = None
        current.claimed_watermark_message_id = 0
        current.claimed_revision = 0
        current.last_error = f"{type(exc).__name__}: {exc}"[:1000]
        if (
            int(current.watermark_message_id or 0) > claimed_watermark
            or int(current.revision or 0) > claimed_revision
        ):
            current.status = IgConversationAnalysisJob.Status.PENDING
            current.attempts = 0
            current.next_attempt_at = max(current.due_at, now)
        else:
            attempt = max(1, int(current.attempts or 1))
            terminal = attempt >= MAX_ATTEMPTS
            delay = RETRY_DELAYS[min(attempt - 1, len(RETRY_DELAYS) - 1)]
            current.status = (
                IgConversationAnalysisJob.Status.FAILED
                if terminal
                else IgConversationAnalysisJob.Status.PENDING
            )
            current.next_attempt_at = now + timedelta(seconds=delay)
        current.save(update_fields=[
            "status", "attempts", "next_attempt_at", "lease_token", "lease_until",
            "claimed_watermark_message_id", "claimed_revision", "last_error", "updated_at",
        ])


def _record_media_phase(
    job_id: int,
    token: str,
    *,
    phase: str,
    error_kind: str = "",
    started_at=None,
    completed_at=None,
    item_count: int = 0,
) -> bool:
    now = timezone.now()
    updates = {
        "media_phase": phase,
        "media_error_kind": str(error_kind or "")[:64],
        "media_item_count": max(0, min(int(item_count or 0), 65535)),
        "lease_until": now + timedelta(seconds=LEASE_SECONDS),
        "updated_at": now,
    }
    if started_at is not None:
        updates["media_started_at"] = started_at
    if completed_at is not None:
        updates["media_completed_at"] = completed_at
    return bool(
        IgConversationAnalysisJob.objects.filter(
            pk=job_id,
            status=IgConversationAnalysisJob.Status.PROCESSING,
            lease_token=token,
            lease_until__gt=now,
        ).update(**updates)
    )


def _process_claim(
    job: IgConversationAnalysisJob,
    watermark: int,
    claimed_revision: int,
    token: str,
    now,
) -> str:
    client = IgClient.objects.get(pk=job.client_id)
    analyzed_watermark = int(job.analyzed_watermark_message_id or 0)
    if _historical_reconcile_job(job, watermark):
        return _finish_skip(
            job.pk,
            token,
            watermark,
            claimed_revision,
            "historical_reconcile",
            now,
        )
    reason = _skip_reason(
        client,
        watermark=watermark,
        analyzed_watermark=analyzed_watermark,
    )
    if reason:
        return _finish_skip(job.pk, token, watermark, claimed_revision, reason, now)
    media_started_at = timezone.now()
    if not _record_media_phase(
        job.pk,
        token,
        phase=IgConversationAnalysisJob.MediaPhase.ACQUIRING,
        started_at=media_started_at,
    ):
        return "superseded"
    def media_heartbeat() -> bool:
        return _record_media_phase(
            job.pk,
            token,
            phase=IgConversationAnalysisJob.MediaPhase.ACQUIRING,
            started_at=media_started_at,
        )

    try:
        transcript, by_id, media_sources = _conversation(
            client.pk,
            watermark,
            on_media_progress=media_heartbeat,
        )
    except Exception:
        _record_media_phase(
            job.pk,
            token,
            phase=IgConversationAnalysisJob.MediaPhase.FAILED,
            error_kind="media_exception",
            started_at=media_started_at,
            completed_at=timezone.now(),
        )
        raise
    if not transcript:
        return _finish_skip(
            job.pk, token, watermark, claimed_revision, "empty_conversation", now
        )
    initial_truth_state = _required_truth_state(client)
    media_images = []
    image_labels = []
    media_error_kind = next((
        str(source.get("media_error_kind") or "")[:64]
        for source in media_sources
        if isinstance(source, dict) and source.get("media_error_kind")
    ), "")
    media_sources = [
        source for source in media_sources
        if isinstance(source, dict) and source.get("url")
    ]
    try:
        from management.services.instagram_bot import _collect_media_images

        seen_urls = set()
        for source in media_sources:
            if not media_heartbeat():
                return "superseded"
            url = str(source.get("url") or "")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            collected = _collect_media_images([source], limit=1)
            image = collected[0] if collected else None
            if image:
                image_labels.append({
                    "inline_image_index": len(media_images),
                    "message_id": source.get("message_id"),
                    "media_index": source.get("media_index"),
                })
                media_images.append(image)
            elif source.get("provenance") != "historical_import":
                media_error_kind = str(
                    source.get("error_kind") or "media_unavailable"
                )[:64]
            if len(media_images) >= 8:
                break
    except Exception:
        media_images = []
        image_labels = []
        media_error_kind = "media_exception"
    if media_error_kind:
        media_phase = IgConversationAnalysisJob.MediaPhase.FAILED
    elif media_sources and not media_images:
        media_phase = IgConversationAnalysisJob.MediaPhase.METADATA_ONLY
    else:
        media_phase = IgConversationAnalysisJob.MediaPhase.READY
    if not _record_media_phase(
        job.pk,
        token,
        phase=media_phase,
        error_kind=media_error_kind,
        started_at=media_started_at,
        completed_at=timezone.now(),
        item_count=len(media_sources),
    ):
        return "superseded"
    if _customer_reply_work_waiting():
        if _defer_claim_for_customer_reply(job.pk, token, now=timezone.now()):
            return "deferred"
        return "superseded"
    result = gemini_generate_json(
        SYSTEM_PROMPT,
        json.dumps({
            "verified_payment": initial_truth_state["verified_payment"],
            "truth_state": initial_truth_state,
            "watermark_message_id": watermark,
            "conversation": transcript,
        }, ensure_ascii=False, default=str),
        role="management",
        max_output_tokens=4096,
        reasoning_task="conversation_reanalysis",
        images=media_images,
        image_labels=image_labels,
    )
    meta = result.get("meta") if isinstance(result.get("meta"), dict) else {}
    model = str(result.get("model") or meta.get("used_model") or "unknown")[:80]
    # Revalidate ownership and every hard policy/truth after the slow provider
    # call. Keep the same client -> job lock order used by ingress scheduling.
    with transaction.atomic():
        client = IgClient.objects.select_for_update().get(pk=job.client_id)
        current_job = (
            IgConversationAnalysisJob.objects.select_for_update()
            .filter(pk=job.pk)
            .first()
        )
        finalized_at = timezone.now()
        if not current_job or not _lease_is_owned(
            current_job,
            token=token,
            now=finalized_at,
        ):
            return "superseded"
        if not _claim_is_current(
            current_job,
            token=token,
            claimed_watermark=watermark,
            claimed_revision=claimed_revision,
            now=finalized_at,
        ):
            current_job.status = IgConversationAnalysisJob.Status.PENDING
            current_job.lease_token = ""
            current_job.lease_until = None
            current_job.claimed_watermark_message_id = 0
            current_job.claimed_revision = 0
            current_job.attempts = 0
            current_job.next_attempt_at = max(current_job.due_at, finalized_at)
            current_job.save(update_fields=[
                "status",
                "lease_token",
                "lease_until",
                "claimed_watermark_message_id",
                "claimed_revision",
                "attempts",
                "next_attempt_at",
                "updated_at",
            ])
            return "superseded"
        # Match paid-order materialization: projection -> deal -> linked order.
        list(
            client.payment_projections.select_for_update()
            .order_by("pk")
            .values_list("pk", flat=True)
        )
        locked_deals = list(
            client.deals.select_for_update()
            .order_by("pk")
            .values("pk", "order_id")
        )
        order_ids = sorted({
            int(row["order_id"])
            for row in locked_deals
            if row.get("order_id")
        })
        if order_ids:
            from orders.models import Order

            list(
                Order.objects.select_for_update()
                .filter(pk__in=order_ids)
                .order_by("pk")
                .values_list("pk", flat=True)
            )
        reason = _skip_reason(
            client,
            watermark=watermark,
            analyzed_watermark=int(
                current_job.analyzed_watermark_message_id or 0
            ),
        )
        if reason:
            return _finish_skip(
                job.pk,
                token,
                watermark,
                claimed_revision,
                reason,
                finalized_at,
            )
        final_truth_state = _required_truth_state(client)
        final_fingerprint = _fingerprint_for_truth(
            client.pk,
            watermark,
            final_truth_state,
        )
        if final_truth_state != initial_truth_state:
            order_truth_changed = (
                final_truth_state["order_truth"] != initial_truth_state["order_truth"]
            )
            current_job.revision = int(current_job.revision or 0) + 1
            current_job.required_state_fingerprint = final_fingerprint
            current_job.trigger = "order_truth" if order_truth_changed else "payment_truth"
            current_job.status = IgConversationAnalysisJob.Status.PENDING
            current_job.lease_token = ""
            current_job.lease_until = None
            current_job.claimed_watermark_message_id = 0
            current_job.claimed_revision = 0
            current_job.attempts = 0
            current_job.next_attempt_at = finalized_at
            current_job.save(update_fields=[
                "revision", "required_state_fingerprint", "trigger", "status",
                "lease_token", "lease_until", "claimed_watermark_message_id",
                "claimed_revision", "attempts", "next_attempt_at", "updated_at",
            ])
            return "superseded"
        verified_payment = bool(final_truth_state["verified_payment"])
        normalized = _normalize(
            result.get("parsed"), by_id, verified_payment=verified_payment
        )
        repeat_intent = normalized["repeat_intent"]
        repeat_intent_snapshot = (
            {
                **repeat_intent,
                "confidence": str(repeat_intent["confidence"]),
            }
            if repeat_intent
            else {}
        )
        # Analysis is descriptive only. Operational repeat-purchase state is
        # materialized by the owned action consumer after this snapshot commits.
        commercial_episode = client.commercial_episodes.filter(open_slot=1).first()
        final_truth_state = _required_truth_state(client)
        final_fingerprint = _fingerprint_for_truth(
            client.pk,
            watermark,
            final_truth_state,
        )
        snapshot, snapshot_created = IgConversationAnalysisSnapshot.objects.get_or_create(
            dedupe_key=(
                f"ai:{ANALYSIS_PROMPT_VERSION}:{client.pk}:{watermark}:r{claimed_revision}"
            ),
            defaults={
                "client": client,
                "last_analyzed_message_id": watermark,
                "score_band": normalized["score_band"],
                "interaction_type": normalized["interaction_type"],
                "purchase_probability": normalized["purchase_probability"],
                "confidence": normalized["confidence"],
                "evidence": normalized["evidence"],
                "uncertainties": normalized["uncertainties"],
                "repeat_intent": repeat_intent_snapshot,
                "commercial_episode": commercial_episode,
                "analysis_model": model,
                "analysis_prompt_version": ANALYSIS_PROMPT_VERSION,
                "required_state_fingerprint": final_fingerprint,
                "key_alias": str(meta.get("key") or "")[:32],
                "reasoning_task": str(meta.get("reasoning_task") or "conversation_reanalysis")[:64],
                "reasoning_level": str(meta.get("reasoning_level") or "")[:16],
                "reasoning_policy_version": str(meta.get("reasoning_policy_version") or "")[:32],
                "thoughts_tokens": max(0, int(meta.get("thoughts_tokens") or 0)),
                "candidates_tokens": max(0, int(meta.get("candidates_tokens") or 0)),
                "trigger": (job.trigger or "message")[:32],
                "analysis_latency_ms": max(0, int(meta.get("latency_ms") or 0)),
                "analyzed_at": finalized_at,
            },
        )
        if (
            not snapshot_created
            and commercial_episode
            and not snapshot.commercial_episode_id
        ):
            snapshot.commercial_episode = commercial_episode
            snapshot.save(update_fields=["commercial_episode"])
        if repeat_intent and verified_payment:
            from management.services.ig_analysis_events import (
                publish_repeat_episode_event,
            )

            publish_repeat_episode_event(
                client=client,
                snapshot=snapshot,
                repeat_intent=repeat_intent,
                analysis_model=model,
                analysis_prompt_version=ANALYSIS_PROMPT_VERSION,
                required_state_fingerprint=final_fingerprint,
            )
        current_job.analysis_model = model
        current_job.analysis_prompt_version = ANALYSIS_PROMPT_VERSION
        current_job.required_state_fingerprint = final_fingerprint
        current_job.key_alias = str(meta.get("key") or "")[:32]
        current_job.reasoning_task = str(
            meta.get("reasoning_task") or "conversation_reanalysis"
        )[:64]
        current_job.reasoning_level = str(meta.get("reasoning_level") or "")[:16]
        current_job.reasoning_policy_version = str(
            meta.get("reasoning_policy_version") or ""
        )[:32]
        current_job.thoughts_tokens = max(0, int(meta.get("thoughts_tokens") or 0))
        current_job.candidates_tokens = max(0, int(meta.get("candidates_tokens") or 0))
        current_job.analysis_latency_ms = max(0, int(meta.get("latency_ms") or 0))
        current_job.analyzed_at = finalized_at
        current_job.analyzed_watermark_message_id = max(
            int(current_job.analyzed_watermark_message_id or 0), watermark
        )
        current_job.analyzed_revision = max(
            int(current_job.analyzed_revision or 0), claimed_revision
        )
        current_job.lease_token = ""
        current_job.lease_until = None
        current_job.claimed_watermark_message_id = 0
        current_job.claimed_revision = 0
        current_job.attempts = 0
        current_job.last_error = ""
        if (
            int(current_job.watermark_message_id or 0) > watermark
            or int(current_job.revision or 0) > claimed_revision
        ):
            current_job.status = IgConversationAnalysisJob.Status.PENDING
            current_job.next_attempt_at = max(current_job.due_at, finalized_at)
        else:
            current_job.status = IgConversationAnalysisJob.Status.DONE
            current_job.next_attempt_at = finalized_at
        current_job.save(update_fields=[
            "analysis_model",
            "analysis_prompt_version",
            "required_state_fingerprint",
            "key_alias",
            "reasoning_task",
            "reasoning_level",
            "reasoning_policy_version",
            "thoughts_tokens",
            "candidates_tokens",
            "analysis_latency_ms",
            "analyzed_at",
            "analyzed_watermark_message_id",
            "analyzed_revision",
            "lease_token",
            "lease_until",
            "claimed_watermark_message_id",
            "claimed_revision",
            "attempts",
            "last_error",
            "status",
            "next_attempt_at",
            "updated_at",
        ])
    return "done"


def _customer_reply_work_waiting() -> bool:
    if not InstagramBotSettings.load().is_enabled:
        return False
    now = timezone.now()
    cutoff = now - timedelta(seconds=REPLY_PROCESSING_GRACE_SECONDS)
    active_opt_out = Q(
        client__opted_out_at__isnull=False,
    ) & (
        Q(client__opted_in_at__isnull=True)
        | Q(client__opted_in_at__lt=F("client__opted_out_at"))
    )
    processing = Q(status=InstagramBotMessage.Status.PROCESSING) & (
        Q(processing_started_at__isnull=True)
        | Q(processing_started_at__gte=cutoff)
    )
    eligible_client = Q(client_id__isnull=True) | Q(
        role=InstagramBotMessage.Role.USER,
        client__hidden_at__isnull=True,
        client__is_blocked=False,
        client__bot_paused=False,
    )
    return InstagramBotMessage.objects.filter(
        role=InstagramBotMessage.Role.USER,
    ).filter(eligible_client).exclude(
        client__stage=IgClient.Stage.SPAM,
    ).exclude(
        active_opt_out,
    ).filter(
        Q(status=InstagramBotMessage.Status.PENDING) | processing,
    ).exists()


def _defer_claim_for_customer_reply(job_id: int, token: str, now=None) -> bool:
    """Return a claimed analysis job to pending without consuming an attempt."""
    now = now or timezone.now()
    with transaction.atomic():
        job = IgConversationAnalysisJob.objects.select_for_update().filter(
            pk=job_id,
            status=IgConversationAnalysisJob.Status.PROCESSING,
            lease_token=token,
        ).first()
        if not job:
            return False
        job.status = IgConversationAnalysisJob.Status.PENDING
        job.lease_token = ""
        job.lease_until = None
        job.claimed_watermark_message_id = 0
        job.claimed_revision = 0
        job.attempts = 0
        job.last_error = "deferred_for_live_reply"
        job.next_attempt_at = max(job.due_at, now)
        job.save(update_fields=[
            "status", "lease_token", "lease_until",
            "claimed_watermark_message_id", "claimed_revision", "attempts",
            "last_error", "next_attempt_at", "updated_at",
        ])
        return True


def process_due_analysis(*, limit: int = 2, now=None) -> dict:
    """Claim and analyze due jobs independently from all customer reply flags."""
    counts = {"done": 0, "failed": 0, "skipped": 0, "superseded": 0}
    for _unused in range(max(0, min(int(limit), 10))):
        if _customer_reply_work_waiting():
            break
        claim_now = now or timezone.now()
        _reclaim_stale(claim_now)
        claimed = _claim_due(claim_now)
        if not claimed:
            break
        job, watermark, claimed_revision, token = claimed
        if _customer_reply_work_waiting():
            _defer_claim_for_customer_reply(job.pk, token, now=claim_now)
            break
        try:
            outcome = _process_claim(
                job, watermark, claimed_revision, token, claim_now
            )
            if outcome == "deferred":
                break
            counts[outcome] += 1
        except Exception as exc:
            failure_now = now or timezone.now()
            _finish_failure(
                job,
                token,
                watermark,
                claimed_revision,
                exc,
                failure_now,
            )
            counts["failed"] += 1
    return counts


def reconcile_analysis_jobs(*, limit: int = 500, now=None) -> dict:
    """Queue changed or prompt-stale conversations without invoking Gemini."""
    now = now or timezone.now()
    bounded_limit = max(1, min(int(limit), 5000))
    settings_obj = InstagramBotSettings.load()
    cursor = int(settings_obj.analysis_reconcile_cursor or 0)
    cutoff = settings_obj.analysis_reconcile_after
    include_history = _historical_backfill_allowed(settings_obj)
    base = (
        InstagramBotMessage.objects.filter(
            client_id__isnull=False,
            role__in=[InstagramBotMessage.Role.USER, InstagramBotMessage.Role.MANAGER],
        )
        .values("client_id")
        .annotate(
            latest_message_at=Max(Coalesce("provider_created_at", "created_at")),
        )
        .order_by("client_id")
    )
    latest_rows = list(base.filter(client_id__gt=cursor)[:bounded_limit])
    if not latest_rows and cursor:
        cursor = 0
        latest_rows = list(base[:bounded_limit])
    queued = 0
    unchanged = 0
    historical_blocked = 0
    hidden_excluded = 0
    for row in latest_rows:
        client_id = int(row["client_id"])
        job = IgConversationAnalysisJob.objects.filter(client_id=client_id).first()
        client = IgClient.objects.filter(pk=client_id).first()
        if not client or client.hidden_at:
            hidden_excluded += 1
            continue
        message = (
            InstagramBotMessage.objects.filter(
                client_id=client_id,
                role__in=[
                    InstagramBotMessage.Role.USER,
                    InstagramBotMessage.Role.MANAGER,
                ],
            )
            .annotate(event_at=Coalesce("provider_created_at", "created_at"))
            .order_by("-event_at", "-id")
            .first()
        )
        if not message:
            unchanged += 1
            continue
        watermark = int(message.pk)
        truth_changed_at = _latest_truth_change(client) if client else None
        if not _reconcile_candidate_is_eligible(
            cutoff=cutoff,
            latest_message_at=row.get("latest_message_at"),
            job_created_at=getattr(job, "created_at", None),
            truth_changed_at=truth_changed_at,
            include_history=include_history,
        ):
            historical_blocked += 1
            continue
        latest_ai = (
            IgConversationAnalysisSnapshot.objects.filter(client_id=client_id)
            .exclude(analysis_model="rules")
            .order_by("-id")
            .values(
                "last_analyzed_message_id",
                "analysis_prompt_version",
                "required_state_fingerprint",
                "score_band",
            )
            .first()
        )
        required_state_fingerprint = (
            _required_state_fingerprint(client, watermark) if client else ""
        )
        payment_truth_matches = bool(
            latest_ai
            and latest_ai.get("required_state_fingerprint")
            == required_state_fingerprint
        )
        skipped_current = bool(
            job
            and job.status == IgConversationAnalysisJob.Status.SKIPPED
            and int(job.analyzed_watermark_message_id or 0) >= watermark
            and int(job.analyzed_revision or 0) >= int(job.revision or 0)
            and job.required_state_fingerprint == required_state_fingerprint
        )
        analyzed_current = bool(
            latest_ai
            and int(latest_ai.get("last_analyzed_message_id") or 0) >= watermark
            and latest_ai.get("analysis_prompt_version") == ANALYSIS_PROMPT_VERSION
            and latest_ai.get("required_state_fingerprint")
            == required_state_fingerprint
            and payment_truth_matches
            and job
            and int(job.analyzed_watermark_message_id or 0) >= watermark
            and int(job.analyzed_revision or 0) >= int(job.revision or 0)
            and job.status == IgConversationAnalysisJob.Status.DONE
        )
        current = skipped_current or analyzed_current
        if current or _job_covers_required_analysis(
            job,
            watermark=watermark,
            required_state_fingerprint=required_state_fingerprint,
        ):
            unchanged += 1
            continue
        if message and client:
            schedule_analysis(
                client,
                message,
                trigger="reconcile",
                now=now,
                delay_seconds=0,
            )
            # Deterministic CRM state and a no-network snapshot are reconciled
            # only after cutoff/eligibility and the durable job boundary pass.
            from management.services.bot_sales_classifier import reconcile_rules_projection

            reconcile_rules_projection(client, watermark=watermark)
            queued += 1
    next_cursor = (
        int(latest_rows[-1]["client_id"])
        if len(latest_rows) >= bounded_limit
        else 0
    )
    InstagramBotSettings.objects.filter(pk=settings_obj.pk).update(
        analysis_reconcile_cursor=next_cursor
    )
    return {
        "queued": queued,
        "unchanged": unchanged,
        "historical_blocked": historical_blocked,
        "hidden_excluded": hidden_excluded,
        "historical_backfill_requested": bool(settings_obj.analysis_backfill_enabled),
        "historical_backfill_allowed": include_history,
        "reconcile_after": cutoff.isoformat(),
        "scanned": len(latest_rows),
        "cursor_from": cursor,
        "cursor_next": next_cursor,
    }
