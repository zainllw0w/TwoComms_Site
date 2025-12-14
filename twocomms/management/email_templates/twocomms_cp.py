from __future__ import annotations

from dataclasses import dataclass
import re
import time
from typing import Any, Literal
from urllib.parse import urljoin, urlparse

from django.conf import settings
from django.db.models import Q
from django.template.loader import render_to_string
from django.utils.html import escape

CpMode = Literal["LIGHT", "VISUAL"]
CpSegmentMode = Literal["NEUTRAL", "EDGY"]
CpSubjectPreset = Literal["PRESET_1", "PRESET_2", "PRESET_3", "CUSTOM"]
CpCtaType = Literal[
    "TELEGRAM_MANAGER",
    "TELEGRAM_GENERAL",
    "MAILTO_COOPERATION",
    "REPLY_HINT_ONLY",
    "CUSTOM_URL",
]

_UNIT_DEFAULTS_CACHE: dict[str, Any] = {"ts": 0.0, "data": None}
_GALLERY_DEFAULTS_CACHE: dict[str, Any] = {"ts": 0.0, "data": None}

# Fallback defaults if we can't fetch from DB (must be realistic)
FALLBACK_TEE_ENTRY = 250
FALLBACK_TEE_RETAIL = 690
FALLBACK_HOODIE_ENTRY = 520
FALLBACK_HOODIE_RETAIL = 1490

_PRODUCT_SLUG_RE = re.compile(r"/product/(?P<slug>[-a-zA-Z0-9_]+)/?")


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


def _normalize_cta_type(value: Any) -> CpCtaType | None:
    v = (str(value or "").strip().upper() or "")
    allowed = {
        "TELEGRAM_MANAGER",
        "TELEGRAM_GENERAL",
        "MAILTO_COOPERATION",
        "REPLY_HINT_ONLY",
        "CUSTOM_URL",
    }
    if v in allowed:
        return v  # type: ignore[return-value]
    return None


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    s = str(value).strip().lower()
    return s in {"1", "true", "yes", "on"}


def _normalize_tg(value: str) -> str:
    v = (value or "").strip()
    if not v:
        return ""
    if v.startswith(("http://", "https://")):
        return v
    if v.startswith("tg:"):
        return v
    if v.startswith("@"):
        return f"https://t.me/{v[1:]}"
    if v.startswith("t.me/"):
        return f"https://{v}"
    if "t.me/" in v:
        # e.g. 'https://t.me/xxx?start=...'
        return v if v.startswith(("http://", "https://")) else f"https://{v}"
    # assume username
    return f"https://t.me/{v}"


def _build_cta(
    *,
    requested_type: CpCtaType | None,
    manager_tg: str,
    general_tg: str,
    custom_url: str,
    cooperation_email: str,
) -> tuple[CpCtaType, str]:
    manager_tg_url = _normalize_tg(manager_tg)
    general_tg_url = _normalize_tg(general_tg)
    custom_url_val = (custom_url or "").strip()

    # Auto default: manager TG → general TG → mailto
    resolved_type = requested_type
    if not resolved_type:
        if manager_tg_url:
            resolved_type = "TELEGRAM_MANAGER"
        elif general_tg_url:
            resolved_type = "TELEGRAM_GENERAL"
        else:
            resolved_type = "MAILTO_COOPERATION"

    if resolved_type == "TELEGRAM_MANAGER":
        if manager_tg_url:
            return resolved_type, manager_tg_url
        if general_tg_url:
            return "TELEGRAM_GENERAL", general_tg_url
        return "MAILTO_COOPERATION", f"mailto:{cooperation_email}"

    if resolved_type == "TELEGRAM_GENERAL":
        if general_tg_url:
            return resolved_type, general_tg_url
        if manager_tg_url:
            return "TELEGRAM_MANAGER", manager_tg_url
        return "MAILTO_COOPERATION", f"mailto:{cooperation_email}"

    if resolved_type == "CUSTOM_URL":
        if custom_url_val:
            return resolved_type, custom_url_val
        if manager_tg_url:
            return "TELEGRAM_MANAGER", manager_tg_url
        if general_tg_url:
            return "TELEGRAM_GENERAL", general_tg_url
        return "MAILTO_COOPERATION", f"mailto:{cooperation_email}"

    if resolved_type == "REPLY_HINT_ONLY":
        return resolved_type, ""

    # MAILTO_COOPERATION
    return resolved_type, f"mailto:{cooperation_email}"


def _get_unit_defaults() -> dict[str, Any]:
    """
    Try to get defaults from DB (real site data). Falls back to constants.
    Returns:
      tee_entry_default, tee_retail_default, hoodie_entry_default, hoodie_retail_default,
      source: 'site' | 'fallback'
    """
    now = time.time()
    if _UNIT_DEFAULTS_CACHE["data"] and now - float(_UNIT_DEFAULTS_CACHE["ts"]) < 300:
        return _UNIT_DEFAULTS_CACHE["data"]

    data: dict[str, Any] = {
        "tee_entry_default": FALLBACK_TEE_ENTRY,
        "tee_retail_default": FALLBACK_TEE_RETAIL,
        "hoodie_entry_default": FALLBACK_HOODIE_ENTRY,
        "hoodie_retail_default": FALLBACK_HOODIE_RETAIL,
        "source": "fallback",
    }

    try:
        from storefront.models import Product, ProductStatus  # lazy import

        base_qs = Product.objects.select_related("category").filter(status=ProductStatus.PUBLISHED)

        tee = (
            base_qs.filter(
                Q(title__icontains="футбол")
                | Q(title__icontains="t-shirt")
                | Q(title__icontains="tshirt")
                | Q(category__slug__icontains="tshirt")
                | Q(category__slug__icontains="tee")
            )
            .order_by("-priority", "-id")
            .first()
        )
        hoodie = (
            base_qs.filter(
                Q(title__icontains="худ")
                | Q(title__icontains="hood")
                | Q(category__slug__iexact="hoodie")
                | Q(category__slug__icontains="hoodie")
            )
            .order_by("-priority", "-id")
            .first()
        )

        def pick_entry(p) -> int | None:
            if not p:
                return None
            if getattr(p, "wholesale_price", 0) and int(p.wholesale_price) > 0:
                return int(p.wholesale_price)
            if getattr(p, "drop_price", 0) and int(p.drop_price) > 0:
                return int(p.drop_price)
            try:
                drop = int(p.get_drop_price() or 0)
                return drop if drop > 0 else None
            except Exception:
                return None

        def pick_retail(p) -> int | None:
            if not p:
                return None
            try:
                val = int(getattr(p, "final_price", None) or 0)
                return val if val > 0 else int(getattr(p, "price", 0) or 0) or None
            except Exception:
                try:
                    return int(getattr(p, "price", 0) or 0) or None
                except Exception:
                    return None

        tee_entry = pick_entry(tee)
        tee_retail = pick_retail(tee)
        hoodie_entry = pick_entry(hoodie)
        hoodie_retail = pick_retail(hoodie)

        if tee_entry and tee_retail:
            data["tee_entry_default"] = tee_entry
            data["tee_retail_default"] = tee_retail
        if hoodie_entry and hoodie_retail:
            data["hoodie_entry_default"] = hoodie_entry
            data["hoodie_retail_default"] = hoodie_retail

        if (tee_entry and tee_retail) or (hoodie_entry and hoodie_retail):
            data["source"] = "site"
    except Exception:
        pass

    _UNIT_DEFAULTS_CACHE.update({"ts": now, "data": data})
    return data


def get_twocomms_cp_unit_defaults() -> dict[str, Any]:
    return _get_unit_defaults()


def _extract_product_slug(url_or_path: str) -> str:
    s = (url_or_path or "").strip()
    if not s:
        return ""
    try:
        path = urlparse(s).path if s.startswith(("http://", "https://")) else s
    except Exception:
        path = s
    match = _PRODUCT_SLUG_RE.search(path)
    return match.group("slug") if match else ""


def _get_gallery_default_urls(segment_mode: CpSegmentMode) -> list[str]:
    now = time.time()
    cached = _GALLERY_DEFAULTS_CACHE.get("data")
    if cached and now - float(_GALLERY_DEFAULTS_CACHE.get("ts") or 0.0) < 300:
        return list(cached.get(segment_mode, []))

    data: dict[str, Any] = {"NEUTRAL": [], "EDGY": []}
    try:
        from storefront.models import Product, ProductStatus  # lazy import

        qs = Product.objects.select_related("category").filter(status=ProductStatus.PUBLISHED).order_by("-priority", "-id")

        neutral_pref = qs.filter(
            Q(title__icontains="футбол")
            | Q(title__icontains="t-shirt")
            | Q(title__icontains="tshirt")
            | Q(title__icontains="худі")
            | Q(title__icontains="hood")
            | Q(category__slug__in=["tshirt", "tee", "hoodie"])
        ).distinct()
        edgy_pref = qs.filter(
            Q(title__icontains="street")
            | Q(title__icontains="military")
            | Q(title__icontains="принт")
            | Q(title__icontains="print")
            | Q(title__icontains="black")
        ).distinct()

        def pick_three(preferred_qs):
            picked = list(preferred_qs[:3])
            if len(picked) >= 3:
                return picked
            extra = list(qs.exclude(id__in=[p.id for p in picked])[: (3 - len(picked))])
            return picked + extra

        data["NEUTRAL"] = [f"/product/{p.slug}/" for p in pick_three(neutral_pref)]
        data["EDGY"] = [f"/product/{p.slug}/" for p in pick_three(edgy_pref)]
    except Exception:
        pass

    _GALLERY_DEFAULTS_CACHE.update({"ts": now, "data": data})
    return list(data.get(segment_mode, []))


def _resolve_gallery_urls(urls: list[str]) -> tuple[list[CpGalleryItem], list[str], list[dict[str, Any]]]:
    """
    Returns:
      - items: list[CpGalleryItem] (ready for template)
      - normalized_urls: list[str] (cleaned urls)
      - snapshot: list[dict] (for logging / history)
    """
    cleaned = [str(u or "").strip() for u in (urls or [])]
    cleaned = [u for u in cleaned if u][:6]
    if not cleaned:
        return [], [], []

    slugs: list[str] = []
    normalized_urls: list[str] = []
    for raw in cleaned:
        slug = _extract_product_slug(raw)
        if not slug:
            continue
        slugs.append(slug)
        normalized_urls.append(_abs_url(f"/product/{slug}/"))

    if not slugs:
        return [], [], []

    by_slug: dict[str, Any] = {}
    try:
        from storefront.models import Product, ProductStatus  # lazy import

        products = (
            Product.objects.select_related("category")
            .filter(status=ProductStatus.PUBLISHED, slug__in=slugs)
            .order_by("-priority", "-id")
        )
        by_slug = {p.slug: p for p in products}
    except Exception:
        by_slug = {}

    items: list[CpGalleryItem] = []
    snapshot: list[dict[str, Any]] = []
    for slug in slugs:
        p = by_slug.get(slug)
        if not p:
            continue
        img = getattr(p, "display_image", None)
        img_url = ""
        try:
            img_url = _abs_url(img.url) if img and getattr(img, "url", None) else ""
        except Exception:
            img_url = ""
        if not img_url:
            continue

        title = (getattr(p, "title", "") or "").strip() or slug
        link_url = _abs_url(f"/product/{p.slug}/")
        items.append(CpGalleryItem(title=title[:90], img_url=img_url, link_url=link_url))
        snapshot.append(
            {
                "slug": p.slug,
                "title": title,
                "img_url": img_url,
                "link_url": link_url,
                "retail": getattr(p, "final_price", None),
            }
        )

    return items[:6], normalized_urls[:6], snapshot[:6]


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
    urls = _get_gallery_default_urls(segment_mode)
    items, _, _ = _resolve_gallery_urls(urls)
    return items


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

    include_catalog = bool(context.get("include_catalog_link", True))
    include_wholesale = bool(context.get("include_wholesale_link", True))
    include_dropship = bool(context.get("include_dropship_link", True))
    include_instagram = bool(context.get("include_instagram_link", True))
    include_site = bool(context.get("include_site_link", True))

    links_line_main = ""
    if include_catalog:
        links_line_main = f"Каталог та умови: {context['links']['catalog']}"
    elif include_site:
        links_line_main = f"Сайт: {context['links']['site']}"

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
        "Запросити тест-ростовку?",
        (context.get("cta_url") or "").strip() or "Відповідайте на цей лист",
        str((context.get("cta_microtext") or "")).strip(),
        "",
    ]

    if links_line_main:
        lines.append(links_line_main)

    secondary_links: list[str] = []
    if include_wholesale:
        secondary_links.append(f"Опт: {context['links']['wholesale']}")
    if include_dropship:
        secondary_links.append(f"Дроп: {context['links']['dropship']}")
    if secondary_links:
        lines.append(" • ".join(secondary_links))

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

    lines.append(f"Запасний канал зв’язку: {context['links']['general_tg']}")
    if include_instagram:
        lines.append(f"Instagram: {context['links']['instagram']}")
    if include_site:
        lines.append(f"Сайт: {context['links']['site']}")

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

    cta_type = _normalize_cta_type(payload.get("cta_type"))
    cta_custom_url = (payload.get("cta_custom_url") or "").strip()
    cta_button_text = (payload.get("cta_button_text") or "").strip() or "Запросити тест-ростовку"
    cta_microtext = (
        (payload.get("cta_microtext") or "").strip()
        or "Без зобов’язань. Якщо не зайде — повертаєте залишки. Сплачуєте лише доставку."
    )

    defaults = _get_unit_defaults()
    tee_entry = _to_int(payload.get("tee_entry"))
    tee_retail_example = _to_int(payload.get("tee_retail_example"))
    hoodie_entry = _to_int(payload.get("hoodie_entry"))
    hoodie_retail_example = _to_int(payload.get("hoodie_retail_example"))

    if tee_entry is None:
        tee_entry = int(defaults["tee_entry_default"])
    if tee_retail_example is None:
        tee_retail_example = int(defaults["tee_retail_default"])
    if hoodie_entry is None:
        hoodie_entry = int(defaults["hoodie_entry_default"])
    if hoodie_retail_example is None:
        hoodie_retail_example = int(defaults["hoodie_retail_default"])

    tee_profit_raw = int(tee_retail_example) - int(tee_entry)
    hoodie_profit_raw = int(hoodie_retail_example) - int(hoodie_entry)
    tee_profit = max(0, tee_profit_raw)
    hoodie_profit = max(0, hoodie_profit_raw)
    profit_warnings = {
        "tee_negative": tee_profit_raw < 0,
        "hoodie_negative": hoodie_profit_raw < 0,
    }

    subject_custom = (payload.get("subject_custom") or "").strip()
    subject = _build_subject(
        preset=subject_preset,
        shop_name=shop_name,
        tee_entry=tee_entry,
        hoodie_entry=hoodie_entry,
        custom=subject_custom,
    )
    preheader = _build_preheader(tee_entry=tee_entry, hoodie_entry=hoodie_entry)

    include_catalog_link = _to_bool(payload.get("include_catalog_link", True))
    include_wholesale_link = _to_bool(payload.get("include_wholesale_link", True))
    include_dropship_link = _to_bool(payload.get("include_dropship_link", True))
    include_instagram_link = _to_bool(payload.get("include_instagram_link", True))
    include_site_link = _to_bool(payload.get("include_site_link", True))

    links = {
        "site": _abs_url("/"),
        "catalog": _abs_url("/catalog/"),
        "cooperation": _abs_url("/cooperation/"),
        "wholesale": _abs_url("/wholesale/"),
        "dropship": _abs_url("/dropshipper/"),
        "instagram": "https://instagram.com/twocomms",
        "general_tg": _normalize_tg((payload.get("general_tg") or "").strip()) or "https://t.me/twocomms",
    }

    resolved_cta_type, cta_url = _build_cta(
        requested_type=cta_type,
        manager_tg=manager_tg,
        general_tg=links["general_tg"],
        custom_url=cta_custom_url,
        cooperation_email="cooperation@twocomms.shop",
    )

    entry_hint = ""
    if tee_entry and hoodie_entry:
        entry_hint = f"Вхідні ціни від {_fmt_uah(tee_entry)}/{_fmt_uah(hoodie_entry)} грн — деталі скину."
    elif tee_entry or hoodie_entry:
        entry_hint = f"Вхідні ціни від {_fmt_uah(tee_entry or hoodie_entry)} грн — деталі скину."
    else:
        entry_hint = "Вхідні ціни від —, деталі скину."

    gallery_urls_provided = "gallery_urls" in payload
    gallery_urls_raw = payload.get("gallery_urls")
    if isinstance(gallery_urls_raw, list):
        gallery_urls = [str(x or "").strip() for x in gallery_urls_raw if str(x or "").strip()]
    elif isinstance(gallery_urls_raw, str):
        gallery_urls = [gallery_urls_raw.strip()] if gallery_urls_raw.strip() else []
    else:
        gallery_urls = []

    if (not gallery_urls) and (not gallery_urls_provided):
        gallery_urls = _get_gallery_default_urls(segment_mode)

    gallery, gallery_urls_norm, gallery_snapshot = _resolve_gallery_urls(gallery_urls)
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
        "cta_type": resolved_cta_type,
        "cta_url": cta_url,
        "cta_button_text": cta_button_text,
        "cta_microtext": cta_microtext,
        "include_catalog_link": include_catalog_link,
        "include_wholesale_link": include_wholesale_link,
        "include_dropship_link": include_dropship_link,
        "include_instagram_link": include_instagram_link,
        "include_site_link": include_site_link,
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
        "gallery_urls": gallery_urls_norm,
        "entry_hint": entry_hint,
        "defaults_source": defaults.get("source", "fallback"),
        "profit_warnings": profit_warnings,
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
        "cta_type": resolved_cta_type,
        "cta_url": cta_url,
        "cta_button_text": cta_button_text,
        "cta_microtext": cta_microtext,
        "include_catalog_link": include_catalog_link,
        "include_wholesale_link": include_wholesale_link,
        "include_dropship_link": include_dropship_link,
        "include_instagram_link": include_instagram_link,
        "include_site_link": include_site_link,
        "gallery_urls": gallery_urls_norm,
        "gallery_items": gallery_snapshot,
        "tee_entry": tee_entry,
        "tee_retail_example": tee_retail_example,
        "tee_profit": tee_profit,
        "hoodie_entry": hoodie_entry,
        "hoodie_retail_example": hoodie_retail_example,
        "hoodie_profit": hoodie_profit,
        "defaults_source": defaults.get("source", "fallback"),
        "profit_warnings": profit_warnings,
    }
