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
    build_placement_specs,
)


logger = logging.getLogger(__name__)

MAIN_PUBLIC_BASE_URL = "https://twocomms.shop"
ADDON_LABELS = {
    "lacing": "Люверси зі шнурками",
    "grommets": "Люверси зі шнурками",
    "inside_label": "Люверси зі шнурками",
    "hem_tag": "Люверси зі шнурками",
    "fleece": "З флісом",
    "no_fleece": "Без флісу",
    "ribbed_neck": "Щільна горловина (Рібана)",
    "twill_tape": "Кіперна стрічка",
}


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
    items = [_format_placement_descriptor(spec, include_text=True) for spec in _placement_specs_for_lead(lead)]
    if lead.placement_note:
        items.append(f"Примітка: {lead.placement_note}")
    return " | ".join(filter(None, items)) or "—"


def _placement_specs_for_lead(lead) -> list[dict]:
    placement_specs = getattr(lead, "placement_specs_json", None) or []
    if placement_specs:
        return [spec for spec in placement_specs if isinstance(spec, dict)]
    return [
        {
            "zone": zone,
            "placement_key": zone,
            "label": ZONE_LABELS.get(zone, zone),
        }
        for zone in (lead.placements or [])
    ]


def _format_placement_descriptor(spec: dict, *, include_text: bool) -> str:
    placement_key = spec.get("placement_key") or spec.get("zone")
    label = spec.get("label") or ZONE_LABELS.get(placement_key or spec.get("zone"), spec.get("zone") or "—")
    parts = [label]
    if spec.get("size_preset"):
        parts.append(str(spec["size_preset"]).upper())
    elif spec.get("zone") == "sleeve":
        parts.append("текст" if spec.get("mode") == "full_text" else "A6")
    if include_text and spec.get("text"):
        parts.append(str(spec["text"]))
    return " · ".join(part for part in parts if part)


def _placement_descriptor_by_key(lead) -> dict[str, str]:
    mapping = {}
    for spec in _placement_specs_for_lead(lead):
        placement_key = spec.get("placement_key") or spec.get("zone")
        if not placement_key:
            continue
        mapping[placement_key] = _format_placement_descriptor(spec, include_text=False)
    return mapping


def _build_attachment_caption(lead, placement_key: str, index: int, total: int) -> str:
    descriptor = _placement_descriptor_by_key(lead).get(placement_key) or ZONE_LABELS.get(placement_key, placement_key or "Файл")
    return f"{index}/{total} · {descriptor}"


def _collect_attachment_payloads(lead) -> list[dict]:
    placement_index = {
        (spec.get("placement_key") or spec.get("zone")): idx
        for idx, spec in enumerate(_placement_specs_for_lead(lead))
    }
    attachments = list(getattr(lead.attachments, "all", lambda: [])())
    ordered_attachments = sorted(
        attachments,
        key=lambda attachment: (
            placement_index.get(getattr(attachment, "placement_zone", ""), 999),
            getattr(attachment, "sort_order", 0),
        ),
    )
    existing = []
    for attachment in ordered_attachments:
        file_path = getattr(getattr(attachment, "file", None), "path", "")
        if not file_path or not os.path.exists(file_path):
            continue
        existing.append(attachment)

    payloads = []
    total = len(existing)
    for index, attachment in enumerate(existing, start=1):
        file_path = getattr(getattr(attachment, "file", None), "path", "")
        payloads.append(
            {
                "path": file_path,
                "is_image": _is_image_attachment(attachment),
                "caption": _build_attachment_caption(lead, getattr(attachment, "placement_zone", ""), index, total),
            }
        )
    return payloads


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


def _build_moderation_action_url(lead, action: str) -> str:
    """Build absolute signed URL for telegram moderation action (approve/reject)."""
    from storefront.views.static_pages import _custom_print_action_signature
    lead.ensure_moderation_token()
    token = lead.moderation_token
    signature = _custom_print_action_signature(lead.pk, action, token)
    return f"{MAIN_PUBLIC_BASE_URL}/custom-print/moderation/{lead.pk}/{action}/?token={token}&sig={signature}"


def _build_contact_client_url(lead) -> str:
    """Build the tg.me/wa.me/tel: URL for the customer's preferred channel."""
    channel = (getattr(lead, "contact_channel", "") or "").strip().lower()
    raw_value = (getattr(lead, "contact_value", "") or "").strip()
    cleaned = raw_value.lstrip("@").replace(" ", "")
    if channel == "telegram":
        handle = cleaned.lstrip("@")
        if handle.startswith("http"):
            return handle
        return f"https://t.me/{handle}" if handle else TELEGRAM_MANAGER_URL
    if channel == "whatsapp":
        digits = "".join(ch for ch in raw_value if ch.isdigit())
        return f"https://wa.me/{digits}" if digits else TELEGRAM_MANAGER_URL
    if channel == "phone":
        digits = "".join(ch for ch in raw_value if ch.isdigit() or ch == "+")
        return f"tel:{digits}" if digits else TELEGRAM_MANAGER_URL
    return TELEGRAM_MANAGER_URL


def _moderation_reply_markup(lead):
    """Approve / Reject / Contact client inline keyboard for the manager's chat."""
    if lead is None:
        return None
    approve_url = _build_moderation_action_url(lead, "approve")
    reject_url = _build_moderation_action_url(lead, "reject")
    contact_url = _build_contact_client_url(lead)
    channel = (getattr(lead, "contact_channel", "") or "").strip().lower()
    channel_emoji = {"telegram": "✈️", "whatsapp": "💬", "phone": "📞"}.get(channel, "📨")
    contact_label = f"{channel_emoji} Звʼязатися з клієнтом"
    return {
        "inline_keyboard": [
            [
                {"text": "✅ Погодити", "url": approve_url},
                {"text": "❌ Відхилити", "url": reject_url},
            ],
            [
                {"text": contact_label, "url": contact_url},
            ],
            [
                {"text": "Відкрити в панелі", "url": _build_admin_panel_link(lead)},
            ],
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
    product_parts = [escape(lead.get_product_type_display())]
    if getattr(lead, "fit", ""):
        product_parts.append(escape(FIT_LABELS.get(lead.fit, lead.fit)))
    if getattr(lead, "fabric", ""):
        product_parts.append(escape(FABRIC_LABELS.get(lead.fabric, lead.fabric)))
    if getattr(lead, "color_choice", ""):
        product_parts.append(escape(lead.color_choice))

    parts = [
        "<b>Кастомний принт: нова заявка</b>",
        "",
        "<b>Заявка</b>",
        f"• <b>Номер:</b> <code>{escape(lead.lead_number)}</code>",
        f"• <b>Сценарій:</b> {escape(lead.get_client_kind_display())}",
        f"• <b>Послуга:</b> {escape(lead.get_service_kind_display())}",
    ]
    if getattr(lead, "business_kind", ""):
        parts.append(f"• <b>B2B:</b> {escape(lead.get_business_kind_display())}")
    if getattr(lead, "brand_name", ""):
        parts.append(f"• <b>Бренд / команда:</b> {escape(lead.brand_name)}")

    parts.extend(
        [
            "",
            "<b>Виріб</b>",
            f"• <b>Конфігурація:</b> {' / '.join(product_parts)}",
        ]
    )
    if getattr(lead, "add_ons", None):
        mapped_addons = [ADDON_LABELS.get(a, a) for a in lead.add_ons]
        parts.append(f"• <b>Доповнення:</b> {escape(', '.join(mapped_addons))}")

    if getattr(lead, "garment_note", ""):
        parts.append(f"• <b>Опис виробу:</b> {escape(lead.garment_note)}")
    if getattr(lead, "file_triage_status", ""):
        parts.append(f"• <b>File triage:</b> {escape(lead.file_triage_status)}")

    placement_lines = [f"• {escape(_format_placement_descriptor(spec, include_text=True))}" for spec in _placement_specs_for_lead(lead)]
    parts.extend(
        [
            "",
            "<b>Макет / зони</b>",
            *(placement_lines if placement_lines else ["• —"]),
            f"• <b>Файлів:</b> {attachment_count}",
        ]
    )
    if getattr(lead, "placement_note", ""):
        parts.append(f"• <b>Примітка:</b> {escape(lead.placement_note)}")

    parts.extend(
        [
            "",
            "<b>Кількість / ціна</b>",
            f"• <b>Кількість:</b> {lead.quantity}",
            f"• <b>Режим розмірів:</b> {escape(getattr(lead, 'get_size_mode_display', lambda: '—')() or '—')}",
            f"• <b>Розміри:</b> {escape(lead.sizes_note or '—')}",
            f"• <b>Прорахунок:</b> {escape(_pricing_text(lead))}",
            "",
            "<b>Контакт</b>",
            f"• <b>Ім'я:</b> {escape(lead.name)}",
            f"• <b>Канал:</b> {escape(lead.get_contact_channel_display())}",
            f"• <b>Контакт:</b> {escape(lead.contact_value)}",
            "",
            "<b>Бриф / завдання</b>",
            escape((lead.brief or "—")[:1200]),
            "",
            f'• <a href="{_build_admin_panel_link(lead)}">Відкрити в панелі</a>',
        ]
    )
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
    add_ons = print_payload.get("add_ons") or []
    parts = []
    placement_specs = build_placement_specs(snapshot)
    if placement_specs:
        items = []
        for spec in placement_specs:
            label = spec.get("label") or ZONE_LABELS.get(spec.get("placement_key") or spec.get("zone"), spec.get("zone") or "—")
            if spec.get("size_preset"):
                label = f"{label} · {spec['size_preset']}"
            elif spec.get("zone") == "sleeve":
                label = f"{label} · {'текст' if spec.get('mode') == 'full_text' else 'A6'}"
            if spec.get("text"):
                label = f"{label} ({spec['text']})"
            items.append(label)
        parts.append(", ".join(items))
    else:
        zones = [ZONE_LABELS.get(zone, zone) for zone in (print_payload.get("zones") or [])]
        if zones:
            parts.append(", ".join(zones))
    placement_note = (print_payload.get("placement_note") or "").strip()
    if placement_note:
        parts.append(f"Примітка: {placement_note}")

    mapped_addons = [ADDON_LABELS.get(a, a) for a in add_ons]
    if mapped_addons:
        parts.append(f"Add-ons: {', '.join(mapped_addons)}")
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

        success = notifier.send_admin_message(
            _build_message(lead),
            parse_mode="HTML",
            reply_markup=_reply_markup(lead),
        )
        payloads = _collect_attachment_payloads(lead)
        image_payloads = [payload for payload in payloads if payload["is_image"]]
        document_payloads = [payload for payload in payloads if not payload["is_image"]]

        if len(image_payloads) > 1:
            success = notifier.send_admin_media_group(
                [payload["path"] for payload in image_payloads],
                captions=[payload["caption"] for payload in image_payloads],
                parse_mode="HTML",
            ) or success
        elif len(image_payloads) == 1:
            success = notifier.send_admin_photo(
                image_payloads[0]["path"],
                caption=image_payloads[0]["caption"],
                parse_mode="HTML",
            ) or success

        for payload in document_payloads:
            success = notifier.send_admin_document(
                payload["path"],
                caption=payload["caption"],
                filename=Path(payload["path"]).name,
                parse_mode="HTML",
            ) or success

        return success
    except Exception as exc:
        logger.warning("Custom print Telegram notify failed: %s", exc, exc_info=True)
        return False


def _build_moderation_request_message(lead) -> str:
    base = _build_message(lead)
    header = (
        "<b>🛒 Кастомний кошик: потрібна перевірка</b>\n"
        f"• <b>Ціна зі знижкою клієнта:</b> {escape(str(lead.final_price_value))} грн\n"
        "• Натисніть «Погодити», щоб клієнт міг оплатити, або «Відхилити».\n"
        "• Для уточнення — «Звʼязатися з клієнтом».\n\n"
    )
    return header + base


def notify_custom_print_moderation_request(lead) -> bool:
    """Send notification to manager when user submits the custom cart for review.

    Includes full lead details, attached images/documents, and approve/reject/contact
    inline buttons.
    """
    try:
        notifier = _build_notifier()
        if not notifier.is_configured():
            logger.warning("Custom print moderation notifier is not configured.")
            return False

        lead.ensure_moderation_token()
        markup = _moderation_reply_markup(lead)
        success = notifier.send_admin_message(
            _build_moderation_request_message(lead),
            parse_mode="HTML",
            reply_markup=markup,
        )
        payloads = _collect_attachment_payloads(lead)
        image_payloads = [payload for payload in payloads if payload["is_image"]]
        document_payloads = [payload for payload in payloads if not payload["is_image"]]

        if len(image_payloads) > 1:
            success = notifier.send_admin_media_group(
                [payload["path"] for payload in image_payloads],
                captions=[payload["caption"] for payload in image_payloads],
                parse_mode="HTML",
            ) or success
        elif len(image_payloads) == 1:
            success = notifier.send_admin_photo(
                image_payloads[0]["path"],
                caption=image_payloads[0]["caption"],
                parse_mode="HTML",
            ) or success

        for payload in document_payloads:
            success = notifier.send_admin_document(
                payload["path"],
                caption=payload["caption"],
                filename=Path(payload["path"]).name,
                parse_mode="HTML",
            ) or success

        return success
    except Exception as exc:
        logger.warning("Custom print moderation notify failed: %s", exc, exc_info=True)
        return False


def notify_custom_print_moderation_result(lead) -> bool:
    """Notify the customer (best-effort) about the outcome of moderation.

    Sends a concise message to the manager chat so the manager can forward or
    contact the customer. If there's a structured customer telegram handle we
    could extend later to send DM.
    """
    try:
        notifier = _build_notifier()
        if not notifier.is_configured():
            return False
        status = getattr(lead, "moderation_status", "")
        if status == "approved":
            emoji = "✅"
            title = "Схвалено менеджером"
        elif status == "rejected":
            emoji = "❌"
            title = "Відхилено менеджером"
        else:
            return False
        price_line = ""
        try:
            if getattr(lead, "approved_price", None):
                price_line = f"\n<b>Фінальна ціна:</b> {lead.approved_price} грн"
        except Exception:
            pass
        note_line = ""
        note = (getattr(lead, "manager_note", "") or "").strip()
        if note:
            note_line = f"\n<b>Коментар менеджера:</b> {note}"
        message = (
            f"{emoji} <b>Заявка {getattr(lead, 'lead_number', lead.pk)} — {title}</b>"
            f"{price_line}"
            f"{note_line}"
        )
        return notifier.send_admin_message(message, parse_mode="HTML")
    except Exception as exc:
        logger.warning("Custom print moderation-result notify failed: %s", exc, exc_info=True)
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
