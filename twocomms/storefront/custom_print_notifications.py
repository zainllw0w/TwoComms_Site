import logging
import os
from html import escape

from orders.telegram_notifications import TelegramNotifier


logger = logging.getLogger(__name__)

MAIN_PUBLIC_BASE_URL = "https://twocomms.shop"


def _first_env(*keys: str) -> str:
    for key in keys:
        value = (os.environ.get(key) or "").strip()
        if value:
            return value
    return ""


def _build_notifier() -> TelegramNotifier:
    return TelegramNotifier(
        bot_token=_first_env("DTF_TG_BOT_TOKEN"),
        chat_id=_first_env("DTF_TG_CHAT_ID", "TELEGRAM_CHAT_ID"),
        admin_id=_first_env("DTF_TG_ADMIN_ID", "TELEGRAM_ADMIN_ID"),
        async_enabled=False,
    )


def _placements_text(lead) -> str:
    mapping = {
        "front": "Спереду",
        "back": "На спині",
        "sleeve": "На рукаві",
        "custom": "Інший варіант",
    }
    items = [mapping.get(item, str(item)) for item in (lead.placements or [])]
    if lead.placement_note:
        items.append(f"Примітка: {lead.placement_note}")
    return ", ".join(items) or "—"


def _admin_link(lead) -> str:
    return f"{MAIN_PUBLIC_BASE_URL}/admin/storefront/customprintlead/{lead.pk}/change/"


def _build_message(lead) -> str:
    attachment_count = lead.attachments.count() if getattr(lead, "pk", None) else 0
    parts = [
        "🟠 <b>Кастомний принт: нова заявка</b>",
        f"• <b>Номер:</b> <code>{escape(lead.lead_number)}</code>",
        f"• <b>Послуга:</b> {escape(lead.get_service_kind_display())}",
        f"• <b>Виріб:</b> {escape(lead.get_product_type_display())}",
        f"• <b>Розміщення:</b> {escape(_placements_text(lead))}",
        f"• <b>Кількість:</b> {lead.quantity}",
        f"• <b>Розміри:</b> {escape(lead.sizes_note or '—')}",
        f"• <b>Тип клієнта:</b> {escape(lead.get_client_kind_display())}",
        f"• <b>Ім'я:</b> {escape(lead.name)}",
        f"• <b>Канал зв'язку:</b> {escape(lead.get_contact_channel_display())}",
        f"• <b>Контакт:</b> {escape(lead.contact_value)}",
        f"• <b>Файлів:</b> {attachment_count}",
        f"• <b>Бриф:</b> {escape((lead.brief or '—')[:1200])}",
        "",
        f'• <a href="{_admin_link(lead)}">Відкрити в адмінці</a>',
    ]
    if lead.brand_name:
        parts.insert(9, f"• <b>Бренд / команда:</b> {escape(lead.brand_name)}")
    return "\n".join(parts)


def notify_new_custom_print_lead(lead) -> bool:
    try:
        notifier = _build_notifier()
        if not notifier.is_configured():
            logger.warning("Custom print Telegram notifier is not configured.")
            return False
        return notifier.send_admin_message(_build_message(lead), parse_mode="HTML")
    except Exception as exc:
        logger.warning("Custom print Telegram notify failed: %s", exc, exc_info=True)
        return False
