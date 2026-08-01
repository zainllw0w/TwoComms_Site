"""Deterministic sales-signal classifier for the Instagram Direct bot.

This is a lightweight pre/post processor around Gemini. It must be cheap enough
to run for every inbound and manager echo message, and conservative enough not
to invent product/price facts.
"""
from __future__ import annotations

import re
from decimal import Decimal
from typing import Iterable

from django.db.models import Q
from django.db.models.functions import Coalesce
from django.utils import timezone

from management.models import (
    IgClient,
    IgConversationAnalysisSnapshot,
    IgConversationSignal,
    IgDeal,
    InstagramBotMessage,
)
from management.services.ig_funnel_reset import current_message_floor

ANALYSIS_RULES_VERSION = "2026-07-30.v6"


UK_HINTS = (
    "ціна", "скільки", "розмір", "подарунок", "передоплат", "наклад", "відправ",
    "дякую", "хочу", "можна", "собі", "друк", "футболк",
)
RU_HINTS = (
    "цена", "сколько", "размер", "подарок", "предоплат", "налож", "отправ",
    "спасибо", "хочу", "можно", "себе", "печать", "футболк",
)
EN_HINTS = (
    "hello", "hi", "greetings", "please", "thanks", "thank", "order",
    "status", "delivery", "deliver", "ship", "tracking", "return", "refund",
    "exchange", "collaboration", "partnership", "price", "cost", "want",
    "need", "help", "what", "how", "where", "when", "can", "could", "yes",
    "no", "good", "afternoon", "morning", "evening", "show", "interested",
    "available", "buy",
)
URL_RE = re.compile(r"(?:https?://|www\.)\S+", re.I)
NO_BUY_RE = re.compile(
    r"\b(?:не\s+буду\s+(?:брати|брать|купувати|покупать|замовляти|заказывать)|"
    r"не\s+хочу\s+(?:купувати|покупать|замовляти|заказывать)|"
    r"(?:брати|брать|купувати|покупать|замовляти|заказывать)\s+не\s+(?:буду|хочу)|"
    r"відмовляюсь\s+від\s+(?:покупки|замовлення)|"
    r"отказываюсь\s+от\s+(?:покупки|заказа))\b",
    re.I,
)
OPT_OUT_RE = re.compile(
    r"(?:\b(?:не\s+(?:пиш(?:и|іть|ите)(?:\s+мені|\s+мне)?|"
    r"надсилайте|присылайте|відправляйте|отправляйте)|"
    r"(?:мені|мне)\s+не\s+(?:потрібно|нужно)\s+(?:більше\s+|больше\s+)?(?:писати|писать)|"
    r"(?:мене|меня)\s+не\s+(?:цікавить|интересует)\s+(?:ця\s+|эта\s+)?(?:розсилка|рассылка)|"
    r"не\s+хочу\s+(?:більше\s+|больше\s+)?(?:отримувати|получать)\s+(?:повідомлення|сообщения|розсилку|рассылку)|"
    r"відпишіть\s+мене|отпишите\s+меня|відписатися|отписаться|"
    r"приберіть\s+(?:мене\s+)?з\s+розсилки|уберите\s+(?:меня\s+)?из\s+рассылки|"
    r"unsubscribe|(?:do\s+not|don['’]?t)\s+(?:message|contact)\s+me(?:\s+again)?|"
    r"i\s+(?:do\s+not|don['’]?t)\s+want\s+(?:any\s+)?more\s+messages)\b|"
    r"^\s*stop\s*$|\bstop\s+(?:messaging(?:\s+me)?|sending\s+(?:me\s+)?messages)\b)",
    re.I,
)


def is_explicit_opt_out(text: str) -> bool:
    """Return deterministic consent truth without CRM or provider side effects."""
    return bool(OPT_OUT_RE.search(str(text or "")))
THINKING_RE = re.compile(r"\b(подумаю|подумаємо|думаю|подума|позже|пізніше|потом)\b", re.I)
DEFER_RE = re.compile(
    r"\b(не\s+зараз|не\s+сейчас|пізніше|позже|подумаю|подумаємо|потом|"
    r"немає\s+(?:мого\s+)?(?:розміру|кольору)|нет\s+(?:моего\s+)?(?:размера|цвета))\b",
    re.I,
)
PRICE_RE = re.compile(r"\b(дорого|дорогувато|цена|ціна|сколько|скільки|price|cost|how\s+much|вартість)\b", re.I)
PREPAY_RE = re.compile(r"\b(предоплат|передоплат|налож|наклад|післяплат|без\s+пред|без\s+перед)\b", re.I)
SIZE_RE = re.compile(r"\b(размер|розмір|size|size\s+guide|fit|сітка|сетка|oversize|оверсайз|regular|регуляр|xs|s|m|l|xl|xxl)\b", re.I)
CUSTOM_REQUEST_RE = re.compile(
    r"(?:\b(?:кастом(?:н\w*)?|custom)(?:\s+(?:принт\w*|дизайн\w*))?\b|"
    r"\b(?:св(?:ой|ій)|власн\w*|мо[йяє]|мій)\s+(?:принт\w*|дизайн\w*)\b|"
    r"\b(?:зроб(?:іть|ити)|сдел(?:айте|ать)|надрук\w*|напечат\w*|нанес\w*|"
    r"змін(?:ити|іть|ювати)|измен(?:ить|ите))\b.{0,80}\b"
    r"(?:принт\w*|дизайн\w*|зображенн\w*|изображен\w*)\b|"
    r"\b(?:принт\w*|дизайн\w*|зображенн\w*|изображен\w*)\b.{0,80}\b"
    r"(?:зроб(?:іть|ити)|сдел(?:айте|ать)|надрук\w*|напечат\w*|нанес\w*|"
    r"змін(?:ити|іть|ювати)|измен(?:ить|ите))\b)",
    re.I,
)
PRODUCT_RE = re.compile(
    r"\b(товар\w*|футболк\w*|худі|худи|лонгслів\w*|одяг\w*|одежд\w*|"
    r"колекц\w*|модель\w*|термохром\w*|product\w*|t-?shirt\w*|shirt\w*|"
    r"hoodie\w*|longsleeve\w*|clothing)\b",
    re.I,
)
PAYMENT_RE = re.compile(r"\b(оплат\w*|платеж\w*|платіж\w*|payment|pay|checkout|invoice|ссылка|посилання|линк|лінк|link|card|карта|monobank|монобанк)\b", re.I)
DELIVERY_RE = re.compile(r"\b(достав|відправ|отправ|delivery|deliver\w*|ship\w*|tracking|nova\s+poshta|нова\s+пошта|новая\s+почта|нп|branch|відділен|отделен)\b", re.I)
ORDER_STATUS_RE = re.compile(
    r"(?:\b(?:order|замовлен\w*|заказ\w*)\b.{0,80}"
    r"\b(?:status|where|when|tracking|delivery|deliver\w*|ship\w*|статус|де|где|коли|когда|достав\w*|відправ\w*|отправ\w*)\b|"
    r"\b(?:status|where|when|tracking|статус|де|где|коли|когда)\b.{0,80}"
    r"\b(?:order|замовлен\w*|заказ\w*)\b|"
    r"\bTWC[A-Z0-9-]{5,30}\b)",
    re.I,
)
GIFT_RE = re.compile(r"\b(подарок|подарунок|на\s+подар|в\s+подар)\b", re.I)
SELF_RE = re.compile(r"\b(себе|собі|для\s+себя|для\s+себе)\b", re.I)
PHONE_RE = re.compile(r"(?:\+?38)?0\d{9}")
QTY_RE = re.compile(r"\b(?:x|х|×)?\s*(\d{1,2})\s*(?:шт|штук|pcs|од)\b", re.I)
SIZE_TOKEN_RE = re.compile(r"\b(xs|s|m|l|xl|xxl|xxxl|2xl|3xl)\b", re.I)
COLLAB_RE = re.compile(
    r"\b(коллаб\w*|колаб\w*|collab\w*|cooperat\w*|partnership\w*|creator|креатор|блогер\w*|інфлюенсер\w*|"
    r"инфлюенсер\w*|партнерств\w*|співпрац\w*|сотруднич\w*|постачальник\w*|"
    r"поставщик\w*|supplier\w*|sponsor\w*|influencer\w*)\b",
    re.I,
)
WHOLESALE_RE = re.compile(
    r"(?:\b(опт\w*|оптов\w*|wholesale|b2b|дропшип\w*|тираж\w*|партію|партия)\b|"
    r"\b(?:для|в)\s+(?:магазин\w*|бутик\w*))",
    re.I,
)
SUPPORT_RE = re.compile(
    r"(?:\b(?:скарг\w*|жалоб\w*|проблем\w*|problem\w*|issue\w*|damaged|wrong|"
    r"refund\w*|return\w*|exchange\w*|брак\w*|поверн\w*|обмін\w*|обмен\w*|"
    r"верн(?:іть|ите)|пошкодж\w*|підтримк\w*|поддержк\w*)\b|"
    r"\b(?:товар\w*|замовлен\w*|заказ\w*|посилк\w*|посылк\w*)\s+не\s+"
    r"(?:прийш(?:ов|ла|ло|ли)|приш(?:ёл|ел|ла|ло|ли)|доставлен\w*)\b|"
    r"\bне\s+(?:прийш(?:ов|ла|ло|ли)|приш(?:ёл|ел|ла|ло|ли)|достав(?:или|лено))\s+"
    r"(?:товар\w*|замовлен\w*|заказ\w*|посилк\w*|посылк\w*)\b|"
    r"\bне\s+(?:отримав|отримала|отримали|получил|получила|получили)\s+"
    r"(?:товар\w*|замовлен\w*|заказ\w*|посилк\w*|посылк\w*)\b|"
    r"\b(?:товар\w*|замовлен\w*|заказ\w*|посилк\w*|посылк\w*)\s+не\s+"
    r"(?:отриман\w*|получен\w*)\b|"
    r"\b(?:принт\w*|друк\w*|печать)\s+"
    r"(?:не\s+то[йяе]|не\s+такий|інш\w*|друг\w*)\b)",
    re.I,
)
COMMUNITY_RE = re.compile(
    r"\b(мем\w*|прикол\w*|прикольно|круто|топчик|класно|классно|ахаха|смішн\w*|смешн\w*)\b",
    re.I,
)
COLOR_WORDS = {
    "чорн": "black",
    "черн": "black",
    "білий": "white",
    "бел": "white",
    "олив": "olive",
    "хакі": "khaki",
    "хаки": "khaki",
    "сір": "gray",
    "сер": "gray",
}
REACTION_MARKS = ("🔥", "❤", "👍", "👏", "😍", "😂", "🥰", "🙌", "💯", "🙏", "✨", "😊")


def is_reaction_only(text: str) -> bool:
    value = (text or "").strip()
    return bool(
        value
        and len(value) <= 24
        and not any(char.isalnum() for char in value)
        and any(mark in value for mark in REACTION_MARKS)
    )


def is_explicit_custom_print_request(text: str) -> bool:
    """Return true only for explicit manufacturing or design-change intent."""
    value = str(text or "")
    return bool(
        CUSTOM_REQUEST_RE.search(value)
        and not SUPPORT_RE.search(value)
        and not COLLAB_RE.search(value)
    )


def _contains_any(text: str, terms: Iterable[str]) -> int:
    low = text.lower()
    return sum(1 for term in terms if term in low)


def detect_language(text: str) -> str:
    low = URL_RE.sub(" ", (text or "").lower())
    has_cyrillic = bool(re.search(r"[а-яёіїєґ]", low))
    if re.search(r"[a-z]", low) and not has_cyrillic:
        words = re.findall(r"[a-z]+", low)
        if any(word in EN_HINTS for word in words):
            return "en"
        return ""
    if not has_cyrillic:
        return ""
    if re.search(r"[їєіґ]", low):
        return "uk"
    uk = _contains_any(low, UK_HINTS)
    ru = _contains_any(low, RU_HINTS)
    if uk > ru:
        return "uk"
    if ru > uk:
        return "ru"
    return "uk" if any(ch in low for ch in "іїєґ") else "ru"


def _signal(client, signal_type: str, *, message=None, confidence: float = 0.9, value: str = "", payload=None):
    message_obj = message if isinstance(message, InstagramBotMessage) else None
    fields = {
        "client": client,
        "message": message_obj,
        "signal_type": signal_type,
        "value": (value or "")[:255],
    }
    defaults = {
        "confidence": Decimal(str(confidence)),
        "payload": payload or {},
    }
    if message_obj is not None:
        signal, _created = IgConversationSignal.objects.get_or_create(
            **fields,
            defaults=defaults,
        )
        return signal
    return IgConversationSignal.objects.create(**fields, **defaults)


def _resolve_readiness(
    previous: int,
    turn_score: int,
    *,
    preserve: bool = False,
    hard_zero: bool = False,
    soft_negative: bool = False,
    verified_payment: bool = False,
) -> int:
    """Resolve the compatibility score without cumulatively adding repeats."""
    previous = max(0, min(100, int(previous or 0)))
    turn_score = max(0, min(100, int(turn_score or 0)))
    if verified_payment:
        return 100
    if hard_zero:
        return 0
    if preserve:
        return previous
    if soft_negative:
        return min(35, max(turn_score, previous - 15))
    if turn_score:
        return max(turn_score, min(previous, 70))
    return max(0, previous - 10)


def _extract_context(text: str) -> dict:
    low = (text or "").lower()
    ctx: dict = {}
    qty = QTY_RE.search(low)
    if qty:
        try:
            ctx["quantity"] = max(1, min(99, int(qty.group(1))))
        except Exception:
            pass
    size = SIZE_TOKEN_RE.search(low)
    if size:
        ctx["size"] = size.group(1).upper()
    for stem, color in COLOR_WORDS.items():
        if stem in low:
            ctx["color"] = color
            break
    if GIFT_RE.search(low):
        ctx["gift"] = True
    if SELF_RE.search(low):
        ctx["self_purchase"] = True
    return ctx


def _record_context_provenance(
    sales_context: dict,
    context: dict,
    *,
    message=None,
    role: str = "",
    confidence: float = 0.8,
) -> dict:
    """Keep legacy flat context while recording bounded source/conflict memory."""
    if not isinstance(sales_context, dict) or not isinstance(context, dict):
        return sales_context if isinstance(sales_context, dict) else {}
    provenance = sales_context.setdefault("_provenance", {})
    if not isinstance(provenance, dict):
        provenance = {}
        sales_context["_provenance"] = provenance
    source_id = getattr(message, "pk", None)
    source_role = role or getattr(message, "role", "") or "unknown"
    observed_at = timezone.now().isoformat()
    for key, value in context.items():
        if value in (None, ""):
            continue
        previous = provenance.get(key)
        record = {
            "value": value,
            "source_message_id": source_id,
            "source_role": source_role,
            "observed_at": observed_at,
            "confidence": max(0.0, min(1.0, float(confidence))),
            "conflict": False,
        }
        if isinstance(previous, dict) and previous.get("value") != value:
            history = previous.get("history") if isinstance(previous.get("history"), list) else []
            history.append({
                "value": previous.get("value"),
                "source_message_id": previous.get("source_message_id"),
                "source_role": previous.get("source_role"),
                "observed_at": previous.get("observed_at"),
            })
            record["history"] = history[-4:]
            record["conflict"] = True
        elif isinstance(previous, dict) and isinstance(previous.get("history"), list):
            record["history"] = previous["history"][-4:]
            record["conflict"] = bool(previous.get("conflict"))
        provenance[key] = record
        sales_context[key] = value
    return sales_context


def _analysis_band(client: IgClient, result: dict) -> str:
    from management.services.bot_payment_truth import client_has_confirmed_purchase

    # CRM presentation, not provider revenue: a purchase confirmed by a manager
    # is still a purchase for the person we are talking to (IMP-013).
    if client_has_confirmed_purchase(client):
        return IgConversationAnalysisSnapshot.Band.PAID
    if result.get("interaction_type") == IgConversationAnalysisSnapshot.InteractionType.OPT_OUT:
        return IgConversationAnalysisSnapshot.Band.OPTED_OUT
    if result.get("no_buy"):
        return IgConversationAnalysisSnapshot.Band.LOST
    if client.stage == IgClient.Stage.SPAM:
        return IgConversationAnalysisSnapshot.Band.LOST
    if client.stage in {IgClient.Stage.CHECKOUT, IgClient.Stage.PAYMENT_PENDING}:
        return IgConversationAnalysisSnapshot.Band.CHECKOUT
    if IgConversationSignal.Type.CHECKOUT_STARTED in result.get("signals", []):
        return IgConversationAnalysisSnapshot.Band.HIGH_INTENT
    if int(result.get("readiness") or 0) >= 40 or client.current_product_id:
        return IgConversationAnalysisSnapshot.Band.QUALIFIED
    if result.get("signals") or client.intent != IgClient.Intent.UNKNOWN:
        return IgConversationAnalysisSnapshot.Band.EXPLORING
    return IgConversationAnalysisSnapshot.Band.COLD


_OBSERVED_FUNNEL_ORDER = [
    IgClient.Stage.NEW,
    IgClient.Stage.QUALIFYING,
    IgClient.Stage.PRODUCT_MATCHED,
    IgClient.Stage.CHECKOUT,
    IgClient.Stage.PAYMENT_PENDING,
    IgClient.Stage.PAID,
    IgClient.Stage.ORDER_CREATED,
    IgClient.Stage.DONE,
]
_OBSERVED_FUNNEL_RANK = {
    value: index for index, value in enumerate(_OBSERVED_FUNNEL_ORDER)
}


def observed_stage_target(
    current_stage: str,
    *,
    signal_types: Iterable[str] = (),
    intent: str = "",
    has_product: bool = False,
    has_size: bool = False,
    payment_pending: bool = False,
    verified_payment: bool = False,
    order_created: bool = False,
) -> str:
    """Return a monotonic evidence-backed funnel stage without reply coupling."""
    if current_stage == IgClient.Stage.SPAM:
        return current_stage
    signals = set(signal_types or ())
    signals.discard(IgConversationSignal.Type.MANAGER_TAKEOVER)
    target = IgClient.Stage.NEW
    if signals or intent not in {"", IgClient.Intent.UNKNOWN} or has_size:
        target = IgClient.Stage.QUALIFYING
    if has_product:
        target = IgClient.Stage.PRODUCT_MATCHED
    if (
        IgConversationSignal.Type.CHECKOUT_STARTED in signals
        or intent == IgClient.Intent.PAYMENT
    ):
        target = IgClient.Stage.CHECKOUT
    if payment_pending:
        target = IgClient.Stage.PAYMENT_PENDING
    if verified_payment:
        target = IgClient.Stage.PAID
    if verified_payment and order_created:
        target = IgClient.Stage.ORDER_CREATED
    current_rank = _OBSERVED_FUNNEL_RANK.get(current_stage, -1)
    target_rank = _OBSERVED_FUNNEL_RANK.get(target, -1)
    if current_stage == IgClient.Stage.COLD and not (
        verified_payment or payment_pending or order_created
    ):
        return current_stage
    if current_stage == IgClient.Stage.LEAD_TO_MANAGER and target not in {
        IgClient.Stage.CHECKOUT,
        IgClient.Stage.PAYMENT_PENDING,
        IgClient.Stage.PAID,
        IgClient.Stage.ORDER_CREATED,
        IgClient.Stage.DONE,
    }:
        return current_stage
    return target if target_rank > current_rank else current_stage


def project_observed_stage(
    client: IgClient,
    *,
    signal_types: Iterable[str] = (),
    reason: str = "observed_message",
) -> str:
    """Advance CRM stage from stored evidence even while replies are paused."""
    if not client or not getattr(client, "pk", None) or client.hidden_at:
        return getattr(client, "stage", IgClient.Stage.NEW)
    from management.services.bot_payment_truth import client_has_confirmed_purchase

    verified_payment = client_has_confirmed_purchase(client)
    deal_states = set(client.deals.values_list("status", flat=True))
    target = observed_stage_target(
        client.stage,
        signal_types=signal_types,
        intent=client.intent,
        has_product=bool(client.current_product_id),
        has_size=bool(client.current_size),
        payment_pending=IgDeal.Status.AWAITING_PAYMENT in deal_states,
        verified_payment=verified_payment,
        order_created=bool(
            IgDeal.Status.ORDER_CREATED in deal_states
            or client.deals.filter(order_id__isnull=False).exists()
        ),
    )
    if target != client.stage:
        client.set_stage(target, reason=reason)
    return target


def _aggregate_interaction_type(client: IgClient, signal_types: Iterable[str]) -> str:
    signals = set(signal_types or ())
    from management.services.bot_payment_truth import client_has_confirmed_purchase

    types = IgConversationAnalysisSnapshot.InteractionType
    if client_has_confirmed_purchase(client):
        return types.PAID_ORDER_WAITING
    if IgConversationSignal.Type.CHECKOUT_STARTED in signals:
        return types.HIGH_INTENT
    if client.intent == IgClient.Intent.PAYMENT:
        return types.HIGH_INTENT
    if IgConversationSignal.Type.CUSTOM_PRINT in signals:
        return types.CUSTOM_PRINT
    if IgConversationSignal.Type.SIZE_CONCERN in signals:
        return types.SIZE_FIT_QUESTION
    if IgConversationSignal.Type.PRICE_OBJECTION in signals:
        return types.PRICE_OBJECTION
    if IgConversationSignal.Type.PRODUCT_INTEREST in signals:
        return types.PRODUCT_INTEREST
    return types.INFORMATION_ONLY


def reconcile_rules_projection(
    client: IgClient,
    *,
    watermark: int,
) -> IgConversationAnalysisSnapshot | None:
    """Build one no-network snapshot from durable signals for visible clients."""
    if (
        not client
        or client.hidden_at
        or client.is_blocked
        or client.stage == IgClient.Stage.SPAM
    ):
        return None
    existing = client.analysis_snapshots.filter(
        analysis_model="rules",
        rules_version=ANALYSIS_RULES_VERSION,
        last_analyzed_message_id=watermark,
    ).order_by("-id").first()
    signal_types = list(dict.fromkeys(
        client.conversation_signals.filter(
            message_id__gte=current_message_floor(client),
            message_id__lte=watermark,
        )
        .exclude(signal_type=IgConversationSignal.Type.MANAGER_TAKEOVER)
        .order_by("id")
        .values_list("signal_type", flat=True)
    ))
    project_observed_stage(
        client,
        signal_types=signal_types,
        reason="rules_reconcile",
    )
    if existing:
        return existing
    message = client.messages.filter(pk=watermark).first()
    if not message:
        return None
    interaction_type = (
        IgConversationAnalysisSnapshot.InteractionType.MANAGER_OBSERVATION
        if message.role == InstagramBotMessage.Role.MANAGER
        else _aggregate_interaction_type(client, signal_types)
    )
    result = {
        "intent": client.intent,
        "objection": client.primary_objection,
        "readiness": client.buying_readiness,
        "signals": signal_types,
        "no_buy": client.primary_objection == IgClient.Objection.NO_BUY,
        "opt_out": bool(
            client.opted_out_at
            and (not client.opted_in_at or client.opted_in_at < client.opted_out_at)
        ),
        "interaction_type": interaction_type,
    }
    return _record_analysis_snapshot(client, message, result, role=message.role)


def _interaction_type(client: IgClient, result: dict, text: str, role: str) -> str:
    from management.services.bot_payment_truth import client_has_confirmed_purchase

    types = IgConversationAnalysisSnapshot.InteractionType
    if role == InstagramBotMessage.Role.MANAGER:
        return types.MANAGER_OBSERVATION
    if is_reaction_only(text):
        return types.REACTION_ONLY
    if result.get("opt_out"):
        return types.OPT_OUT
    if result.get("no_buy"):
        return types.EXPLICIT_NO_BUY
    if SUPPORT_RE.search(text or ""):
        return types.SUPPORT_COMPLAINT
    if client_has_confirmed_purchase(client):
        return types.PAID_ORDER_WAITING
    if client.stage == IgClient.Stage.SPAM or client.is_blocked:
        return types.SPAM_ABUSE
    if result.get("objection") == IgClient.Objection.NO_REPLY:
        return types.NO_REPLY
    if client.stage == IgClient.Stage.PAYMENT_PENDING:
        return types.PAYMENT_PENDING
    if IgConversationSignal.Type.CHECKOUT_STARTED in result.get("signals", []):
        return types.HIGH_INTENT
    if COLLAB_RE.search(text or ""):
        return types.COLLABORATION
    if WHOLESALE_RE.search(text or ""):
        return types.WHOLESALE_B2B
    if result.get("intent") == IgClient.Intent.CUSTOM_PRINT:
        return types.CUSTOM_PRINT
    if result.get("intent") == IgClient.Intent.SIZE:
        return types.SIZE_FIT_QUESTION
    if result.get("objection") == IgClient.Objection.PRICE:
        return types.PRICE_OBJECTION
    if result.get("intent") == IgClient.Intent.PRODUCT:
        return types.PRODUCT_INTEREST
    if COMMUNITY_RE.search(text or ""):
        return types.COMMUNITY_CASUAL
    if (text or "").strip():
        return types.INFORMATION_ONLY
    return types.UNKNOWN


def _record_analysis_snapshot(
    client: IgClient,
    message: InstagramBotMessage | None,
    result: dict,
    *,
    role: str,
) -> IgConversationAnalysisSnapshot:
    """Persist one rules snapshot per client/message/rules watermark."""
    band = _analysis_band(client, result)
    readiness = max(0, min(100, int(result.get("readiness") or 0)))
    if band == IgConversationAnalysisSnapshot.Band.PAID:
        probability = Decimal("1.0000")
        confidence = Decimal("1.0000")
    elif band in {
        IgConversationAnalysisSnapshot.Band.LOST,
        IgConversationAnalysisSnapshot.Band.OPTED_OUT,
    }:
        probability = Decimal("0.0000")
        confidence = Decimal("0.9500")
    else:
        probability = (Decimal(readiness) / Decimal("100")).quantize(Decimal("0.0001"))
        confidence = min(
            Decimal("0.9000"),
            Decimal("0.5500") + Decimal("0.0500") * len(result.get("signals", [])),
        )

    source_role = role or getattr(message, "role", "") or "unknown"
    evidence = [{
        "source_role": source_role,
        "message_id": getattr(message, "pk", None),
        "manager_evidence": source_role == InstagramBotMessage.Role.MANAGER,
        "signals": list(result.get("signals", [])),
        "intent": result.get("intent") or IgClient.Intent.UNKNOWN,
        "objection": result.get("objection") or IgClient.Objection.NONE,
        "legacy_readiness": readiness,
    }]
    uncertainties = []
    if not client.current_product_id:
        uncertainties.append("product")
    if not client.current_size:
        uncertainties.append("size")
    if (
        result.get("intent") == IgClient.Intent.PAYMENT
        and band != IgConversationAnalysisSnapshot.Band.PAID
    ):
        uncertainties.append("payment_unverified")
    if source_role == InstagramBotMessage.Role.MANAGER:
        uncertainties.append("manager_evidence_not_customer_intent")

    message_key = getattr(message, "pk", None) or "none"
    dedupe_key = f"rules:{ANALYSIS_RULES_VERSION}:{client.pk}:{message_key}"
    snapshot, _created = IgConversationAnalysisSnapshot.objects.get_or_create(
        dedupe_key=dedupe_key,
        defaults={
            "client": client,
            "last_analyzed_message": message if isinstance(message, InstagramBotMessage) else None,
            "score_band": band,
            "interaction_type": result.get("interaction_type") or "unknown",
            "purchase_probability": probability,
            "confidence": confidence,
            "evidence": evidence,
            "uncertainties": uncertainties,
            "analysis_model": "rules",
            "rules_version": ANALYSIS_RULES_VERSION,
            "trigger": "message",
        },
    )
    return snapshot


def classify_message(
    client: IgClient,
    *,
    message: InstagramBotMessage | None = None,
    text: str | None = None,
    role: str = "",
    media_context: list[dict] | None = None,
    operational_effects: bool = True,
) -> dict:
    """Classify a single message and persist CRM state/signals.

    Returns a small dict for callers that need immediate routing decisions.
    """
    if not client:
        return {"signals": [], "readiness": 0}
    text = (text if text is not None else getattr(message, "text", "")) or ""
    low = text.lower()
    role = role or getattr(message, "role", "") or ""
    is_manager = role == InstagramBotMessage.Role.MANAGER
    reaction_only = bool(not is_manager and is_reaction_only(text))
    detected_language = detect_language(text) if text.strip() else ""
    lang = (
        client.language or "uk"
        if is_manager
        else detected_language or client.language or "uk"
    )

    signals: list[str] = []
    # Keep durable sales context for ordinary follow-ups, but custom-print is
    # episode-scoped and must be re-earned from the current turn's evidence.
    intent = client.intent or IgClient.Intent.UNKNOWN
    objection = client.primary_objection or IgClient.Objection.NONE
    if not is_manager and not reaction_only and intent == IgClient.Intent.CUSTOM_PRINT:
        intent = IgClient.Intent.UNKNOWN
    previous_readiness = int(client.buying_readiness or 0)
    readiness = previous_readiness if is_manager or reaction_only else 0
    sales_context = dict(client.sales_context or {})

    ctx = _extract_context(text)
    if ctx:
        _record_context_provenance(
            sales_context,
            ctx,
            message=message,
            role=role,
            confidence=0.85,
        )
    if ctx.get("quantity"):
        client.current_qty = ctx["quantity"]
    if ctx.get("size"):
        client.current_size = ctx["size"][:16]
    if ctx.get("color"):
        client.current_color = ctx["color"][:64]

    # Media is an evidence axis, not a replacement for the text classifier.
    # Keep bounded provenance in sales_context so a later high-reasoning pass
    # can distinguish a product question, purchase candidate, receipt, and
    # custom reference even while replies are paused.
    media_context = [item for item in (media_context or []) if isinstance(item, dict)]
    if media_context:
        observations = sales_context.setdefault("_media_evidence", [])
        if not isinstance(observations, list):
            observations = []
            sales_context["_media_evidence"] = observations
        for item in media_context[:8]:
            observation = {
                "url": str(item.get("url") or "")[:1200],
                "role": str(item.get("role") or "other")[:32],
                "intent": str(item.get("intent") or "unknown")[:40],
                "actionable": bool(item.get("actionable")),
                "payment_evidence": bool(item.get("payment_evidence")),
                "catalog_match_allowed": bool(item.get("catalog_match_allowed")),
                "source_message_id": getattr(message, "pk", None),
                "observed_at": timezone.now().isoformat(),
            }
            if observation["url"] and not any(
                row.get("url") == observation["url"]
                and row.get("source_message_id") == observation["source_message_id"]
                for row in observations
                if isinstance(row, dict)
            ):
                observations.append(observation)
        del observations[:-40]

    def add(sig: str, *, conf: float = 0.9, value: str = ""):
        signals.append(sig)
        try:
            _signal(client, sig, message=message, confidence=conf, value=value)
        except Exception:
            pass

    if is_manager:
        add(IgConversationSignal.Type.MANAGER_TAKEOVER, conf=1.0)

    if not is_manager and (client.ad_id or client.ad_ref or client.referral_payload):
        add(IgConversationSignal.Type.AD_REPLY, conf=0.85, value=client.ad_id or client.ad_ref)

    was_opted_out = bool(
        client.opted_out_at
        and (not client.opted_in_at or client.opted_in_at < client.opted_out_at)
    )
    message_event_at = (
        getattr(message, "provider_created_at", None)
        or getattr(message, "created_at", None)
        or timezone.now()
    )
    explicit_opt_out = bool(not is_manager and is_explicit_opt_out(low))
    opt_out = bool(
        explicit_opt_out
        and (not client.opted_in_at or client.opted_in_at < message_event_at)
        and (not client.opted_out_at or client.opted_out_at <= message_event_at)
    )
    no_buy = bool(not is_manager and NO_BUY_RE.search(low))
    if no_buy:
        objection = IgClient.Objection.NO_BUY
        client.lost_reason = "no_buy"
        add(IgConversationSignal.Type.LOST, conf=0.95, value="no_buy")
        from management.services.bot_payment_truth import client_has_confirmed_purchase

        # A buyer who declines the next offer is not a cold lead.
        if not client_has_confirmed_purchase(client):
            try:
                client.set_stage(IgClient.Stage.COLD, reason="no_buy")
            except Exception:
                client.stage = IgClient.Stage.COLD
    if opt_out:
        opted_out_at = message_event_at
        client.opted_out_at = opted_out_at
        client.opt_out_message_id = getattr(message, "pk", None)
        client.bot_paused = True
        if not was_opted_out:
            client.reply_permission_epoch = int(client.reply_permission_epoch or 0) + 1
        client.paused_reason = "opt_out"
        client.paused_at = client.paused_at or opted_out_at

    commercially_actionable = not is_manager and not reaction_only and not no_buy and not opt_out
    media_intents = {str(item.get("intent") or "") for item in media_context}
    media_roles = {str(item.get("role") or "") for item in media_context}
    if commercially_actionable and "custom_print_request" in media_intents:
        intent = IgClient.Intent.CUSTOM_PRINT
        readiness += 25
        add(IgConversationSignal.Type.CUSTOM_PRINT, conf=0.85, value="media")
    elif commercially_actionable and "payment_evidence" in media_intents:
        # A receipt is a manager-review signal only; provider truth remains
        # pending until the payment ledger confirms it.
        intent = IgClient.Intent.PAYMENT
        readiness += 30
        add(IgConversationSignal.Type.CHECKOUT_STARTED, conf=0.8, value="media_receipt")
    elif commercially_actionable and "product" in media_roles:
        intent = IgClient.Intent.PRODUCT
        readiness += 25 if "purchase_candidate" in media_intents else 10
        add(IgConversationSignal.Type.PRODUCT_INTEREST, conf=0.85, value="media")
    if (
        commercially_actionable
        and is_explicit_custom_print_request(low)
        and "custom_print_request" not in media_intents
    ):
        intent = IgClient.Intent.CUSTOM_PRINT
        readiness += 30
        add(IgConversationSignal.Type.CUSTOM_PRINT, conf=0.9)
    elif commercially_actionable and SUPPORT_RE.search(text):
        intent = IgClient.Intent.SUPPORT
    elif commercially_actionable and (PAYMENT_RE.search(low) or PHONE_RE.search(low)) and "payment_evidence" not in media_intents:
        intent = IgClient.Intent.PAYMENT
        readiness += 40
        add(IgConversationSignal.Type.CHECKOUT_STARTED, conf=0.8)
    elif commercially_actionable and ORDER_STATUS_RE.search(text):
        intent = IgClient.Intent.ORDER_STATUS
    elif commercially_actionable and DELIVERY_RE.search(low):
        intent = IgClient.Intent.DELIVERY
    elif commercially_actionable and SIZE_RE.search(low):
        intent = IgClient.Intent.SIZE
        readiness += 20
    elif commercially_actionable and PRICE_RE.search(low):
        intent = IgClient.Intent.PRICE
        readiness += 20
    elif commercially_actionable and PRODUCT_RE.search(low) and "product" not in media_roles:
        intent = IgClient.Intent.PRODUCT
        readiness += 10
        add(IgConversationSignal.Type.PRODUCT_INTEREST, conf=0.75)

    if not is_manager and not no_buy and not opt_out and PRICE_RE.search(low):
        objection = IgClient.Objection.PRICE
        readiness += 12
        add(IgConversationSignal.Type.PRICE_OBJECTION, conf=0.85)
    if not is_manager and not no_buy and not opt_out and PREPAY_RE.search(low):
        objection = IgClient.Objection.PREPAYMENT
        readiness += 10
        add(IgConversationSignal.Type.PREPAYMENT_OBJECTION, conf=0.9)
    if not is_manager and not no_buy and not opt_out and SIZE_RE.search(low):
        if objection == IgClient.Objection.NONE:
            objection = IgClient.Objection.SIZE
        readiness += 8
        add(IgConversationSignal.Type.SIZE_CONCERN, conf=0.8)
    if not is_manager and not no_buy and not opt_out and THINKING_RE.search(low):
        objection = IgClient.Objection.THINKING
        readiness = max(readiness, 25)
    if not is_manager and not no_buy and not opt_out and GIFT_RE.search(low):
        add(IgConversationSignal.Type.GIFT, conf=0.85)
        readiness += 10
    if not is_manager and not no_buy and not opt_out and SELF_RE.search(low):
        add(IgConversationSignal.Type.SELF_PURCHASE, conf=0.75)
        readiness += 8

    from management.services.bot_payment_truth import client_has_confirmed_purchase

    readiness = _resolve_readiness(
        previous_readiness,
        readiness,
        # Opt-out is a communication decision, not proof that the commercial
        # opportunity disappeared. Explicit no-buy is the hard negative axis.
        preserve=is_manager or reaction_only or (opt_out and not no_buy),
        hard_zero=no_buy,
        soft_negative=bool(DEFER_RE.search(low)) and not bool(
            IgConversationSignal.Type.CHECKOUT_STARTED in signals
        ),
        # F-SCORE-004: six polite messages after a purchase used to decay the
        # score to zero, because the only guard read provider truth.
        verified_payment=client_has_confirmed_purchase(client),
    )
    client.language = lang
    client.intent = intent
    client.primary_objection = objection
    client.buying_readiness = readiness
    client.sales_context = sales_context
    fields = [
        "language",
        "intent",
        "primary_objection",
        "buying_readiness",
        "lost_reason",
        "current_size",
        "current_color",
        "current_qty",
        "sales_context",
        "updated_at",
    ]
    if opt_out:
        fields.extend([
            "opted_out_at", "opt_out_message_id", "bot_paused",
            "reply_permission_epoch", "paused_reason", "paused_at",
        ])
    if is_manager:
        if (
            not client.last_manager_message_at
            or client.last_manager_message_at < message_event_at
        ):
            client.last_manager_message_at = message_event_at
            fields.append("last_manager_message_at")
    try:
        client.save(update_fields=fields)
    except Exception:
        client.save()
    result = {
        "language": lang,
        "intent": intent,
        "objection": objection,
        "readiness": readiness,
        "signals": signals,
        "no_buy": no_buy,
        "opt_out": opt_out,
        "sales_context": sales_context,
        "media_context": media_context,
    }
    project_observed_stage(
        client,
        signal_types=signals,
        reason=f"observed_{role or 'message'}",
    )
    result["interaction_type"] = _interaction_type(client, result, text, role)
    try:
        snapshot = _record_analysis_snapshot(client, message, result, role=role)
        result["analysis_snapshot_id"] = snapshot.pk
    except Exception:
        result["analysis_snapshot_id"] = None
    if isinstance(message, InstagramBotMessage) and not client.hidden_at:
        try:
            from management.services.ig_post_sale import open_post_sale_case

            result["post_sale_case_id"] = getattr(
                open_post_sale_case(client, message), "pk", None
            )
        except Exception:
            result["post_sale_case_id"] = None
        if operational_effects:
            try:
                from management.services.ig_payment_review import create_payment_review

                review = create_payment_review(client, watermark=message.pk)
                evidence = (
                    review.evidence
                    if review and isinstance(review.evidence, dict)
                    else {}
                )
                catalog_match = (
                    evidence.get("catalog_match")
                    if isinstance(evidence.get("catalog_match"), dict)
                    else {}
                )
                if catalog_match.get("status") == "matched":
                    match = {
                        "product_id": catalog_match.get("product_id"),
                        "confidence": catalog_match.get("confidence", 0),
                    }
                    sales_context["_media_catalog_match"] = {
                        "product_id": catalog_match.get("product_id"),
                        "title": str(catalog_match.get("title") or "")[:255],
                        "confidence": catalog_match.get("confidence", 0),
                        "source_message_ids": (
                            catalog_match.get("source_message_ids") or [message.pk]
                        ),
                        "observed_at": timezone.now().isoformat(),
                    }
                    client.sales_context = sales_context
                    client.save(update_fields=["sales_context", "updated_at"])
                    try:
                        from management.services import bot_orders

                        if any(
                            item.get("role") == "product"
                            and item.get("intent") == "purchase_candidate"
                            and item.get("catalog_match_allowed") is True
                            for item in media_context
                        ):
                            bot_orders.pin_product(client, match["product_id"])
                    except Exception:
                        pass
            except Exception:
                # Payment review is an operational alert; it must never block
                # message persistence or the reply boundary.
                pass
    if operational_effects and isinstance(message, InstagramBotMessage):
        try:
            from management.services.bot_conversation_analysis import schedule_analysis

            job = schedule_analysis(client, message)
            result["analysis_job_id"] = job.pk if job else None
        except Exception:
            result["analysis_job_id"] = None
    return result


def ensure_rule_classification(
    client: IgClient,
    message: InstagramBotMessage,
    *,
    media_context: list[dict] | None = None,
    operational_effects: bool = True,
) -> dict | None:
    """Run the deterministic projection once for a durable message watermark."""
    if not client or not message or not getattr(message, "pk", None):
        return None
    if not client.hidden_at:
        try:
            from management.services.ig_post_sale import open_post_sale_case

            open_post_sale_case(client, message)
        except Exception:
            pass
    message_event_at = message.provider_created_at or message.created_at
    explicit_opt_out = bool(
        message.role == InstagramBotMessage.Role.USER
        and is_explicit_opt_out(message.text or "")
    )
    if (
        explicit_opt_out
        and message_event_at
        and client.opted_in_at
        and client.opted_in_at >= message_event_at
    ):
        # A later audited opt-in wins over recovered historical consent text.
        # Do not let mixed wording mutate the current commercial projection.
        return None
    has_newer_projection = bool(message_event_at and (
        InstagramBotMessage.objects.filter(client_id=client.pk)
        .exclude(pk=message.pk)
        .annotate(
            message_event_at=Coalesce(
                "provider_created_at",
                "created_at",
            )
        )
        .filter(
            Q(message_event_at__gt=message_event_at)
            | Q(message_event_at=message_event_at)
        )
        .filter(
            ~Q(source="manual_refresh")
            | Q(analysis_snapshots__analysis_model="rules")
        )
        .exists()
    ))
    if has_newer_projection and not explicit_opt_out:
        return None
    if client.analysis_snapshots.filter(
        analysis_model="rules",
        rules_version=ANALYSIS_RULES_VERSION,
        last_analyzed_message_id=message.pk,
    ).exists():
        return None
    return classify_message(
        client,
        message=message,
        role=message.role,
        media_context=media_context,
        operational_effects=operational_effects,
    )
