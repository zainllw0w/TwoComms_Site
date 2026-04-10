import logging
import mimetypes
import os
from html import escape
from pathlib import Path

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
    placement_specs = getattr(lead, "placement_specs_json", None) or []
    items = []
    if placement_specs:
        for spec in placement_specs:
            zone = spec.get("zone")
            label = spec.get("label") or mapping.get(zone, str(zone))
            suffix = " (доп.)" if not spec.get("is_free", False) else ""
            items.append(f"{label}{suffix}")
    else:
        items = [mapping.get(item, str(item)) for item in (lead.placements or [])]
    if lead.placement_note:
        items.append(f"Примітка: {lead.placement_note}")
    return ", ".join(items) or "—"


def _build_admin_panel_link(lead) -> str:
    return f"{MAIN_PUBLIC_BASE_URL}/admin-panel/?section=custom_print_orders&lead={lead.pk}"


def _pricing_text(lead) -> str:
    snapshot = getattr(lead, "pricing_snapshot_json", None) or {}
    if not snapshot:
        return "Уточнюється менеджером"

    final_total = snapshot.get("final_total")
    estimate_required = snapshot.get("estimate_required")
    design_price = snapshot.get("design_price")
    discount_percent = snapshot.get("discount_percent")

    parts = []
    if snapshot.get("base_price") not in (None, ""):
        parts.append(f"база {snapshot['base_price']} грн")
    if design_price:
        parts.append(f"дизайнер +{design_price} грн")
    if discount_percent:
        parts.append(f"знижка {discount_percent}%")
    if estimate_required:
        parts.append("потрібен точний прорахунок")
    elif final_total not in (None, ""):
        parts.append(f"разом {final_total} грн")
    return ", ".join(parts) or "Уточнюється менеджером"


def _reply_markup(lead):
    return {
        "inline_keyboard": [
            [
                {
                    "text": "Відкрити в панелі",
                    "url": _build_admin_panel_link(lead),
                }
            ]
        ]
    }


def _is_image_attachment(attachment) -> bool:
    file_name = getattr(getattr(attachment, "file", None), "name", "")
    mime_type, _ = mimetypes.guess_type(file_name)
    if mime_type:
        return mime_type.startswith("image/")
    return Path(file_name).suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def _build_message(lead) -> str:
    attachment_count = lead.attachments.count() if getattr(lead, "pk", None) else 0
    business_kind = getattr(lead, "business_kind", "")
    parts = [
        "<b>Кастомний принт: нова заявка</b>",
        f"• <b>Номер:</b> <code>{escape(lead.lead_number)}</code>",
        f"• <b>Сценарій:</b> {escape(lead.get_client_kind_display())}",
        f"• <b>Послуга:</b> {escape(lead.get_service_kind_display())}",
        f"• <b>Виріб:</b> {escape(lead.get_product_type_display())}",
        f"• <b>Розміщення:</b> {escape(_placements_text(lead))}",
        f"• <b>Кількість:</b> {lead.quantity}",
        f"• <b>Режим розмірів:</b> {escape(getattr(lead, 'get_size_mode_display', lambda: '—')() or '—')}",
        f"• <b>Розміри:</b> {escape(lead.sizes_note or '—')}",
        f"• <b>Прорахунок:</b> {escape(_pricing_text(lead))}",
        f"• <b>Ім'я:</b> {escape(lead.name)}",
        f"• <b>Канал зв'язку:</b> {escape(lead.get_contact_channel_display())}",
        f"• <b>Контакт:</b> {escape(lead.contact_value)}",
        f"• <b>Файлів:</b> {attachment_count}",
        f"• <b>Бриф:</b> {escape((lead.brief or '—')[:1200])}",
        "• <b>Доставка / оплата:</b> Нова Пошта, старт після повної оплати та погодження мокапа.",
        "",
        f'• <a href="{_build_admin_panel_link(lead)}">Відкрити в панелі</a>',
    ]
    if business_kind:
        parts.insert(3, f"• <b>B2B:</b> {escape(lead.get_business_kind_display())}")
    if lead.brand_name:
        parts.insert(10, f"• <b>Бренд / команда:</b> {escape(lead.brand_name)}")
    if getattr(lead, "garment_note", ""):
        parts.insert(8, f"• <b>Опис виробу:</b> {escape(lead.garment_note)}")
    return "\n".join(parts)


def notify_new_custom_print_lead(lead) -> bool:
    try:
        notifier = _build_notifier()
        if not notifier.is_configured():
            logger.warning("Custom print Telegram notifier is not configured.")
            return False

        image_paths = []
        document_paths = []
        for attachment in lead.attachments.all():
            file_path = getattr(getattr(attachment, "file", None), "path", "")
            if not file_path or not os.path.exists(file_path):
                continue
            if _is_image_attachment(attachment):
                image_paths.append(file_path)
            else:
                document_paths.append(file_path)

        if len(image_paths) > 1:
            notifier.send_admin_media_group(image_paths)
        elif len(image_paths) == 1:
            notifier.send_admin_photo(image_paths[0], caption="")

        for file_path in document_paths:
            notifier.send_admin_document(file_path, caption="Файл із заявки", filename=Path(file_path).name)

        return notifier.send_admin_message(
            _build_message(lead),
            parse_mode="HTML",
            reply_markup=_reply_markup(lead),
        )
    except Exception as exc:
        logger.warning("Custom print Telegram notify failed: %s", exc, exc_info=True)
        return False
