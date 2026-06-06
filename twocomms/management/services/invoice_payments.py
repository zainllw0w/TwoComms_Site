"""
Оплата накладних менеджерів через Monobank acquiring (`mono_hrefs` токен).

Окремий токен від storefront-корзини: інший мерчант → інший публічний ключ
для перевірки підпису. Гроші підтверджуються ТІЛЬКИ pull-істиною через
`/api/merchant/invoice/status` (захист від підробки webhook), а перехід у
`paid` ідемпотентний.

Док: twocomms/Management Implementations/04_INVOICE_MONOBANK_PAYMENTS.md
"""
from __future__ import annotations

import logging
from decimal import Decimal

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger("management.invoice_payments")

# Кеш-ключ публічного ключа acquiring-мерчанта (окремий від storefront).
ACQUIRING_PUBKEY_CACHE_KEY = "monobank_acquiring_public_key"

SUCCESS_STATUSES = {"success", "hold"}
PENDING_STATUSES = {"processing", "created"}
FAILURE_STATUSES = {"failure", "expired", "rejected", "canceled", "cancelled", "reversed"}


def acquiring_token() -> str:
    return getattr(settings, "MONOBANK_ACQUIRING_TOKEN", "") or getattr(settings, "MONOBANK_TOKEN", "")


def _webhook_url() -> str:
    base = getattr(settings, "MONOBANK_PUBLIC_BASE_URL", "https://twocomms.shop").rstrip("/")
    return f"{base}/payments/monobank/webhook/"


def _redirect_url(invoice) -> str:
    base = getattr(settings, "MANAGEMENT_BASE_URL", "https://management.twocomms.shop").rstrip("/")
    return f"{base}/invoices/payment-return/?invoice={invoice.id}"


def create_payment_link(invoice) -> tuple[str, str]:
    """Створює Monobank invoice через acquiring-токен. Повертає (url, invoice_id).

    Кидає MonobankAPIError / ValueError при помилці.
    """
    from storefront.views.monobank import _monobank_api_request

    amount_decimal = Decimal(str(invoice.total_amount or 0))
    if amount_decimal <= 0:
        raise ValueError("Невірна сума накладної")
    amount_minor = int((amount_decimal * 100).to_integral_value())
    reference = f"MGMT-INV-{invoice.id}"

    payload = {
        "amount": amount_minor,
        "ccy": 980,
        "merchantPaymInfo": {
            "reference": reference,
            "destination": f"Оплата накладної {invoice.invoice_number}",
            "basketOrder": [
                {
                    "name": f"Накладна {invoice.invoice_number}",
                    "qty": 1,
                    "sum": amount_minor,
                    "unit": "шт",
                }
            ],
        },
        "redirectUrl": _redirect_url(invoice),
        "webHookUrl": _webhook_url(),
    }

    data = _monobank_api_request(
        "POST", "/api/merchant/invoice/create", json_payload=payload, token=acquiring_token()
    )
    result = data.get("result") if isinstance(data.get("result"), dict) else data
    invoice_id = result.get("invoiceId") or data.get("invoiceId")
    url = result.get("pageUrl") or data.get("pageUrl") or data.get("invoiceUrl")
    if not url or not invoice_id:
        raise ValueError("Monobank не повернув посилання/ідентифікатор інвойсу")
    return url, invoice_id


def fetch_invoice_status(monobank_invoice_id: str) -> dict:
    """Pull-істина: статус інвойсу через acquiring-токен."""
    from storefront.views.monobank import _monobank_api_request

    data = _monobank_api_request(
        "GET",
        "/api/merchant/invoice/status",
        params={"invoiceId": monobank_invoice_id},
        token=acquiring_token(),
    )
    return data.get("result") if isinstance(data.get("result"), dict) else data


def apply_payment_status(invoice, status, amount_minor=None) -> bool:
    """Ідемпотентно застосовує статус оплати. Повертає True якщо щось змінилось.

    Перехід у `paid` встановлює paid_at та payment_amount_minor ДО save, тож
    сигнал нарахування комісії (orders.signals) бачить фактичну суму.
    """
    status_lower = (status or "").strip().lower()
    fields: list[str] = []

    if status_lower in SUCCESS_STATUSES:
        if invoice.payment_status != "paid":
            invoice.payment_status = "paid"
            fields.append("payment_status")
            if not invoice.paid_at:
                invoice.paid_at = timezone.now()
                fields.append("paid_at")
            if amount_minor:
                try:
                    invoice.payment_amount_minor = int(amount_minor)
                    fields.append("payment_amount_minor")
                except (TypeError, ValueError):
                    pass
    elif status_lower in PENDING_STATUSES:
        if invoice.payment_status != "pending":
            invoice.payment_status = "pending"
            fields.append("payment_status")
    elif status_lower in FAILURE_STATUSES:
        if invoice.payment_status != "failed":
            invoice.payment_status = "failed"
            fields.append("payment_status")
        # НЕ обнуляємо monobank_invoice_id: він потрібен поллінгу/повторній
        # перевірці. payment_url теж лишаємо для аудиту.
    else:
        # Невідомий статус — нічого не робимо.
        return False

    if fields:
        invoice.save(update_fields=list(dict.fromkeys(fields)))
        # Сповіщення про оплату — лише при реальному переході в paid.
        if "payment_status" in fields and invoice.payment_status == "paid":
            try:
                from management.models import ManagerCommissionAccrual
                from management.services.notify import notify_invoice_paid
                accrual = ManagerCommissionAccrual.objects.filter(invoice=invoice).first()
                notify_invoice_paid(invoice, accrual)
            except Exception as exc:
                logger.warning("paid notification failed for invoice %s: %s", invoice.id, exc)
        return True
    return False


def sync_invoice_payment(invoice) -> str | None:
    """Підтягує статус через API і застосовує. Повертає рядок статусу або None."""
    if not invoice.monobank_invoice_id:
        return None
    try:
        result = fetch_invoice_status(invoice.monobank_invoice_id)
    except Exception as exc:
        logger.warning("Status pull failed for invoice %s: %s", invoice.id, exc)
        return None
    status = result.get("status")
    amount_minor = result.get("amount")
    apply_payment_status(invoice, status, amount_minor)
    return status


def process_webhook(invoice, payload, request=None) -> str | None:
    """Обробка webhook накладної: довіра лише pull-істині (defense in depth).

    Тіло webhook не використовується для грошей — завжди підтягуємо статус
    через status API під acquiring-токеном. Це закриває підробку webhook
    навіть без перевірки підпису (підпис — додатковий рівень нижче).
    """
    # М'яка перевірка підпису (інформативно; рішення — за pull-істиною).
    try:
        from storefront.views.monobank import _verify_monobank_signature

        if request is not None:
            ok = _verify_monobank_signature(
                request, token=acquiring_token(), cache_key=ACQUIRING_PUBKEY_CACHE_KEY
            )
            if not ok:
                logger.info("WholesaleInvoice %s webhook signature not verified (pull-truth used)", invoice.id)
    except Exception:
        pass

    return sync_invoice_payment(invoice)
