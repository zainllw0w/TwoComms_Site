from __future__ import annotations

from copy import deepcopy


TELEGRAM_MANAGER_URL = "https://t.me/twocomms"
CUSTOM_PRINT_DRAFT_STORAGE_KEY = "twocomms.custom_print.v2.draft"
SESSION_CUSTOM_CART_KEY = "custom_print_cart"

# ── V2 business constants ────────────────────────────────────────────
GIFT_SERVICE = {
    "value": "gift_pack",
    "label": "Подарункова упаковка",
    "price": 100,
    "promo_code": "GIFT10",
    "promo_discount_percent": 10,
    "note": "Ми упакуємо замовлення в преміум-крафт, додамо листівку і заховаємо цінники.",
    "bonus_note": "Бонус: разовий промокод -10% на наступну покупку в TwoComms.",
}

B2B_TIER = {
    "unit_step": 5,
    "discount_per_unit": 10,
    "hint": "Кожні 5 одиниць — -10 грн/шт. Калькулятор оновлюється миттєво.",
}

SIZE_GRID = ["XS", "S", "M", "L", "XL", "2XL"]

# ── Display labels (legacy + V2) ─────────────────────────────────────
ZONE_LABELS = {
    "front": "Спереду",
    "back": "На спині",
    "sleeve": "На рукаві",
    "custom": "Інша зона",
}

PRODUCT_LABELS = {
    "hoodie": "Худі",
    "tshirt": "Футболка",
    "longsleeve": "Лонгслів",
    "customer_garment": "Свій одяг",
}

FIT_LABELS = {
    "regular": "Класичний",
    "oversize": "Оверсайз",
}

FABRIC_LABELS = {
    "standard": "База",
    "premium": "Преміум",
}

SERVICE_LABELS = {
    "ready": "Готовий файл",
    "adjust": "Потрібно допрацювати",
    "design": "Потрібен дизайн",
}

TRIAGE_LABELS = {
    "print-ready": "Готовий до друку",
    "needs-work": "Потрібна підготовка",
    "reference-only": "Лише референс",
    "needs-review": "Потрібна перевірка",
}

# Legacy (kept for back-compat with old drafts / admin filters).
QUICK_START_MODES = [
    {
        "value": "start_blank",
        "label": "Почати з нуля",
        "hint": "Збираємо конфігурацію покроково: виріб, зони, стиль і контакт.",
    },
    {
        "value": "have_file",
        "label": "У мене є файл",
        "hint": "Фокус на перевірці макета, оцінці файлів і швидкому запуску в роботу.",
    },
    {
        "value": "starter_style",
        "label": "Показати стартові стилі",
        "hint": "Починаємо з кураторського напряму і швидко збираємо зрозумілий бриф.",
    },
]

CLIENT_MODES = [
    {
        "value": "personal",
        "label": "Для себе",
        "hint": "Один виріб або невелика серія без зайвої бюрократії.",
        "icon": "user",
    },
    {
        "value": "brand",
        "label": "Для команди / бренду",
        "hint": "Опт від 5 шт. Живий калькулятор знижок.",
        "icon": "brand",
    },
]

STARTER_STYLES = [
    {
        "value": "minimal",
        "label": "Мінімальний",
        "accent": "Чисті пропорції, один акцент, багато повітря.",
    },
    {
        "value": "bold",
        "label": "Сміливий",
        "accent": "Контрастні площини, великі композиції, більш помітний жест.",
    },
    {
        "value": "logo-first",
        "label": "Лого в центрі",
        "accent": "Логотип або короткий знак як центр всієї композиції.",
    },
]

ARTWORK_SERVICES = [
    {
        "value": "ready",
        "label": "Готовий файл",
        "price_delta": 0,
        "hint": "Ви вже маєте макет і хочете перейти до друку максимально швидко.",
        "badge": "0 грн",
    },
    {
        "value": "adjust",
        "label": "Потрібно допрацювати",
        "price_delta": 300,
        "hint": "Є файл або референс, але потрібна чистка, адаптація чи підготовка.",
        "badge": "+300 грн",
    },
    {
        "value": "design",
        "label": "Потрібен дизайн",
        "price_delta": 500,
        "hint": "Є ідея, вайб або референси, а ми допоможемо зібрати макет з нуля.",
        "badge": "+500 грн",
    },
]

TRIAGE_STATUSES = [
    {
        "value": "print-ready",
        "label": "Готовий до друку",
        "hint": "Файл виглядає готовим до друку без додаткової підготовки.",
    },
    {
        "value": "needs-work",
        "label": "Потрібна підготовка",
        "hint": "Потрібно підчистити, перевести у правильний формат або підготувати деталі.",
    },
    {
        "value": "reference-only",
        "label": "Лише референс",
        "hint": "Це референс, на основі якого ще треба зібрати робочий макет.",
    },
]

SIZE_MODES = [
    {"value": "single", "label": "Один розмір"},
    {"value": "mixed", "label": "Мікс розмірів"},
    {"value": "manager", "label": "Уточню з менеджером"},
]

CONTACT_CHANNELS = [
    {
        "value": "telegram",
        "label": "Telegram",
        "placeholder": "@username або https://t.me/username",
    },
    {
        "value": "whatsapp",
        "label": "WhatsApp",
        "placeholder": "+380...",
    },
    {
        "value": "phone",
        "label": "Телефон",
        "placeholder": "+380...",
    },
]

# ── Product matrix ───────────────────────────────────────────────────
PRODUCT_MATRIX = {
    "hoodie": {
        "label": "Худі",
        "eyebrow": "Головний сценарій",
        "summary": "Найглибший шлях: посадка, тканина, колір, зони і виробничі деталі.",
        "hero_note": "Найзручніший старт, якщо хочете точно зібрати худі під свій принт.",
        "fits": [
            {"value": "regular", "label": "Класичний", "description": "Базова посадка для щоденного мерчу."},
            {"value": "oversize", "label": "Оверсайз", "description": "Більш масивний силует з відчуттям преміум-речі."},
        ],
        "fabrics": {
            "regular": [
                {"value": "standard", "label": "База"},
                {"value": "premium", "label": "Преміум"},
            ],
            "oversize": [
                {"value": "premium", "label": "Преміум"},
            ],
        },
        "default_fit": "regular",
        "default_fabric": "premium",
        "colors": [
            {"value": "black", "label": "Чорний", "hex": "#151515"},
            {"value": "graphite", "label": "Графіт", "hex": "#3b3b3f"},
            {"value": "sand", "label": "Пісочний", "hex": "#c8b28d"},
            {"value": "bone", "label": "Світлий", "hex": "#ebe3d6"},
        ],
        "default_color": "black",
        "zones": ["front", "back", "sleeve"],
        "default_zones": [],
        "add_ons": [
            {
                "value": "lacing",
                "label": "Люверси зі шнурками",
                "price_delta": 300,
                "icon": "lacing",
                "badge": "+300 грн",
                "hint": "Преміум-апгрейд: металеві люверси й унікальні шнурки замість стандартних.",
            },
        ],
        "pricing": {
            "base": 1600,
            "premium_delta": 250,
            "oversize_delta": 200,
            "extra_zone_delta": 180,
            "add_on_delta": 0,  # V2: add-on prices are per-item via price_delta
        },
    },
    "tshirt": {
        "label": "Футболка",
        "eyebrow": "Швидкий старт",
        "summary": "Легший шлях без зайвої конфігурації.",
        "hero_note": "Швидкий варіант, якщо потрібен чистий старт з однією або двома зонами.",
        "fits": [],
        "fabrics": {},
        "default_fit": "",
        "default_fabric": "",
        "colors": [
            {"value": "black", "label": "Чорний", "hex": "#151515"},
            {"value": "white", "label": "Білий", "hex": "#f1ede6"},
            {"value": "graphite", "label": "Графіт", "hex": "#4a4a52"},
        ],
        "default_color": "black",
        "zones": ["front", "back"],
        "default_zones": [],
        "add_ons": [],
        "pricing": {
            "base": 700,
            "premium_delta": 0,
            "oversize_delta": 0,
            "extra_zone_delta": 150,
            "add_on_delta": 0,
        },
    },
    "longsleeve": {
        "label": "Лонгслів",
        "eyebrow": "Швидкий старт",
        "summary": "Помірно глибокий шлях між футболкою та худі.",
        "hero_note": "Підійде, якщо потрібен чистий фронт, спина або акцент на рукаві.",
        "fits": [],
        "fabrics": {},
        "default_fit": "",
        "default_fabric": "",
        "colors": [
            {"value": "black", "label": "Чорний", "hex": "#151515"},
            {"value": "bone", "label": "Світлий", "hex": "#e7ddcf"},
            {"value": "olive", "label": "Оливковий", "hex": "#59604a"},
        ],
        "default_color": "black",
        "zones": ["front", "back", "sleeve"],
        "default_zones": [],
        "add_ons": [],
        "pricing": {
            "base": 900,
            "premium_delta": 0,
            "oversize_delta": 0,
            "extra_zone_delta": 160,
            "add_on_delta": 0,
        },
    },
    "customer_garment": {
        "label": "Свій одяг",
        "eyebrow": "Через менеджера",
        "summary": "Менеджерський сценарій для вашого виробу з ручним прорахунком.",
        "hero_note": "Головне тут: опис виробу, зони і чітке формулювання задачі.",
        "fits": [],
        "fabrics": {},
        "default_fit": "",
        "default_fabric": "",
        "colors": [
            {"value": "own", "label": "Ваш колір", "hex": "#6d6d6d"},
        ],
        "default_color": "own",
        "zones": ["front", "back", "custom"],
        "default_zones": [],
        "add_ons": [],
        "pricing": {
            "base": None,
            "premium_delta": 0,
            "oversize_delta": 0,
            "extra_zone_delta": 0,
            "add_on_delta": 0,
        },
    },
}


def _coerce_int(value, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _coerce_price(value):
    if value in (None, ""):
        return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def _allowed_values(items):
    return {item["value"] for item in items}


def build_custom_print_config(*, submit_url: str, safe_exit_url: str, add_to_cart_url: str = "") -> dict:
    return {
        "version": 2,
        "storage_key": CUSTOM_PRINT_DRAFT_STORAGE_KEY,
        "submit_url": submit_url,
        "safe_exit_url": safe_exit_url,
        "add_to_cart_url": add_to_cart_url,
        "telegram_manager_url": TELEGRAM_MANAGER_URL,
        "quick_start_modes": deepcopy(QUICK_START_MODES),  # legacy
        "modes": deepcopy(CLIENT_MODES),
        "starter_styles": deepcopy(STARTER_STYLES),  # legacy
        "artwork_services": deepcopy(ARTWORK_SERVICES),
        "triage_statuses": deepcopy(TRIAGE_STATUSES),
        "size_modes": deepcopy(SIZE_MODES),
        "contact_channels": deepcopy(CONTACT_CHANNELS),
        "zone_labels": deepcopy(ZONE_LABELS),
        "product_labels": deepcopy(PRODUCT_LABELS),
        "products": deepcopy(PRODUCT_MATRIX),
        "gift_service": deepcopy(GIFT_SERVICE),
        "b2b_tier": deepcopy(B2B_TIER),
        "size_grid": list(SIZE_GRID),
        "defaults": normalize_custom_print_snapshot({}),
    }


def build_placement_specs(snapshot: dict) -> list[dict]:
    zones = list((snapshot.get("print") or {}).get("zones") or [])
    specs = []
    for index, zone in enumerate(zones):
        specs.append(
            {
                "zone": zone,
                "label": ZONE_LABELS.get(zone, zone),
                "variant": "standard" if index == 0 and zone in {"front", "back"} else "estimate",
                "is_free": index == 0 and zone in {"front", "back"},
                "format": "standard" if zone in {"front", "back"} else "custom",
                "size": "standard" if zone in {"front", "back"} else "manager_review",
                "file_index": index,
                "attachment_role": "design",
            }
        )
    return specs


def normalize_custom_print_snapshot(raw_snapshot: dict | None) -> dict:
    raw_snapshot = raw_snapshot or {}

    quick_start_mode = (raw_snapshot.get("quick_start_mode") or "start_blank").strip()
    if quick_start_mode not in _allowed_values(QUICK_START_MODES):
        quick_start_mode = "start_blank"

    mode = (raw_snapshot.get("mode") or "personal").strip()
    if mode not in {"personal", "brand"}:
        mode = "personal"

    product_payload = raw_snapshot.get("product") or {}
    product_type = (product_payload.get("type") or "hoodie").strip()
    if product_type not in PRODUCT_MATRIX:
        product_type = "hoodie"
    product_config = PRODUCT_MATRIX[product_type]

    fit = (product_payload.get("fit") or product_config.get("default_fit") or "").strip()
    fit_choices = {item["value"] for item in product_config.get("fits") or []}
    if fit_choices and fit not in fit_choices:
        fit = product_config.get("default_fit") or next(iter(fit_choices))
    if not fit_choices:
        fit = ""

    fabric_choices = {
        item["value"]
        for item in (product_config.get("fabrics") or {}).get(fit or product_config.get("default_fit") or "", [])
    }
    fabric = (product_payload.get("fabric") or product_config.get("default_fabric") or "").strip()
    if fabric_choices and fabric not in fabric_choices:
        fabric = next(iter(fabric_choices))
    if not fabric_choices:
        fabric = product_config.get("default_fabric", "")

    color_choices = {item["value"] for item in product_config.get("colors") or []}
    color = (product_payload.get("color") or product_config.get("default_color") or "").strip()
    if color_choices and color not in color_choices:
        color = product_config.get("default_color") or next(iter(color_choices))

    print_payload = raw_snapshot.get("print") or {}
    available_zones = set(product_config.get("zones") or [])
    zones = []
    for zone in print_payload.get("zones") or []:
        if zone in available_zones and zone not in zones:
            zones.append(zone)

    add_on_choices = {item["value"] for item in product_config.get("add_ons") or []}
    add_ons = []
    raw_add_ons = print_payload.get("add_ons") or []
    for add_on in raw_add_ons:
        # Legacy compat: old hoodie drafts with inside_label/hem_tag/grommets → collapse to lacing.
        if product_type == "hoodie" and add_on in {"inside_label", "hem_tag", "grommets"}:
            add_on = "lacing"
        if add_on in add_on_choices and add_on not in add_ons:
            add_ons.append(add_on)

    artwork_payload = raw_snapshot.get("artwork") or {}
    service_kind = (artwork_payload.get("service_kind") or "").strip()
    if service_kind not in SERVICE_LABELS:
        service_kind = ""

    files = []
    for index, item in enumerate(artwork_payload.get("files") or []):
        if not isinstance(item, dict):
            continue
        zone = item.get("zone")
        if zone not in available_zones:
            zone = zones[min(index, len(zones) - 1)] if zones else ""
        status = (item.get("status") or "").strip()
        if status not in TRIAGE_LABELS:
            status = "needs-review"
        files.append(
            {
                "name": str(item.get("name") or "").strip(),
                "zone": zone,
                "status": status,
                "role": str(item.get("role") or "design").strip() or "design",
            }
        )

    triage_status = (artwork_payload.get("triage_status") or "").strip()
    if triage_status not in TRIAGE_LABELS:
        if service_kind == "ready":
            triage_status = "print-ready" if files else "needs-review"
        elif service_kind == "adjust":
            triage_status = "needs-work"
        elif files:
            triage_status = "reference-only"
        else:
            triage_status = "needs-review"

    order_payload = raw_snapshot.get("order") or {}
    size_mode = (order_payload.get("size_mode") or "single").strip()
    if size_mode not in _allowed_values(SIZE_MODES):
        size_mode = "single"

    raw_size_breakdown = order_payload.get("size_breakdown") or {}
    if not isinstance(raw_size_breakdown, dict):
        raw_size_breakdown = {}
    size_breakdown = {}
    for key in SIZE_GRID:
        try:
            qty = int(raw_size_breakdown.get(key, 0) or 0)
        except (TypeError, ValueError):
            qty = 0
        if qty < 0:
            qty = 0
        size_breakdown[key] = qty

    gift_payload = order_payload.get("gift")
    if isinstance(gift_payload, dict):
        gift_enabled = bool(gift_payload.get("enabled"))
        gift_text = str(gift_payload.get("text") or "").strip()
    else:
        gift_enabled = bool(gift_payload)
        gift_text = str(order_payload.get("gift_text") or "").strip()

    contact_payload = raw_snapshot.get("contact") or {}
    channel = (contact_payload.get("channel") or "").strip()
    if channel not in _allowed_values(CONTACT_CHANNELS):
        channel = ""

    pricing_payload = raw_snapshot.get("pricing") or {}
    notes_payload = raw_snapshot.get("notes") or {}
    current_step = str(((raw_snapshot.get("ui") or {}).get("current_step") or "mode")).strip() or "mode"

    submission_type = (raw_snapshot.get("submission_type") or "lead").strip()
    if submission_type not in {"lead", "cart", "safe_exit"}:
        submission_type = "lead"

    return {
        "version": 2,
        "submission_type": submission_type,
        "quick_start_mode": quick_start_mode,
        "mode": mode,
        "starter_style": str(raw_snapshot.get("starter_style") or "").strip(),
        "product": {
            "type": product_type,
            "fit": fit,
            "fabric": fabric,
            "color": color,
        },
        "print": {
            "zones": zones,
            "add_ons": add_ons,
            "placement_note": str(print_payload.get("placement_note") or "").strip(),
        },
        "artwork": {
            "service_kind": service_kind,
            "triage_status": triage_status,
            "files": files,
        },
        "order": {
            "quantity": _coerce_int(order_payload.get("quantity"), 1),
            "size_mode": size_mode,
            "sizes_note": str(order_payload.get("sizes_note") or "").strip(),
            "size_breakdown": size_breakdown,
            "gift": gift_enabled,
            "gift_text": gift_text,
        },
        "contact": {
            "channel": channel,
            "name": str(contact_payload.get("name") or "").strip(),
            "value": str(contact_payload.get("value") or "").strip(),
        },
        "pricing": {
            "base_price": _coerce_price(pricing_payload.get("base_price")),
            "design_price": _coerce_price(pricing_payload.get("design_price")),
            "addons_price": _coerce_price(pricing_payload.get("addons_price")),
            "gift_price": _coerce_price(pricing_payload.get("gift_price")),
            "discount_percent": _coerce_price(pricing_payload.get("discount_percent")),
            "discount_amount": _coerce_price(pricing_payload.get("discount_amount")),
            "b2b_discount_per_unit": _coerce_price(pricing_payload.get("b2b_discount_per_unit")),
            "unit_total": _coerce_price(pricing_payload.get("unit_total")),
            "final_total": _coerce_price(pricing_payload.get("final_total")),
            "estimate_required": bool(pricing_payload.get("estimate_required")),
            "estimate_reason": str(pricing_payload.get("estimate_reason") or "").strip(),
        },
        "notes": {
            "brand_name": str(notes_payload.get("brand_name") or "").strip(),
            "brief": str(notes_payload.get("brief") or "").strip(),
            "garment_note": str(notes_payload.get("garment_note") or "").strip(),
        },
        "ui": {
            "current_step": current_step,
        },
    }


def compute_cart_label(snapshot: dict) -> str:
    product_type = ((snapshot.get("product") or {}).get("type") or "hoodie").strip()
    label = PRODUCT_LABELS.get(product_type, product_type or "Кастом")
    zones = [ZONE_LABELS.get(z, z) for z in ((snapshot.get("print") or {}).get("zones") or [])]
    suffix = f" · {', '.join(zones)}" if zones else ""
    return f"Кастом · {label}{suffix}"
