import logging

from django.urls import reverse
from django.utils.html import escape

from orders.telegram_notifications import TelegramNotifier

logger = logging.getLogger(__name__)


def _format_contact_line(label, value):
    if not value:
        return ""
    return f"{label} {escape(value)}"


def _build_admin_link(path: str) -> str:
    base = "https://dtf.twocomms.shop"
    return f"{base}{path}"


def notify_new_lead(lead):
    try:
        notifier = TelegramNotifier()
        message = (
            "🟡 <b>Нова заявка (DTF)</b>\n"
            f"№ {escape(lead.lead_number)}\n\n"
            f"👤 {escape(lead.name)}\n"
            f"📞 {escape(lead.phone)}\n"
        )
        if lead.contact_handle:
            message += _format_contact_line("💬", lead.contact_handle) + "\n"
        if lead.task_description:
            message += f"\n📝 {escape(lead.task_description)}\n"
        message += f"\n🌐 Адмін: <a href=\"{_build_admin_link('/admin/dtf/dtflead/') }\">відкрити</a>"
        notifier.send_admin_message(message)
    except Exception as exc:
        logger.warning("DTF Telegram notify_new_lead failed: %s", exc, exc_info=True)


def notify_new_order(order):
    try:
        notifier = TelegramNotifier()
        message = (
            "🟢 <b>Нове DTF замовлення</b>\n"
            f"№ {escape(order.order_number)}\n\n"
            f"👤 {escape(order.name)}\n"
            f"📞 {escape(order.phone)}\n"
            f"📦 {escape(order.city)} / {escape(order.np_branch)}\n"
        )
        if order.meters_total:
            message += f"\n📏 Метраж: {order.meters_total} м"
        if order.price_total:
            message += f"\n💰 Сума: {order.price_total} грн"
        message += f"\n\n🌐 Статус: <a href=\"{_build_admin_link('/status') }\">перевірити</a>"
        message += f"\n🌐 Адмін: <a href=\"{_build_admin_link('/admin/dtf/dtforder/') }\">відкрити</a>"
        notifier.send_admin_message(message)
    except Exception as exc:
        logger.warning("DTF Telegram notify_new_order failed: %s", exc, exc_info=True)


def notify_need_fix(order, reason: str):
    try:
        notifier = TelegramNotifier()
        message = (
            "🟠 <b>DTF: потрібні правки</b>\n"
            f"№ {escape(order.order_number)}\n\n"
            f"Причина: {escape(reason)}"
        )
        notifier.send_admin_message(message)
    except Exception as exc:
        logger.warning("DTF Telegram notify_need_fix failed: %s", exc, exc_info=True)


def notify_awaiting_payment(order):
    try:
        notifier = TelegramNotifier()
        message = (
            "🟣 <b>DTF: очікує оплату</b>\n"
            f"№ {escape(order.order_number)}"
        )
        notifier.send_admin_message(message)
    except Exception as exc:
        logger.warning("DTF Telegram notify_awaiting_payment failed: %s", exc, exc_info=True)


def notify_paid(order):
    try:
        notifier = TelegramNotifier()
        message = (
            "✅ <b>DTF: оплата підтверджена</b>\n"
            f"№ {escape(order.order_number)}"
        )
        notifier.send_admin_message(message)
    except Exception as exc:
        logger.warning("DTF Telegram notify_paid failed: %s", exc, exc_info=True)


def notify_shipped(order):
    try:
        notifier = TelegramNotifier()
        ttn = f" (ТТН {escape(order.tracking_number)})" if order.tracking_number else ""
        message = (
            "📦 <b>DTF: відправлено</b>\n"
            f"№ {escape(order.order_number)}{ttn}"
        )
        notifier.send_admin_message(message)
    except Exception as exc:
        logger.warning("DTF Telegram notify_shipped failed: %s", exc, exc_info=True)
