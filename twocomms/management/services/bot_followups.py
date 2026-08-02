"""Scheduled follow-ups for the Instagram Direct sales bot."""
from __future__ import annotations

import sys
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from management.models import (
    IgClient,
    IgConversationSignal,
    IgDeal,
    IgFollowUpTask,
    InstagramBotMessage,
    InstagramBotSettings,
)
from management.services.bot_payment_truth import (
    TERMINAL_NEGATIVE_PAYMENT_TRUTHS,
    client_has_terminal_negative_payment,
    client_has_confirmed_purchase,
    client_has_verified_payment,
    verified_payment_deals,
)

KYIV_TZ = ZoneInfo("Europe/Kyiv")
QUIET_START = time(10, 0)
QUIET_END = time(19, 0)
META_REPLY_WINDOW = timedelta(hours=23)
FOLLOWUP_MAX_ATTEMPTS = 4
FOLLOWUP_RETRY_BASE = timedelta(minutes=5)
FOLLOWUP_RETRY_CAP = timedelta(hours=1)


def _now() -> datetime:
    return timezone.now()


def _local(dt: datetime) -> datetime:
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, KYIV_TZ)
    return dt.astimezone(KYIV_TZ)


def next_allowed_send_at(candidate: datetime) -> datetime:
    """Return the next 10:00-19:00 Kyiv slot for an automated follow-up."""
    local = _local(candidate)
    if local.time() < QUIET_START:
        local = local.replace(hour=10, minute=0, second=0, microsecond=0)
    elif local.time() >= QUIET_END:
        local = (local + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
    return local.astimezone(timezone.get_current_timezone())


def meta_window_deadline(client: IgClient) -> datetime | None:
    base = client.last_message_at or client.first_contact_at
    if not base:
        return None
    return base + META_REPLY_WINDOW


def _update_client_next(client: IgClient) -> None:
    nxt = (
        IgFollowUpTask.objects.filter(client=client, status=IgFollowUpTask.Status.PENDING)
        .order_by("due_at", "id")
        .first()
    )
    client.next_followup_at = nxt.due_at if nxt else None
    client.save(update_fields=["next_followup_at", "updated_at"])


def cancel_pending(client: IgClient, *, reason: str = "") -> int:
    if not client:
        return 0
    count = IgFollowUpTask.objects.filter(
        client=client, status=IgFollowUpTask.Status.PENDING
    ).update(
        status=IgFollowUpTask.Status.CANCELLED,
        skip_reason=(reason or "cancelled")[:255],
        updated_at=_now(),
    )
    if count:
        _update_client_next(client)
    return count


def cancel_pending_for_deal(deal: IgDeal, *, reason: str = "") -> int:
    if not deal:
        return 0
    count = IgFollowUpTask.objects.filter(
        deal=deal, status=IgFollowUpTask.Status.PENDING
    ).update(
        status=IgFollowUpTask.Status.CANCELLED,
        skip_reason=(reason or "deal_cancelled")[:255],
        updated_at=_now(),
    )
    if count and deal.client_id:
        _update_client_next(deal.client)
    return count


def _has_open_service_conversation(client: IgClient) -> bool:
    """Whether this conversation is currently about service, not about buying.

    Two independent signals, because either can exist without the other: a
    manager may open an exchange case before the customer's next message, and a
    customer may complain without anyone opening a case yet.
    """
    from management.ig_bot_models import IgConversationAnalysisSnapshot
    from management.services.ig_post_sale import open_service_case

    if open_service_case(client) is not None:
        return True
    latest = (
        client.analysis_snapshots.exclude(
            interaction_type=(
                IgConversationAnalysisSnapshot.InteractionType.MANAGER_OBSERVATION
            )
        )
        .order_by("-id")
        .values_list("interaction_type", flat=True)
        .first()
    )
    return latest in {
        IgConversationAnalysisSnapshot.InteractionType.SUPPORT_COMPLAINT,
        IgConversationAnalysisSnapshot.InteractionType.EXCHANGE_REQUEST,
        IgConversationAnalysisSnapshot.InteractionType.RETURN_REQUEST,
    }


# IMP-052. Частотный лимит — предохранитель, а не удобство: удлинение каскада
# без него превращает добивку в спам и ставит под удар само приложение Meta.
# Считаются только автосообщения клиенту; задача менеджеру сообщением не является.
MIN_HOURS_BETWEEN_AUTOMATED_TOUCHES = 18
MAX_AUTOMATED_TOUCHES_PER_30_DAYS = 5
CUSTOMER_FACING_KINDS = (
    IgFollowUpTask.Kind.QUALIFICATION,
    IgFollowUpTask.Kind.PAYMENT,
    IgFollowUpTask.Kind.THINKING,
    IgFollowUpTask.Kind.RESCUE,
    IgFollowUpTask.Kind.FINAL,
)
# Стадии, на которых добивать нечего или нельзя.
SUPPRESSED_STAGES = {
    IgClient.Stage.COLD: "cold",
    IgClient.Stage.LEAD_TO_MANAGER: "lead_to_manager",
}


def _active_opt_out(client: IgClient) -> bool:
    return bool(
        client.opted_out_at
        and (not client.opted_in_at or client.opted_in_at < client.opted_out_at)
    )


def _suppressed_interaction(client: IgClient) -> str:
    """Non-sales conversations must not receive a sales follow-up."""
    from management.ig_bot_models import IgConversationAnalysisSnapshot

    types = IgConversationAnalysisSnapshot.InteractionType
    latest = (
        client.analysis_snapshots.exclude(
            interaction_type=types.MANAGER_OBSERVATION
        )
        .order_by("-id")
        .values_list("interaction_type", flat=True)
        .first()
    )
    return {
        types.WHOLESALE_B2B: "wholesale_b2b",
        types.COLLABORATION: "collaboration",
    }.get(latest, "")


def _frequency_limit_reason(client: IgClient, *, now: datetime | None = None) -> str:
    now = now or _now()
    sent = IgFollowUpTask.objects.filter(
        client=client,
        status=IgFollowUpTask.Status.SENT,
        kind__in=CUSTOMER_FACING_KINDS,
        sent_at__isnull=False,
    )
    recent_cutoff = now - timedelta(hours=MIN_HOURS_BETWEEN_AUTOMATED_TOUCHES)
    if sent.filter(sent_at__gt=recent_cutoff).exists():
        return "frequency_limit"
    month_cutoff = now - timedelta(days=30)
    if sent.filter(sent_at__gt=month_cutoff).count() >= MAX_AUTOMATED_TOUCHES_PER_30_DAYS:
        return "frequency_limit"
    return ""


def _client_allows_followup(client: IgClient, *, deal: IgDeal | None = None) -> tuple[bool, str]:
    if client.hidden_at:
        return False, "hidden"
    if client.is_blocked or client.stage == IgClient.Stage.SPAM:
        return False, "spam"
    if client.manager_takeover or client.bot_paused:
        return False, "manager_takeover"
    # Opt-out как самостоятельная причина: раньше он читался только внутри
    # платёжной ветки, поэтому отказ «не пишіть» не останавливал остальные виды.
    if _active_opt_out(client):
        return False, "opted_out"
    stage_reason = SUPPRESSED_STAGES.get(client.stage)
    if stage_reason:
        return False, stage_reason
    # F-SCORE-009: asking for an exchange used to schedule a 5% rescue offer
    # twelve hours later. Client #59 was saved from it by manager_takeover,
    # which is luck, not a rule.
    if _has_open_service_conversation(client):
        return False, "service_case_open"
    interaction_reason = _suppressed_interaction(client)
    if interaction_reason:
        return False, interaction_reason
    frequency_reason = _frequency_limit_reason(client)
    if frequency_reason:
        return False, frequency_reason
    if deal is not None:
        if verified_payment_deals(IgDeal.objects.filter(pk=deal.pk)).exists():
            return False, "already_converted"
        projection = getattr(deal, "payment_projection", None)
        truth = projection.truth if projection else deal.payment_truth
        if truth in TERMINAL_NEGATIVE_PAYMENT_TRUTHS:
            return False, "payment_reversed"
    else:
        if client_has_confirmed_purchase(client):
            return False, "already_converted"
        if client_has_terminal_negative_payment(client):
            return False, "payment_reversed"
    if client.primary_objection == IgClient.Objection.NO_BUY or client.lost_reason in {"no_buy", "stop"}:
        return False, "client_no_buy"
    return True, ""


def schedule_followup(
    client: IgClient,
    *,
    kind: str,
    delay: timedelta,
    reason: str,
    now: datetime | None = None,
    deal: IgDeal | None = None,
    discount_percent: int = 0,
    message_text: str = "",
    level: int | None = None,
) -> IgFollowUpTask | None:
    """Create one pending follow-up, adjusted for quiet hours and Meta window."""
    now = now or _now()
    due = next_allowed_send_at(now + delay)
    deadline = meta_window_deadline(client)
    status = IgFollowUpTask.Status.PENDING
    skip_reason = ""
    task_kind = kind
    task_reason = reason
    if deadline and due > deadline and kind != IgFollowUpTask.Kind.MANAGER_TASK:
        # IMP-049: раньше здесь ставился SKIPPED, и ≈половина «подумаю»-добивок
        # исчезала молча — работа существовала, но не была видна как работа.
        # Задача менеджеру со статусом PENDING остаётся в очереди человека.
        task_kind = IgFollowUpTask.Kind.MANAGER_TASK
        task_reason = "meta_window_closed"

    # IMP-052: дедуп текста. Один и тот же текст, уже отправленный клиенту,
    # второй раз выглядит как сбой автоматики, а не как забота.
    if message_text:
        already_sent = IgFollowUpTask.objects.filter(
            client=client,
            status=IgFollowUpTask.Status.SENT,
            message_text=message_text,
        ).exists()
        if already_sent:
            return None

    with transaction.atomic():
        IgFollowUpTask.objects.filter(
            client=client, status=IgFollowUpTask.Status.PENDING, kind=kind
        ).update(
            status=IgFollowUpTask.Status.CANCELLED,
            skip_reason="replaced",
            updated_at=_now(),
        )
        task = IgFollowUpTask.objects.create(
            client=client,
            deal=deal,
            due_at=due,
            status=status,
            kind=task_kind,
            level=client.followup_level if level is None else level,
            reason=(task_reason or "")[:120],
            discount_percent=max(0, min(10, int(discount_percent or 0))),
            meta_window_deadline=deadline,
            message_text=message_text or "",
            skip_reason=skip_reason,
            next_attempt_at=None,
        )
    _update_client_next(client)
    return task


def next_discount_percent(client: IgClient, *, explicit_negotiation: bool = False) -> int:
    current = int(client.discount_offered_percent or 0)
    if current >= 10:
        return 0
    if explicit_negotiation:
        return 10 if current < 10 else 0
    if current <= 0 and int(client.followup_level or 0) >= 1:
        return 5
    return 0


def schedule_rescue_offer(client: IgClient, *, explicit_negotiation: bool = False, now: datetime | None = None) -> IgFollowUpTask | None:
    pct = next_discount_percent(client, explicit_negotiation=explicit_negotiation)
    if not pct:
        return None
    # IMP-047: NEW и QUALIFYING были исключены, поэтому rescue не доходил до
    # клиента, который ещё не выбрал товар, — а именно там он и нужен.
    # COLD и LEAD_TO_MANAGER отсекаются раньше, в `_client_allows_followup`.
    if client.stage not in {
        IgClient.Stage.NEW,
        IgClient.Stage.QUALIFYING,
        IgClient.Stage.PRODUCT_MATCHED,
        IgClient.Stage.CHECKOUT,
        IgClient.Stage.PAYMENT_PENDING,
    }:
        return None
    allowed, _why = _client_allows_followup(client)
    if not allowed:
        return None
    return schedule_followup(
        client,
        kind=IgFollowUpTask.Kind.RESCUE if pct == 5 else IgFollowUpTask.Kind.FINAL,
        delay=timedelta(hours=12),
        reason="discount_rescue",
        now=now,
        discount_percent=pct,
        level=int(client.followup_level or 0) + 1,
    )


def schedule_payment_followup(deal: IgDeal, *, now: datetime | None = None) -> IgFollowUpTask | None:
    if not deal or not deal.client_id:
        return None
    allowed, _why = _client_allows_followup(deal.client, deal=deal)
    if not allowed:
        return None
    return schedule_followup(
        deal.client,
        kind=IgFollowUpTask.Kind.PAYMENT,
        delay=timedelta(minutes=45),
        reason="payment_link_unpaid",
        now=now,
        deal=deal,
    )


def schedule_after_inbound(client: IgClient, *, reason: str = "client_reply") -> None:
    """A client reply cancels automated reminders until the bot/manager answers again."""
    cancel_pending(client, reason=reason)


def schedule_after_bot_reply(client: IgClient, *, reply: str = "", control: dict | None = None, deal: IgDeal | None = None) -> IgFollowUpTask | None:
    if not client:
        return None
    allowed, why = _client_allows_followup(client, deal=deal)
    if not allowed:
        cancel_pending(client, reason=why)
        return None
    if deal and deal.status == IgDeal.Status.AWAITING_PAYMENT:
        return schedule_payment_followup(deal)
    if client.stage == IgClient.Stage.PAYMENT_PENDING:
        return schedule_followup(
            client,
            kind=IgFollowUpTask.Kind.PAYMENT,
            delay=timedelta(minutes=45),
            reason="payment_link_unpaid",
        )
    if client.primary_objection in {IgClient.Objection.THINKING, IgClient.Objection.PRICE}:
        return schedule_followup(
            client,
            kind=IgFollowUpTask.Kind.THINKING,
            delay=timedelta(hours=12),
            reason="thinking_or_price_hesitation",
        )
    if client.stage in {IgClient.Stage.NEW, IgClient.Stage.QUALIFYING, IgClient.Stage.PRODUCT_MATCHED, IgClient.Stage.CHECKOUT}:
        return schedule_followup(
            client,
            kind=IgFollowUpTask.Kind.QUALIFICATION,
            delay=timedelta(hours=2),
            reason="qualification_unanswered",
        )
    return None


def _lang(client: IgClient) -> str:
    language = (client.language or "").lower()
    if language.startswith("en"):
        return "en"
    return "ru" if language.startswith("ru") else "uk"


def compose_followup(task: IgFollowUpTask) -> str:
    client = task.client
    language = _lang(client)
    ru = language == "ru"
    en = language == "en"
    pct = int(task.discount_percent or 0)
    if task.kind == IgFollowUpTask.Kind.PAYMENT:
        if en:
            return (
                "Reminder: the payment link is still active. If it does not open "
                "or you need help with payment, reply here and I will help."
            )
        return (
            "Напомню: ссылка на оплату еще активна. Если что-то не открывается или нужно помочь с оплатой - напишите, подскажу."
            if ru else
            "Нагадаю: посилання на оплату ще активне. Якщо щось не відкривається або треба допомогти з оплатою - напишіть, підкажу."
        )
    if pct == 10:
        if en:
            return (
                "I can offer a final option: 10% off this order. If it does not "
                "work for you, that is fine and I will not send more reminders."
            )
        return (
            "Могу предложить финальный вариант: скидка 10% на этот заказ. Если не подходит - все ок, больше не буду вас отвлекать."
            if ru else
            "Можу запропонувати фінальний варіант: знижка 10% на це замовлення. Якщо не підходить - все ок, більше не буду вас відволікати."
        )
    if pct == 5:
        if en:
            return (
                "For a first order, we can offer a small 5% discount. Reply here "
                "and I will help you place the order."
            )
        return (
            "Как для первого заказа можем сделать небольшую скидку 5%. Если хотите - помогу быстро оформить."
            if ru else
            "Як для першого замовлення можемо зробити невелику знижку 5%. Якщо хочете - допоможу швидко оформити."
        )
    if task.kind == IgFollowUpTask.Kind.THINKING:
        if en:
            return (
                "Have you had a chance to think about the order? If you have a "
                "question about size, fabric, or payment, I can help."
            )
        return (
            "Хотел уточнить, получилось подумать по заказу? Если есть вопрос по размеру, ткани или оплате - подскажу коротко."
            if ru else
            "Хотів уточнити, чи вийшло подумати щодо замовлення? Якщо є питання по розміру, тканині або оплаті - коротко підкажу."
        )
    if en:
        return "Is this order still relevant? I can help with the size, color, or payment."
    return (
        "Подскажите, пожалуйста, актуален еще заказ? Могу помочь с размером, цветом или оплатой."
        if ru else
        "Підкажіть, будь ласка, чи актуальне ще замовлення? Можу допомогти з розміром, кольором або оплатою."
    )


def _mark_skipped(task: IgFollowUpTask, reason: str) -> None:
    task.status = IgFollowUpTask.Status.SKIPPED
    task.skip_reason = (reason or "skipped")[:255]
    task.updated_at = _now()
    task.save(update_fields=["status", "skip_reason", "updated_at"])
    _update_client_next(task.client)


def _claim_due_followup(
    task_id: int, *, now: datetime, automation
) -> tuple[IgFollowUpTask, IgClient, str] | None:
    """Obtain the shared client lease and re-read one pending follow-up.

    The initial due-task list is intentionally only a list of ids. Hide can
    cancel a task after that list is read, so no stale task/client object may
    reach the send path.
    """
    candidate = IgFollowUpTask.objects.filter(
        pk=task_id,
        status=IgFollowUpTask.Status.PENDING,
        due_at__lte=now,
    ).filter(
        Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=now),
    ).values("client_id").first()
    if not candidate:
        return None
    client, lease_token = automation.acquire_client_automation_lease(
        candidate["client_id"]
    )
    if not client:
        # Busy means another automation owns this client and the task remains
        # pending. A real policy block keeps the prior behavior: skip it once
        # so it cannot be reconsidered forever after a pause/hide/paid state.
        fresh_client = IgClient.objects.filter(pk=candidate["client_id"]).first()
        if fresh_client:
            stale_task = IgFollowUpTask.objects.select_related("deal").filter(
                pk=task_id,
                client_id=fresh_client.id,
                status=IgFollowUpTask.Status.PENDING,
            ).first()
            allowed, why = _client_allows_followup(
                fresh_client, deal=stale_task.deal if stale_task else None
            )
            if not allowed:
                if stale_task:
                    stale_task.client = fresh_client
                    _mark_skipped(stale_task, why)
        return None
    task = IgFollowUpTask.objects.select_related("client", "deal").filter(
        pk=task_id,
        client_id=client.id,
        status=IgFollowUpTask.Status.PENDING,
        due_at__lte=now,
    ).filter(
        Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=now),
    ).first()
    if not task:
        automation.release_client_automation_lease(client.id, lease_token)
        return None
    task.client = client
    allowed, why = _client_allows_followup(client, deal=task.deal)
    if not allowed:
        _mark_skipped(task, why)
        automation.release_client_automation_lease(client.id, lease_token)
        return None
    return task, client, lease_token


def _renew_due_followup_claim(
    task_id: int, client_id: int, lease_token: str, *, now: datetime, automation
) -> tuple[IgFollowUpTask, IgClient] | None:
    """Last no-I/O check: task remains pending and the client remains active."""
    client = automation.renew_client_automation_lease(client_id, lease_token)
    if not client:
        return None
    task = IgFollowUpTask.objects.select_related("client", "deal").filter(
        pk=task_id,
        client_id=client.id,
        status=IgFollowUpTask.Status.PENDING,
        due_at__lte=now,
    ).filter(
        Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=now),
    ).first()
    if not task:
        return None
    task.client = client
    allowed, why = _client_allows_followup(client, deal=task.deal)
    if not allowed:
        _mark_skipped(task, why)
        return None
    return task, client


def process_due_followups(s: InstagramBotSettings | None = None, *, now: datetime | None = None, limit: int = 20) -> int:
    s = s or InstagramBotSettings.load()
    now = now or _now()
    sent = 0
    task_ids = list(
        IgFollowUpTask.objects
        .filter(status=IgFollowUpTask.Status.PENDING, due_at__lte=now)
        .filter(Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=now))
        .order_by("due_at", "id")[:limit]
        .values_list("id", flat=True)
    )
    from management.services import instagram_bot
    from management.services.ig_reply_boundary import (
        customer_send_boundary,
        reply_execution_boundary,
    )

    for task_id in task_ids:
        claim = _claim_due_followup(task_id, now=now, automation=instagram_bot)
        if not claim:
            continue
        task, client, lease_token = claim
        reply_boundary = reply_execution_boundary(s.pk, client.id)
        reply_boundary_entered = False
        try:
            permission = reply_boundary.__enter__()
            reply_boundary_entered = True
            if not permission:
                _mark_skipped(task, "reply_paused")
                continue
            if task.meta_window_deadline and now > task.meta_window_deadline:
                _mark_skipped(task, "meta_window_closed")
                continue
            allowed_time = next_allowed_send_at(now)
            if allowed_time > now + timedelta(seconds=1):
                task.due_at = allowed_time
                task.save(update_fields=["due_at", "updated_at"])
                _update_client_next(client)
                continue
            text = (task.message_text or "").strip() or compose_followup(task)
            renewed = _renew_due_followup_claim(
                task.id, client.id, lease_token, now=now, automation=instagram_bot
            )
            if not renewed:
                continue
            task, client = renewed
            with customer_send_boundary(s.pk, client.id, permission) as send_allowed:
                if not send_allowed:
                    _mark_skipped(task, "permission_epoch_changed")
                    continue
            try:
                ok, kind, hint = instagram_bot.send_text(
                    s,
                    client.igsid,
                    text,
                    permission_boundary_factory=lambda: customer_send_boundary(
                        s.pk, client.id, permission
                    ),
                )
            except Exception as exc:
                ok, kind, hint = False, "transient", repr(exc)
            if kind == "cancelled":
                _mark_skipped(task, "permission_epoch_changed")
                continue
            if not ok:
                if kind == "permanent":
                    _mark_skipped(task, hint or "send_blocked")
                elif kind == "unknown":
                    _mark_skipped(task, hint or "delivery_unknown")
                else:
                    task.attempt_count = int(task.attempt_count or 0) + 1
                    if task.attempt_count >= FOLLOWUP_MAX_ATTEMPTS:
                        _mark_skipped(task, hint or "retry_exhausted")
                    else:
                        delay = min(
                            FOLLOWUP_RETRY_CAP,
                            FOLLOWUP_RETRY_BASE * (2 ** (task.attempt_count - 1)),
                        )
                        retry_at = next_allowed_send_at(now + delay)
                        task.next_attempt_at = retry_at
                        task.due_at = retry_at
                        task.last_error = (hint or "transient_send_error")[:500]
                        task.updated_at = _now()
                        task.save(update_fields=[
                            "attempt_count", "next_attempt_at", "due_at", "last_error", "updated_at",
                        ])
                        _update_client_next(client)
                continue
            msg = InstagramBotMessage.objects.create(
                sender_id=client.igsid,
                client=client,
                role=InstagramBotMessage.Role.MODEL,
                text=text,
                status=InstagramBotMessage.Status.DONE,
                source="followup",
                processed_at=now,
            )
            task.status = IgFollowUpTask.Status.SENT
            task.sent_at = now
            task.sent_message = msg
            task.next_attempt_at = None
            task.last_error = ""
            task.save(update_fields=[
                "status", "sent_at", "sent_message", "next_attempt_at", "last_error", "updated_at",
            ])
            client.followup_level = max(int(client.followup_level or 0), int(task.level or 0) + 1)
            if task.discount_percent:
                client.discount_offered_percent = max(
                    int(client.discount_offered_percent or 0), int(task.discount_percent or 0)
                )
                try:
                    IgConversationSignal.objects.create(
                        client=client,
                        message=msg,
                        signal_type=IgConversationSignal.Type.DISCOUNT_OFFER,
                        value=str(task.discount_percent),
                        payload={"discount_percent": task.discount_percent},
                    )
                except Exception:
                    pass
            client.last_bot_reply_at = now
            client.next_followup_at = None
            client.save(update_fields=[
                "followup_level", "discount_offered_percent", "last_bot_reply_at",
                "next_followup_at", "updated_at",
            ])
            sent += 1
            if not task.discount_percent and task.kind in {
                IgFollowUpTask.Kind.QUALIFICATION,
                IgFollowUpTask.Kind.THINKING,
                IgFollowUpTask.Kind.PAYMENT,
            }:
                schedule_rescue_offer(client, now=now)
        finally:
            if reply_boundary_entered:
                reply_boundary.__exit__(*sys.exc_info())
            instagram_bot.release_client_automation_lease(client.id, lease_token)
    return sent
