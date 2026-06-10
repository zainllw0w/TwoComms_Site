from __future__ import annotations

from dataclasses import dataclass
import re
import time
from typing import Any, Literal
from urllib.parse import quote, urljoin, urlparse

from django.conf import settings
from django.core import signing
from django.db.models import Q
from django.template.loader import render_to_string
from django.utils.html import escape

CpMode = Literal["LIGHT", "VISUAL"]
CpSegmentMode = Literal["NEUTRAL", "EDGY"]
CpSubjectPreset = Literal["PRESET_1", "PRESET_2", "PRESET_3", "CUSTOM"]
CpCtaType = Literal[
    "TELEGRAM_MANAGER",
    "WHATSAPP_MANAGER",
    "TELEGRAM_GENERAL",
    "MAILTO_COOPERATION",
    "REPLY_HINT_ONLY",
    "CUSTOM_URL",
]
CpPricingMode = Literal["OPT", "DROP"]
CpOptTier = Literal["8_15", "16_31", "32_63", "64_99", "100_PLUS"]

_RETAIL_DEFAULTS_CACHE: dict[str, Any] = {"ts": 0.0, "data": None}
_GALLERY_DEFAULTS_CACHE: dict[str, Any] = {"ts": 0.0, "data": None}

# Pricing config (fallback, must match your real price policy)
OPT_TIER_LABELS: dict[CpOptTier, str] = {
    "8_15": "8–15",
    "16_31": "16–31",
    "32_63": "32–63",
    "64_99": "64–99",
    "100_PLUS": "100+",
}

OPT_TIER_WHOLESALE_TEE: dict[CpOptTier, int] = {
    "8_15": 540,
    "16_31": 520,
    "32_63": 500,
    "64_99": 490,
    "100_PLUS": 480,
}
OPT_TIER_WHOLESALE_HOODIE: dict[CpOptTier, int] = {
    "8_15": 1300,
    "16_31": 1250,
    "32_63": 1200,
    "64_99": 1175,
    "100_PLUS": 1150,
}

DROP_FIXED_TEE_PRICE = 570
DROP_FIXED_HOODIE_PRICE = 1350

# Retail example defaults if we can't fetch from DB (must be realistic)
FALLBACK_TEE_RETAIL = 750
FALLBACK_HOODIE_RETAIL = 1790

_PRODUCT_SLUG_RE = re.compile(r"/product/(?P<slug>[-a-zA-Z0-9_]+)/?")
_IMAGE_EXT_RE = re.compile(r"\.(png|jpe?g|webp|gif)(?:\\?|$)", re.IGNORECASE)


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


def _management_base_url() -> str:
    base = (getattr(settings, "MANAGEMENT_BASE_URL", "") or "https://management.twocomms.shop").strip()
    return base.rstrip("/")


def _cp_pixel_url(track_token: str) -> str:
    token = (track_token or "").strip()
    if not token:
        return ""
    return f"{_management_base_url()}/cp/o/{token}.png"


def _cp_wrap_click(url: str, track_token: str) -> str:
    """Wrap an outbound http(s) CTA into the signed click-redirect for tracking."""
    token = (track_token or "").strip()
    if not token or not url or not url.startswith(("http://", "https://")):
        return url
    signed = signing.dumps(url, salt="cp.click")
    return f"{_management_base_url()}/cp/c/{token}/?u={quote(signed)}"


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
        "WHATSAPP_MANAGER",
        "TELEGRAM_GENERAL",
        "MAILTO_COOPERATION",
        "REPLY_HINT_ONLY",
        "CUSTOM_URL",
    }
    if v in allowed:
        return v  # type: ignore[return-value]
    return None


def _normalize_pricing_mode(value: Any) -> CpPricingMode:
    v = (str(value or "").strip().upper() or "OPT")
    return "DROP" if v == "DROP" else "OPT"


def _normalize_opt_tier(value: Any) -> CpOptTier:
    v = (str(value or "").strip().upper() or "8_15")
    if v in {"8_15", "16_31", "32_63", "64_99", "100_PLUS"}:
        return v  # type: ignore[return-value]
    return "8_15"


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


def _normalize_wa_phone(value: str) -> str:
    digits = re.sub(r"\D+", "", (value or "").strip())
    if not digits:
        return ""
    if digits.startswith("380") and len(digits) == 12:
        return digits
    if digits.startswith("0") and len(digits) == 10:
        return f"38{digits}"
    if len(digits) == 9:
        return f"380{digits}"
    return digits


def _whatsapp_url(value: str) -> str:
    digits = _normalize_wa_phone(value)
    return f"https://wa.me/{digits}" if digits else ""


def _build_cta(
    *,
    requested_type: CpCtaType | None,
    manager_tg: str,
    manager_whatsapp: str,
    general_tg: str,
    custom_url: str,
    cooperation_email: str,
    mailto_subject: str = "",
) -> tuple[CpCtaType, str]:
    manager_tg_url = _normalize_tg(manager_tg)
    manager_wa_url = _whatsapp_url(manager_whatsapp)
    general_tg_url = _normalize_tg(general_tg)
    custom_url_val = (custom_url or "").strip()
    mailto = (
        f"mailto:{cooperation_email}?subject={quote(mailto_subject)}"
        if (mailto_subject or "").strip()
        else f"mailto:{cooperation_email}"
    )

    # Auto default (primary CTA): manager TG → WhatsApp → mailto
    resolved_type = requested_type
    if not resolved_type:
        if manager_tg_url:
            resolved_type = "TELEGRAM_MANAGER"
        elif manager_wa_url:
            resolved_type = "WHATSAPP_MANAGER"
        else:
            resolved_type = "MAILTO_COOPERATION"

    if resolved_type == "TELEGRAM_MANAGER":
        if manager_tg_url:
            return resolved_type, manager_tg_url
        if manager_wa_url:
            return "WHATSAPP_MANAGER", manager_wa_url
        return "MAILTO_COOPERATION", mailto

    if resolved_type == "WHATSAPP_MANAGER":
        if manager_wa_url:
            return resolved_type, manager_wa_url
        if manager_tg_url:
            return "TELEGRAM_MANAGER", manager_tg_url
        return "MAILTO_COOPERATION", mailto

    if resolved_type == "TELEGRAM_GENERAL":
        if general_tg_url:
            return resolved_type, general_tg_url
        if manager_tg_url:
            return "TELEGRAM_MANAGER", manager_tg_url
        if manager_wa_url:
            return "WHATSAPP_MANAGER", manager_wa_url
        return "MAILTO_COOPERATION", mailto

    if resolved_type == "CUSTOM_URL":
        if custom_url_val:
            return resolved_type, custom_url_val
        if manager_tg_url:
            return "TELEGRAM_MANAGER", manager_tg_url
        if manager_wa_url:
            return "WHATSAPP_MANAGER", manager_wa_url
        return "MAILTO_COOPERATION", mailto

    if resolved_type == "REPLY_HINT_ONLY":
        return resolved_type, ""

    # MAILTO_COOPERATION
    return resolved_type, mailto


def _get_retail_defaults() -> dict[str, Any]:
    """
    Try to get retail defaults from DB (real site data). Falls back to constants.
    Returns:
      tee_retail_default, hoodie_retail_default,
      source: 'site' | 'fallback'
    """
    now = time.time()
    if _RETAIL_DEFAULTS_CACHE["data"] and now - float(_RETAIL_DEFAULTS_CACHE["ts"]) < 300:
        return _RETAIL_DEFAULTS_CACHE["data"]

    data: dict[str, Any] = {
        "tee_retail_default": FALLBACK_TEE_RETAIL,
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

        tee_retail = pick_retail(tee)
        hoodie_retail = pick_retail(hoodie)

        if tee_retail:
            data["tee_retail_default"] = tee_retail
        if hoodie_retail:
            data["hoodie_retail_default"] = hoodie_retail
        if tee_retail or hoodie_retail:
            data["source"] = "site"
    except Exception:
        pass

    _RETAIL_DEFAULTS_CACHE.update({"ts": now, "data": data})
    return data


def get_twocomms_cp_unit_defaults(
    *,
    pricing_mode: CpPricingMode = "OPT",
    opt_tier: CpOptTier = "8_15",
    drop_tee_price: int | None = None,
    drop_hoodie_price: int | None = None,
) -> dict[str, Any]:
    retail = _get_retail_defaults()
    tier = _normalize_opt_tier(opt_tier)
    mode = _normalize_pricing_mode(pricing_mode)

    drop_tee_val = int(drop_tee_price) if (drop_tee_price is not None and int(drop_tee_price) > 0) else DROP_FIXED_TEE_PRICE
    drop_hoodie_val = (
        int(drop_hoodie_price) if (drop_hoodie_price is not None and int(drop_hoodie_price) > 0) else DROP_FIXED_HOODIE_PRICE
    )

    if mode == "DROP":
        tee_entry_default = drop_tee_val
        hoodie_entry_default = drop_hoodie_val
    else:
        tee_entry_default = int(OPT_TIER_WHOLESALE_TEE[tier])
        hoodie_entry_default = int(OPT_TIER_WHOLESALE_HOODIE[tier])

    tee_min = int(OPT_TIER_WHOLESALE_TEE["100_PLUS"])
    tee_max = int(OPT_TIER_WHOLESALE_TEE["8_15"])
    hoodie_min = int(OPT_TIER_WHOLESALE_HOODIE["100_PLUS"])
    hoodie_max = int(OPT_TIER_WHOLESALE_HOODIE["8_15"])

    return {
        "pricing_mode": mode,
        "opt_tier": tier,
        "opt_tier_label": OPT_TIER_LABELS.get(tier, "8–15"),
        "tee_entry_default": tee_entry_default,
        "hoodie_entry_default": hoodie_entry_default,
        "drop_tee_price_default": drop_tee_val,
        "drop_hoodie_price_default": drop_hoodie_val,
        "tee_retail_default": int(retail["tee_retail_default"]),
        "hoodie_retail_default": int(retail["hoodie_retail_default"]),
        "retail_source": retail.get("source", "fallback"),
        "opt_tee_range": f"{_fmt_uah(tee_max)} → {_fmt_uah(tee_min)}",
        "opt_hoodie_range": f"{_fmt_uah(hoodie_max)} → {_fmt_uah(hoodie_min)}",
    }


OPT_TIER_ORDER: tuple[CpOptTier, ...] = ("8_15", "16_31", "32_63", "64_99", "100_PLUS")
OPT_TIER_RANGE_LABELS: dict[CpOptTier, str] = {
    "8_15": "8–15 шт",
    "16_31": "16–31 шт",
    "32_63": "32–63 шт",
    "64_99": "64–99 шт",
    "100_PLUS": "100+ шт",
}


def get_twocomms_cp_opt_grid() -> list[dict[str, Any]]:
    """Wholesale price grid by quantity tier (single source of truth with invoice).

    Returns rows ordered from the smallest tier (highest unit price) to the
    largest tier (lowest unit price), e.g.::

        [{"tier": "8_15", "range": "8–15 шт", "tee": 540, "hoodie": 1300}, ...]

    Prices come from ``OPT_TIER_WHOLESALE_TEE`` / ``OPT_TIER_WHOLESALE_HOODIE``
    which must mirror ``management.invoice_service._WHOLESALE_PRICE_CONTEXT``.
    """
    grid: list[dict[str, Any]] = []
    for tier in OPT_TIER_ORDER:
        grid.append(
            {
                "tier": tier,
                "range": OPT_TIER_RANGE_LABELS[tier],
                "tee": int(OPT_TIER_WHOLESALE_TEE[tier]),
                "tee_display": _fmt_uah(int(OPT_TIER_WHOLESALE_TEE[tier])),
                "hoodie": int(OPT_TIER_WHOLESALE_HOODIE[tier]),
                "hoodie_display": _fmt_uah(int(OPT_TIER_WHOLESALE_HOODIE[tier])),
            }
        )
    return grid


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


def _looks_like_image_url(url_or_path: str) -> bool:
    s = (url_or_path or "").strip()
    if not s:
        return False
    try:
        path = urlparse(s).path if s.startswith(("http://", "https://")) else s
    except Exception:
        path = s
    return bool(_IMAGE_EXT_RE.search(path or ""))


def _normalize_gallery_input(raw: Any) -> list[dict[str, str]]:
    """
    Backward-compatible gallery input.
    Accepts:
      - list[str] (old)
      - list[dict] with keys: url, caption/title
      - str (single url)
    Returns list[{url, caption}] up to 6.
    """
    if raw is None:
        return []
    if isinstance(raw, str):
        s = raw.strip()
        return [{"url": s, "caption": ""}] if s else []
    if not isinstance(raw, list):
        return []

    slots: list[dict[str, str]] = []
    for item in raw:
        if isinstance(item, str):
            u = item.strip()
            if u:
                slots.append({"url": u, "caption": ""})
            continue
        if isinstance(item, dict):
            u = str(item.get("url") or item.get("link") or item.get("href") or "").strip()
            if not u:
                continue
            caption = str(item.get("caption") or item.get("title") or "").strip()
            slots.append({"url": u, "caption": caption})
            continue
    return slots[:6]


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


def _resolve_gallery_urls(
    urls_or_slots: Any,
) -> tuple[list[CpGalleryItem], list[dict[str, str]], list[dict[str, Any]]]:
    """
    Returns:
      - items: list[CpGalleryItem] (ready for template)
      - normalized_slots: list[{url, caption}] (cleaned input)
      - snapshot: list[dict] (for logging / history)
    """
    slots = _normalize_gallery_input(urls_or_slots)
    if not slots:
        return [], [], []

    slugs_needed: list[str] = []
    for slot in slots:
        slug = _extract_product_slug(slot.get("url") or "")
        if slug:
            slugs_needed.append(slug)

    by_slug: dict[str, Any] = {}
    if slugs_needed:
        try:
            from storefront.models import Product, ProductStatus  # lazy import

            products = (
                Product.objects.select_related("category")
                .filter(status=ProductStatus.PUBLISHED, slug__in=slugs_needed)
                .order_by("-priority", "-id")
            )
            by_slug = {p.slug: p for p in products}
        except Exception:
            by_slug = {}

    items: list[CpGalleryItem] = []
    normalized_slots: list[dict[str, str]] = []
    snapshot: list[dict[str, Any]] = []

    for slot in slots:
        raw_url = (slot.get("url") or "").strip()
        caption = (slot.get("caption") or "").strip()

        slug = _extract_product_slug(raw_url)
        if slug:
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

            title = caption or (getattr(p, "title", "") or "").strip() or slug
            link_url = _abs_url(f"/product/{p.slug}/")
            items.append(CpGalleryItem(title=title[:90], img_url=img_url, link_url=link_url))
            normalized_slots.append({"url": _abs_url(f"/product/{p.slug}/"), "caption": caption[:120]})
            snapshot.append(
                {
                    "source": "product",
                    "slug": p.slug,
                    "title": title,
                    "caption": caption,
                    "img_url": img_url,
                    "link_url": link_url,
                    "retail": getattr(p, "final_price", None),
                }
            )
            continue

        if _looks_like_image_url(raw_url):
            img_url = _abs_url(raw_url)
            title = caption or "Фото"
            link_url = _abs_url(raw_url)
            items.append(CpGalleryItem(title=title[:90], img_url=img_url, link_url=link_url))
            normalized_slots.append({"url": img_url, "caption": caption[:120]})
            snapshot.append(
                {
                    "source": "image",
                    "title": title,
                    "caption": caption,
                    "img_url": img_url,
                    "link_url": link_url,
                }
            )

    return items[:6], normalized_slots[:6], snapshot[:6]


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
        "Опт від 8 шт — ціна залежить від обсягу (можу під ваш обсяг підтвердити рівень).",
    ]
    if bool(context.get("dropship_loyalty_bonus")):
        lines.append("Бонус (дроп): після кожного замовлення — -10 грн до наступного.")

    lines.extend(
        [
            "",
            *unit_lines,
            "*Це приклад розрахунку. Роздрібну ціну встановлюєте ви.",
            "",
            "Запросити тест-ростовку?",
            (context.get("cta_url") or "").strip() or "Відповідайте на цей лист",
            str((context.get("cta_microtext") or "")).strip(),
            "",
        ]
    )

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

    lines.append("TwoComms — одяг для свідомих.")
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
    cta_button_text = (payload.get("cta_button_text") or "").strip() or "Зв'язатися з менеджером"
    cta_microtext = (
        (payload.get("cta_microtext") or "").strip()
        or "Менеджер підтвердить умови під ваш обсяг."
    )

    pricing_mode = _normalize_pricing_mode(payload.get("pricing_mode"))
    opt_tier = _normalize_opt_tier(payload.get("opt_tier"))
    drop_tee_price = _to_int(payload.get("drop_tee_price"))
    drop_hoodie_price = _to_int(payload.get("drop_hoodie_price"))
    dropship_loyalty_bonus = _to_bool(payload.get("dropship_loyalty_bonus"))

    unit_defaults = get_twocomms_cp_unit_defaults(
        pricing_mode=pricing_mode,
        opt_tier=opt_tier,
        drop_tee_price=drop_tee_price,
        drop_hoodie_price=drop_hoodie_price,
    )

    tee_entry = _to_int(payload.get("tee_entry"))
    tee_retail_example = _to_int(payload.get("tee_retail_example"))
    hoodie_entry = _to_int(payload.get("hoodie_entry"))
    hoodie_retail_example = _to_int(payload.get("hoodie_retail_example"))

    if tee_entry is None:
        tee_entry = int(unit_defaults["tee_entry_default"])
    if tee_retail_example is None:
        tee_retail_example = int(unit_defaults["tee_retail_default"])
    if hoodie_entry is None:
        hoodie_entry = int(unit_defaults["hoodie_entry_default"])
    if hoodie_retail_example is None:
        hoodie_retail_example = int(unit_defaults["hoodie_retail_default"])

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

    mailto_subject = f"Запит тест-ростовки TwoComms{(' — ' + shop_name) if shop_name else ''}"
    resolved_cta_type, cta_url = _build_cta(
        requested_type=cta_type,
        manager_tg=manager_tg,
        manager_whatsapp=manager_whatsapp,
        general_tg=links["general_tg"],
        custom_url=cta_custom_url,
        cooperation_email="cooperation@twocomms.shop",
        mailto_subject=mailto_subject,
    )

    entry_hint = ""
    if tee_entry and hoodie_entry:
        entry_hint = f"Вхідні ціни від {_fmt_uah(tee_entry)}/{_fmt_uah(hoodie_entry)} грн — деталі скину."
    elif tee_entry or hoodie_entry:
        entry_hint = f"Вхідні ціни від {_fmt_uah(tee_entry or hoodie_entry)} грн — деталі скину."
    else:
        entry_hint = "Вхідні ціни від —, деталі скину."

    gallery_urls_provided = "gallery_urls" in payload
    gallery_slots = _normalize_gallery_input(payload.get("gallery_urls"))
    if (not gallery_slots) and (not gallery_urls_provided):
        gallery_slots = [{"url": u, "caption": ""} for u in _get_gallery_default_urls(segment_mode)]

    gallery, gallery_urls_norm, gallery_snapshot = _resolve_gallery_urls(gallery_slots)
    logo_url = _abs_url("/static/img/favicon-192x192.png")

    opt_grid = get_twocomms_cp_opt_grid()

    # Secondary CTA always points to the assortment (wholesale → catalog → site).
    if include_wholesale_link:
        cta_secondary_url = links["wholesale"]
    elif include_catalog_link:
        cta_secondary_url = links["catalog"]
    else:
        cta_secondary_url = links["site"]
    cta_secondary_text = "Переглянути асортимент"

    trust_points = [
        "Договір та КЕП",
        "Нова Пошта по Україні",
        "Повернення залишків тесту",
        "Опт від 8 шт",
    ]
    why_us = [
        "Тест-ростовка S–XL на 14 днів — перевіряєте попит майже без ризику.",
        "Опт від 8 шт: чим більший обсяг — тим нижча ціна за одиницю.",
        "Дропшип без складу: XML-вивантаження та кабінет партнера з ТТН/трекінгом.",
    ]
    if dropship_loyalty_bonus:
        why_us.append("Бонус для дропу: −10 грн до наступного замовлення після кожного.")

    track_token = (payload.get("track_token") or "").strip()
    tracking_pixel_url = _cp_pixel_url(track_token)
    cta_url_tracked = _cp_wrap_click(cta_url, track_token)
    cta_secondary_url_tracked = _cp_wrap_click(cta_secondary_url, track_token)

    template_context: dict[str, Any] = {
        "opt_grid": opt_grid,
        "trust_points": trust_points,
        "why_us": why_us,
        "cta_secondary_url": cta_secondary_url_tracked,
        "cta_secondary_text": cta_secondary_text,
        "tracking_pixel_url": tracking_pixel_url,
        "shop_name": shop_name,
        "show_manager": show_manager,
        "manager_name": manager_name,
        "manager_phone": manager_phone,
        "manager_viber": manager_viber,
        "manager_whatsapp": manager_whatsapp,
        "manager_tg": manager_tg,
        "manager_photo_url": manager_photo_url,
        "general_tg": links["general_tg"],
        "pricing_mode": pricing_mode,
        "opt_tier": opt_tier,
        "opt_tier_label": unit_defaults.get("opt_tier_label", ""),
        "opt_tee_range": unit_defaults.get("opt_tee_range", ""),
        "opt_hoodie_range": unit_defaults.get("opt_hoodie_range", ""),
        "drop_tee_price": int(unit_defaults.get("drop_tee_price_default") or DROP_FIXED_TEE_PRICE),
        "drop_hoodie_price": int(unit_defaults.get("drop_hoodie_price_default") or DROP_FIXED_HOODIE_PRICE),
        "dropship_loyalty_bonus": dropship_loyalty_bonus,
        "mode": mode,
        "segment_mode": segment_mode,
        "subject": subject,
        "preheader": preheader,
        "cta_type": resolved_cta_type,
        "cta_url": cta_url_tracked,
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
        "defaults_source": unit_defaults.get("retail_source", "fallback"),
        "profit_warnings": profit_warnings,
    }

    text = _build_light_text({**template_context, "entry_hint": entry_hint})
    html_visual = render_to_string("management/emails/twocomms_cp_dark.html", template_context)
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
        "pricing_mode": pricing_mode,
        "opt_tier": opt_tier,
        "opt_tier_label": unit_defaults.get("opt_tier_label", ""),
        "drop_tee_price": int(unit_defaults.get("drop_tee_price_default") or DROP_FIXED_TEE_PRICE),
        "drop_hoodie_price": int(unit_defaults.get("drop_hoodie_price_default") or DROP_FIXED_HOODIE_PRICE),
        "dropship_loyalty_bonus": dropship_loyalty_bonus,
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
        "defaults_source": unit_defaults.get("retail_source", "fallback"),
        "profit_warnings": profit_warnings,
    }
