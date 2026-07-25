"""
Пост-оплатний потік IG-бота: збір даних НП, створення замовлення, формування
посилання на оплату за тегами моделі.

Потік (повний автопілот, Q1; замовлення після оплати, Q2; дані НП текстом, Q3):
- [PAYLINK:full|prepay] (+опц. [PRODUCT:id]) → create_deal_and_link → надсилаємо лінк.
- оплата підтверджена (вебхук/поллінг) → on_deal_paid: якщо є дані НП — створюємо
  замовлення; якщо ні — сповіщаємо й бот збирає дані в діалозі.
- [ORDER] → collect_np_and_fulfill: витягуємо дані НП з діалогу й створюємо заказ.
"""
from __future__ import annotations

import logging
import re
from contextlib import contextmanager
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from threading import RLock
from weakref import WeakValueDictionary

from django.db.models import Q
from django.db import connection

from management.services.bot_payments import create_payment_link
from management.services.bot_payment_truth import (
    verified_payment_deals,
    verified_payment_q,
)
from management.services.call_ai_analysis import gemini_generate_text
from management.services.instagram_bot import notify_manager, send_text
from orders.services.order_builder import create_order_from_deal

logger = logging.getLogger(__name__)

MAX_PAYLINK_ITEMS = 12
MAX_PAYLINK_QUANTITY = 50
MAX_PAYLINK_VALUE = Decimal("1000000.00")

_PAYLINK_LOCKS = WeakValueDictionary()
_PAYLINK_LOCKS_GUARD = RLock()


@contextmanager
def _paylink_client_lock(client_id):
    """Serialize deal reuse/creation for one client across MariaDB workers."""
    lock_name = f"twocomms:ig-paylink:{int(client_id)}"
    if connection.vendor in {"mysql", "mariadb"}:
        with connection.cursor() as cursor:
            cursor.execute("SELECT GET_LOCK(%s, 15)", [lock_name])
            acquired = cursor.fetchone()[0]
        if acquired != 1:
            raise RuntimeError("Could not acquire Instagram paylink lock")
        try:
            yield
        finally:
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT RELEASE_LOCK(%s)", [lock_name])
            except Exception:
                logger.warning("Failed to release paylink advisory lock", exc_info=True)
        return

    with _PAYLINK_LOCKS_GUARD:
        lock = _PAYLINK_LOCKS.setdefault(int(client_id), RLock())
    with lock:
        yield

NP_EXTRACT_INSTRUCTION = (
    "З наведеного діалогу витягни дані доставки Новою Поштою у форматі JSON без "
    "markdown: {\"full_name\":\"ПІБ\",\"phone\":\"телефон\",\"city\":\"місто\","
    "\"office\":\"відділення/поштомат\"}. Якщо чогось немає — порожній рядок."
)


def deal_has_np_data(deal) -> bool:
    return all([
        (deal.np_full_name or "").strip(),
        (deal.np_phone or "").strip(),
        (deal.np_city or "").strip(),
        (deal.np_office or "").strip(),
    ])


def extract_np_data(client) -> dict:
    """Витягує дані НП з останніх повідомлень клієнта (management-модель)."""
    from management.models import InstagramBotMessage

    rows = list(
        InstagramBotMessage.objects.filter(client=client).order_by("-id")[:14]
    )
    rows.reverse()
    transcript = "\n".join(
        f"{'Клієнт' if r.role == 'user' else 'Бот'}: {r.text}"
        for r in rows
        if (r.text or "").strip()
    )
    if not transcript.strip():
        return {}
    payload = {
        "contents": [{"role": "user", "parts": [{"text": NP_EXTRACT_INSTRUCTION + "\n\nДІАЛОГ:\n" + transcript}]}],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 4096,
            "responseMimeType": "application/json",
        },
    }
    try:
        out = gemini_generate_text(
            payload, role="management", reasoning_task="order_decision"
        )
    except Exception:
        return {}
    from management.services.bot_vision import _parse_fingerprint

    return _parse_fingerprint(out.get("parsed") or "")


def fulfill_if_ready(deal, created_by=None) -> bool:
    """Створює замовлення, якщо угода оплачена, ще без замовлення і дані НП повні."""
    if deal.order_id:
        return False
    if not verified_payment_deals(deal.__class__.objects.filter(pk=deal.pk)).exists():
        return False
    if not deal_has_np_data(deal):
        return False
    order = create_order_from_deal(deal, created_by=created_by)
    try:
        notify_manager(
            f"✅ IG: оплачено і створено замовлення {order.order_number} "
            f"({deal.amount} грн) — {deal.np_full_name}, {deal.np_city}, {deal.np_office}."
        )
    except Exception:
        pass
    return True


def collect_np_and_fulfill(client, created_by=None) -> bool:
    """Знаходить оплачену угоду без замовлення, витягує дані НП з діалогу (якщо
    бракує), зберігає й створює замовлення. True, якщо замовлення створено."""
    from management.models import IgDeal

    deal = (
        verified_payment_deals(
            IgDeal.objects.filter(client=client, order__isnull=True)
        )
        .order_by("-id")
        .first()
    )
    if not deal:
        return False
    if not deal_has_np_data(deal):
        data = extract_np_data(client) or {}
        deal.np_full_name = (data.get("full_name") or deal.np_full_name or "")[:255]
        deal.np_phone = (data.get("phone") or deal.np_phone or "")[:50]
        deal.np_city = (data.get("city") or deal.np_city or "")[:160]
        deal.np_office = (data.get("office") or deal.np_office or "")[:255]
        deal.save(update_fields=["np_full_name", "np_phone", "np_city", "np_office", "updated_at"])
    return fulfill_if_ready(deal, created_by=created_by)


def on_deal_paid(deal) -> None:
    """Хук «оплачено»: якщо дані НП є — створюємо замовлення; інакше сповіщаємо,
    і бот збере дані в діалозі."""
    if deal_has_np_data(deal):
        fulfill_if_ready(deal)
    else:
        try:
            notify_manager(
                f"💸 IG: оплата отримана (угода #{deal.id}, {deal.amount} грн), "
                f"але бракує даних доставки — бот збирає ПІБ/телефон/місто/відділення."
            )
        except Exception:
            pass


def pin_product(client, product_id) -> bool:
    """Закріплює товар за клієнтом (current_product), якщо він опублікований.

    Викликається, коли модель дала [PRODUCT:id] або матчинг фото впевнено
    визначив товар. Робить наступне формування лінку детермінованим.
    """
    if not client or not product_id:
        return False
    from storefront.models import Product, ProductStatus

    try:
        p = Product.objects.filter(id=int(product_id), status=ProductStatus.PUBLISHED).first()
    except (TypeError, ValueError):
        p = None
    if not p:
        return False
    if client.current_product_id == p.id:
        if not client.current_product_confidence:
            client.current_product_confidence = 1
            client.save(update_fields=["current_product_confidence", "updated_at"])
        return True
    client.current_product = p
    client.current_product_confidence = 1
    client.save(update_fields=["current_product", "current_product_confidence", "updated_at"])
    return True


def resolve_product_for_payment(client, product_id=None):
    """Визначає товар для оплати НАДІЙНО (не підставляє випадковий товар).

    Пріоритет:
      1) явний product_id (з тегу [PRODUCT:id]) → товар;
      2) інакше — management-модель за діалогом + каталогом обирає id товару з
         урахуванням типу (футболка/худі/лонгслів) і впевненості. Це переживає
         різницю «з/с», скорочення й розмовні назви, чого не вміє підрядковий матч.
    Якщо впевненості немає — повертає None (краще покликати менеджера, ніж
    виставити рахунок не за той товар)."""
    from storefront.models import Product, ProductStatus

    explicit_product = product_id not in (None, "", False)
    if explicit_product:
        try:
            p = Product.objects.filter(id=int(product_id), status=ProductStatus.PUBLISHED).first()
        except (TypeError, ValueError):
            p = None
        return p

    # 2) закріплений товар діалогу (швидко й детерміновано, без виклику моделі).
    cur = getattr(client, "current_product", None)
    if cur is not None and getattr(cur, "status", None) == ProductStatus.PUBLISHED:
        return cur

    from management.models import InstagramBotMessage

    rows = list(InstagramBotMessage.objects.filter(client=client).order_by("-id")[:16])
    rows.reverse()
    transcript = "\n".join(
        f"{'Клієнт' if r.role == 'user' else 'Бот'}: {r.text}"
        for r in rows
        if (r.text or "").strip()
    )
    if not transcript.strip():
        return None

    cat_lines = []
    for p in Product.objects.filter(status=ProductStatus.PUBLISHED).only("id", "title", "price")[:300]:
        try:
            price = int(getattr(p, "final_price", None) or p.price)
        except Exception:
            price = p.price
        cat_lines.append(f"{p.id}|{p.title}|{price}")
    if not cat_lines:
        return None

    instruction = (
        "За діалогом визнач, ЯКИЙ САМЕ товар з каталогу клієнт хоче оплатити. "
        "Враховуй ТИП (футболка / худі / лонгслів) і назву принта. Поверни лише JSON "
        'без markdown: {"product_id": <id з каталогу або null>, "confidence": <0..1>}. '
        "Якщо не зрозуміло однозначно — product_id:null, confidence:0. "
        "Каталог (формат id|назва|ціна_грн):\n" + "\n".join(cat_lines)
    )
    payload = {
        "contents": [{"role": "user", "parts": [{"text": instruction + "\n\nДІАЛОГ:\n" + transcript}]}],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 4096,
            "responseMimeType": "application/json",
        },
    }
    try:
        out = gemini_generate_text(
            payload, role="management", reasoning_task="product_decision"
        )
    except Exception:
        return None
    from management.services.bot_vision import _parse_fingerprint

    data = _parse_fingerprint(out.get("parsed") or "")
    pid = data.get("product_id")
    try:
        pid = int(pid) if pid not in (None, "", "null") else None
    except (TypeError, ValueError):
        pid = None
    try:
        conf = float(data.get("confidence") or 0)
    except (TypeError, ValueError):
        conf = 0.0
    if not pid or conf < 0.6:
        return None
    return Product.objects.filter(id=pid, status=ProductStatus.PUBLISHED).first()


def _message_text(message) -> str:
    if isinstance(message, dict):
        return " ".join(str(message.get("text") or "").split())
    return " ".join(str(getattr(message, "text", "") or "").split())


def _message_role(message) -> str:
    if isinstance(message, dict):
        return str(message.get("role") or "").casefold()
    return str(getattr(message, "role", "") or "").casefold()


def _price_message_matches_product(text: str, product) -> bool:
    """Reject an offer whose explicit garment type conflicts with the target."""
    if not product:
        return True
    low = _message_text({"text": text}).casefold()
    product_tags = re.findall(r"\[product:(\d+)\]", low)
    if product_tags and str(getattr(product, "pk", "")) not in product_tags:
        return False
    target = " ".join(
        str(value or "").casefold()
        for value in (getattr(product, "title", ""), getattr(product, "slug", ""))
    )
    type_tokens = {
        "худі": "худі", "худи": "худі", "hoodie": "худі",
        "лонгслів": "лонгслів", "лонгслив": "лонгслів", "longsleeve": "лонгслів",
        "футболк": "футболка", "t-shirt": "футболка", "tee": "футболка",
    }
    mentioned = {mapped for token, mapped in type_tokens.items() if token in low}
    target_types = {mapped for token, mapped in type_tokens.items() if token in target}
    if mentioned and target_types and not mentioned.intersection(target_types):
        return False
    return True


def _is_product_media_switch(message) -> bool:
    """Return true for a later customer product image, not a payment receipt."""
    text = _message_text(message).casefold()
    if re.search(r"\b(оплат\w*|сплат\w*|переказ\w*|чек\w*|квитанц\w*)\b", text):
        return False
    media = message.get("media") if isinstance(message, dict) else None
    if isinstance(media, list) and any(
        isinstance(item, dict) and (
            item.get("role") == "product"
            or str(item.get("type") or "").casefold() in {"ig_post", "share", "story", "reel"}
        )
        for item in media
    ):
        return True
    attachments = str(message.get("attachments") or "") if isinstance(message, dict) else str(getattr(message, "attachments", "") or "")
    return bool(
        attachments
        and re.search(r"ig_post|share|story|product", attachments, re.IGNORECASE)
        and re.search(r"\b(хочу|беру|давайте|обираю|вибираю|цей|цю|таку)\b", text)
    )


def _conversation_price_evidence(messages, *, qty: int = 1, product=None) -> dict:
    """Resolve the latest commercial price epoch from persisted message rows."""
    amount_re = re.compile(r"(?<!\d)(\d{2,6}(?:[.,]\d{1,2})?)\s*(?:грн|uah|₴)", re.IGNORECASE)
    payment_re = re.compile(
        r"\b(передоплат\w*|аванс\w*|оплат\w*|сплач\w*|переказ\w*|перевод\w*|"
        r"чек\w*|квитанц\w*|receipt|paid)\b",
        re.IGNORECASE,
    )
    price_re = re.compile(
        r"\b(ціна|цена|вартість|стоимость|сума|сумма|разом|итого|всього|всего|знижк\w*|скидк\w*)\b|"
        r"\bза\s+\d{2,6}",
        re.IGNORECASE,
    )
    acceptance_re = re.compile(
        r"\b(так|да|ок|добре|хорошо|домов\w*|можемо|погодж\w*|соглас\w*|"
        r"оформл\w*|замовл\w*|заказ\w*|беру|забираю)\b",
        re.IGNORECASE,
    )
    product_switch_re = re.compile(
        r"\b(?:тоді|тепер|а\s+зараз|хочу|беру|давайте|обираю|вибираю|выбираю)\b"
        r"[^.!?]{0,100}\b(?:оверсайз\w*|oversize|класич\w*|classic|"
        r"футболк\w*|худі|худи|лонгслів\w*|модел\w*|\[product:\d+\])\b",
        re.IGNORECASE,
    )
    recent_text = " ".join(_message_text(message) for message in messages[-30:]).casefold()
    multi_item = bool(
        (re.search(r"\b(базов\w*|класич\w*|classic)\b", recent_text)
         and re.search(r"\b(оверсайз\w*|oversize)\b", recent_text))
        or re.search(r"\b(?:2|3|4|5)\s+(?:футбол\w*|товар\w*|шт\.?|штук\w*)", recent_text)
        or int(qty or 1) > 1
    )
    commercial_rows = []
    for index, message in enumerate(messages):
        text = _message_text(message)
        amounts = amount_re.findall(text)
        if not amounts or payment_re.search(text):
            continue
        if not price_re.search(text):
            continue
        kind = "order_total" if re.search(
            r"\b(сума|сумма|разом|итого|всього|всего)\b", text, re.IGNORECASE
        ) else "unit_price"
        if kind == "order_total" and multi_item:
            commercial_rows.append({
                "status": "ambiguous",
                "price": None,
                "source_message_id": getattr(message, "pk", None),
                "kind": kind,
            })
            continue
        try:
            price = Decimal(amounts[-1].replace(",", ".")).quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError):
            continue
        if price <= 0 or price > Decimal("1000000"):
            continue
        role = _message_role(message)
        customer_roles = {"user", "customer", "client"}
        seller_roles = {"manager", "human_manager", "operator", "admin"}
        next_message = next(
            (
                later for later in messages[index + 1:]
                if _message_text(later)
            ),
            None,
        )
        next_role = _message_role(next_message)
        next_text = _message_text(next_message)
        accepted = False
        if role in seller_roles:
            accepted = next_role in customer_roles and bool(acceptance_re.search(next_text))
        elif role in customer_roles:
            # A customer amount is a counter-offer, never a self-authorized
            # discount. It needs the seller's immediate explicit acceptance.
            accepted = next_role in seller_roles and bool(acceptance_re.search(next_text))
            previous = commercial_rows[-1] if commercial_rows else None
            if previous and previous.get("seller_offer") and previous.get("message_index") == index - 1 and previous.get("offered_price") == price and acceptance_re.search(text):
                previous.update({
                    "status": "accepted",
                    "price": price,
                    "acceptance_message_id": getattr(message, "pk", None),
                })
                continue
        if role in seller_roles and commercial_rows:
            previous = commercial_rows[-1]
            if previous.get("message_index") == index - 1 and previous.get("customer_counteroffer") and acceptance_re.search(text):
                previous.update({
                    "status": "accepted",
                    "price": previous.get("offered_price"),
                    "acceptance_message_id": getattr(message, "pk", None),
                })
                continue
        commercial_rows.append({
            "status": "accepted" if accepted else "ambiguous",
            "price": price if accepted else None,
            "source_message_id": getattr(message, "pk", None),
            "kind": kind,
            "message_index": index,
            "offered_price": price,
            "seller_offer": role in seller_roles,
            "customer_counteroffer": role in customer_roles,
            "acceptance_message_id": (
                getattr(next_message, "pk", None) if accepted else None
            ),
        })
    if commercial_rows:
        decision = commercial_rows[-1]
        later_messages = messages[decision.get("message_index", 0) + 1:]
        if any(
            product_switch_re.search(_message_text(later)) or _is_product_media_switch(later)
            for later in later_messages
        ):
            decision = {
                "status": "ambiguous",
                "price": None,
                "source_message_id": decision.get("source_message_id"),
                "kind": decision.get("kind"),
            }
        if decision.get("status") == "accepted" and product:
            offer_message = messages[decision.get("message_index", 0)]
            offer_text = _message_text(offer_message)
            if not _price_message_matches_product(offer_text, product):
                decision = {
                    "status": "ambiguous",
                    "price": None,
                    "source_message_id": decision.get("source_message_id"),
                    "kind": decision.get("kind"),
                }
        return {
            key: decision.get(key)
            for key in (
                "status", "price", "source_message_id", "acceptance_message_id", "kind"
            )
        }
    return {"status": "none", "price": None, "source_message_id": None}


def _accepted_conversation_price(messages, requested=None, *, qty: int = 1, product=None) -> Decimal | None:
    """Return only the accepted amount from the latest commercial epoch."""
    decision = _conversation_price_evidence(list(messages or ()), qty=qty, product=product)
    accepted = decision.get("price") if decision.get("status") == "accepted" else None
    if accepted is None:
        return None
    if requested is None:
        return accepted
    try:
        requested_price = Decimal(str(requested).replace(",", ".")).quantize(Decimal("0.01"))
    except Exception:
        return None
    return accepted if accepted == requested_price else None


def _conversation_price_decision(client, product=None, qty: int = 1) -> dict:
    """Resolve one accepted merchandise price, excluding receipts/prepayments."""
    if not client or not getattr(client, "pk", None) or product is None:
        return {"status": "none", "price": None, "source_message_id": None}
    try:
        from management.models import InstagramBotMessage

        messages = list(InstagramBotMessage.objects.filter(client=client).order_by("-id")[:80])
        messages.reverse()
    except Exception:
        return {"status": "unavailable", "price": None, "source_message_id": None}
    decision = _conversation_price_evidence(messages, qty=qty, product=product)
    if decision.get("status") == "accepted":
        decision["product_id"] = product.pk
    return decision


def _validated_negotiated_price(client, value, *, product=None, qty: int = 1) -> Decimal | None:
    """Return a conversation price only when the exact amount is evidenced.

    The model may propose ``[PRICE:...]`` but cannot manufacture a discount. The
    amount must occur in a persisted conversation message before it can affect
    an invoice or deal item.
    """
    if not client:
        return None
    if product is None:
        product = getattr(client, "current_product", None)
    decision = _conversation_price_decision(client, product=product, qty=qty)
    accepted = decision.get("price") if decision.get("status") == "accepted" else None
    if value is None:
        return accepted
    try:
        price = Decimal(str(value).replace(",", ".")).quantize(Decimal("0.01"))
    except Exception:
        return None
    if price <= 0 or price > Decimal("1000000"):
        return None
    return price if accepted == price else None


def _create_deal_and_link_unlocked(
    client,
    pay_type: str = "full",
    product_id=None,
    qty: int = 1,
    size: str = "",
    fit_option_code: str = "",
    negotiated_price=None,
    items=None,
) -> dict:
    """Формує/переюзає угоду клієнта і повертає посилання на оплату Monobank.

    Товар визначається серверно (resolve_product_for_payment) — навіть якщо модель
    не передала [PRODUCT:id]. Гроші коректні: посилання на правильний товар/суму,
    стара чернетка/invoice скидаються при зміні товару чи типу оплати.
    """
    from management.models import IgDeal, IgDealItem

    pt = IgDeal.PayType.PREPAY_200 if pay_type == "prepay" else IgDeal.PayType.ONLINE_FULL

    if items is not None:
        if not isinstance(items, (list, tuple)) or not items:
            return {"ok": False, "error": "invalid_items"}
        if len(items) > MAX_PAYLINK_ITEMS:
            return {"ok": False, "error": "too_many_items"}
        if len(items) > 1 and negotiated_price is not None:
            return {"ok": False, "error": "price_allocation_required"}
        from storefront.models import ProductFitOption
        from productcolors.models import ProductColorVariant
        from fable5.services import effective_cart_unit_price, variant_allows_purchase
        from storefront.services.size_guides import resolve_product_sizes

        prepared_items = []
        identities = set()
        aggregate_qty = 0
        for raw in items:
            if not isinstance(raw, dict):
                return {"ok": False, "error": "invalid_items"}
            try:
                item_product_id = int(raw.get("product_id"))
                item_qty = int(raw.get("qty", 1))
            except (TypeError, ValueError):
                return {"ok": False, "error": "invalid_items"}
            if item_product_id <= 0 or item_qty < 1 or item_qty > MAX_PAYLINK_QUANTITY:
                return {"ok": False, "error": "invalid_qty"}
            aggregate_qty += item_qty
            if aggregate_qty > MAX_PAYLINK_QUANTITY:
                return {"ok": False, "error": "aggregate_qty_limit"}
            item_size = str(raw.get("size") or "").strip().upper()[:16]
            item_fit_code = str(raw.get("fit_option_code") or "").strip().lower()[:50]
            color_variant_id = raw.get("color_variant_id")
            if color_variant_id in (None, "", False):
                normalized_color_id = 0
            else:
                try:
                    normalized_color_id = int(color_variant_id)
                except (TypeError, ValueError):
                    return {"ok": False, "error": "invalid_color_variant"}
                if normalized_color_id <= 0:
                    return {"ok": False, "error": "invalid_color_variant"}
            identity = (item_product_id, normalized_color_id, item_size, item_fit_code)
            if identity in identities:
                return {"ok": False, "error": "duplicate_items"}
            identities.add(identity)
            prepared_items.append({
                "product_id": item_product_id,
                "qty": item_qty,
                "size": item_size,
                "fit_option_code": item_fit_code,
                "color_variant_id": normalized_color_id,
            })

        normalized_items = []
        aggregate_value = Decimal("0")
        for raw in prepared_items:
            item_product_id = raw["product_id"]
            item_qty = raw["qty"]
            item_product = resolve_product_for_payment(client, item_product_id)
            if item_product is None:
                return {"ok": False, "error": "no_product"}
            item_size = raw["size"]
            item_fit_code = raw["fit_option_code"]
            if not item_size:
                return {"ok": False, "error": "missing_size"}
            allowed_sizes = {
                str(value or "").strip().upper()
                for value in resolve_product_sizes(item_product)
            }
            if item_fit_code == "oversize":
                allowed_sizes.add("XS")
            if allowed_sizes and item_size not in allowed_sizes:
                return {"ok": False, "error": "invalid_size"}
            fit_label = ""
            if item_fit_code:
                fit = ProductFitOption.objects.filter(
                    product=item_product, code=item_fit_code, is_active=True,
                ).first()
                if not fit:
                    return {"ok": False, "error": "invalid_fit_option"}
                fit_label = fit.label
            elif ProductFitOption.objects.filter(product=item_product, is_active=True).exists():
                return {"ok": False, "error": "missing_fit_option"}
            color_variant_id = raw["color_variant_id"]
            color_variant = None
            if color_variant_id:
                color_variant = ProductColorVariant.objects.filter(
                    pk=color_variant_id, product=item_product,
                ).first()
                if not color_variant:
                    return {"ok": False, "error": "invalid_color_variant"}
                if int(color_variant.stock or 0) < item_qty:
                    return {"ok": False, "error": "insufficient_stock"}
            option_values = {"fit": item_fit_code} if item_fit_code else {}
            if not variant_allows_purchase(
                item_product,
                color_variant,
                fit_code=item_fit_code,
                size=item_size,
                option_values=option_values,
            ):
                return {"ok": False, "error": "unavailable_selection"}
            price_decision = _conversation_price_decision(
                client, product=item_product, qty=item_qty,
            )
            item_override = None
            if len(items) == 1 and negotiated_price is not None:
                item_override = _validated_negotiated_price(
                    client, negotiated_price, product=item_product, qty=item_qty,
                )
                if item_override is None:
                    return {"ok": False, "error": "invalid_negotiated_price"}
            elif price_decision.get("status") == "accepted":
                if len(items) > 1:
                    return {"ok": False, "error": "price_allocation_required"}
                item_override = price_decision.get("price")
            elif price_decision.get("status") in {"ambiguous", "unavailable"}:
                return {"ok": False, "error": "ambiguous_conversation_price"}
            try:
                catalog_price = Decimal(str(effective_cart_unit_price(
                    item_product,
                    color_variant,
                    fit_code=item_fit_code,
                    option_values=option_values,
                ))).quantize(Decimal("0.01"))
            except (InvalidOperation, TypeError, ValueError):
                return {"ok": False, "error": "invalid_catalog_price"}
            unit_price = item_override or catalog_price
            aggregate_value += unit_price * item_qty
            if aggregate_value > MAX_PAYLINK_VALUE:
                return {"ok": False, "error": "aggregate_value_limit"}
            normalized_items.append({
                "product": item_product,
                "color_variant": color_variant,
                "qty": item_qty,
                "size": item_size,
                "fit_option_code": item_fit_code,
                "fit_option_label": fit_label,
                "unit_price": unit_price,
                "price_source": "conversation_evidence" if item_override is not None else "catalog",
                "price_evidence_message_ids": (
                    [message_id for message_id in (
                        price_decision.get("source_message_id"),
                        price_decision.get("acceptance_message_id"),
                    ) if message_id]
                ),
            })
        open_deals = list(
            IgDeal.objects.filter(client=client, order__isnull=True)
            .exclude(status=IgDeal.Status.PAID)
            .order_by("-id")
        )
        desired_signature = sorted(
            (
                item["product"].pk,
                item["color_variant"].pk if item["color_variant"] else 0,
                item["size"],
                item["fit_option_code"],
                item["qty"],
                item["unit_price"],
            )
            for item in normalized_items
        )
        for existing in open_deals:
            if existing.pay_type != pt or not existing.invoice_id or not existing.invoice_url:
                continue
            current_signature = sorted(
                (
                    item.product_id,
                    item.color_variant_id or 0,
                    item.size or "",
                    item.fit_option_code or "",
                    item.qty,
                    item.unit_price,
                )
                for item in existing.items.all()
            )
            if current_signature == desired_signature:
                return create_payment_link(existing)
        deal = IgDeal.objects.create(client=client, pay_type=pt)
        for item in normalized_items:
            IgDealItem.objects.create(
                deal=deal,
                product=item["product"],
                color_variant=item["color_variant"],
                title=item["product"].title,
                size=item["size"],
                fit_option_code=item["fit_option_code"],
                fit_option_label=item["fit_option_label"],
                option_values={"fit": item["fit_option_code"]} if item["fit_option_code"] else {},
                option_labels={"fit": item["fit_option_label"]} if item["fit_option_label"] else {},
                qty=item["qty"],
                unit_price=item["unit_price"],
                price_source=item["price_source"],
                price_evidence_message_ids=item["price_evidence_message_ids"],
            )
        deal.recalc_total()
        res = create_payment_link(deal)
        if res.get("ok"):
            try:
                from management.models import IgClient
                deal.client.set_stage(IgClient.Stage.PAYMENT_PENDING, reason="paylink")
            except Exception:
                pass
        return res

    product = resolve_product_for_payment(client, product_id)
    try:
        qty = int(qty)
    except (TypeError, ValueError):
        return {"ok": False, "error": "invalid_qty"}
    if qty < 1 or qty > MAX_PAYLINK_QUANTITY:
        return {"ok": False, "error": "invalid_qty"}
    size = str(size or "").strip().upper()[:16]
    fit_option_code = str(fit_option_code or "").strip().lower()[:50]
    fit_option_label = ""
    if product is not None and fit_option_code:
        from storefront.models import ProductFitOption

        fit_option = ProductFitOption.objects.filter(
            product=product, code=fit_option_code, is_active=True,
        ).first()
        if not fit_option:
            return {"ok": False, "error": "invalid_fit_option"}
        fit_option_label = fit_option.label
    if product is not None and size:
        from storefront.services.size_guides import resolve_product_sizes

        allowed_sizes = {
            str(value or "").strip().upper()
            for value in resolve_product_sizes(product)
        }
        if fit_option_code == "oversize":
            allowed_sizes.add("XS")
        if allowed_sizes and size not in allowed_sizes:
            return {"ok": False, "error": "invalid_size"}
    open_deals = list(
        IgDeal.objects.filter(client=client, order__isnull=True)
        .exclude(status=IgDeal.Status.PAID)
        .order_by("-id")
    )

    price_decision = _conversation_price_decision(client, product=product, qty=qty) if product else {
        "status": "none", "price": None,
    }
    unit_price_override = None
    if negotiated_price is not None:
        unit_price_override = _validated_negotiated_price(
            client, negotiated_price, product=product, qty=qty,
        )
        if unit_price_override is None:
            return {"ok": False, "error": "invalid_negotiated_price"}
    elif price_decision.get("status") == "accepted":
        unit_price_override = price_decision.get("price")
    elif price_decision.get("status") in {"ambiguous", "unavailable"}:
        return {"ok": False, "error": "ambiguous_conversation_price"}

    intended_price = unit_price_override
    if product is not None and intended_price is None:
        try:
            from fable5.services import effective_cart_unit_price

            intended_price = Decimal(str(effective_cart_unit_price(
                product,
                None,
                fit_code=fit_option_code,
                option_values={"fit": fit_option_code} if fit_option_code else {},
            ))).quantize(Decimal("0.01"))
        except Exception:
            intended_price = Decimal(str(product.price or 0)).quantize(Decimal("0.01"))
    if intended_price is not None and intended_price * qty > MAX_PAYLINK_VALUE:
        return {"ok": False, "error": "aggregate_value_limit"}

    deal = None
    if product is not None:
        # 1) точний реюз: та сама угода (товар + тип оплати) вже має лінк
        for d in open_deals:
            if (
                d.pay_type == pt
                and d.items.count() == 1
                and d.items.filter(product_id=product.id).exists()
                and d.invoice_id
                and d.invoice_url
                and d.items.first().unit_price == intended_price
                and d.items.first().qty == qty
                and (d.items.first().size or "") == size
                and (d.items.first().fit_option_code or "") == fit_option_code
            ):
                return create_payment_link(d)
        # 2) свіжа угода саме під цей товар
        deal = IgDeal.objects.create(client=client, pay_type=pt)
        price = intended_price
        IgDealItem.objects.create(
            deal=deal, product=product, title=product.title, size=size or "",
            fit_option_code=fit_option_code,
            fit_option_label=fit_option_label,
            option_values={"fit": fit_option_code} if fit_option_code else {},
            option_labels={"fit": fit_option_label} if fit_option_label else {},
            qty=qty,
            unit_price=price,
            price_source="conversation_evidence" if unit_price_override is not None else "catalog",
            price_evidence_message_ids=(
                [message_id for message_id in (
                    price_decision.get("source_message_id"),
                    price_decision.get("acceptance_message_id"),
                ) if message_id]
            ),
        )
    else:
        # Товар не визначено → остання відкрита угода з позиціями.
        for d in open_deals:
            if d.items.exists():
                deal = d
                break
        if deal is None:
            return {"ok": False, "error": "no_product"}
        if deal.pay_type == pt and deal.invoice_id and deal.invoice_url:
            return create_payment_link(deal)
        deal.pay_type = pt
        deal.invoice_id = ""
        deal.invoice_url = ""
        deal.save(update_fields=["pay_type", "invoice_id", "invoice_url", "updated_at"])

    deal.recalc_total()
    res = create_payment_link(deal)
    if res.get("ok"):
        try:
            from management.models import IgClient

            deal.client.set_stage(IgClient.Stage.PAYMENT_PENDING, reason="paylink")
        except Exception:
            pass
    return res


def create_deal_and_link(
    client,
    pay_type: str = "full",
    product_id=None,
    qty: int = 1,
    size: str = "",
    fit_option_code: str = "",
    negotiated_price=None,
    items=None,
) -> dict:
    """Create or reuse one payment deal while serializing the client flow."""
    client_id = getattr(client, "pk", None)
    if not client_id:
        return {"ok": False, "error": "invalid_client"}
    with _paylink_client_lock(client_id):
        return _create_deal_and_link_unlocked(
            client,
            pay_type=pay_type,
            product_id=product_id,
            qty=qty,
            size=size,
            fit_option_code=fit_option_code,
            negotiated_price=negotiated_price,
            items=items,
        )


def fulfill_ready_paid_deals(limit: int = 50) -> int:
    """Safety-net: створює замовлення для ОПЛАЧЕНИХ угод без замовлення, у яких
    уже є повні дані НП (якщо модель не виставила тег [ORDER]). Для крону."""
    from management.models import IgDeal
    from storefront.models import UserAction

    purchase_order_ids = UserAction.objects.filter(
        action_type='purchase',
        order_id__isnull=False,
    ).values('order_id')
    missing_order = verified_payment_q() & Q(order__isnull=True)
    missing_purchase = (
        Q(
            status=IgDeal.Status.ORDER_CREATED,
            payment_status__in=("paid", "prepaid"),
            paid_at__isnull=False,
            order__isnull=False,
            order__payment_status__in=('paid', 'prepaid', 'partial'),
        )
        & ~Q(order_id__in=purchase_order_ids)
    )
    qs = (
        IgDeal.objects.filter(missing_order | missing_purchase)
        .select_related('order')
        .order_by('id')[:limit]
    )
    created = 0
    for deal in qs:
        try:
            if deal.order_id:
                # Four-minute cron retry for a post-commit analytics failure.
                create_order_from_deal(deal)
            elif deal_has_np_data(deal) and fulfill_if_ready(deal):
                created += 1
        except Exception:
            # One broken deal must not abort healing/creation for the batch.
            logger.exception('Failed to fulfil or heal paid IG deal %s', deal.pk)
    return created


NP_TRACK_URL = "https://novaposhta.ua/tracking/?cargo_number="
SHIPMENT_RESPONSE_WINDOW = timedelta(hours=23)
SHIPMENT_REVIEW_REASONS = {"shipment_human_review", "shipment_delivery_review"}


def _shipment_message(ttn: str) -> str:
    return (
        "📦 Гарна новина — ваше замовлення вже відправлено Новою Поштою! 🚚\n"
        f"ТТН: {ttn}\n"
        f"Відстежити: {NP_TRACK_URL}{ttn}\n"
        "Дякуємо за покупку 💛 Будуть питання — пишіть, я на зв'язку!"
    )


def _queue_shipment_manager_review(deal, text: str, *, reason: str, hint: str = ""):
    from django.utils import timezone

    from management.models import IgFollowUpTask

    task, created = IgFollowUpTask.objects.get_or_create(
        client=deal.client,
        deal=deal,
        kind=IgFollowUpTask.Kind.MANAGER_TASK,
        reason=reason,
        defaults={
            "due_at": timezone.now(),
            # Manager tasks must never enter the automatic send worker.
            "status": IgFollowUpTask.Status.SKIPPED,
            "skip_reason": "human_agent_required",
            "message_text": text,
            "last_error": (hint or "")[:500],
        },
    )
    if not created:
        changed = []
        if task.message_text != text:
            task.message_text = text
            changed.append("message_text")
        bounded_hint = (hint or "")[:500]
        if task.last_error != bounded_hint:
            task.last_error = bounded_hint
            changed.append("last_error")
        if changed:
            changed.append("updated_at")
            task.save(update_fields=changed)
    client_label = deal.client.username or deal.client.display_name or deal.client.igsid
    notify_manager(
        f"📦 IG: потрібна ручна відповідь про відправку для {client_label}. "
        f"Угода #{deal.pk}; готовий текст збережено у завданні менеджеру.",
        dedupe_key=f"{reason}:{deal.pk}",
        event_type="shipment_human_review",
        client=deal.client,
    )
    return task


def notify_shipped_deals(limit: int = 50) -> int:
    """Сповіщає IG-клієнта в Direct, що замовлення відправлено (з ТТН).

    Лише для IG-угод, чиє замовлення в статусі 'ship' і має tracking_number.
    Усередині response window надсилає звичайний RESPONSE. Поза вікном або
    після непідтвердженої доставки створює завдання менеджеру; автоматичний
    HUMAN_AGENT tag не використовується.
    """
    from django.utils import timezone

    from management.models import IgDeal, InstagramBotSettings
    from management.services.bot_payment_truth import verified_payment_q

    s = InstagramBotSettings.load()
    qs = (
        IgDeal.objects.filter(
            order__isnull=False, order__status="ship", shipped_notified_at__isnull=True
        )
        .filter(verified_payment_q())
        .exclude(order__tracking_number__isnull=True)
        .exclude(order__tracking_number="")
        .select_related("order", "client")[:limit]
    )
    sent = 0
    for deal in qs:
        ttn = (deal.order.tracking_number or "").strip()
        if not ttn or not deal.client_id:
            continue
        text = _shipment_message(ttn)
        existing_review = deal.followup_tasks.filter(
            reason__in=SHIPMENT_REVIEW_REASONS
        ).first()
        if existing_review:
            _queue_shipment_manager_review(
                deal,
                text,
                reason=existing_review.reason,
                hint=existing_review.last_error,
            )
            continue
        response_deadline = (
            deal.client.last_message_at + SHIPMENT_RESPONSE_WINDOW
            if deal.client.last_message_at
            else None
        )
        if not response_deadline or timezone.now() > response_deadline:
            _queue_shipment_manager_review(
                deal,
                text,
                reason="shipment_human_review",
                hint="standard_response_window_closed",
            )
            continue
        try:
            ok, kind, hint = send_text(s, deal.client.igsid, text)
        except Exception as exc:
            ok, kind, hint = False, "unknown", repr(exc)
        if ok:
            deal.shipped_notified_at = timezone.now()
            deal.order_truth_updated_at = deal.shipped_notified_at
            deal.save(update_fields=[
                "shipped_notified_at",
                "order_truth_updated_at",
                "updated_at",
            ])
            sent += 1
        else:
            _queue_shipment_manager_review(
                deal,
                text,
                reason="shipment_delivery_review",
                hint=f"{kind}:{hint}",
            )
    return sent
