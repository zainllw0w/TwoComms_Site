import logging
import os
from decimal import Decimal, InvalidOperation
from urllib.parse import quote

from django.utils import timezone
from django.utils.html import escape

from orders.telegram_notifications import TelegramNotifier

logger = logging.getLogger(__name__)

DTF_PUBLIC_BASE_URL = "https://dtf.twocomms.shop"


def _first_env(*keys: str) -> str:
    for key in keys:
        value = (os.environ.get(key) or "").strip()
        if value:
            return value
    return ""


def _build_dtf_notifier() -> TelegramNotifier:
    return TelegramNotifier(
        bot_token=_first_env("DTF_TG_BOT_TOKEN"),
        chat_id=_first_env("DTF_TG_CHAT_ID", "TELEGRAM_CHAT_ID"),
        admin_id=_first_env("DTF_TG_ADMIN_ID", "TELEGRAM_ADMIN_ID"),
        async_enabled=False,
    )


def _send_admin_message(message: str) -> bool:
    notifier = _build_dtf_notifier()
    if not notifier.is_configured():
        logger.warning(
            "DTF Telegram is not configured: expected DTF_TG_BOT_TOKEN and DTF_TG_CHAT_ID/DTF_TG_ADMIN_ID "
            "(or TELEGRAM_CHAT_ID/TELEGRAM_ADMIN_ID as fallback for recipients)."
        )
        return False
    return notifier.send_admin_message(message, parse_mode="HTML")


def _build_admin_link(path: str) -> str:
    return f"{DTF_PUBLIC_BASE_URL}{path}"


def _safe(value, default: str = "—") -> str:
    if value is None:
        return default
    text = str(value).strip()
    if not text:
        return default
    return escape(text)


def _safe_truncated(value, limit: int = 360, default: str = "—") -> str:
    if value is None:
        return default
    text = str(value).strip()
    if not text:
        return default
    if len(text) > limit:
        text = f"{text[: limit - 1].rstrip()}…"
    return escape(text)


def _fmt_datetime(value) -> str:
    if not value:
        return "—"
    try:
        return timezone.localtime(value).strftime("%d.%m.%Y %H:%M")
    except Exception:
        return _safe(value)


def _fmt_amount(value, suffix: str) -> str:
    if value in (None, ""):
        return "—"
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return _safe(value)

    normalized = f"{amount:.2f}".rstrip("0").rstrip(".")
    return f"{escape(normalized)} {suffix}"


def _fmt_money(value) -> str:
    return _fmt_amount(value, "грн")


def _fmt_meters(value) -> str:
    return _fmt_amount(value, "м")


def _choice_label(instance, display_method: str, raw_attr: str) -> str:
    display_fn = getattr(instance, display_method, None)
    if callable(display_fn):
        try:
            return _safe(display_fn())
        except Exception:
            pass
    return _safe(getattr(instance, raw_attr, None))


def _append_section(lines: list[str], title: str, rows: list[str]):
    rows = [row for row in rows if row]
    if not rows:
        return

    lines.append(f"<b>{title}</b>")
    for row in rows:
        lines.append(f"• {row}")
    lines.append("")


def _compose_message(header: str, *, event_rows: list[str] | None = None, sections: list[tuple[str, list[str]]], links: list[str] | None = None) -> str:
    lines = [
        header,
        f"🕒 <b>Час події:</b> {_fmt_datetime(timezone.now())}",
        "",
    ]

    if event_rows:
        _append_section(lines, "Подія", event_rows)

    for section_title, section_rows in sections:
        _append_section(lines, section_title, section_rows)

    if links:
        lines.append("<b>Посилання</b>")
        for link in links:
            lines.append(f"• {link}")

    return "\n".join(lines).strip()


def _order_links(order) -> list[str]:
    order_id = getattr(order, "pk", None)
    order_number = getattr(order, "order_number", "")

    admin_path = "/admin/dtf/dtforder/"
    if order_id:
        admin_path = f"/admin/dtf/dtforder/{order_id}/change/"

    status_path = "/status"
    if order_number:
        status_path = f"/status/{quote(str(order_number))}/"

    return [
        f'<a href="{_build_admin_link(admin_path)}">Адмінка замовлення</a>',
        f'<a href="{_build_admin_link(status_path)}">Сторінка статусу</a>',
    ]


def _lead_links(lead) -> list[str]:
    lead_id = getattr(lead, "pk", None)
    admin_path = "/admin/dtf/dtflead/"
    if lead_id:
        admin_path = f"/admin/dtf/dtflead/{lead_id}/change/"

    return [f'<a href="{_build_admin_link(admin_path)}">Адмінка заявки</a>']


def _order_overview_rows(order) -> list[str]:
    return [
        f"<b>№:</b> <code>{_safe(getattr(order, 'order_number', None))}</code>",
        f"<b>Тип замовлення:</b> {_choice_label(order, 'get_order_type_display', 'order_type')}",
        f"<b>Формат виконання:</b> {_choice_label(order, 'get_fulfillment_kind_display', 'fulfillment_kind')}",
        f"<b>Статус:</b> {_choice_label(order, 'get_status_display', 'status')}",
        f"<b>Етап:</b> {_choice_label(order, 'get_lifecycle_status_display', 'lifecycle_status')}",
        f"<b>Кількість:</b> {_safe(getattr(order, 'product_quantity', None) or getattr(order, 'copies', None))}",
        f"<b>Метраж:</b> {_fmt_meters(getattr(order, 'meters_total', None))}",
        f"<b>Сума:</b> {_fmt_money(getattr(order, 'price_total', None))}",
        f"<b>Потрібна ручна перевірка:</b> {'Так' if bool(getattr(order, 'requires_review', False)) else 'Ні'}",
        f"<b>Створено:</b> {_fmt_datetime(getattr(order, 'created_at', None))}",
        f"<b>Оновлено:</b> {_fmt_datetime(getattr(order, 'updated_at', None))}",
    ]


def _order_customer_rows(order) -> list[str]:
    rows = [
        f"<b>Ім'я:</b> {_safe(getattr(order, 'name', None))}",
        f"<b>Телефон:</b> {_safe(getattr(order, 'phone', None))}",
        f"<b>Канал зв'язку:</b> {_choice_label(order, 'get_contact_channel_display', 'contact_channel')}",
    ]

    contact_handle = getattr(order, "contact_handle", "")
    if contact_handle:
        rows.append(f"<b>Контакт:</b> {_safe(contact_handle)}")

    comment = getattr(order, "comment", "")
    if comment:
        rows.append(f"<b>Коментар:</b> {_safe_truncated(comment)}")

    return rows


def _order_delivery_rows(order) -> list[str]:
    rows = [
        f"<b>Місто:</b> {_safe(getattr(order, 'city', None))}",
        f"<b>Відділення НП:</b> {_safe(getattr(order, 'np_branch', None))}",
    ]

    delivery_point = getattr(order, "delivery_point_label", "") or getattr(order, "delivery_point_code", "")
    if delivery_point:
        rows.append(f"<b>Точка доставки:</b> {_safe(delivery_point)}")

    tracking_number = getattr(order, "tracking_number", "")
    if tracking_number:
        rows.append(f"<b>ТТН:</b> <code>{_safe(tracking_number)}</code>")

    return rows


def _order_payment_rows(order) -> list[str]:
    rows = [
        f"<b>Статус оплати:</b> {_choice_label(order, 'get_payment_status_display', 'payment_status')}",
        f"<b>Сума до оплати:</b> {_fmt_money(getattr(order, 'payment_amount', None) or getattr(order, 'price_total', None))}",
        f"<b>Оновлено:</b> {_fmt_datetime(getattr(order, 'payment_updated_at', None))}",
    ]

    payment_reference = getattr(order, "payment_reference", "")
    if payment_reference:
        rows.append(f"<b>Референс:</b> <code>{_safe(payment_reference)}</code>")

    payment_link = getattr(order, "payment_link", "")
    if payment_link:
        rows.append(f'<b>Посилання на оплату:</b> <a href="{escape(payment_link)}">відкрити</a>')

    return rows


def _build_order_message(order, title: str, icon: str, event_rows: list[str] | None = None) -> str:
    sections = [
        ("Замовлення", _order_overview_rows(order)),
        ("Клієнт", _order_customer_rows(order)),
        ("Доставка", _order_delivery_rows(order)),
        ("Оплата", _order_payment_rows(order)),
    ]
    return _compose_message(
        f"{icon} <b>{escape(title)}</b>",
        event_rows=event_rows,
        sections=sections,
        links=_order_links(order),
    )


def _lead_rows(lead) -> list[str]:
    rows = [
        f"<b>№:</b> <code>{_safe(getattr(lead, 'lead_number', None))}</code>",
        f"<b>Тип заявки:</b> {_choice_label(lead, 'get_lead_type_display', 'lead_type')}",
        f"<b>Статус:</b> {_choice_label(lead, 'get_status_display', 'status')}",
        f"<b>Джерело:</b> {_safe(getattr(lead, 'source', None))}",
        f"<b>Створено:</b> {_fmt_datetime(getattr(lead, 'created_at', None))}",
    ]

    deadline_note = getattr(lead, "deadline_note", "")
    if deadline_note:
        rows.append(f"<b>Дедлайн:</b> {_safe(deadline_note)}")

    return rows


def _lead_contact_rows(lead) -> list[str]:
    rows = [
        f"<b>Ім'я:</b> {_safe(getattr(lead, 'name', None))}",
        f"<b>Телефон:</b> {_safe(getattr(lead, 'phone', None))}",
        f"<b>Канал зв'язку:</b> {_choice_label(lead, 'get_contact_channel_display', 'contact_channel')}",
        f"<b>Місто:</b> {_safe(getattr(lead, 'city', None))}",
        f"<b>Відділення НП:</b> {_safe(getattr(lead, 'np_branch', None))}",
    ]

    contact_handle = getattr(lead, "contact_handle", "")
    if contact_handle:
        rows.append(f"<b>Контакт:</b> {_safe(contact_handle)}")

    return rows


def _lead_request_rows(lead) -> list[str]:
    rows = []

    task_description = getattr(lead, "task_description", "")
    if task_description:
        rows.append(f"<b>Опис задачі:</b> {_safe_truncated(task_description, limit=500)}")

    folder_link = getattr(lead, "folder_link", "")
    if folder_link:
        rows.append(f'<b>Папка з файлами:</b> <a href="{escape(folder_link)}">відкрити</a>')

    manager_note = getattr(lead, "manager_note", "")
    if manager_note:
        rows.append(f"<b>Нотатка менеджера:</b> {_safe_truncated(manager_note)}")

    return rows


def _build_lead_message(lead) -> str:
    sections = [
        ("Заявка", _lead_rows(lead)),
        ("Контактні дані", _lead_contact_rows(lead)),
        ("Деталі", _lead_request_rows(lead)),
    ]
    return _compose_message(
        "🟡 <b>DTF: нова заявка</b>",
        sections=sections,
        links=_lead_links(lead),
    )


def notify_new_lead(lead):
    try:
        _send_admin_message(_build_lead_message(lead))
    except Exception as exc:
        logger.warning("DTF Telegram notify_new_lead failed: %s", exc, exc_info=True)


def notify_new_order(order):
    try:
        message = _build_order_message(
            order,
            title="DTF: нове замовлення",
            icon="🟢",
            event_rows=[
                f"<b>Номер:</b> <code>{_safe(getattr(order, 'order_number', None))}</code>",
                f"<b>Режим:</b> {_choice_label(order, 'get_order_type_display', 'order_type')}",
            ],
        )
        _send_admin_message(message)
    except Exception as exc:
        logger.warning("DTF Telegram notify_new_order failed: %s", exc, exc_info=True)


def notify_need_fix(order, reason: str):
    try:
        message = _build_order_message(
            order,
            title="DTF: потрібні правки",
            icon="🟠",
            event_rows=[f"<b>Причина правок:</b> {_safe_truncated(reason, limit=500)}"],
        )
        _send_admin_message(message)
    except Exception as exc:
        logger.warning("DTF Telegram notify_need_fix failed: %s", exc, exc_info=True)


def notify_awaiting_payment(order):
    try:
        message = _build_order_message(
            order,
            title="DTF: очікує оплату",
            icon="🟣",
            event_rows=[
                f"<b>Сума до оплати:</b> {_fmt_money(getattr(order, 'payment_amount', None) or getattr(order, 'price_total', None))}"
            ],
        )
        _send_admin_message(message)
    except Exception as exc:
        logger.warning("DTF Telegram notify_awaiting_payment failed: %s", exc, exc_info=True)


def notify_paid(order):
    try:
        message = _build_order_message(
            order,
            title="DTF: оплату підтверджено",
            icon="✅",
            event_rows=[
                f"<b>Підтверджено:</b> {_fmt_datetime(getattr(order, 'payment_updated_at', None) or timezone.now())}",
                f"<b>Оплачено:</b> {_fmt_money(getattr(order, 'payment_amount', None) or getattr(order, 'price_total', None))}",
            ],
        )
        _send_admin_message(message)
    except Exception as exc:
        logger.warning("DTF Telegram notify_paid failed: %s", exc, exc_info=True)


def notify_shipped(order):
    try:
        tracking_number = getattr(order, "tracking_number", "")
        message = _build_order_message(
            order,
            title="DTF: замовлення відправлено",
            icon="📦",
            event_rows=[
                f"<b>ТТН:</b> <code>{_safe(tracking_number)}</code>" if tracking_number else "<b>ТТН:</b> —"
            ],
        )
        _send_admin_message(message)
    except Exception as exc:
        logger.warning("DTF Telegram notify_shipped failed: %s", exc, exc_info=True)
