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

from decimal import Decimal

from management.services.bot_payments import create_payment_link
from management.services.call_ai_analysis import gemini_generate_text
from management.services.instagram_bot import notify_manager
from orders.services.order_builder import create_order_from_deal

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
            "maxOutputTokens": 300,
            "responseMimeType": "application/json",
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }
    try:
        out = gemini_generate_text(payload, role="management")
    except Exception:
        return {}
    from management.services.bot_vision import _parse_fingerprint

    return _parse_fingerprint(out.get("parsed") or "")


def fulfill_if_ready(deal, created_by=None) -> bool:
    """Створює замовлення, якщо угода оплачена, ще без замовлення і дані НП повні."""
    if deal.order_id:
        return False
    if deal.status != deal.Status.PAID:
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
        IgDeal.objects.filter(client=client, status=IgDeal.Status.PAID, order__isnull=True)
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


def create_deal_and_link(client, pay_type: str = "full", product_id=None, qty: int = 1, size: str = "") -> dict:
    """Формує/переюзає угоду клієнта і повертає посилання на оплату Monobank.
    pay_type: 'full' | 'prepay'. product_id — обраний товар (за тегом [PRODUCT:id]).

    Коректність грошей: посилання має бути на ПРАВИЛЬНИЙ товар і суму. Тому
    переюзаємо угоду лише якщо вона ТОЧНО відповідає запиту (той самий товар і
    тип оплати) і вже має invoice. Інакше — створюємо свіжу угоду / скидаємо
    старий invoice, щоб лінк був на актуальну суму (а не стару чернеткову).
    """
    from management.models import IgDeal, IgDealItem

    pt = IgDeal.PayType.PREPAY_200 if pay_type == "prepay" else IgDeal.PayType.ONLINE_FULL
    open_deals = list(
        IgDeal.objects.filter(client=client, order__isnull=True)
        .exclude(status=IgDeal.Status.PAID)
        .order_by("-id")
    )

    def _is_single_product(d, pid) -> bool:
        return d.items.count() == 1 and d.items.filter(product_id=pid).exists()

    deal = None
    if product_id:
        # 1) точний реюз: та сама угода (товар + тип оплати) вже має лінк
        for d in open_deals:
            if d.pay_type == pt and _is_single_product(d, product_id) and d.invoice_id and d.invoice_url:
                return create_payment_link(d)
        # 2) свіжа угода саме під цей товар
        deal = IgDeal.objects.create(client=client, pay_type=pt)
        try:
            from storefront.models import Product

            p = Product.objects.filter(id=product_id).first()
        except Exception:
            p = None
        if p:
            try:
                price = Decimal(str(int(getattr(p, "final_price", None) or p.price)))
            except Exception:
                price = Decimal(str(p.price or 0))
            IgDealItem.objects.create(
                deal=deal, product=p, title=p.title, size=size or "",
                qty=max(1, int(qty or 1)), unit_price=price,
            )
    else:
        # Без [PRODUCT] — беремо останню відкриту угоду з позиціями (товар уже
        # обговорювали). Якщо немає позицій — нема що оплачувати.
        for d in open_deals:
            if d.items.exists():
                deal = d
                break
        if deal is None:
            return {"ok": False, "error": "no_items"}
        if deal.pay_type == pt and deal.invoice_id and deal.invoice_url:
            return create_payment_link(deal)
        # тип оплати змінився → скидаємо старий invoice (інша сума)
        deal.pay_type = pt
        deal.invoice_id = ""
        deal.invoice_url = ""
        deal.save(update_fields=["pay_type", "invoice_id", "invoice_url", "updated_at"])

    if deal is None:
        return {"ok": False, "error": "no_items"}
    deal.recalc_total()
    res = create_payment_link(deal)
    if res.get("ok"):
        try:
            from management.models import IgClient

            deal.client.set_stage(IgClient.Stage.PAYMENT_PENDING, reason="paylink")
        except Exception:
            pass
    return res


def fulfill_ready_paid_deals(limit: int = 50) -> int:
    """Safety-net: створює замовлення для ОПЛАЧЕНИХ угод без замовлення, у яких
    уже є повні дані НП (якщо модель не виставила тег [ORDER]). Для крону."""
    from management.models import IgDeal

    qs = IgDeal.objects.filter(
        status=IgDeal.Status.PAID, order__isnull=True
    ).order_by("id")[:limit]
    created = 0
    for deal in qs:
        if deal_has_np_data(deal) and fulfill_if_ready(deal):
            created += 1
    return created
