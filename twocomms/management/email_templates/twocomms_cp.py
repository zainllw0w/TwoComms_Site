from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import urljoin

from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import escape

CpMode = Literal["LIGHT", "VISUAL"]
CpSegmentMode = Literal["NEUTRAL", "EDGY"]
CpSubjectPreset = Literal["PRESET_1", "PRESET_2", "PRESET_3", "CUSTOM"]


@dataclass(frozen=True)
class CpGalleryItem:
    title: str
    img_url: str
    link_url: str


def _site_base_url() -> str:
    base = (getattr(settings, "SITE_BASE_URL", "") or "").strip() or "https://twocomms.shop"
    if not base.endswith("/"):
        base += "/"
    return base


def _abs_url(path_or_url: str) -> str:
    if not path_or_url:
        return _site_base_url()
    if path_or_url.startswith(("http://", "https://")):
        return path_or_url
    return urljoin(_site_base_url(), path_or_url.lstrip("/"))


def _fmt_uah(value: int | None) -> str:
    if value is None:
        return "—"
    try:
        return f"{int(value):,}".replace(",", " ")
    except Exception:
        return str(value)


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    s = str(value).strip()
    if not s:
        return None
    try:
        return int(float(s.replace(" ", "").replace(",", ".")))
    except Exception:
        return None


def _normalize_mode(value: Any) -> CpMode:
    v = (str(value or "").strip().upper() or "VISUAL")
    return "LIGHT" if v == "LIGHT" else "VISUAL"


def _normalize_segment(value: Any) -> CpSegmentMode:
    v = (str(value or "").strip().upper() or "NEUTRAL")
    return "EDGY" if v == "EDGY" else "NEUTRAL"


def _normalize_subject_preset(value: Any) -> CpSubjectPreset:
    v = (str(value or "").strip().upper() or "PRESET_1")
    if v in {"PRESET_1", "PRESET_2", "PRESET_3", "CUSTOM"}:
        return v  # type: ignore[return-value]
    return "PRESET_1"


def _build_subject(*, preset: CpSubjectPreset, shop_name: str, tee_entry: int | None, hoodie_entry: int | None, custom: str) -> str:
    if preset == "CUSTOM":
        subject = (custom or "").strip()
        return subject[:255] if subject else "Комерційна пропозиція бренду TwoComms"

    if preset == "PRESET_1":
        name = (shop_name or "").strip()
        if name:
            return f"TwoComms: Тест-ростовка 14 днів для {name} (майже без ризику)"[:255]
        return "TwoComms: Тест-ростовка 14 днів (майже без ризику)"[:255]

    if preset == "PRESET_2":
        base = "Опт від 8 шт / Дропшип без складу — худі та футболки"
        entry_val = tee_entry or hoodie_entry
        if entry_val is None:
            return base[:255]
        return f"{base} (Вхід від {_fmt_uah(entry_val)} грн)"[:255]

    # PRESET_3
    return "📦 Тест-драйв 14 днів: street & military колекція TwoComms"[:255]


def _build_preheader(*, tee_entry: int | None, hoodie_entry: int | None) -> str:
    if tee_entry and hoodie_entry:
        return f"Вхідні ціни від {_fmt_uah(tee_entry)}/{_fmt_uah(hoodie_entry)} грн. Тест-ростовка S–XL на 14 днів. Опт або дроп."
    if tee_entry or hoodie_entry:
        entry_val = tee_entry or hoodie_entry
        return f"Вхідні ціни від {_fmt_uah(entry_val)} грн. Тест-ростовка S–XL на 14 днів. Опт або дроп."
    return "Тест-ростовка S–XL на 14 днів. Опт або дроп. Сплачуєте лише доставку."


def _gallery_items(segment_mode: CpSegmentMode) -> list[CpGalleryItem]:
    # Placeholder gallery (3 items). Replace img/link later with the final commercial pack.
    placeholder_img = _abs_url("/static/img/placeholder.jpg")
    catalog = _abs_url("/catalog/")

    if segment_mode == "EDGY":
        return [
            CpGalleryItem(title="Street hit: чорний принт", img_url=placeholder_img, link_url=catalog),
            CpGalleryItem(title="Military vibe: базове худі", img_url=placeholder_img, link_url=catalog),
            CpGalleryItem(title="Drop: лімітований дизайн", img_url=placeholder_img, link_url=catalog),
        ]

    return [
        CpGalleryItem(title="Бестселер: футболка (база)", img_url=placeholder_img, link_url=catalog),
        CpGalleryItem(title="Бестселер: худі (база)", img_url=placeholder_img, link_url=catalog),
        CpGalleryItem(title="Хіт сезону: street колекція", img_url=placeholder_img, link_url=catalog),
    ]


def _build_light_text(context: dict[str, Any]) -> str:
    shop_name = (context.get("shop_name") or "").strip()
    show_manager = bool(context.get("show_manager"))

    greeting = f"Вітаю, {shop_name}!" if shop_name else "Вітаю!"

    manager_name = (context.get("manager_name") or "").strip()
    who_line = f"Це {manager_name} з TwoComms. Street & Military одяг." if (show_manager and manager_name) else "Це команда TwoComms. Street & Military одяг."

    tee_entry = context.get("tee_entry")
    tee_retail = context.get("tee_retail_example")
    tee_profit = context.get("tee_profit")
    hoodie_entry = context.get("hoodie_entry")
    hoodie_retail = context.get("hoodie_retail_example")
    hoodie_profit = context.get("hoodie_profit")

    unit_lines: list[str] = []
    if tee_entry and tee_retail and tee_profit is not None:
        unit_lines.append(
            f"Вхід футболка: {_fmt_uah(tee_entry)} грн → роздріб (приклад): {_fmt_uah(tee_retail)} грн → різниця: {_fmt_uah(tee_profit)} грн*"
        )
    if hoodie_entry and hoodie_retail and hoodie_profit is not None:
        unit_lines.append(
            f"Вхід худі: {_fmt_uah(hoodie_entry)} грн → роздріб (приклад): {_fmt_uah(hoodie_retail)} грн → різниця: {_fmt_uah(hoodie_profit)} грн*"
        )

    if not unit_lines:
        entry_hint = context.get("entry_hint") or "Вхідні ціни від —, деталі скину."
        unit_lines.append(str(entry_hint))

    links_line = " / ".join(
        [
            str(context["links"]["cooperation"]),
            str(context["links"]["wholesale"]),
            str(context["links"]["dropship"]),
        ]
    )

    lines: list[str] = [
        greeting,
        "",
        who_line,
        "",
        "Можемо відправити тест-ростовку S–XL на 14 днів. Якщо не зайде — повертаєте залишки. Сплачуєте лише доставку.",
        "",
        *unit_lines,
        "*Це приклад розрахунку. Роздрібну ціну встановлюєте ви.",
        "",
        "Скинути каталог та умови?",
        links_line,
        "",
    ]

    if show_manager:
        contact_lines: list[str] = []
        if manager_name:
            contact_lines.append(manager_name)

        phone = (context.get("manager_phone") or "").strip()
        if phone:
            contact_lines.append(f"Телефон: {phone}")

        viber = (context.get("manager_viber") or "").strip()
        if viber:
            contact_lines.append(f"Viber: {viber}")

        whatsapp = (context.get("manager_whatsapp") or "").strip()
        if whatsapp:
            contact_lines.append(f"WhatsApp: {whatsapp}")

        tg = (context.get("manager_tg") or "").strip()
        if tg:
            contact_lines.append(f"Telegram: {tg}")

        if contact_lines:
            lines.extend(["З повагою,", *contact_lines, ""])

    lines.extend(
        [
            f"Запасний канал зв’язку: {context['links']['general_tg']}",
            f"Instagram: {context['links']['instagram']}",
            f"Сайт: {context['links']['site']}",
        ]
    )

    return "\n".join(lines).strip() + "\n"


def _light_text_to_min_html(text: str) -> str:
    safe = escape(text)
    # Minimal HTML: no images, no external CSS.
    return (
        "<!doctype html>"
        "<html><head><meta charset=\"utf-8\"></head>"
        "<body style=\"margin:0;padding:0;background:#ffffff;\">"
        "<div style=\"max-width:600px;margin:0 auto;padding:20px 18px;"
        "font-family:Arial,Helvetica,sans-serif;font-size:15px;line-height:1.55;color:#111111;"
        "white-space:pre-wrap;\">"
        f"{safe}"
        "</div></body></html>"
    )


def build_twocomms_cp_email(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Build TwoComms commercial offer email.

    Returns dict:
      - subject
      - preheader
      - html: VISUAL HTML version
      - text: LIGHT text version
      - html_light: minimal HTML derived from text (for LIGHT sending/logging)
      - normalized + derived fields (mode/segment/prices/profits)
    """
    mode = _normalize_mode(payload.get("mode"))
    segment_mode = _normalize_segment(payload.get("segment_mode"))
    subject_preset = _normalize_subject_preset(payload.get("subject_preset"))

    shop_name = (payload.get("shop_name") or payload.get("recipient_name") or "").strip()
    show_manager = bool(payload.get("show_manager"))

    manager_name = (payload.get("manager_name") or "").strip()
    manager_phone = (payload.get("manager_phone") or payload.get("phone") or "").strip()
    manager_viber = (payload.get("manager_viber") or payload.get("viber") or "").strip()
    manager_whatsapp = (payload.get("manager_whatsapp") or payload.get("whatsapp") or "").strip()
    manager_tg = (payload.get("manager_tg") or payload.get("telegram") or "").strip()
    manager_photo_url = (payload.get("manager_photo_url") or "").strip()

    tee_entry = _to_int(payload.get("tee_entry"))
    tee_retail_example = _to_int(payload.get("tee_retail_example"))
    hoodie_entry = _to_int(payload.get("hoodie_entry"))
    hoodie_retail_example = _to_int(payload.get("hoodie_retail_example"))

    tee_profit = (tee_retail_example - tee_entry) if (tee_entry is not None and tee_retail_example is not None) else None
    hoodie_profit = (hoodie_retail_example - hoodie_entry) if (hoodie_entry is not None and hoodie_retail_example is not None) else None

    subject_custom = (payload.get("subject_custom") or "").strip()
    subject = _build_subject(
        preset=subject_preset,
        shop_name=shop_name,
        tee_entry=tee_entry,
        hoodie_entry=hoodie_entry,
        custom=subject_custom,
    )
    preheader = _build_preheader(tee_entry=tee_entry, hoodie_entry=hoodie_entry)

    links = {
        "site": _abs_url("/"),
        "catalog": _abs_url("/catalog/"),
        "cooperation": _abs_url("/cooperation/"),
        "wholesale": _abs_url("/wholesale/"),
        "dropship": _abs_url("/dropshipper/"),
        "instagram": "https://instagram.com/twocomms",
        "general_tg": "https://t.me/twocomms",
    }

    entry_hint = ""
    if tee_entry and hoodie_entry:
        entry_hint = f"Вхідні ціни від {_fmt_uah(tee_entry)}/{_fmt_uah(hoodie_entry)} грн — деталі скину."
    elif tee_entry or hoodie_entry:
        entry_hint = f"Вхідні ціни від {_fmt_uah(tee_entry or hoodie_entry)} грн — деталі скину."
    else:
        entry_hint = "Вхідні ціни від —, деталі скину."

    gallery = _gallery_items(segment_mode)
    logo_url = _abs_url("/static/img/favicon-192x192.png")

    template_context: dict[str, Any] = {
        "shop_name": shop_name,
        "show_manager": show_manager,
        "manager_name": manager_name,
        "manager_phone": manager_phone,
        "manager_viber": manager_viber,
        "manager_whatsapp": manager_whatsapp,
        "manager_tg": manager_tg,
        "manager_photo_url": manager_photo_url,
        "general_tg": links["general_tg"],
        "mode": mode,
        "segment_mode": segment_mode,
        "subject": subject,
        "preheader": preheader,
        "links": links,
        "logo_url": logo_url,
        "tee_entry": tee_entry,
        "tee_entry_display": _fmt_uah(tee_entry),
        "tee_retail_example": tee_retail_example,
        "tee_retail_example_display": _fmt_uah(tee_retail_example),
        "tee_profit": tee_profit,
        "tee_profit_display": _fmt_uah(tee_profit),
        "hoodie_entry": hoodie_entry,
        "hoodie_entry_display": _fmt_uah(hoodie_entry),
        "hoodie_retail_example": hoodie_retail_example,
        "hoodie_retail_example_display": _fmt_uah(hoodie_retail_example),
        "hoodie_profit": hoodie_profit,
        "hoodie_profit_display": _fmt_uah(hoodie_profit),
        "gallery": gallery,
        "entry_hint": entry_hint,
    }

    text = _build_light_text({**template_context, "entry_hint": entry_hint})
    html_visual = render_to_string("management/emails/twocomms_cp_visual.html", template_context)
    html_light = _light_text_to_min_html(text)

    return {
        "subject": subject,
        "preheader": preheader,
        "html": html_visual,
        "text": text,
        "html_light": html_light,
        "mode": mode,
        "segment_mode": segment_mode,
        "subject_preset": subject_preset,
        "subject_custom": subject_custom,
        "shop_name": shop_name,
        "show_manager": show_manager,
        "manager_name": manager_name,
        "manager_phone": manager_phone,
        "manager_viber": manager_viber,
        "manager_whatsapp": manager_whatsapp,
        "manager_tg": manager_tg,
        "manager_photo_url": manager_photo_url,
        "tee_entry": tee_entry,
        "tee_retail_example": tee_retail_example,
        "tee_profit": tee_profit,
        "hoodie_entry": hoodie_entry,
        "hoodie_retail_example": hoodie_retail_example,
        "hoodie_profit": hoodie_profit,
    }

