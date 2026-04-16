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

PROGRESS_STEPS = [
    {"value": "mode", "label": "Формат"},
    {"value": "product", "label": "Виріб"},
    {"value": "config", "label": "Налаштування"},
    {"value": "zones", "label": "Зони"},
    {"value": "artwork", "label": "Макет"},
    {"value": "quantity", "label": "Кількість"},
    {"value": "gift", "label": "Подарунок"},
    {"value": "contact", "label": "Контакт"},
]

FRONT_SIZE_PRESETS = [
    {"value": "A6", "label": "A6", "stage_scale": 0.44},
    {"value": "A5", "label": "A5", "stage_scale": 0.58},
    {"value": "A4", "label": "A4", "stage_scale": 0.74},
]
FRONT_SIZE_DEFAULT = "A4"

BACK_SIZE_PRESETS = [
    {"value": "A4", "label": "A4", "stage_scale": 0.62},
    {"value": "A3", "label": "A3", "stage_scale": 0.78},
    {"value": "A2", "label": "A2", "stage_scale": 0.92},
]
BACK_SIZE_DEFAULT = "A4"

SLEEVE_MODE_OPTIONS = [
    {"value": "a6", "label": "A6", "badge": "A6", "stage_scale": 0.42},
    {"value": "full_text", "label": "На весь рукав текстом", "badge": "Текст", "stage_scale": 0.94},
]
SLEEVE_MODE_DEFAULT = "a6"

STAGE_META = {
    "placeholder_title": "Виріб на сцені",
    "placeholder_note": "Оберіть виріб, щоб побачити сцену, зони і масштаб принта.",
}

# ── Display labels (legacy + V2) ─────────────────────────────────────
ZONE_LABELS = {
    "front": "Спереду",
    "back": "На спині",
    "sleeve": "На рукавах",
    "sleeve_left": "Лівий рукав",
    "sleeve_right": "Правий рукав",
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
    "thermo": "Термо",
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
        "price_delta": 150,
        "hint": "Є файл або референс, але потрібна чистка, адаптація чи підготовка.",
        "badge": "+150 грн",
    },
    {
        "value": "design",
        "label": "Потрібен дизайн",
        "price_delta": 300,
        "hint": "Є ідея, вайб або референси, а ми допоможемо зібрати макет з нуля.",
        "badge": "+300 грн",
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


def _svg_markup(*lines: str) -> str:
    return "\n".join(line.strip() for line in lines if line is not None).strip()


def _stage_box(x: float, y: float, width: float, height: float, rotate: float = 0, radius: float = 18, shape: str = "panel") -> dict:
    return {
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "rotate": rotate,
        "radius": radius,
        "shape": shape,
    }

ISO_SIZES = {
    "A6": (105, 148),
    "A5": (148, 210),
    "A4": (210, 297),
    "A3": (297, 420),
    "A2": (420, 594),
}

def calc_iso_box(format_key: str, body_width_mm: float, svg_body_width: float, svg_collar_y: float, top_offset_mm: float = 50, x_center: float = 50, radius: float = 24, shape: str = "panel", padding_mm: float = 0) -> dict:
    w_mm, h_mm = ISO_SIZES.get(format_key, (210, 297))
    scale = svg_body_width / body_width_mm
    
    box_w = (w_mm + padding_mm) * scale
    box_h = (h_mm + padding_mm) * scale
    
    y_start_svg = svg_collar_y + (top_offset_mm * scale)
    y_center_svg = y_start_svg + (box_h / 2.0)
    
    width_pct = (box_w / 420.0) * 100
    height_pct = (box_h / 520.0) * 100
    y_center_pct = (y_center_svg / 520.0) * 100
    
    return _stage_box(x_center, round(y_center_pct, 1), round(width_pct, 1), round(height_pct, 1), 0, radius, shape)



def _stage_anchor(button_x: float, button_y: float, *, presets: dict | None = None, modes: dict | None = None, default: dict | None = None) -> dict:
    payload = {
        "button": {
            "x": button_x,
            "y": button_y,
        },
    }
    if presets:
        payload["presets"] = presets
    if modes:
        payload["modes"] = modes
    if default:
        payload["default"] = default
    return payload

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
                {"value": "standard", "label": "База", "price_delta": 0, "included_in_base": True},
                {"value": "premium", "label": "Преміум", "price_delta": 250, "included_in_base": False},
            ],
            "oversize": [
                {"value": "premium", "label": "Преміум", "price_delta": 0, "included_in_base": True},
            ],
        },
        "default_fit": "regular",
        "default_fabric": "standard",
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
                "value": "fleece",
                "label": "З флісом",
                "price_delta": 0,
                "icon": "fleece",
                "group": "fleece"
            },
            {
                "value": "no_fleece",
                "label": "Без флісу",
                "price_delta": 0,
                "icon": "no_fleece",
                "group": "fleece"
            },
            {
                "value": "lacing",
                "label": "Люверси зі шнурками",
                "price_delta": 150,
                "icon": "lacing",
                "badge": "+150 грн",
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
        "summary": "Легкий виріб з окремим вибором посадки, тканини й принта на сцені.",
        "hero_note": "Швидкий варіант, якщо потрібна футболка з фронтом, спиною або принтом на рукаві.",
        "fits": [
            {"value": "regular", "label": "Класична", "description": "Рівна класична посадка для базового принта."},
            {"value": "oversize", "label": "Оверсайз", "description": "Більш вільний силует без додаткової анкети."},
        ],
        "fabrics": {
            "regular": [
                {"value": "standard", "label": "Стандарт", "price_delta": 0, "included_in_base": True},
                {"value": "premium", "label": "Преміум", "price_delta": 150, "included_in_base": False},
            ],
            "oversize": [
                {"value": "standard", "label": "Стандарт", "price_delta": 0, "included_in_base": True},
                {"value": "premium", "label": "Преміум", "price_delta": 150, "included_in_base": False},
                {
                    "value": "thermo", "label": "Термо", "price_delta": 500, "included_in_base": False,
                    "info_title": "Футболка з WOW-ефектом❤️",
                    "info_desc": "Реагує на тепло тіла та змінює колір.\nІдеальна для образів, які привертають увагу.",
                    "colors": [
                        {"value": "thermo_green", "label": "Зелений (Термо)", "hex": "#8ba38d"},
                        {"value": "thermo_pink", "label": "Рожевий (Термо)", "hex": "#e78ba7"}
                    ]
                },
            ],
        },
        "default_fit": "regular",
        "default_fabric": "premium",
        "colors": [
            {"value": "black", "label": "Чорний", "hex": "#151515"},
            {"value": "white", "label": "Білий", "hex": "#f1ede6"},
            {"value": "graphite", "label": "Графіт", "hex": "#4a4a52"},
        ],
        "default_color": "black",
        "zones": ["front", "back"],
        "default_zones": [],
                "add_ons": [
            {
                "value": "ribbed_neck",
                "label": "Щільна горловина (Рібана)",
                "price_delta": 0,
                "icon": "ribbed_neck",
                "badge": "Включено",
                "hint": "Еластична горловина, що довго не втрачає форму.",
                "auto_include_condition": "premium_or_oversize"
            },
            {
                "value": "twill_tape",
                "label": "Кіперна стрічка",
                "price_delta": 0,
                "icon": "twill_tape",
                "badge": "Включено",
                "hint": "Укріплення задньої частини шиї, підвищений комфорт.",
                "auto_include_condition": "premium_or_oversize"
            }
        ],
        "pricing": {
            "base": 700,
            "premium_delta": 0,
            "thermo_delta": 500,
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
                "add_ons": [
            {
                "value": "ribbed_neck",
                "label": "Щільна горловина (Рібана)",
                "price_delta": 0,
                "icon": "ribbed_neck",
                "badge": "Включено",
                "hint": "Еластична горловина, що довго не втрачає форму.",
                "auto_include_condition": "premium_or_oversize"
            },
            {
                "value": "twill_tape",
                "label": "Кіперна стрічка",
                "price_delta": 0,
                "icon": "twill_tape",
                "badge": "Включено",
                "hint": "Укріплення задньої частини шиї, підвищений комфорт.",
                "auto_include_condition": "premium_or_oversize"
            }
        ],
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
                "add_ons": [
            {
                "value": "ribbed_neck",
                "label": "Щільна горловина (Рібана)",
                "price_delta": 0,
                "icon": "ribbed_neck",
                "badge": "Включено",
                "hint": "Еластична горловина, що довго не втрачає форму.",
                "auto_include_condition": "premium_or_oversize"
            },
            {
                "value": "twill_tape",
                "label": "Кіперна стрічка",
                "price_delta": 0,
                "icon": "twill_tape",
                "badge": "Включено",
                "hint": "Укріплення задньої частини шиї, підвищений комфорт.",
                "auto_include_condition": "premium_or_oversize"
            }
        ],
        "pricing": {
            "base": None,
            "premium_delta": 0,
            "oversize_delta": 0,
            "extra_zone_delta": 0,
            "add_on_delta": 0,
        },
    },
}


STAGE_PROFILES = {
    "tshirt": {
        "default_fit": "regular",
        "regular": {
            "front": {
                "view_box": "0 0 420 520",
                "svg_markup": _svg_markup(
                    "<path class='cp-stage-svg__part cp-stage-svg__part--shade' d='M80 150 C50 160 30 180 20 220 L30 320 C40 330 60 330 80 320 L100 220 L100 450 C100 480 120 490 210 490 C300 490 320 480 320 450 L320 220 L340 320 C360 330 380 330 390 320 L400 220 C390 180 370 160 340 150 L280 120 C240 140 180 140 140 120 Z'/>",
                    "<path class='cp-stage-svg__part cp-stage-svg__part--base' d='M100 150 C130 180 160 190 210 190 C260 190 290 180 320 150 L340 160 C320 220 320 250 320 450 C320 480 290 490 210 490 C130 490 100 480 100 450 C100 250 100 220 80 160 Z'/>",
                    "<path class='cp-stage-svg__part cp-stage-svg__part--top' d='M140 120 C160 150 180 160 210 160 C240 160 260 150 280 120 C260 100 160 100 140 120 Z'/>",
                    "<path class='cp-stage-svg__detail cp-stage-svg__detail--line' d='M140 120 C160 140 180 150 210 150 C240 150 260 140 280 120'/>",
                    "<path class='cp-stage-svg__detail cp-stage-svg__detail--line' d='M120 470 H300'/>",
                ),
                "anchors": {
                    "front": _stage_anchor(
                        50,
                        40,
                        presets={
                            "A6": calc_iso_box("A6", body_width_mm=550, svg_body_width=220, svg_collar_y=160, top_offset_mm=210, x_center=65, radius=16),
                            "A5": calc_iso_box("A5", body_width_mm=550, svg_body_width=220, svg_collar_y=160, top_offset_mm=260, radius=18),
                            "A4": calc_iso_box("A4", body_width_mm=550, svg_body_width=220, svg_collar_y=160, top_offset_mm=280, radius=20),
                        },
                    ),
                    "sleeve_left": _stage_anchor(25, 45, modes={"a6": _stage_box(30, 48, 12, 18, 0, 16, "sleeve_patch")}),
                    "sleeve_right": _stage_anchor(75, 45, modes={"a6": _stage_box(70, 48, 12, 18, 0, 16, "sleeve_patch")})
                },
            },
            "back": {
                "view_box": "0 0 420 520",
                "svg_markup": _svg_markup(
                    "<path class='cp-stage-svg__part cp-stage-svg__part--shade' d='M80 150 C50 160 30 180 20 220 L30 320 C40 330 60 330 80 320 L100 220 L100 450 C100 480 120 490 210 490 C300 490 320 480 320 450 L320 220 L340 320 C360 330 380 330 390 320 L400 220 C390 180 370 160 340 150 L280 120 C240 140 180 140 140 120 Z'/>",
                    "<path class='cp-stage-svg__part cp-stage-svg__part--base' d='M100 150 C130 130 160 120 210 120 C260 120 290 130 320 150 L340 160 C320 220 320 250 320 450 C320 480 290 490 210 490 C130 490 100 480 100 450 C100 250 100 220 80 160 Z'/>",
                    "<path class='cp-stage-svg__part cp-stage-svg__part--top' d='M140 120 C160 130 180 140 210 140 C240 140 260 130 280 120 C260 100 160 100 140 120 Z'/>",
                    "<path class='cp-stage-svg__detail cp-stage-svg__detail--line' d='M140 120 C160 130 180 135 210 135 C240 135 260 130 280 120'/>",
                    "<path class='cp-stage-svg__detail cp-stage-svg__detail--line' d='M120 470 H300'/>",
                ),
                "anchors": {
                    "back": _stage_anchor(
                        50,
                        40,
                        presets={
                            "A4": calc_iso_box("A4", body_width_mm=550, svg_body_width=220, svg_collar_y=135, top_offset_mm=260, radius=20),
                            "A3": calc_iso_box("A3", body_width_mm=550, svg_body_width=220, svg_collar_y=135, top_offset_mm=290, radius=21),
                            "A2": calc_iso_box("A2", body_width_mm=550, svg_body_width=220, svg_collar_y=135, top_offset_mm=320, radius=22),
                        },
                    ),
                    "sleeve_left": _stage_anchor(25, 45, modes={"a6": _stage_box(30, 48, 12, 18, 0, 16, "sleeve_patch")}),
                    "sleeve_right": _stage_anchor(75, 45, modes={"a6": _stage_box(70, 48, 12, 18, 0, 16, "sleeve_patch")})
                },
            },
        },
        "oversize": {
            "front": {
                "view_box": "0 0 420 520",
                "svg_markup": _svg_markup(
                    "<path class='cp-stage-svg__part cp-stage-svg__part--shade' d='M60 150 C30 160 10 180 5 220 L15 360 C25 370 45 370 65 360 L85 240 L85 450 C85 480 105 490 210 490 C315 490 335 480 335 450 L335 240 L355 360 C375 370 395 370 405 360 L415 220 C410 180 390 160 360 150 L280 120 C240 140 180 140 140 120 Z'/>",
                    "<path class='cp-stage-svg__part cp-stage-svg__part--base' d='M85 150 C115 180 145 190 210 190 C275 190 305 180 335 150 L355 160 C335 240 335 270 335 450 C335 480 305 490 210 490 C115 490 85 480 85 450 C85 270 85 240 65 160 Z'/>",
                    "<path class='cp-stage-svg__part cp-stage-svg__part--top' d='M140 120 C160 150 180 160 210 160 C240 160 260 150 280 120 C260 100 160 100 140 120 Z'/>",
                    "<path class='cp-stage-svg__detail cp-stage-svg__detail--line' d='M140 120 C160 140 180 150 210 150 C240 150 260 140 280 120'/>",
                    "<path class='cp-stage-svg__detail cp-stage-svg__detail--line' d='M105 470 H315'/>",
                ),
                "anchors": {
                    "front": _stage_anchor(
                        50,
                        40,
                        presets={
                            "A6": calc_iso_box("A6", body_width_mm=600, svg_body_width=250, svg_collar_y=160, top_offset_mm=210, x_center=65, radius=16),
                            "A5": calc_iso_box("A5", body_width_mm=600, svg_body_width=250, svg_collar_y=160, top_offset_mm=260, radius=18),
                            "A4": calc_iso_box("A4", body_width_mm=600, svg_body_width=250, svg_collar_y=160, top_offset_mm=280, radius=20),
                        },
                    ),
                    "sleeve_left": _stage_anchor(20, 45, modes={"a6": _stage_box(25, 48, 12, 18, 0, 16, "sleeve_patch")}),
                    "sleeve_right": _stage_anchor(80, 45, modes={"a6": _stage_box(75, 48, 12, 18, 0, 16, "sleeve_patch")})
                },
            },
            "back": {
                "view_box": "0 0 420 520",
                "svg_markup": _svg_markup(
                    "<path class='cp-stage-svg__part cp-stage-svg__part--shade' d='M60 150 C30 160 10 180 5 220 L15 360 C25 370 45 370 65 360 L85 240 L85 450 C85 480 105 490 210 490 C315 490 335 480 335 450 L335 240 L355 360 C375 370 395 370 405 360 L415 220 C410 180 390 160 360 150 L280 120 C240 140 180 140 140 120 Z'/>",
                    "<path class='cp-stage-svg__part cp-stage-svg__part--base' d='M85 150 C115 130 145 120 210 120 C275 120 305 130 335 150 L355 160 C335 240 335 270 335 450 C335 480 305 490 210 490 C115 490 85 480 85 450 C85 270 85 240 65 160 Z'/>",
                    "<path class='cp-stage-svg__part cp-stage-svg__part--top' d='M140 120 C160 130 180 140 210 140 C240 140 260 130 280 120 C260 100 160 100 140 120 Z'/>",
                    "<path class='cp-stage-svg__detail cp-stage-svg__detail--line' d='M140 120 C160 130 180 135 210 135 C240 135 260 130 280 120'/>",
                    "<path class='cp-stage-svg__detail cp-stage-svg__detail--line' d='M105 470 H315'/>",
                ),
                "anchors": {
                    "back": _stage_anchor(
                        50,
                        40,
                        presets={
                            "A4": calc_iso_box("A4", body_width_mm=600, svg_body_width=250, svg_collar_y=135, top_offset_mm=260, radius=20),
                            "A3": calc_iso_box("A3", body_width_mm=600, svg_body_width=250, svg_collar_y=135, top_offset_mm=290, radius=21),
                            "A2": calc_iso_box("A2", body_width_mm=600, svg_body_width=250, svg_collar_y=135, top_offset_mm=320, radius=22),
                        },
                    ),
                    "sleeve_left": _stage_anchor(20, 45, modes={"a6": _stage_box(25, 48, 12, 18, 0, 16, "sleeve_patch")}),
                    "sleeve_right": _stage_anchor(80, 45, modes={"a6": _stage_box(75, 48, 12, 18, 0, 16, "sleeve_patch")})
                },
            },
        },
    },
    "hoodie": {
        "default_fit": "regular",
        "regular": {
            "front": {
                "view_box": "0 0 420 520",
                "svg_markup": _svg_markup(
                    "<path class='cp-stage-svg__part cp-stage-svg__part--shade' d='M126 130 C95 140 69 163 54 194 C40 223 35 264 39 308 C41 330 54 346 74 348 C89 349 101 341 108 328 L136 170 C139 156 136 141 126 130 Z'/>",
                    "<path class='cp-stage-svg__part cp-stage-svg__part--shade' d='M294 130 C325 140 351 163 366 194 C380 223 385 264 381 308 C379 330 366 346 346 348 C331 349 319 341 312 328 L284 170 C281 156 284 141 294 130 Z'/>",
                    "<path class='cp-stage-svg__part cp-stage-svg__part--base' d='M138 132 C158 108 183 94 210 94 C237 94 262 108 282 132 L294 148 C306 160 312 176 311 193 L302 446 C301 468 284 486 262 486 H158 C136 486 119 468 118 446 L109 193 C108 176 114 160 126 148 Z'/>",
                    "<path class='cp-stage-svg__part cp-stage-svg__part--top' d='M154 138 C156 98 179 66 210 66 C241 66 264 98 266 138 C255 150 241 158 226 162 H194 C179 158 165 150 154 138 Z'/>",
                    "<path class='cp-stage-svg__detail cp-stage-svg__detail--line' d='M175 154 C185 147 197 144 210 144 C223 144 235 147 245 154'/>",
                    "<path class='cp-stage-svg__detail cp-stage-svg__detail--line' d='M145 312 C163 303 186 298 210 298 C234 298 257 303 275 312'/>",
                    "<path class='cp-stage-svg__detail cp-stage-svg__detail--line' d='M162 314 C155 344 152 375 152 408 H268 C268 375 265 344 258 314'/>",
                    "<path class='cp-stage-svg__detail cp-stage-svg__detail--line' d='M147 473 H273'/>",
                ),
                "anchors": {
                    "front": _stage_anchor(
                        50,
                        42.5,
                        presets={
                            "A6": calc_iso_box("A6", body_width_mm=600, svg_body_width=204, svg_collar_y=138, top_offset_mm=230, x_center=58, radius=18),
                            "A5": calc_iso_box("A5", body_width_mm=600, svg_body_width=204, svg_collar_y=138, top_offset_mm=280, radius=19),
                            "A4": calc_iso_box("A4", body_width_mm=600, svg_body_width=204, svg_collar_y=138, top_offset_mm=280, radius=20),
                        },
                    ),
                    "sleeve_left": _stage_anchor(
                        27.5,
                        45.5,
                        modes={
                            "a6": _stage_box(28.5, 47.8, 10.4, 15.8, 21, 16, "sleeve_patch"),
                            "full_text": _stage_box(24.8, 55.8, 8.2, 35.5, 19, 18, "sleeve_text"),
                        },
                    ),
                    "sleeve_right": _stage_anchor(
                        72.5,
                        45.5,
                        modes={
                            "a6": _stage_box(71.5, 47.8, 10.4, 15.8, -21, 16, "sleeve_patch"),
                            "full_text": _stage_box(75.2, 55.8, 8.2, 35.5, -19, 18, "sleeve_text"),
                        },
                    ),
                },
            },
            "back": {
                "view_box": "0 0 420 520",
                "svg_markup": _svg_markup(
                    "<path class='cp-stage-svg__part cp-stage-svg__part--shade' d='M124 136 C95 149 72 172 59 202 C47 230 42 271 46 314 C49 336 61 351 80 354 C95 356 106 348 112 335 L132 178 C135 163 133 147 124 136 Z'/>",
                    "<path class='cp-stage-svg__part cp-stage-svg__part--shade' d='M296 136 C325 149 348 172 361 202 C373 230 378 271 374 314 C371 336 359 351 340 354 C325 356 314 348 308 335 L288 178 C285 163 287 147 296 136 Z'/>",
                    "<path class='cp-stage-svg__part cp-stage-svg__part--base' d='M134 140 C154 119 181 108 210 108 C239 108 266 119 286 140 L296 152 C307 164 312 180 311 196 L302 446 C301 468 284 486 262 486 H158 C136 486 119 468 118 446 L109 196 C108 180 113 164 124 152 Z'/>",
                    "<path class='cp-stage-svg__part cp-stage-svg__part--top' d='M152 139 C160 107 182 86 210 86 C238 86 260 107 268 139 L248 163 C237 171 224 175 210 175 C196 175 183 171 172 163 Z'/>",
                    "<path class='cp-stage-svg__detail cp-stage-svg__detail--line' d='M176 178 C186 184 198 187 210 187 C222 187 234 184 244 178'/>",
                    "<path class='cp-stage-svg__detail cp-stage-svg__detail--line' d='M143 472 H277'/>",
                    "<path class='cp-stage-svg__detail cp-stage-svg__detail--line' d='M141 228 C162 214 186 208 210 208 C234 208 258 214 279 228'/>",
                ),
                "anchors": {
                    "back": _stage_anchor(
                        50,
                        44.5,
                        presets={
                            "A4": calc_iso_box("A4", body_width_mm=600, svg_body_width=204, svg_collar_y=140, top_offset_mm=380, radius=22),
                            "A3": calc_iso_box("A3", body_width_mm=600, svg_body_width=204, svg_collar_y=140, top_offset_mm=380, radius=22),
                            "A2": calc_iso_box("A2", body_width_mm=600, svg_body_width=204, svg_collar_y=140, top_offset_mm=380, radius=24),
                        },
                    ),
                    "sleeve_left": _stage_anchor(
                        27.2,
                        46.2,
                        modes={
                            "a6": _stage_box(27.2, 49.6, 10.5, 16.2, -19, 16, "sleeve_patch"),
                            "full_text": _stage_box(24.5, 57.4, 8.2, 36.2, -17, 18, "sleeve_text"),
                        },
                    ),
                    "sleeve_right": _stage_anchor(
                        72.8,
                        46.2,
                        modes={
                            "a6": _stage_box(72.8, 49.6, 10.5, 16.2, 19, 16, "sleeve_patch"),
                            "full_text": _stage_box(75.5, 57.4, 8.2, 36.2, 17, 18, "sleeve_text"),
                        },
                    ),
                },
            },
        },
        "oversize": {
            "front": {
                "view_box": "0 0 420 520",
                "svg_markup": _svg_markup(
                    "<path class='cp-stage-svg__part cp-stage-svg__part--shade' d='M108 152 C66 163 32 191 14 229 C-1 262 -5 302 0 342 C3 366 18 382 42 386 C63 389 81 380 91 364 L124 196 C129 177 124 162 108 152 Z'/>",
                    "<path class='cp-stage-svg__part cp-stage-svg__part--shade' d='M312 152 C354 163 388 191 406 229 C421 262 425 302 420 342 C417 366 402 382 378 386 C357 389 339 380 329 364 L296 196 C291 177 296 162 312 152 Z'/>",
                    "<path class='cp-stage-svg__part cp-stage-svg__part--base' d='M118 152 C145 124 177 110 210 110 C243 110 275 124 302 152 L318 170 C334 187 341 208 339 230 L328 452 C327 475 307 492 284 492 H136 C113 492 93 475 92 452 L81 230 C79 208 86 187 102 170 Z'/>",
                    "<path class='cp-stage-svg__part cp-stage-svg__part--top' d='M145 154 C150 104 176 70 210 70 C244 70 270 104 275 154 C262 168 246 177 229 180 H191 C174 177 158 168 145 154 Z'/>",
                    "<path class='cp-stage-svg__detail cp-stage-svg__detail--line' d='M169 173 C182 164 196 160 210 160 C224 160 238 164 251 173'/>",
                    "<path class='cp-stage-svg__detail cp-stage-svg__detail--line' d='M138 320 C161 309 185 304 210 304 C235 304 259 309 282 320'/>",
                    "<path class='cp-stage-svg__detail cp-stage-svg__detail--line' d='M163 323 C154 355 151 386 151 418 H269 C269 386 266 355 257 323'/>",
                    "<path class='cp-stage-svg__detail cp-stage-svg__detail--line' d='M141 478 H279'/>",
                ),
                "anchors": {
                    "front": _stage_anchor(
                        50,
                        43.8,
                        presets={
                            "A6": calc_iso_box("A6", body_width_mm=650, svg_body_width=220, svg_collar_y=154, top_offset_mm=230, x_center=58, radius=18),
                            "A5": calc_iso_box("A5", body_width_mm=650, svg_body_width=220, svg_collar_y=154, top_offset_mm=280, radius=19),
                            "A4": calc_iso_box("A4", body_width_mm=650, svg_body_width=220, svg_collar_y=154, top_offset_mm=280, radius=21),
                        },
                    ),
                    "sleeve_left": _stage_anchor(
                        24.5,
                        47.5,
                        modes={
                            "a6": _stage_box(25.2, 50.2, 10.8, 16.8, 23, 17, "sleeve_patch"),
                            "full_text": _stage_box(21.6, 58.2, 8.4, 38.4, 20, 18, "sleeve_text"),
                        },
                    ),
                    "sleeve_right": _stage_anchor(
                        75.5,
                        47.5,
                        modes={
                            "a6": _stage_box(74.8, 50.2, 10.8, 16.8, -23, 17, "sleeve_patch"),
                            "full_text": _stage_box(78.4, 58.2, 8.4, 38.4, -20, 18, "sleeve_text"),
                        },
                    ),
                },
            },
            "back": {
                "view_box": "0 0 420 520",
                "svg_markup": _svg_markup(
                    "<path class='cp-stage-svg__part cp-stage-svg__part--shade' d='M106 158 C68 172 38 198 22 234 C8 267 4 307 9 347 C12 370 27 386 50 390 C69 393 85 385 94 370 L121 202 C126 183 121 168 106 158 Z'/>",
                    "<path class='cp-stage-svg__part cp-stage-svg__part--shade' d='M314 158 C352 172 382 198 398 234 C412 267 416 307 411 347 C408 370 393 386 370 390 C351 393 335 385 326 370 L299 202 C294 183 299 168 314 158 Z'/>",
                    "<path class='cp-stage-svg__part cp-stage-svg__part--base' d='M116 158 C144 132 177 118 210 118 C243 118 276 132 304 158 L319 174 C334 190 341 210 339 231 L328 452 C327 475 307 492 284 492 H136 C113 492 93 475 92 452 L81 231 C79 210 86 190 101 174 Z'/>",
                    "<path class='cp-stage-svg__part cp-stage-svg__part--top' d='M144 160 C154 118 179 92 210 92 C241 92 266 118 276 160 L252 184 C239 193 225 197 210 197 C195 197 181 193 168 184 Z'/>",
                    "<path class='cp-stage-svg__detail cp-stage-svg__detail--line' d='M172 195 C184 203 197 206 210 206 C223 206 236 203 248 195'/>",
                    "<path class='cp-stage-svg__detail cp-stage-svg__detail--line' d='M143 476 H277'/>",
                    "<path class='cp-stage-svg__detail cp-stage-svg__detail--line' d='M134 236 C159 219 184 212 210 212 C236 212 261 219 286 236'/>",
                ),
                "anchors": {
                    "back": _stage_anchor(
                        50,
                        45.8,
                        presets={
                            "A4": calc_iso_box("A4", body_width_mm=650, svg_body_width=220, svg_collar_y=140, top_offset_mm=380, radius=20),
                            "A3": calc_iso_box("A3", body_width_mm=650, svg_body_width=220, svg_collar_y=140, top_offset_mm=380, radius=21),
                            "A2": calc_iso_box("A2", body_width_mm=650, svg_body_width=220, svg_collar_y=140, top_offset_mm=380, radius=22),
                        },
                    ),
                    "sleeve_left": _stage_anchor(
                        24.2,
                        48.4,
                        modes={
                            "a6": _stage_box(24.5, 52.0, 11.0, 17.1, -20, 17, "sleeve_patch"),
                            "full_text": _stage_box(21.4, 60.4, 8.4, 39.0, -18, 18, "sleeve_text"),
                        },
                    ),
                    "sleeve_right": _stage_anchor(
                        75.8,
                        48.4,
                        modes={
                            "a6": _stage_box(75.5, 52.0, 11.0, 17.1, 20, 17, "sleeve_patch"),
                            "full_text": _stage_box(78.6, 60.4, 8.4, 39.0, 18, 18, "sleeve_text"),
                        },
                    ),
                },
            },
        },
    },
    }
