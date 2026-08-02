"""Evidence-bound exchange and return cases for Instagram purchases."""
from __future__ import annotations

import re

from django.db import transaction

from management.ig_bot_models import IgPostSaleCase
from management.models import InstagramBotMessage


EXCHANGE_RE = re.compile(
    r"\b(?:обмін\w*|обмен\w*|обміняти|обменять|поміняти|поменять|"
    r"замін(?:а|и|у|ою|ити|ювати)\w*|замен(?:а|ы|у|ой|ить|ять)\w*"
    r")\b",
    re.I,
)
RETURN_RE = re.compile(
    # The imperative forms («поверніть кошти», «верніть гроші») are the most
    # common way a customer asks for a refund and were not matched at all, so
    # the request fell through to SUPPORT_RE and became a complaint.
    # Deliberately enumerated instead of a broad `поверн\w*`: that would also
    # swallow «повернуся до вас завтра», which is not a refund request.
    r"\b(?:повернен\w*|возврат\w*|повернути|поверн(?:іть|ите)|"
    r"верн(?:іть|ите|уть))\b",
    re.I,
)
ENGLISH_POST_SALE_TERMS_RE = re.compile(
    r"\b(?:exchange\w*|replace\w*|swap\w*|return\w*|refund\w*)\b",
    re.I,
)
ENGLISH_PRE_SALE_RE = re.compile(
    r"\b(?:policy|policies)\b|"
    r"\b(?:before|if)\s+(?:i|we)\s+(?:order|buy|purchase)\b|"
    r"\breturning\s+(?:customer|client|buyer)\b",
    re.I,
)
ENGLISH_POST_SALE_REQUEST_RE = re.compile(
    r"\b(?:"
    r"(?:i|we)\s+(?:need|want|would\s+like|wish|have)\s+(?:to\s+|an?\s+)?"
    r"(?:exchange|replace|swap|return|refund)\b|"
    r"(?:can|could|would)\s+(?:i|you)\s+(?:please\s+)?"
    r"(?:exchange|replace|swap|return|refund)\s+"
    r"(?:this|my|the|it|an?\s+(?:order|shirt|item|purchase))\b|"
    r"please\s+(?:exchange|replace|swap|return|refund)\b|"
    r"(?:exchange|replace|swap|return|refund)\s+"
    r"(?:this|my|the|it|order|shirt|t-shirt|item|purchase|size)\b|"
    r"(?:get|receive)\s+(?:a\s+)?refund\b"
    r")",
    re.I,
)
FIT_RE = re.compile(r"\b(oversize|оверсайз|regular|регуляр|classic|класик\w*)\b", re.I)
SIZE_RE = re.compile(r"\b(3xl|2xl|xxxl|xxl|xl|xs|s|m|l)\b", re.I)
TARGET_SIZE_RE = re.compile(
    r"(?:\bна|\bto)\s+(?:розмір\s+|размер\s+)?(3xl|2xl|xxxl|xxl|xl|xs|s|m|l)\b",
    re.I,
)


PRINT_SUBJECT_RE = re.compile(
    r"\b(?:принт\w*|дизайн\w*|зображенн\w*|изображен\w*|логотип\w*|надпис\w*)\b",
    re.I,
)
# F-STATE-008 / F-PAT-001 #3: «а можна поміняти розмір на L?» — это вопрос про
# умови до покупки, а не сервісне звернення. Англійська частина цього фільтра
# існувала (`ENGLISH_PRE_SALE_RE`), а українська та російська — ні.
PRE_SALE_HYPOTHETICAL_RE = re.compile(
    r"(?:\b(?:а\s+)?(?:чи\s+)?(?:можна|можно|мож[еo]те|можете)\s+"
    r"(?:буде\s+|потім\s+|пізніше\s+|потом\s+|позже\s+)?"
    r"(?:поміняти|обміняти|замінити|поменять|обменять|заменить|"
    r"повернути|вернуть|обмін|обмен)\b|"
    r"\b(?:якщо|если)\s+не\s+(?:підійде|подойдет|подойдёт|сподобається|понравится)\b|"
    r"\b(?:умови|условия|політика|политика|правила)\s+"
    r"(?:обміну|обмена|поверненн\w*|возврат\w*)\b|"
    r"\b(?:у\s+вас\s+)?(?:є|есть)\s+(?:обмін|обмен|поверненн\w*|возврат)\b)",
    re.I,
)
# Але доказ отриманого товару перебиває гіпотетичність: «а можна поміняти, бо
# не підійшов розмір» — це вже реальне звернення.
RECEIVED_EVIDENCE_RE = re.compile(
    r"\b(?:не\s+під(?:ійшов|ійшла|ійшло|ійшли)|"
    r"не\s+подош(?:ёл|ел|ла|ло|ли)|"
    r"отрима(?:в|ла|ли)|получи(?:в|л|ла|ли)|"
    r"прийш(?:ов|ла|ло|ли)|приш(?:ёл|ел|ла|ло|ли)|"
    r"замал\w*|завелик\w*|тісн\w*|тесн\w*|"
    r"вже\s+(?:у\s+мене|отримав\w*|прийшл\w*)|уже\s+(?:у\s+меня|получил\w*))\b",
    re.I,
)


def detect_post_sale_type(text: str) -> str:
    value = str(text or "")
    # F-PAT-001 #4: EXCHANGE_RE матчит `замін\w*`, поэтому «хочу замінити принт
    # на свій» открывало постпродажный кейс обмена товара. Замена принта — это
    # запрос кастома до покупки, а не сервисный кейс по уже купленному.
    if PRINT_SUBJECT_RE.search(value) and not SIZE_RE.search(value):
        return ""
    # English verbs are polysemous in a storefront conversation.  A case is a
    # manager workflow, so require an explicit customer request for their item
    # rather than treating policy and pre-purchase questions as a return.
    if ENGLISH_POST_SALE_TERMS_RE.search(value):
        if ENGLISH_PRE_SALE_RE.search(value) or not ENGLISH_POST_SALE_REQUEST_RE.search(value):
            return ""
        if re.search(r"\b(?:exchange\w*|replace\w*|swap\w*)\b", value, re.I):
            return IgPostSaleCase.CaseType.EXCHANGE
        return IgPostSaleCase.CaseType.RETURN
    if EXCHANGE_RE.search(value):
        return IgPostSaleCase.CaseType.EXCHANGE
    if RETURN_RE.search(value):
        return IgPostSaleCase.CaseType.RETURN
    return ""


TERMINAL_CASE_STATUSES = (
    IgPostSaleCase.Status.COMPLETED,
    IgPostSaleCase.Status.REJECTED,
    IgPostSaleCase.Status.CANCELLED,
)


def open_service_case(client):
    """Return the client's unresolved exchange/return case, or None.

    "Unresolved" is anything but a terminal status. ``in_transit`` counts:
    a replacement on its way is still an open obligation, and offering a
    discount in the middle of it is what the customer complained about.

    Deliberately wider than the ``{needs_details, open}`` set used by the
    "needs a manager" badge. That set answers "is someone waiting for me to
    act?"; this one answers "is this conversation still about service?".
    """
    if not client or not getattr(client, "pk", None):
        return None
    return (
        IgPostSaleCase.objects.filter(client_id=client.pk)
        .exclude(status__in=TERMINAL_CASE_STATUSES)
        .order_by("-updated_at", "-id")
        .first()
    )


RECIPIENT_ORDER_STATUSES = ("ship", "done")


def client_looks_like_recipient(client) -> bool:
    """Whether anything in the client's state says they already have the goods.

    Deliberately wider than ``client_has_confirmed_purchase``: order attribution
    exists for 2 clients out of 289 on production, so a recorded purchase is a
    weak signal of physical delivery. A CRM stage of paid/order_created/done or
    any linked order already shipped counts too.
    """
    if not client or not getattr(client, "pk", None):
        return False
    from management.models import IgClient
    from management.services.bot_payment_truth import client_has_confirmed_purchase

    if client_has_confirmed_purchase(client):
        return True
    if client.stage in {
        IgClient.Stage.PAID,
        IgClient.Stage.ORDER_CREATED,
        IgClient.Stage.DONE,
    }:
        return True
    from management.ig_bot_models import IgOrderAssignment, IgOrderAttribution

    if IgOrderAssignment.objects.filter(
        client_id=client.pk,
        unassigned_at__isnull=True,
        order__status__in=RECIPIENT_ORDER_STATUSES,
    ).exists():
        return True
    if IgOrderAttribution.objects.filter(
        client_id=client.pk,
        order__status__in=RECIPIENT_ORDER_STATUSES,
    ).exists():
        return True
    return client.deals.filter(
        order__status__in=RECIPIENT_ORDER_STATUSES
    ).exists()


def record_return_shipment(
    case, tracking, *, actor=None, evidence_message_id=None, payer=None
):
    """Record the parcel the customer sent back to us.

    Cannot be derived like the outbound leg: the number arrives as digits inside
    a chat message, and a bare 14-digit number can be anything. The manager
    confirms it, which follows the decision already taken for money in this
    project — a human check instead of automatic trust.

    The number may legitimately equal the outbound one: a Nova Poshta "fast
    return" travels back on the same waybill and costs the customer nothing.
    That case is recorded, flagged, and billed to the shop by default; a return
    on a separate waybill defaults to the customer having paid for it.
    """
    from management.ig_bot_models import IgOrderShipment
    from management.services.ig_shipments import normalize_tracking

    if case is None or not getattr(case, "pk", None):
        raise ValueError("Сервісне звернення не знайдено.")
    if not case.order_id:
        raise ValueError(
            "Спочатку прив'яжіть замовлення: ТТН повернення живе на замовленні."
        )
    number = normalize_tracking(tracking)
    if not number:
        raise ValueError("Це не схоже на номер ТТН Нової Пошти.")
    existing = IgOrderShipment.objects.filter(
        order_id=case.order_id,
        tracking_number=number,
        direction=IgOrderShipment.Direction.INBOUND,
    ).first()
    if existing is not None:
        return existing
    reuses = IgOrderShipment.objects.filter(
        order_id=case.order_id,
        tracking_number=number,
        direction=IgOrderShipment.Direction.OUTBOUND,
    ).exists()
    resolved_payer = payer or (
        IgOrderShipment.Payer.SHOP if reuses else IgOrderShipment.Payer.CUSTOMER
    )
    return IgOrderShipment.objects.create(
        order_id=case.order_id,
        post_sale_case=case,
        tracking_number=number,
        direction=IgOrderShipment.Direction.INBOUND,
        purpose=IgOrderShipment.Purpose.RETURN_INBOUND,
        source=IgOrderShipment.Source.MANAGER_MANUAL,
        payer=resolved_payer,
        reuses_outbound_tracking=reuses,
        evidence_message_id=evidence_message_id,
        created_by=actor if getattr(actor, "pk", None) else None,
    )


def record_replacement_shipment(case, tracking, *, actor=None, note=""):
    """Record a replacement parcel the manager already sent.

    The automatic derivation only works while the case is open: changing
    ``Order.tracking_number`` after the case is closed is a correction. But a
    real exchange can be closed by hand before anyone records the number, and
    then the replacement tracking exists only as digits in the conversation.
    This is the field for that case.

    Deliberately does **not** touch ``Order.tracking_number``: the parcel is
    already on its way and the manager has already told the customer, so moving
    the field would make the worker send a second notification.
    """
    from management.ig_bot_models import IgOrderShipment
    from management.services.ig_shipments import normalize_tracking

    if case is None or not getattr(case, "pk", None):
        raise ValueError("Сервісне звернення не знайдено.")
    if not case.order_id:
        raise ValueError(
            "Спочатку прив'яжіть замовлення: ТТН заміни живе на замовленні."
        )
    number = normalize_tracking(tracking)
    if not number:
        raise ValueError("Це не схоже на номер ТТН Нової Пошти.")
    order = case.order
    if number == normalize_tracking(getattr(order, "tracking_number", "")):
        raise ValueError(
            "Це поточна ТТН замовлення, а не заміна. Вкажіть номер нової посилки."
        )
    existing = IgOrderShipment.objects.filter(
        order_id=case.order_id,
        tracking_number=number,
        direction=IgOrderShipment.Direction.OUTBOUND,
    ).first()
    if existing is not None:
        return existing
    previous_outbound = (
        IgOrderShipment.objects.filter(
            order_id=case.order_id,
            direction=IgOrderShipment.Direction.OUTBOUND,
        )
        .order_by("created_at", "id")
        .last()
    )
    return IgOrderShipment.objects.create(
        order_id=case.order_id,
        post_sale_case=case,
        tracking_number=number,
        direction=IgOrderShipment.Direction.OUTBOUND,
        purpose=IgOrderShipment.Purpose.EXCHANGE_REPLACEMENT,
        supersedes=previous_outbound,
        source=IgOrderShipment.Source.MANAGER_MANUAL,
        created_by=actor if getattr(actor, "pk", None) else None,
        note=str(note or "")[:500],
    )


def post_sale_request_for_client(client, text: str) -> str:
    """Post-sale case type for this client and message, or "".

    ``detect_post_sale_type`` answers a question about wording alone, and by
    itself it cannot tell «Можно поменять оверсайз на regular?» asked before a
    purchase from the same sentence asked after delivery. Only the client's state
    disambiguates it, so the hypothetical filter lives here (DR-008).
    """
    case_type = detect_post_sale_type(text)
    if not case_type:
        return ""
    value = str(text or "")
    if not PRE_SALE_HYPOTHETICAL_RE.search(value):
        return case_type
    if RECEIVED_EVIDENCE_RE.search(value):
        return case_type
    return case_type if client_looks_like_recipient(client) else ""


def _extract_details(text: str) -> dict:
    value = str(text or "")
    sizes = [match.group(1).upper() for match in SIZE_RE.finditer(value)]
    target = TARGET_SIZE_RE.search(value)
    fit = FIT_RE.search(value)
    requested_size = target.group(1).upper() if target else (sizes[1] if len(sizes) > 1 else "")
    source_size = sizes[0] if sizes and not (target and len(sizes) == 1) else ""
    return {
        "source_fit": fit.group(1)[:64] if fit else "",
        "source_size": source_size[:32],
        "requested_size": requested_size[:32],
        "reason": value[:500],
    }


def _attributed_orders(client):
    from management.ig_bot_models import IgOrderAssignment, IgOrderAttribution

    assignments = list(
        IgOrderAssignment.objects.filter(
            client=client,
            unassigned_at__isnull=True,
        )
        .select_related("order")
        .order_by("-assigned_at", "-id")[:3]
    )
    if assignments:
        return assignments
    return list(
        IgOrderAttribution.objects.filter(
            client=client,
            order__instagram_assignment__isnull=True,
        )
        .select_related("order")
        .order_by("-created_at", "-id")[:3]
    )


def _update_active_case(active, message, details):
    evidence_ids = list(active.evidence_message_ids or [])
    if message.pk not in evidence_ids:
        evidence_ids.append(message.pk)
    active.evidence_message_ids = evidence_ids[-20:]
    for field in ("source_fit", "source_size", "requested_fit", "requested_size"):
        value = details.get(field)
        if value:
            setattr(active, field, value)
    active.reason = "\n".join(
        part for part in (active.reason, details.get("reason")) if part
    )[-500:]
    active.save(update_fields=[
        "evidence_message_ids", "source_fit", "source_size",
        "requested_fit", "requested_size", "reason", "updated_at",
    ])
    return active


@transaction.atomic
def open_post_sale_case(client, message, *, order=None):
    """Create exactly one case from explicit customer evidence.

    A linked order is inferred only when this client has exactly one durable
    Instagram attribution. Multiple purchases remain unresolved until a
    manager/customer identifies the intended order.
    """
    if not isinstance(message, InstagramBotMessage):
        return None
    if message.role != InstagramBotMessage.Role.USER or message.client_id != client.pk:
        return None
    case_type = post_sale_request_for_client(client, message.text)
    if not case_type:
        active_cases = list(
            IgPostSaleCase.objects.select_for_update()
            .filter(
                client=client,
                status__in=[IgPostSaleCase.Status.NEEDS_DETAILS, IgPostSaleCase.Status.OPEN],
            )
            .order_by("-updated_at", "-id")[:2]
        )
        if len(active_cases) != 1:
            return None
        sizes = [match.group(1).upper() for match in SIZE_RE.finditer(str(message.text or ""))]
        fit = FIT_RE.search(str(message.text or ""))
        if not sizes and not fit:
            return None
        details = _extract_details(message.text)
        details["source_size"] = ""
        details["source_fit"] = ""
        if sizes:
            details["requested_size"] = sizes[-1]
        if fit:
            details["requested_fit"] = fit.group(1)[:64]
        return _update_active_case(active_cases[0], message, details)

    existing = IgPostSaleCase.objects.select_for_update().filter(source_message=message).first()
    if existing:
        return existing

    active = (
        IgPostSaleCase.objects.select_for_update()
        .filter(
            client=client,
            case_type=case_type,
            status__in=[IgPostSaleCase.Status.NEEDS_DETAILS, IgPostSaleCase.Status.OPEN],
        )
        .order_by("-updated_at", "-id")
        .first()
    )
    if active:
        details = _extract_details(message.text)
        return _update_active_case(active, message, details)

    attribution = None
    if order is None:
        attributions = _attributed_orders(client)
        if len(attributions) == 1:
            owner = attributions[0]
            order = owner.order
            if hasattr(owner, "order_attribution_id"):
                attribution = owner
    else:
        from management.ig_bot_models import IgOrderAssignment, IgOrderAttribution

        assignment = IgOrderAssignment.objects.filter(order=order).first()
        if assignment and (
            assignment.client_id != client.pk or assignment.unassigned_at is not None
        ):
            order = None
        attribution = (
            IgOrderAttribution.objects.filter(client=client, order=order).first()
            if order is not None
            else None
        )

    episode = None
    if attribution is not None:
        episode = getattr(attribution, "commercial_episode", None)
    if episode is None and order is not None:
        episode = getattr(order, "instagram_commercial_episode", None)

    details = _extract_details(message.text)
    return IgPostSaleCase.objects.create(
        client=client,
        order=order,
        commercial_episode=episode,
        source_message=message,
        case_type=case_type,
        status=(IgPostSaleCase.Status.OPEN if order is not None else IgPostSaleCase.Status.NEEDS_DETAILS),
        evidence_message_ids=[message.pk],
        **details,
    )
