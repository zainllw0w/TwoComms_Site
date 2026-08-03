"""Scheduled follow-ups for the Instagram Direct sales bot."""
from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from decimal import Decimal, InvalidOperation
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
# IMP-054. Окно инициации автосообщений. Прежние 10:00–19:00 отрезали вечер —
# самое живое время в Instagram, — и не совпадали со второй конфигурацией тишины
# в `services/config_versions.py` (21:00–08:00). Одна конфигурация на домен.
QUIET_START = time(10, 0)
QUIET_END = time(21, 30)
# Аварийное окно шире и используется только когда иначе задача умрёт от
# 24-часового окна Meta. Разбудить человека в 22:15 хуже, чем не ответить
# вообще, — но потерять единственную возможность ответить хуже обоих.
EMERGENCY_START = time(9, 0)
EMERGENCY_END = time(22, 30)
META_REPLY_WINDOW = timedelta(hours=23)
FOLLOWUP_MAX_ATTEMPTS = 4
FOLLOWUP_RETRY_BASE = timedelta(minutes=5)
FOLLOWUP_RETRY_CAP = timedelta(hours=1)


@dataclass(frozen=True, slots=True)
class FollowupPolicyStep:
    index: int
    offset: timedelta | None
    trigger: str
    kind: str
    condition: str
    copy_key: str
    discount_percent: int = 0


@dataclass(frozen=True, slots=True)
class FollowupPolicy:
    scenario: str
    steps: tuple[FollowupPolicyStep, ...]
    terminal_conditions: tuple[str, ...]
    exhausted_reason: str = ""
    next_scenario: str = ""
    next_step_index: int = 0


def _policy_step(
    index: int,
    offset: timedelta | None,
    trigger: str,
    kind: str,
    condition: str,
    copy_key: str,
    *,
    discount_percent: int = 0,
) -> FollowupPolicyStep:
    return FollowupPolicyStep(
        index=index,
        offset=offset,
        trigger=trigger,
        kind=kind,
        condition=condition,
        copy_key=copy_key,
        discount_percent=discount_percent,
    )


# IMP-053. The design offsets stay absolute so the intended funnel remains
# auditable. Runtime scheduling may delay or hand a step to a manager when the
# 18-hour frequency cap, quiet hours, or Meta's reply window make it unsafe.
FOLLOWUP_POLICIES: dict[str, FollowupPolicy] = {
    "payment_link_unpaid": FollowupPolicy(
        scenario="payment_link_unpaid",
        steps=(
            _policy_step(0, timedelta(minutes=25), "time", IgFollowUpTask.Kind.PAYMENT, "deal_unpaid", "payment_a1"),
            _policy_step(1, timedelta(hours=4), "time", IgFollowUpTask.Kind.PAYMENT, "deal_unpaid", "payment_a2"),
            _policy_step(2, timedelta(hours=23), "time", IgFollowUpTask.Kind.PAYMENT, "deal_unpaid", "payment_a3"),
            _policy_step(3, None, "event", IgFollowUpTask.Kind.PAYMENT, "invoice_expired", "payment_a4"),
            _policy_step(4, timedelta(hours=72), "time", IgFollowUpTask.Kind.RESCUE, "deal_unpaid", "payment_a5", discount_percent=5),
        ),
        terminal_conditions=("verified_payment", "client_reply", "two_delivery_failures"),
        exhausted_reason="payment_followup_exhausted",
    ),
    "price_quoted_silence": FollowupPolicy(
        scenario="price_quoted_silence",
        steps=(
            _policy_step(0, timedelta(hours=2), "time", IgFollowUpTask.Kind.QUALIFICATION, "no_customer_reply", "price_b1"),
            _policy_step(1, timedelta(hours=24), "time", IgFollowUpTask.Kind.QUALIFICATION, "no_customer_reply", "price_b2"),
            _policy_step(2, timedelta(hours=72), "time", IgFollowUpTask.Kind.RESCUE, "no_customer_reply", "price_b3", discount_percent=5),
        ),
        terminal_conditions=("client_reply", "verified_payment", "explicit_no_buy"),
        exhausted_reason="price_quote_silence",
    ),
    "thinking_hesitation": FollowupPolicy(
        scenario="thinking_hesitation",
        steps=(
            _policy_step(0, timedelta(hours=20), "time", IgFollowUpTask.Kind.THINKING, "thinking_unresolved", "thinking_c1"),
            _policy_step(1, timedelta(hours=72), "time", IgFollowUpTask.Kind.RESCUE, "thinking_unresolved", "thinking_c2", discount_percent=5),
            _policy_step(2, timedelta(days=7), "time", IgFollowUpTask.Kind.THINKING, "thinking_unresolved", "thinking_c3"),
        ),
        terminal_conditions=("client_reply", "objection_changed", "thinking_exhausted"),
        exhausted_reason="thinking_exhausted",
    ),
    "price_objection": FollowupPolicy(
        scenario="price_objection",
        steps=(
            _policy_step(0, timedelta(hours=24), "time", IgFollowUpTask.Kind.RESCUE, "price_unresolved", "price_d1", discount_percent=5),
            _policy_step(1, timedelta(hours=96), "time", IgFollowUpTask.Kind.FINAL, "price_unresolved", "price_d2", discount_percent=10),
        ),
        terminal_conditions=("client_reply", "verified_payment", "discount_cap_reached"),
        exhausted_reason="price_offer_exhausted",
    ),
    "missing_customer_size": FollowupPolicy(
        scenario="missing_customer_size",
        steps=(
            _policy_step(0, timedelta(minutes=40), "time", IgFollowUpTask.Kind.QUALIFICATION, "customer_size_missing", "size_e1"),
            _policy_step(1, timedelta(hours=6), "time", IgFollowUpTask.Kind.QUALIFICATION, "customer_size_missing", "size_e2"),
            _policy_step(2, timedelta(hours=36), "time", IgFollowUpTask.Kind.QUALIFICATION, "customer_size_missing", "size_e3"),
        ),
        terminal_conditions=("customer_size_known", "client_reply", "explicit_no_buy"),
        exhausted_reason="size_missing_exhausted",
    ),
    "restock_wait": FollowupPolicy(
        scenario="restock_wait",
        steps=(
            _policy_step(0, timedelta(0), "reactive", IgFollowUpTask.Kind.QUALIFICATION, "stock_gap_present", "restock_f1"),
            _policy_step(1, None, "event", IgFollowUpTask.Kind.QUALIFICATION, "restock_confirmed", "restock_f2"),
            _policy_step(2, timedelta(days=14), "time", IgFollowUpTask.Kind.MANAGER_TASK, "stock_gap_present", "restock_f3"),
        ),
        terminal_conditions=("restock_confirmed", "alternative_selected", "client_opt_out"),
        exhausted_reason="restock_waiting",
    ),
    "paid_missing_delivery": FollowupPolicy(
        scenario="paid_missing_delivery",
        steps=(
            _policy_step(0, timedelta(minutes=20), "time", IgFollowUpTask.Kind.FULFILLMENT, "paid_delivery_missing", "delivery_g1"),
            _policy_step(1, timedelta(hours=3), "time", IgFollowUpTask.Kind.FULFILLMENT, "paid_delivery_missing", "delivery_g2"),
            _policy_step(2, timedelta(hours=20), "time", IgFollowUpTask.Kind.FULFILLMENT, "paid_delivery_missing", "delivery_g3"),
        ),
        terminal_conditions=("delivery_complete", "order_created", "manager_takeover"),
        exhausted_reason="paid_delivery_missing",
    ),
    "delivery_ready_unpaid": FollowupPolicy(
        scenario="delivery_ready_unpaid",
        steps=(
            _policy_step(0, timedelta(minutes=30), "time", IgFollowUpTask.Kind.PAYMENT, "delivery_ready_unpaid", "delivery_g4"),
        ),
        terminal_conditions=("verified_payment", "delivery_changed", "client_reply"),
        exhausted_reason="delivery_ready_unpaid",
        next_scenario="payment_link_unpaid",
        next_step_index=1,
    ),
    "first_reply_silence": FollowupPolicy(
        scenario="first_reply_silence",
        steps=(
            _policy_step(0, timedelta(hours=2), "time", IgFollowUpTask.Kind.QUALIFICATION, "first_reply_unanswered", "first_h1"),
            _policy_step(1, timedelta(hours=20), "time", IgFollowUpTask.Kind.QUALIFICATION, "first_reply_unanswered", "first_h2"),
        ),
        terminal_conditions=("client_reply", "meta_window_closed", "first_reply_exhausted"),
        exhausted_reason="first_reply_exhausted",
    ),
}

POLICY_REASON_ALIASES = {
    "checkout_proposal_abandoned": "payment_link_unpaid",
}


FOLLOWUP_POLICY_COPY = {
    "payment_a1": {
        "uk": "Нагадаю про оплату. Якщо посилання не відкривається або потрібен інший спосіб — напишіть, швидко допоможу. Якщо передумали — просто скажіть, і більше не турбуватиму.",
        "ru": "Напомню об оплате. Если ссылка не открывается или нужен другой способ — напишите, быстро помогу. Если передумали — просто скажите, и больше не буду беспокоить.",
        "en": "A quick payment reminder. If the link does not open or you need another payment option, reply here and I will help. If you changed your mind, just tell me and I will not message again.",
    },
    "payment_a2": {
        "uk": "Бачу, оплата ще не пройшла. Підкажіть, що зупиняє: розмір, доставка чи спосіб оплати? Допоможу за пару хвилин.",
        "ru": "Вижу, оплата ещё не прошла. Подскажите, что останавливает: размер, доставка или способ оплаты? Помогу за пару минут.",
        "en": "I can see the payment has not gone through. Is the issue size, delivery, or the payment method? I can help in a couple of minutes.",
    },
    "payment_a3": {
        "uk": "Посилання на оплату скоро закриється. Якщо плануєте оформити — краще зробити це сьогодні. Потрібен новий лінк або інший розмір — напишіть.",
        "ru": "Ссылка на оплату скоро закроется. Если планируете оформить — лучше сделать это сегодня. Нужна новая ссылка или другой размер — напишите.",
        "en": "The payment link will close soon. If you plan to place the order, it is best to do it today. Reply if you need a new link or a different size.",
    },
    "payment_a4": {
        "uk": "Посилання на оплату вже неактивне. Якщо замовлення ще актуальне, напишіть «так» — одразу зроблю нове. Товари й параметри збережені.",
        "ru": "Ссылка на оплату уже неактивна. Если заказ ещё актуален, напишите «да» — сразу сделаю новую. Товары и параметры сохранены.",
        "en": "The payment link is no longer active. If the order is still relevant, reply 'yes' and I will create a new one. Your items and options are saved.",
    },
    "payment_a5": {
        "uk": "Останнє повідомлення по цьому замовленню: можу дати -5% і все оформити за вас. Якщо зараз не актуально — більше не турбуватиму.",
        "ru": "Последнее сообщение по этому заказу: могу дать -5% и всё оформить за вас. Если сейчас неактуально — больше не буду беспокоить.",
        "en": "This is my final message about this order: I can offer 5% off and place it for you. If it is no longer relevant, I will not message again.",
    },
    "price_b1": {
        "uk": "Підкажіть, будь ласка, чи підходить така ціна? Можу показати фото на людині, розповісти про тканину або підказати розмір.",
        "ru": "Подскажите, пожалуйста, подходит ли такая цена? Могу показать фото на человеке, рассказать о ткани или помочь с размером.",
        "en": "Does this price work for you? I can show how it looks when worn, explain the fabric, or help choose a size.",
    },
    "price_b2": {
        "uk": "Не хочу губити ваше замовлення. Якщо готові — оформлю за 2 хвилини, потрібні лише розмір і місто. Якщо передумали — теж скажіть.",
        "ru": "Не хочу потерять ваш заказ. Если готовы — оформлю за 2 минуты, нужны только размер и город. Если передумали — тоже скажите.",
        "en": "I do not want your order to get lost. If you are ready, I can place it in two minutes; I only need the size and city. Tell me if you changed your mind too.",
    },
    "price_b3": {
        "uk": "Фінальна пропозиція: -5% на це замовлення, якщо оформимо сьогодні. Далі не турбуватиму.",
        "ru": "Финальное предложение: -5% на этот заказ, если оформим сегодня. Дальше не буду беспокоить.",
        "en": "Final offer: 5% off this order if we place it today. I will not send more reminders after this.",
    },
    "thinking_c1": {
        "uk": "Не тисну, просто нагадаю про себе. Якщо лишилось питання про розмір, тканину чи доставку — відповім коротко й по факту.",
        "ru": "Не давлю, просто напомню о себе. Если остался вопрос о размере, ткани или доставке — отвечу коротко и по делу.",
        "en": "No pressure, just a quick reminder. If you still have a question about size, fabric, or delivery, I will answer briefly and clearly.",
    },
    "thinking_c2": {
        "uk": "Замовлення ще можна оформити. Як бонус за очікування можу дати -5%. Якщо цікаво — напишіть «так», решту зроблю сама.",
        "ru": "Заказ ещё можно оформить. Как бонус за ожидание могу дать -5%. Если интересно — напишите «да», остальное сделаю сама.",
        "en": "The order can still be placed. I can offer 5% off as a waiting bonus. Reply 'yes' and I will handle the rest.",
    },
    "thinking_c3": {
        "uk": "Останнє повідомлення по цій моделі. Якщо захочете повернутись — просто напишіть, я все пам'ятаю й оформлю швидко.",
        "ru": "Последнее сообщение по этой модели. Если захотите вернуться — просто напишите, я всё помню и быстро оформлю.",
        "en": "This is my last message about this item. If you want to return later, just reply; I remember the details and can place it quickly.",
    },
    "price_d1": {
        "uk": "Можу зробити -5% на це замовлення — це максимум без окремого узгодження. Якщо підходить, оформлю зараз.",
        "ru": "Могу сделать -5% на этот заказ — это максимум без отдельного согласования. Если подходит, оформлю сейчас.",
        "en": "I can offer 5% off this order, which is the maximum without separate approval. If that works, I can place it now.",
    },
    "price_d2": {
        "uk": "Фінальний узгоджений варіант: -10% на це замовлення. Якщо не підходить — усе гаразд, більше не нагадуватиму.",
        "ru": "Финальный согласованный вариант: -10% на этот заказ. Если не подходит — всё хорошо, больше не буду напоминать.",
        "en": "The final approved option is 10% off this order. If it does not work for you, that is fine and I will not send more reminders.",
    },
    "size_e1": {
        "uk": "Залишилось визначитись із розміром. Якщо не впевнені, напишіть зріст і вагу — підкажу, який сяде краще, або скину мірки моделі.",
        "ru": "Осталось определиться с размером. Если не уверены, напишите рост и вес — подскажу, какой сядет лучше, или пришлю замеры модели.",
        "en": "Only the size is left. If you are unsure, send your height and weight and I will recommend the best fit or share the item's measurements.",
    },
    "size_e2": {
        "uk": "Щоб не гадати з розміром, назвіть свій звичний розмір одягу — звірю його з нашою сіткою.",
        "ru": "Чтобы не гадать с размером, назовите свой обычный размер одежды — сверю его с нашей сеткой.",
        "en": "To avoid guessing, tell me your usual clothing size and I will match it to our size chart.",
    },
    "size_e3": {
        "uk": "Підкажіть, чи ще актуально? Потрібен лише розмір, далі підготую оплату й оформлення. Якщо передумали — просто скажіть.",
        "ru": "Подскажите, ещё актуально? Нужен только размер, дальше подготовлю оплату и оформление. Если передумали — просто скажите.",
        "en": "Is this still relevant? I only need the size, then I can prepare payment and place the order. Just tell me if you changed your mind.",
    },
    "restock_f1": {
        "uk": "Саме цього розміру зараз немає. Можу підібрати схожу модель або поставити вас у чергу й написати, щойно він з'явиться.",
        "ru": "Именно этого размера сейчас нет. Могу подобрать похожую модель или поставить вас в очередь и написать, как только он появится.",
        "en": "This exact size is unavailable now. I can suggest a similar item or add you to the restock queue and message you when it returns.",
    },
    "restock_f2": {
        "uk": "Хороша новина: розмір, який ви чекали, знову в наявності. Якщо ще актуально — оформлю зараз, поки є.",
        "ru": "Хорошая новость: размер, который вы ждали, снова в наличии. Если ещё актуально — оформлю сейчас, пока он есть.",
        "en": "Good news: the size you were waiting for is back in stock. If it is still relevant, I can place the order while it is available.",
    },
    "restock_f3": {
        "uk": "Ваш розмір поки не завезли. Можу показати схожі моделі, де він є зараз, або залишити вас у черзі.",
        "ru": "Ваш размер пока не привезли. Могу показать похожие модели, где он есть сейчас, или оставить вас в очереди.",
        "en": "Your size has not returned yet. I can show similar items available now or keep you in the restock queue.",
    },
    "delivery_g1": {
        "uk": "Оплату отримали, дякую. Залишились дані доставки: ПІБ, телефон, місто й номер відділення Нової Пошти.",
        "ru": "Оплату получили, спасибо. Остались данные доставки: ФИО, телефон, город и номер отделения Новой почты.",
        "en": "Payment received, thank you. I only need the delivery details: recipient name, phone, city, and Nova Poshta branch number.",
    },
    "delivery_g2": {
        "uk": "Нагадаю: чекаю ПІБ, телефон, місто й відділення НП. Щойно надішлете, замовлення піде в роботу.",
        "ru": "Напомню: жду ФИО, телефон, город и отделение НП. Как только отправите, заказ пойдёт в работу.",
        "en": "A reminder that I am waiting for the recipient name, phone, city, and Nova Poshta branch. Once received, the order goes into processing.",
    },
    "delivery_g3": {
        "uk": "Оплачене замовлення чекає лише адресу доставки. Якщо потрібен дзвінок менеджера — скажіть, я передам.",
        "ru": "Оплаченный заказ ждёт только адрес доставки. Если нужен звонок менеджера — скажите, я передам.",
        "en": "Your paid order is waiting only for the delivery address. Tell me if you would like a manager to contact you.",
    },
    "delivery_g4": {
        "uk": "У мене вже є всі дані доставки — залишилось оплатити. Посилання: {invoice_url}. Якщо щось не проходить, напишіть.",
        "ru": "У меня уже есть все данные доставки — осталось оплатить. Ссылка: {invoice_url}. Если что-то не проходит, напишите.",
        "en": "I already have all delivery details; only payment remains. Link: {invoice_url}. Reply if anything does not work.",
    },
    "first_h1": {
        "uk": "Можливо, повідомлення загубилось у Direct. Якщо ще цікавить — напишіть, що саме дивились, і я підкажу наявність, розміри й ціну.",
        "ru": "Возможно, сообщение потерялось в Direct. Если ещё интересно — напишите, что смотрели, и я подскажу наличие, размеры и цену.",
        "en": "Perhaps the message got lost in Direct. If you are still interested, tell me what you viewed and I will check availability, sizes, and price.",
    },
    "first_h2": {
        "uk": "Останнє нагадування, щоб не губити ваш запит. Напишіть одне слово — і я підберу модель, розмір, ціну й доставку. Далі не турбуватиму.",
        "ru": "Последнее напоминание, чтобы не потерять ваш запрос. Напишите одно слово — и я подберу модель, размер, цену и доставку. Дальше не буду беспокоить.",
        "en": "One final reminder so your request is not lost. Reply with one word and I will help with the item, size, price, and delivery. I will not message again after this.",
    },
}


def _now() -> datetime:
    return timezone.now()


def _local(dt: datetime) -> datetime:
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, KYIV_TZ)
    return dt.astimezone(KYIV_TZ)


def next_allowed_send_at(candidate: datetime, *, deadline: datetime | None = None) -> datetime:
    """Next Kyiv slot allowed for an automated follow-up.

    A reactive reply to a customer message never passes through here and stays
    available 24/7: silence hours are about us initiating contact, not about
    refusing to answer someone who just wrote.

    ``deadline`` widens the window to the emergency one when postponing until
    the morning would take the task past the Meta reply window — outside it we
    lose the only chance to answer at all.
    """
    local = _local(candidate)
    start, end = QUIET_START, QUIET_END
    if deadline is not None:
        local_deadline = _local(deadline)
        morning = _next_window_start(local, QUIET_START)
        if local_deadline < morning:
            start, end = EMERGENCY_START, EMERGENCY_END
    if local.time() < start:
        local = local.replace(
            hour=start.hour, minute=start.minute, second=0, microsecond=0
        )
    elif local.time() >= end:
        local = (local + timedelta(days=1)).replace(
            hour=start.hour, minute=start.minute, second=0, microsecond=0
        )
    return local.astimezone(timezone.get_current_timezone())


def _next_window_start(local: datetime, start: time) -> datetime:
    """When the next initiation window opens relative to ``local``."""
    today = local.replace(
        hour=start.hour, minute=start.minute, second=0, microsecond=0
    )
    return today if local < today else today + timedelta(days=1)


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


def cancel_pending_fulfillment_for_deal(
    deal: IgDeal,
    *,
    reason: str = "",
) -> int:
    if not deal:
        return 0
    count = IgFollowUpTask.objects.filter(
        deal=deal,
        status=IgFollowUpTask.Status.PENDING,
    ).filter(
        Q(kind=IgFollowUpTask.Kind.FULFILLMENT)
        | Q(
            kind=IgFollowUpTask.Kind.MANAGER_TASK,
            reason="paid_missing_delivery",
        )
    ).update(
        status=IgFollowUpTask.Status.CANCELLED,
        skip_reason=(reason or "fulfillment_complete")[:255],
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
    IgFollowUpTask.Kind.FULFILLMENT,
)
SALES_FREQUENCY_LIMITED_KINDS = tuple(
    kind for kind in CUSTOMER_FACING_KINDS
    if kind != IgFollowUpTask.Kind.FULFILLMENT
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
        kind__in=SALES_FREQUENCY_LIMITED_KINDS,
        sent_at__isnull=False,
    )
    recent_cutoff = now - timedelta(hours=MIN_HOURS_BETWEEN_AUTOMATED_TOUCHES)
    if sent.filter(sent_at__gt=recent_cutoff).exists():
        return "frequency_limit"
    month_cutoff = now - timedelta(days=30)
    if sent.filter(sent_at__gt=month_cutoff).count() >= MAX_AUTOMATED_TOUCHES_PER_30_DAYS:
        return "frequency_limit"
    return ""


def _client_allows_followup(
    client: IgClient,
    *,
    deal: IgDeal | None = None,
    kind: str | None = None,
) -> tuple[bool, str]:
    is_fulfillment = kind == IgFollowUpTask.Kind.FULFILLMENT
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
    if not is_fulfillment:
        frequency_reason = _frequency_limit_reason(client)
        if frequency_reason:
            return False, frequency_reason
    if deal is not None:
        if (
            not is_fulfillment
            and verified_payment_deals(IgDeal.objects.filter(pk=deal.pk)).exists()
        ):
            return False, "already_converted"
        projection = getattr(deal, "payment_projection", None)
        truth = projection.truth if projection else deal.payment_truth
        if truth in TERMINAL_NEGATIVE_PAYMENT_TRUTHS:
            return False, "payment_reversed"
    else:
        if not is_fulfillment and client_has_confirmed_purchase(client):
            return False, "already_converted"
        if client_has_terminal_negative_payment(client):
            return False, "payment_reversed"
    if client.primary_objection == IgClient.Objection.NO_BUY or client.lost_reason in {"no_buy", "stop"}:
        return False, "client_no_buy"
    return True, ""


def _delivery_details_complete(deal: IgDeal | None) -> bool:
    if deal is None:
        return False
    return all(
        str(value or "").strip()
        for value in (
            deal.np_full_name,
            deal.np_phone,
            deal.np_city,
            deal.np_office,
        )
    )


def _deal_is_paid(deal: IgDeal | None) -> bool:
    if deal is None:
        return False
    if deal.status in {IgDeal.Status.PAID, IgDeal.Status.ORDER_CREATED}:
        return True
    return verified_payment_deals(IgDeal.objects.filter(pk=deal.pk)).exists()


def _stock_gap_present(client: IgClient) -> bool:
    context = client.sales_context if isinstance(client.sales_context, dict) else {}
    gap = context.get("_stock_gap")
    if not isinstance(gap, dict):
        return False
    product_id = int(getattr(client, "current_product_id", 0) or 0)
    try:
        gap_product_id = int(gap.get("product_id") or 0)
    except (TypeError, ValueError):
        return False
    return bool(gap_product_id and (not product_id or gap_product_id == product_id))


def resolve_followup_scenario(
    client: IgClient,
    *,
    deal: IgDeal | None = None,
) -> str:
    """Resolve one funnel scenario from durable commerce facts first."""
    if not client:
        return ""
    if deal is not None:
        if _deal_is_paid(deal) and not _delivery_details_complete(deal):
            return "paid_missing_delivery"
        if not _deal_is_paid(deal) and _delivery_details_complete(deal):
            return "delivery_ready_unpaid"
        if deal.status == IgDeal.Status.AWAITING_PAYMENT:
            return "payment_link_unpaid"
    if client.stage == IgClient.Stage.PAYMENT_PENDING:
        return "payment_link_unpaid"
    if _stock_gap_present(client):
        return "restock_wait"
    if client.primary_objection == IgClient.Objection.PRICE:
        return "price_objection"
    if client.primary_objection == IgClient.Objection.THINKING:
        return "thinking_hesitation"
    if client.stage == IgClient.Stage.PRODUCT_MATCHED and not str(
        client.current_size or ""
    ).strip():
        return "missing_customer_size"
    if deal is not None and deal.status == IgDeal.Status.QUOTED:
        return "price_quoted_silence"
    if client.stage in {IgClient.Stage.NEW, IgClient.Stage.QUALIFYING}:
        return "first_reply_silence"
    if client.stage in {IgClient.Stage.PRODUCT_MATCHED, IgClient.Stage.CHECKOUT}:
        return "price_quoted_silence"
    return ""


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
    preserve_reason_on_manager_handoff: bool = False,
) -> IgFollowUpTask | None:
    """Create one pending follow-up, adjusted for quiet hours and Meta window."""
    now = now or _now()
    deadline = meta_window_deadline(client)
    due = next_allowed_send_at(now + delay, deadline=deadline)
    status = IgFollowUpTask.Status.PENDING
    skip_reason = ""
    task_kind = kind
    task_reason = reason
    if deadline and due > deadline and kind != IgFollowUpTask.Kind.MANAGER_TASK:
        # IMP-049: раньше здесь ставился SKIPPED, и ≈половина «подумаю»-добивок
        # исчезала молча — работа существовала, но не была видна как работа.
        # Задача менеджеру со статусом PENDING остаётся в очереди человека.
        task_kind = IgFollowUpTask.Kind.MANAGER_TASK
        if preserve_reason_on_manager_handoff:
            skip_reason = "meta_window_closed"
        else:
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
        if task.kind == IgFollowUpTask.Kind.MANAGER_TASK and not task.message_text:
            task.message_text = compose_followup(task, now=due)
            task.save(update_fields=["message_text", "updated_at"])
    _update_client_next(client)
    return task


def _policy_name(reason: str) -> str:
    reason = str(reason or "")
    return POLICY_REASON_ALIASES.get(reason, reason)


def _policy_step_for_task(
    task: IgFollowUpTask,
) -> tuple[FollowupPolicy, FollowupPolicyStep] | None:
    policy = FOLLOWUP_POLICIES.get(_policy_name(task.reason))
    if policy is None:
        return None
    level = int(task.level or 0)
    if level < 0 or level >= len(policy.steps):
        return None
    return policy, policy.steps[level]


def _policy_condition_holds(
    condition: str,
    client: IgClient,
    *,
    deal: IgDeal | None = None,
) -> bool:
    if condition in {"no_customer_reply", "thinking_unresolved"}:
        if condition == "thinking_unresolved":
            return client.primary_objection == IgClient.Objection.THINKING
        return True
    if condition == "price_unresolved":
        return client.primary_objection == IgClient.Objection.PRICE
    if condition == "customer_size_missing":
        return not str(client.current_size or "").strip()
    if condition == "stock_gap_present":
        return _stock_gap_present(client)
    if condition == "deal_unpaid":
        if deal is None:
            return client.stage == IgClient.Stage.PAYMENT_PENDING
        return not _deal_is_paid(deal) and deal.status != IgDeal.Status.CANCELLED
    if condition == "invoice_expired":
        if deal is None:
            return False
        return _payment_link_status_for_deal(deal, now=_now()) == "expired"
    if condition == "paid_delivery_missing":
        return bool(
            deal
            and not deal.order_id
            and _deal_is_paid(deal)
            and not _delivery_details_complete(deal)
        )
    if condition == "delivery_ready_unpaid":
        return _delivery_details_complete(deal) and not _deal_is_paid(deal)
    if condition == "first_reply_unanswered":
        return client.stage in {IgClient.Stage.NEW, IgClient.Stage.QUALIFYING}
    # Reactive/event conditions are fulfilled by their caller, not a timer.
    if condition == "restock_confirmed":
        return False
    return True


def _persisted_step_kind(step: FollowupPolicyStep) -> str:
    choices = {value for value, _label in IgFollowUpTask.Kind.choices}
    return step.kind if step.kind in choices else IgFollowUpTask.Kind.MANAGER_TASK


def _schedule_policy_step(
    client: IgClient,
    *,
    policy: FollowupPolicy,
    step: FollowupPolicyStep,
    delay: timedelta,
    now: datetime,
    deal: IgDeal | None = None,
    reason: str | None = None,
) -> IgFollowUpTask | None:
    kind = _persisted_step_kind(step)
    return schedule_followup(
        client,
        kind=kind,
        delay=max(delay, timedelta(0)),
        reason=reason or policy.scenario,
        now=now,
        deal=deal,
        discount_percent=step.discount_percent,
        level=step.index,
        preserve_reason_on_manager_handoff=True,
    )


def schedule_policy_followup(
    client: IgClient,
    scenario: str,
    *,
    now: datetime | None = None,
    deal: IgDeal | None = None,
    delay_override: timedelta | None = None,
    reason: str | None = None,
) -> IgFollowUpTask | None:
    policy = FOLLOWUP_POLICIES.get(str(scenario or ""))
    if policy is None:
        return None
    first = next(
        (
            step
            for step in policy.steps
            if step.trigger == "time" and step.offset is not None
        ),
        None,
    )
    if first is None or not _policy_condition_holds(
        first.condition, client, deal=deal
    ):
        return None
    return _schedule_policy_step(
        client,
        policy=policy,
        step=first,
        delay=first.offset if delay_override is None else delay_override,
        now=now or _now(),
        deal=deal,
        reason=reason,
    )


def _schedule_next_policy_step(
    task: IgFollowUpTask,
    client: IgClient,
    *,
    now: datetime,
) -> bool:
    resolved = _policy_step_for_task(task)
    if resolved is None:
        return False
    policy, current = resolved
    target_policy = policy
    next_step = next(
        (
            step
            for step in policy.steps[current.index + 1 :]
            if step.trigger == "time" and step.offset is not None
        ),
        None,
    )
    reason = task.reason
    if next_step is None and policy.next_scenario:
        target_policy = FOLLOWUP_POLICIES[policy.next_scenario]
        next_step = target_policy.steps[policy.next_step_index]
        reason = target_policy.scenario
    if next_step is None:
        return False
    current_offset = current.offset or timedelta(0)
    delay = max(next_step.offset - current_offset, timedelta(0))
    if (
        _persisted_step_kind(next_step) in SALES_FREQUENCY_LIMITED_KINDS
        and delay < timedelta(hours=MIN_HOURS_BETWEEN_AUTOMATED_TOUCHES)
    ):
        delay = timedelta(hours=MIN_HOURS_BETWEEN_AUTOMATED_TOUCHES)
    scheduled = _schedule_policy_step(
        client,
        policy=target_policy,
        step=next_step,
        delay=delay,
        now=now,
        deal=task.deal,
        reason=reason,
    )
    return scheduled is not None


COLD_ON_POLICY_EXHAUSTION = frozenset(
    {
        "payment_link_unpaid",
        "price_quoted_silence",
        "thinking_hesitation",
        "price_objection",
        "missing_customer_size",
        "first_reply_silence",
    }
)


def _complete_policy_after_send(task: IgFollowUpTask, client: IgClient) -> bool:
    resolved = _policy_step_for_task(task)
    if resolved is None:
        return False
    policy, step = resolved
    if step.index != policy.steps[-1].index:
        return False
    if policy.next_scenario:
        return False
    if policy.scenario not in COLD_ON_POLICY_EXHAUSTION:
        return True

    from management.services.ig_funnel_fsm import apply_stage

    with transaction.atomic():
        locked = IgClient.objects.select_for_update().get(pk=client.pk)
        locked.lost_reason = policy.exhausted_reason
        locked.save(update_fields=["lost_reason", "updated_at"])
        apply_stage(
            locked,
            IgClient.Stage.COLD,
            reason=policy.exhausted_reason,
            actor="followup_policy",
        )
    client.lost_reason = locked.lost_reason
    client.stage = locked.stage
    return True


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
    rescue_kind = (
        IgFollowUpTask.Kind.RESCUE if pct == 5 else IgFollowUpTask.Kind.FINAL
    )
    allowed, _why = _client_allows_followup(client, kind=rescue_kind)
    if not allowed:
        return None
    return schedule_followup(
        client,
        kind=rescue_kind,
        delay=timedelta(hours=12),
        reason="discount_rescue",
        now=now,
        discount_percent=pct,
        level=int(client.followup_level or 0) + 1,
    )


def schedule_payment_followup(deal: IgDeal, *, now: datetime | None = None) -> IgFollowUpTask | None:
    if not deal or not deal.client_id:
        return None
    allowed, _why = _client_allows_followup(
        deal.client,
        deal=deal,
        kind=IgFollowUpTask.Kind.PAYMENT,
    )
    if not allowed:
        return None
    return schedule_policy_followup(
        deal.client,
        "payment_link_unpaid",
        now=now,
        deal=deal,
    )


def schedule_after_inbound(client: IgClient, *, reason: str = "client_reply") -> None:
    """A client reply cancels automated reminders until the bot/manager answers again."""
    cancel_pending(client, reason=reason)


def schedule_after_bot_reply(client: IgClient, *, reply: str = "", control: dict | None = None, deal: IgDeal | None = None) -> IgFollowUpTask | None:
    if not client:
        return None
    scenario = resolve_followup_scenario(client, deal=deal)
    policy = FOLLOWUP_POLICIES.get(scenario)
    first_step = policy.steps[0] if policy and policy.steps else None
    kind = _persisted_step_kind(first_step) if first_step else None
    allowed, why = _client_allows_followup(client, deal=deal, kind=kind)
    if not allowed:
        cancel_pending(client, reason=why)
        return None
    now = _now()
    proposal = None
    if deal is not None:
        try:
            proposal = deal.active_checkout_proposal
        except Exception:
            proposal = None
    if proposal is not None and proposal.status in {
        proposal.Status.READY,
        proposal.Status.VIEWED,
    }:
        delay = max(proposal.expires_at - now, timedelta(0))
        return schedule_policy_followup(
            client,
            "payment_link_unpaid",
            now=now,
            deal=deal,
            delay_override=delay,
            reason="checkout_proposal_abandoned",
        )
    return schedule_policy_followup(
        client,
        scenario,
        now=now,
        deal=deal,
    )


def schedule_fulfillment_followup(
    deal: IgDeal,
    *,
    now: datetime | None = None,
) -> IgFollowUpTask | None:
    if not deal or not deal.client_id:
        return None
    existing = IgFollowUpTask.objects.filter(
        deal=deal,
        status=IgFollowUpTask.Status.PENDING,
        reason="paid_missing_delivery",
        level=0,
    ).filter(
        Q(kind=IgFollowUpTask.Kind.FULFILLMENT)
        | Q(kind=IgFollowUpTask.Kind.MANAGER_TASK)
    ).order_by("id").first()
    if existing is not None:
        return existing
    allowed, _why = _client_allows_followup(
        deal.client,
        deal=deal,
        kind=IgFollowUpTask.Kind.FULFILLMENT,
    )
    if not allowed:
        return None
    return schedule_policy_followup(
        deal.client,
        "paid_missing_delivery",
        now=now,
        deal=deal,
    )


def _lang(client: IgClient) -> str:
    language = (client.language or "").lower()
    if language.startswith("en"):
        return "en"
    return "ru" if language.startswith("ru") else "uk"


def _format_money(value) -> str:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return ""
    if not amount.is_finite() or amount <= 0:
        return ""
    return format(amount, "f").rstrip("0").rstrip(".")


def _payment_link_status_for_deal(deal: IgDeal, *, now: datetime) -> str:
    from management.services.bot_payments import invoice_link_state

    state = invoice_link_state(deal, now=now).get("status")
    if state != "none":
        return state or "unknown"
    try:
        proposal = deal.active_checkout_proposal
    except Exception:
        proposal = None
    if proposal is None:
        return "unknown"
    if proposal.status == proposal.Status.PAID:
        return "paid"
    return "expired" if now >= proposal.expires_at else "live"


def _payment_link_status(task: IgFollowUpTask, *, now: datetime) -> str:
    deal = task.deal
    if deal is None:
        return "unknown"
    return _payment_link_status_for_deal(deal, now=now)


def _payment_followup_copy(task: IgFollowUpTask, language: str, *, now: datetime) -> str:
    if int(task.level or 0) >= 1:
        return {
            "uk": (
                "Підкажіть, будь ласка, чи замовлення ще актуальне? Якщо зупинило "
                "питання про розмір, доставку або оплату - допоможу коротко і по факту. "
                "Якщо передумали, напишіть «ні», і більше не турбуватиму."
            ),
            "ru": (
                "Подскажите, пожалуйста, заказ ещё актуален? Если остановил вопрос о "
                "размере, доставке или оплате - помогу коротко и по делу. Если передумали, "
                "напишите «нет», и больше не буду беспокоить."
            ),
            "en": (
                "Is the order still relevant? If a question about size, delivery, or payment "
                "is holding you back, I can help. If you changed your mind, reply 'no' and I "
                "will not message again."
            ),
        }[language]

    status = _payment_link_status(task, now=now)
    if status == "live":
        return {
            "uk": (
                "Нагадаю: посилання на оплату ще активне. Якщо щось не відкривається "
                "або потрібна допомога з оплатою - напишіть, підкажу. Якщо передумали, "
                "просто скажіть, і я не турбуватиму."
            ),
            "ru": (
                "Напомню: ссылка на оплату ещё активна. Если что-то не открывается или "
                "нужна помощь с оплатой - напишите, подскажу. Если передумали, просто "
                "скажите, и я не буду беспокоить."
            ),
            "en": (
                "A quick reminder: the payment link is still active. If it does not open or "
                "you need help with payment, reply here. If you changed your mind, just tell "
                "me and I will not message again."
            ),
        }[language]
    if status == "expired":
        return {
            "uk": (
                "Персональна пропозиція вже неактивна. Якщо замовлення ще актуальне, "
                "напишіть «так» - зроблю нову. Товари й параметри збережені, нічого "
                "повторювати не треба."
            ),
            "ru": (
                "Персональное предложение уже неактивно. Если заказ ещё актуален, "
                "напишите «да» - сделаю новое. Товары и параметры сохранены, ничего "
                "повторять не нужно."
            ),
            "en": (
                "The personal offer is no longer active. If the order is still relevant, "
                "reply 'yes' and I will create a new one. Your items and options are saved, "
                "so you do not need to repeat anything."
            ),
        }[language]
    return {
        "uk": (
            "Не хочу вгадувати стан посилання: перевірю його перед повторною відправкою. "
            "Якщо оплата не відкривається, напишіть сюди - підготую актуальний варіант."
        ),
        "ru": (
            "Не хочу угадывать состояние ссылки: проверю её перед повторной отправкой. "
            "Если оплата не открывается, напишите сюда - подготовлю актуальный вариант."
        ),
        "en": (
            "I do not want to guess the link status. I will check it before sending it again. "
            "If payment does not open, reply here and I will prepare a current option."
        ),
    }[language]


def _policy_followup_copy(
    task: IgFollowUpTask,
    language: str,
    *,
    now: datetime,
) -> str:
    resolved = _policy_step_for_task(task)
    if resolved is None:
        return ""
    _policy, step = resolved
    if step.copy_key == "payment_a1" and _payment_link_status(task, now=now) == "expired":
        return _payment_followup_copy(task, language, now=now)
    if step.copy_key == "payment_a3" and _payment_link_status(task, now=now) != "live":
        return _payment_followup_copy(task, language, now=now)
    if step.copy_key == "payment_a4" and _payment_link_status(task, now=now) != "expired":
        return _payment_followup_copy(task, language, now=now)
    variants = FOLLOWUP_POLICY_COPY.get(step.copy_key) or {}
    text = str(variants.get(language) or variants.get("uk") or "")
    if not text:
        return ""
    invoice_url = str(getattr(task.deal, "invoice_url", "") or "").strip()
    if not invoice_url:
        invoice_url = {
            "uk": "напишіть, і підготую актуальне",
            "ru": "напишите, и подготовлю актуальную",
            "en": "reply and I will prepare a current one",
        }[language]
    return text.format(invoice_url=invoice_url)


def compose_followup(task: IgFollowUpTask, *, now: datetime | None = None) -> str:
    client = task.client
    language = _lang(client)
    ru = language == "ru"
    en = language == "en"
    pct = int(task.discount_percent or 0)
    policy_copy = _policy_followup_copy(task, language, now=now or _now())
    if policy_copy:
        return policy_copy
    if task.kind == IgFollowUpTask.Kind.PAYMENT:
        return _payment_followup_copy(task, language, now=now or _now())
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
        original = _format_money(getattr(task.deal, "amount", None))
        discounted = ""
        if original:
            discounted = _format_money(
                Decimal(str(task.deal.amount)) * Decimal("0.95")
            )
        if original and discounted:
            if en:
                return (
                    f"For a first order, I can offer 5% off: {discounted} UAH instead "
                    f"of {original} UAH. Shall we place the order?"
                )
            return (
                f"Для первого заказа могу сделать скидку 5%: получится {discounted} грн вместо {original}. Оформляем?"
                if ru else
                f"Для першого замовлення можу зробити знижку 5%: вийде {discounted} грн замість {original}. Оформлюємо?"
            )
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
                "I will keep this brief: what is holding you back - size, price, or "
                "something else? If it is no longer relevant, tell me and I will not "
                "message again."
            )
        return (
            "Не буду отнимать много времени: подскажите, что остановило - размер, цена или что-то ещё? Если заказ уже не актуален, скажите, и больше не буду писать."
            if ru else
            "Не забиратиму багато часу: підкажіть, що зупинило - розмір, ціна чи щось інше? Якщо замовлення вже не актуальне, скажіть, і більше не писатиму."
        )
    if en:
        return "Is the order still relevant? If yes, I can place it in two minutes; only the size is left. If not, reply 'no' and I will close it."
    return (
        "Подскажите, заказ ещё актуален? Если да - оформлю всё за 2 минуты, осталось определить размер. Если нет - напишите «нет», и я закрою вопрос."
        if ru else
        "Підкажіть, чи ще актуально? Якщо так - я за 2 хвилини все оформлю, залишилось тільки визначитись із розміром. Якщо ні - напишіть «ні», і я закрию питання."
    )


def _mark_skipped(task: IgFollowUpTask, reason: str) -> None:
    task.status = IgFollowUpTask.Status.SKIPPED
    task.skip_reason = (reason or "skipped")[:255]
    task.updated_at = _now()
    task.save(update_fields=["status", "skip_reason", "updated_at"])
    _update_client_next(task.client)


def _escalate_missing_delivery(task: IgFollowUpTask, client: IgClient) -> bool:
    if not (
        task.kind == IgFollowUpTask.Kind.FULFILLMENT
        and task.reason == "paid_missing_delivery"
        and int(task.level or 0) == 2
        and task.deal_id
    ):
        return False
    from management.services.ig_alerts import client_admin_url, format_alert
    from management.services.instagram_bot import notify_manager

    deal = task.deal
    missing = [
        label
        for label, value in (
            ("ПІБ", deal.np_full_name),
            ("телефон", deal.np_phone),
            ("місто", deal.np_city),
            ("відділення", deal.np_office),
        )
        if not str(value or "").strip()
    ]
    text = format_alert(
        "IG: оплачено, але дані доставки не зібрані за 20 годин",
        lines=(
            f"Угода #{deal.pk}",
            f"Бракує: {', '.join(missing) or 'перевірки даних'}",
        ),
        url=client_admin_url(client.pk),
        url_label="Відкрити клієнта:",
    )
    return notify_manager(
        text,
        dedupe_key=f"fulfillment_missing_delivery:{deal.pk}:g3",
        event_type="fulfillment_missing_delivery",
        client=client,
    )


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
                fresh_client,
                deal=stale_task.deal if stale_task else None,
                kind=stale_task.kind if stale_task else None,
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
    allowed, why = _client_allows_followup(
        client,
        deal=task.deal,
        kind=task.kind,
    )
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
    allowed, why = _client_allows_followup(
        client,
        deal=task.deal,
        kind=task.kind,
    )
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
        .exclude(kind=IgFollowUpTask.Kind.MANAGER_TASK)
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
            policy_step = _policy_step_for_task(task)
            if policy_step is not None and not _policy_condition_holds(
                policy_step[1].condition,
                client,
                deal=task.deal,
            ):
                _mark_skipped(task, "policy_condition_changed")
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
            sales_followup = task.kind != IgFollowUpTask.Kind.FULFILLMENT
            if sales_followup:
                client.followup_level = max(
                    int(client.followup_level or 0),
                    int(task.level or 0) + 1,
                )
            if sales_followup and task.discount_percent:
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
            client_update_fields = [
                "last_bot_reply_at", "next_followup_at", "updated_at",
            ]
            if sales_followup:
                client_update_fields.extend(
                    ["followup_level", "discount_offered_percent"]
                )
            client.save(update_fields=client_update_fields)
            sent += 1
            _escalate_missing_delivery(task, client)
            policy_completed = _complete_policy_after_send(task, client)
            policy_scheduled = False
            if not policy_completed:
                policy_scheduled = _schedule_next_policy_step(task, client, now=now)
            if (
                policy_step is None
                and not policy_scheduled
                and not task.discount_percent
                and task.kind in {
                IgFollowUpTask.Kind.QUALIFICATION,
                IgFollowUpTask.Kind.THINKING,
                IgFollowUpTask.Kind.PAYMENT,
                }
            ):
                schedule_rescue_offer(client, now=now)
        finally:
            if reply_boundary_entered:
                reply_boundary.__exit__(*sys.exc_info())
            instagram_bot.release_client_automation_lease(client.id, lease_token)
    return sent
