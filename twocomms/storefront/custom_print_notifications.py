import logging
import mimetypes
import os
from html import escape
from pathlib import Path

from orders.telegram_notifications import TelegramNotifier
from storefront.custom_print_config import (
    FABRIC_LABELS,
    FIT_LABELS,
    PRODUCT_LABELS,
    SERVICE_LABELS,
    TELEGRAM_MANAGER_URL,
    TRIAGE_LABELS,
    ZONE_LABELS,
)


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
    if lead is None:
        return None
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
    if getattr(lead, "fit", ""):
        parts.insert(8, f"• <b>Посадка:</b> {escape(FIT_LABELS.get(lead.fit, lead.fit))}")
    if getattr(lead, "fabric", ""):
        parts.insert(9, f"• <b>Тканина:</b> {escape(FABRIC_LABELS.get(lead.fabric, lead.fabric))}")
    if getattr(lead, "color_choice", ""):
        parts.insert(10, f"• <b>Колір:</b> {escape(lead.color_choice)}")
    if getattr(lead, "file_triage_status", ""):
        parts.insert(11, f"• <b>File triage:</b> {escape(lead.file_triage_status)}")
    return "\n".join(parts)


def _snapshot_mode_label(snapshot: dict) -> str:
    return "Для команди / бренду" if (snapshot.get("mode") == "brand") else "Для себе"


def _snapshot_product_label(snapshot: dict) -> str:
    product = snapshot.get("product") or {}
    product_type = product.get("type") or "hoodie"
    base = PRODUCT_LABELS.get(product_type, product_type)
    details = []
    fit = (product.get("fit") or "").strip()
    fabric = (product.get("fabric") or "").strip()
    color = (product.get("color") or "").strip()
    if fit:
        details.append(FIT_LABELS.get(fit, fit))
    if fabric:
        details.append(FABRIC_LABELS.get(fabric, fabric))
    if color:
        details.append(color)
    if not details:
        return base
    return f"{base} · {' / '.join(details)}"


def _snapshot_placements_text(snapshot: dict) -> str:
    print_payload = snapshot.get("print") or {}
    zones = [ZONE_LABELS.get(zone, zone) for zone in (print_payload.get("zones") or [])]
    add_ons = print_payload.get("add_ons") or []
    parts = []
    if zones:
        parts.append(", ".join(zones))
    placement_note = (print_payload.get("placement_note") or "").strip()
    if placement_note:
        parts.append(f"Примітка: {placement_note}")
    if add_ons:
        parts.append(f"Add-ons: {', '.join(add_ons)}")
    return " | ".join(parts) or "—"


def _snapshot_pricing_text(snapshot: dict) -> str:
    pricing = snapshot.get("pricing") or {}
    parts = []
    if pricing.get("base_price") not in (None, ""):
        parts.append(f"база {pricing['base_price']} грн")
    if pricing.get("design_price") not in (None, "", 0):
        parts.append(f"дизайн +{pricing['design_price']} грн")
    if pricing.get("discount_percent") not in (None, "", 0):
        parts.append(f"знижка {pricing['discount_percent']}%")
    if pricing.get("estimate_required"):
        parts.append("потрібен менеджерський прорахунок")
    elif pricing.get("final_total") not in (None, ""):
        parts.append(f"разом {pricing['final_total']} грн")
    return ", ".join(parts) or "Уточнюється менеджером"


def _snapshot_contact_text(snapshot: dict) -> tuple[str, str]:
    contact = snapshot.get("contact") or {}
    channel = (contact.get("channel") or "").strip()
    channel_map = {
        "telegram": "Telegram",
        "whatsapp": "WhatsApp",
        "phone": "Телефон",
    }
    return channel_map.get(channel, "Не вказано"), (contact.get("value") or "").strip() or "—"


def _build_safe_exit_message(snapshot: dict, lead=None) -> str:
    artwork = snapshot.get("artwork") or {}
    order = snapshot.get("order") or {}
    ui = snapshot.get("ui") or {}
    channel_label, contact_value = _snapshot_contact_text(snapshot)

    parts = [
        "<b>Кастомний принт: safe exit</b>",
        f"• <b>Режим:</b> {escape(_snapshot_mode_label(snapshot))}",
        f"• <b>Виріб:</b> {escape(_snapshot_product_label(snapshot))}",
        f"• <b>Послуга:</b> {escape(SERVICE_LABELS.get(artwork.get('service_kind'), artwork.get('service_kind') or '—'))}",
        f"• <b>File triage:</b> {escape(TRIAGE_LABELS.get(artwork.get('triage_status'), artwork.get('triage_status') or 'needs-review'))}",
        f"• <b>Зони:</b> {escape(_snapshot_placements_text(snapshot))}",
        f"• <b>Кількість:</b> {escape(str(order.get('quantity') or '—'))}",
        f"• <b>Розміри:</b> {escape(order.get('sizes_note') or '—')}",
        f"• <b>Поточний крок:</b> {escape(ui.get('current_step') or '—')}",
        f"• <b>Прорахунок:</b> {escape(_snapshot_pricing_text(snapshot))}",
        f"• <b>Канал:</b> {escape(channel_label)}",
        f"• <b>Контакт:</b> {escape(contact_value)}",
    ]
    contact_name = ((snapshot.get("contact") or {}).get("name") or "").strip()
    if contact_name:
        parts.append(f"• <b>Ім'я:</b> {escape(contact_name)}")
    if (order.get("gift")):
        parts.append("• <b>Подарунок:</b> так")
    if lead is not None:
        parts.insert(1, f"• <b>Номер:</b> <code>{escape(lead.lead_number)}</code>")
        parts.append("")
        parts.append(f'• <a href="{_build_admin_panel_link(lead)}">Відкрити в панелі</a>')
    else:
        parts.append("")
        parts.append(f'• <a href="{TELEGRAM_MANAGER_URL}">Відкрити Telegram</a>')
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


def notify_custom_print_safe_exit(*, snapshot: dict, lead=None) -> bool:
    try:
        notifier = _build_notifier()
        if not notifier.is_configured():
            logger.warning("Custom print safe-exit notifier is not configured.")
            return False

        return notifier.send_admin_message(
            _build_safe_exit_message(snapshot, lead=lead),
            parse_mode="HTML",
            reply_markup=_reply_markup(lead),
        )
    except Exception as exc:
        logger.warning("Custom print safe-exit notify failed: %s", exc, exc_info=True)
        return False
