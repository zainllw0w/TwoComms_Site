"""
Telegram-сповіщення менеджмента (самодостатній модуль, без імпорту views).

Використовується з invoice_payments / views для красивих повідомлень про
життєвий цикл оплати накладних. Токени/чати — з env (як у решті проєкту).
"""
from __future__ import annotations

import logging
import os
import re

import requests

logger = logging.getLogger("management.notify")


def manager_bot_token() -> str:
    return os.environ.get("MANAGER_TG_BOT_TOKEN") or os.environ.get("MANAGEMENT_TG_BOT_TOKEN") or ""


def admin_chat_ids() -> list[str]:
    raw = os.environ.get("MANAGEMENT_TG_ADMIN_CHAT_ID") or ""
    if not raw:
        return []
    parts = re.split(r"[;,\s]+", str(raw))
    return [p.strip() for p in parts if p.strip()]


def send_message(chat_id, text: str, *, reply_markup=None) -> bool:
    token = manager_bot_token()
    if not token or not chat_id:
        return False
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json=payload, timeout=10,
        )
        data = resp.json()
        return bool(data.get("ok"))
    except Exception as exc:
        logger.warning("Telegram send failed (chat %s): %s", chat_id, exc)
        return False


def _manager_chat_id(user):
    try:
        return getattr(user.userprofile, "tg_manager_chat_id", None)
    except Exception:
        return None


def _manager_name(user) -> str:
    if not user:
        return "—"
    try:
        name = (getattr(user.userprofile, "full_name", "") or "").strip()
        if name:
            return name
    except Exception:
        pass
    return user.get_full_name() or user.username


def _admin_base() -> str:
    from django.conf import settings
    return getattr(settings, "MANAGEMENT_BASE_URL", "https://management.twocomms.shop").rstrip("/")


def notify_payment_link_created(invoice):
    """Адміну: менеджер сформував посилання на оплату."""
    base = _admin_base()
    lines = [
        "🔗 <b>Сформовано посилання на оплату</b>",
        "",
        f"👤 Менеджер: <b>{_manager_name(invoice.created_by)}</b>",
        f"🧾 Накладна: <code>{invoice.invoice_number}</code>",
        f"🏢 Компанія: {invoice.company_name}",
        f"💵 Сума: <b>{invoice.total_amount} грн</b>",
    ]
    kb = {"inline_keyboard": [[
        {"text": "Відкрити в адмінці", "url": f"{base}/admin-panel/?tab=invoices&invoice={invoice.id}"}
    ]]}
    for chat_id in admin_chat_ids():
        send_message(chat_id, "\n".join(lines), reply_markup=kb)


def notify_invoice_paid(invoice, accrual=None):
    """Менеджеру (красиво) + адміну (детально) про оплату накладної."""
    from django.utils import timezone

    paid_at = invoice.paid_at or timezone.now()
    paid_local = timezone.localtime(paid_at).strftime("%d.%m.%Y %H:%M")
    commission = None
    frozen_until = None
    if accrual:
        commission = accrual.amount
        if accrual.frozen_until:
            frozen_until = timezone.localtime(accrual.frozen_until).strftime("%d.%m.%Y")

    # --- Менеджеру ---
    mgr_chat = _manager_chat_id(invoice.created_by)
    if mgr_chat:
        mlines = [
            "✅ <b>Накладну оплачено!</b>",
            "",
            f"🧾 Накладна <code>{invoice.invoice_number}</code> для <b>{invoice.company_name}</b>",
            f"💵 Сума: <b>{invoice.total_amount} грн</b>",
        ]
        if commission is not None:
            mlines.append(f"🎁 Ваша винагорода: <b>{commission} грн</b>")
        if frozen_until:
            mlines.append(f"🔒 Заморожено до <b>{frozen_until}</b> (період можливого повернення)")
        send_message(mgr_chat, "\n".join(mlines))

    # --- Адміну ---
    base = _admin_base()
    alines = [
        "💰 <b>Оплата отримана</b>",
        "",
        f"👤 Менеджер: <b>{_manager_name(invoice.created_by)}</b>",
        f"🧾 Накладна: <code>{invoice.invoice_number}</code>",
        f"🏢 Компанія: {invoice.company_name}",
        f"💵 Сума: <b>{invoice.total_amount} грн</b>",
        f"🕓 Оплачено: {paid_local}",
    ]
    if commission is not None:
        pct = f" ({accrual.percent}%)" if accrual and accrual.percent else ""
        alines.append(f"📊 Комісія: <b>{commission} грн</b>{pct}")
    if frozen_until:
        alines.append(f"🔒 Заморожено до: {frozen_until}")
    kb = {"inline_keyboard": [[
        {"text": "Відкрити в адмінці", "url": f"{base}/admin-panel/?tab=invoices&invoice={invoice.id}"}
    ]]}
    for chat_id in admin_chat_ids():
        send_message(chat_id, "\n".join(alines), reply_markup=kb)
