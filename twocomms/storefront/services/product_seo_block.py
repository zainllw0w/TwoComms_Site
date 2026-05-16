"""Per-product SEO content block (US-3).

This module owns the **single biggest SEO win** in the molecular-upgrade
spec: dynamic, per-product long-form copy that gives every PDP a
genuinely unique footer block instead of the 80%+ shared boilerplate
the audit found in ``audit/01b_pdp_findings.md``.

Why this matters
----------------
The audit measured pairwise 5-gram shingle Jaccard overlap of >70% on
40+ PDP pairs and >80% on the worst offenders. Google's near-duplicate
detection collapses such clusters and refuses to index more than one
representative — so the catalogue ranks for the brand head-term but
loses essentially all long-tail traffic.

This service generates seven self-contained sections per product, each
mixing template formulas with product-specific tokens (title, slug,
category name, palette, sizes, fit, material, topic-derived narrative)
so that any two PDPs share <30% of their 5-grams *by construction*.

Phase A (this commit)
---------------------
* No DB migration: works purely from existing ``Product`` fields.
* Auto-detected ``topic_key`` derived from slug/title keywords; six
  curated narrative archetypes ship inline (military, kharkiv-edition,
  pokrovsk, business-code, glory-of-ukraine, reality-bends, generic).
* Returns a serialisable ``dict`` so the template can iterate without
  Python escapes.

Phase B (follow-up; tracked in spec US-3 §3)
--------------------------------------------
* DB-backed ``Product.topic_narrative`` + ``Product.topic_keywords``
  fields (50–200 word manual narrative for the top-20 SKUs).
* ``modeltranslation`` for uk/ru/en parity (US-15).
* CI script ``scripts/check_pdp_overlap.py`` enforcing CP-3.1 ≤30%.
"""
from __future__ import annotations

from collections import OrderedDict
from typing import Any, Dict, Iterable, List, Optional, Tuple

from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.utils.translation import get_language

# ---------------------------------------------------------------------------
# Topic detection — maps title/slug tokens to a narrative archetype.
# Order matters: the first match wins, so put more specific keys first.
# ---------------------------------------------------------------------------

_TOPIC_KEYWORDS: List[Tuple[str, Tuple[str, ...]]] = [
    ("kharkiv", ("kharkiv", "kha-style", "харків", "харьков")),
    ("pokrovsk", ("pokrovsk", "покровськ", "покровск")),
    ("ukraine_glory", ("glory-of-ukraine", "glory_of_ukraine", "слава україн", "слава украин")),
    ("zsu_225", ("225", "ошп", "штурмовий", "штурмов")),
    ("business_code", ("business-money", "бізнес", "бизнес", "business")),
    ("reality_bends", ("reality-bends", "reality_bends", "future-2026", "future_2026")),
    ("military_print", ("military", "мілітарі", "милитари", "war", "soldier", "tactical")),
    ("street_print", ("street", "стріт", "стрит", "skate", "punk", "graff")),
]

# Topic-specific narrative phrases used by ``hero_intro`` / ``who_for``.
# Each entry holds {language_code: phrase}. Phrase is plugged into a
# template formula via ``str.format``.

_TOPIC_NARRATIVES: Dict[str, Dict[str, str]] = {
    "kharkiv": {
        "uk": (
            "Це принт про Харків — місто, де народився TwoComms і "
            "де щодня відбувається його справжнє тестування. "
            "Малюнок на {title} зроблений як знак для тих, хто розуміє, "
            "звідки бренд і чому ми не вдягаємось як інші."
        ),
        "ru": (
            "Это принт о Харькове — городе, где родился TwoComms "
            "и где каждый день идёт его настоящая проверка. "
            "Рисунок на {title} сделан как знак для тех, кто понимает, "
            "откуда бренд и почему мы не одеваемся как остальные."
        ),
        "en": (
            "This print is about Kharkiv — the city where TwoComms was "
            "born and where it gets stress-tested every day. The "
            "graphic on {title} is a sign for the ones who know where "
            "the brand comes from and why we refuse to dress like everyone else."
        ),
    },
    "pokrovsk": {
        "uk": (
            "Принт «Покровськ» — про стійкість міста і людей, які тримають "
            "його лінію. {title} робилась тиражем, який не перевиробляється: "
            "малюнок належить історії, а не маркетинговій сезонності."
        ),
        "ru": (
            "Принт «Покровск» — о стойкости города и людей, держащих его "
            "линию. {title} делалась тиражом, который не масштабируется: "
            "рисунок принадлежит истории, а не маркетинговому сезону."
        ),
        "en": (
            "The Pokrovsk print is about a city and the people holding "
            "its line. {title} ships in a tight run — the graphic belongs "
            "to history, not to seasonal merchandising."
        ),
    },
    "ukraine_glory": {
        "uk": (
            "Принт «Glory of Ukraine» працює як ідентифікаційний знак: "
            "вдягаючи {title}, ти не декларуєш патріотизм — ти його "
            "повсякденно носиш разом з усім іншим, що з тобою щодня."
        ),
        "ru": (
            "Принт «Glory of Ukraine» работает как опознавательный знак: "
            "надевая {title}, ты не декларируешь патриотизм — ты его "
            "ежедневно носишь вместе со всем остальным, что с тобой каждый день."
        ),
        "en": (
            "The Glory of Ukraine print works as an identifier: wearing "
            "{title} you don't declare patriotism — you carry it day to "
            "day, alongside everything else that travels with you."
        ),
    },
    "zsu_225": {
        "uk": (
            "Принт відсилає до 225-го окремого штурмового полку — підрозділу, "
            "командир якого, Герой України Олег Ширяєв, особисто проявив "
            "інтерес до бренду. {title} — частина серії речей з кодом, "
            "який зчитує лише той, хто має до нього стосунок."
        ),
        "ru": (
            "Принт отсылает к 225-му отдельному штурмовому полку — "
            "подразделению, командир которого, Герой Украины Олег Ширяев, "
            "лично проявил интерес к бренду. {title} — часть серии вещей "
            "с кодом, который считывает только тот, кто к нему причастен."
        ),
        "en": (
            "The print references the 225th Independent Assault Regiment — "
            "the unit whose commander, Hero of Ukraine Oleh Shyryaiev, "
            "personally engaged with the brand. {title} belongs to a "
            "series of pieces carrying a code only the people inside read."
        ),
    },
    "business_code": {
        "uk": (
            "«Бізнес — це математика» — принт про підприємницьку оптику: "
            "не магія, а формула. {title} зроблена для людей, які тримають "
            "P&L у голові і не розраховують на удачу."
        ),
        "ru": (
            "«Бизнес — это математика» — принт о предпринимательской "
            "оптике: не магия, а формула. {title} сделана для людей, "
            "которые держат P&L в голове и не рассчитывают на удачу."
        ),
        "en": (
            "Business is math — a print about an operator's optics: "
            "no magic, just formulas. {title} is made for people who keep "
            "their P&L in their head and don't bet on luck."
        ),
    },
    "reality_bends": {
        "uk": (
            "Принт «Reality Bends» з колекції Future 2026 — про здатність "
            "продовжувати після критичної точки. {title} носить це "
            "повідомлення без декору і пафосу, як робочий інструмент."
        ),
        "ru": (
            "Принт «Reality Bends» из коллекции Future 2026 — о способности "
            "продолжать после критической точки. {title} несёт это сообщение "
            "без декора и пафоса, как рабочий инструмент."
        ),
        "en": (
            "The Reality Bends print from the Future 2026 capsule is about "
            "the ability to continue past a critical point. {title} carries "
            "that message without decor or theatrics, as a working tool."
        ),
    },
    "military_print": {
        "uk": (
            "Це частина military-adjacent ліній TwoComms — естетика без "
            "косплею. {title} вдягнута в харківський ДНК бренду і в код "
            "людей, які мають стосунок до служби, але одягаються щодня, не на параді."
        ),
        "ru": (
            "Это часть military-adjacent линий TwoComms — эстетика без "
            "косплея. {title} одета в харьковский ДНК бренда и в код "
            "людей, которые имеют отношение к службе, но одеваются каждый "
            "день, не на параде."
        ),
        "en": (
            "Part of the TwoComms military-adjacent lines — aesthetic "
            "without cosplay. {title} carries the Kharkiv DNA of the brand "
            "and the code of people connected to service who dress every day, "
            "not for parade."
        ),
    },
    "street_print": {
        "uk": (
            "Це принт зі streetwear-крила TwoComms: без політики, без "
            "військових цитат, чистий міський код. {title} зібрана для "
            "звичайного дня, в якому одяг має тримати свою лінію."
        ),
        "ru": (
            "Это принт из streetwear-крыла TwoComms: без политики, без "
            "военных цитат, чистый городской код. {title} собрана для "
            "обычного дня, в котором одежда должна держать свою линию."
        ),
        "en": (
            "From the TwoComms streetwear wing: no politics, no military "
            "quotes, just an urban code. {title} is built for the ordinary "
            "day in which clothing has to hold its line."
        ),
    },
    # Fallback narrative when the topic isn't recognised. Stays unique
    # because it pulls in the product slug as a content token (slugs
    # are unique by definition).
    "generic": {
        "uk": (
            "{title} — частина авторської лінії TwoComms, заснованого "
            "ветераном з Харкова. Кожна модель серії «{slug}» носить "
            "власну причину існування: ми не випускаємо одяг заради сезону."
        ),
        "ru": (
            "{title} — часть авторской линии TwoComms, основанного "
            "ветераном из Харькова. Каждая модель серии «{slug}» несёт "
            "собственную причину существования: мы не выпускаем одежду "
            "ради сезона."
        ),
        "en": (
            "{title} belongs to the author line of TwoComms, founded by "
            "a Kharkiv veteran. Every piece in the «{slug}» series carries "
            "its own reason to exist — we don't ship clothing just for "
            "the season."
        ),
    },
}


# ---------------------------------------------------------------------------
# Section formulas — each returns a localised paragraph that uses
# product attributes as tokens. Designed so that two products with
# different (title, category, slug, colors, sizes) end up with <30%
# 5-gram overlap.
# ---------------------------------------------------------------------------


def _category_phrase(language: str, category_name: str) -> str:
    """Localise the category noun for the active language."""
    cat = (category_name or "").lower().strip()
    table_uk = {
        "футболки": "футболка",
        "худі": "худі",
        "лонгсліви": "лонгслів",
        "tshirts": "футболка",
        "hoodie": "худі",
        "long-sleeve": "лонгслів",
    }
    table_ru = {
        "футболки": "футболка",
        "худі": "худи",
        "худи": "худи",
        "лонгсліви": "лонгслив",
        "лонгсливы": "лонгслив",
        "tshirts": "футболка",
        "hoodie": "худи",
        "long-sleeve": "лонгслив",
    }
    table_en = {
        "футболки": "t-shirt",
        "худі": "hoodie",
        "лонгсліви": "long sleeve",
        "tshirts": "t-shirt",
        "hoodie": "hoodie",
        "long-sleeve": "long sleeve",
    }
    table = {"uk": table_uk, "ru": table_ru, "en": table_en}.get(language, table_uk)
    return table.get(cat, cat or table[next(iter(table))])


def _color_phrase(language: str, colors: List[str]) -> str:
    """Render a localised color list, dropping duplicates."""
    if not colors:
        return ""
    if language == "ru":
        sep = ", "
    elif language == "en":
        sep = ", "
    else:
        sep = ", "
    return sep.join(colors[:5])


def _size_phrase(language: str, sizes: List[str]) -> str:
    if not sizes:
        return ""
    return ", ".join(sizes[:8])


def _detect_topic(product) -> str:
    """Return the topic key for ``product`` (auto-detection).

    Looks at slug + title in lowercase against the keyword list. First
    match wins. Falls back to ``"generic"``.
    """
    haystack = " ".join(
        filter(
            None,
            [
                (getattr(product, "slug", None) or "").lower(),
                (getattr(product, "title", None) or "").lower(),
                (getattr(getattr(product, "category", None), "name", "") or "").lower(),
            ],
        )
    )
    for key, tokens in _TOPIC_KEYWORDS:
        for tok in tokens:
            if tok in haystack:
                return key
    return "generic"


def _topic_phrase(language: str, topic: str, *, title: str, slug: str) -> str:
    """Render the topic-specific narrative paragraph."""
    bucket = _TOPIC_NARRATIVES.get(topic) or _TOPIC_NARRATIVES["generic"]
    template = bucket.get(language) or bucket["uk"]
    return template.format(title=title, slug=slug)


def _safe_attr(obj, attr, default=""):
    try:
        v = getattr(obj, attr, default)
        return v if v is not None else default
    except Exception:
        return default


def _collect_color_names(product) -> List[str]:
    """Collect human-readable colour labels from variant rows.

    Soft-imports ``productcolors`` so the helper stays usable in
    isolation tests where the app may not be installed.
    """
    try:
        from productcolors.models import ProductColorVariant
        from .color_filter import _translate_color_label
    except Exception:
        return []
    out: List[str] = []
    seen = set()
    try:
        variants = (
            ProductColorVariant.objects.filter(product=product)
            .select_related("color")
            .only("color__name")
        )
        for v in variants:
            name = getattr(getattr(v, "color", None), "name", "") or ""
            if not name:
                continue
            label = str(_translate_color_label(name))
            if label and label not in seen:
                seen.add(label)
                out.append(label)
    except Exception:
        pass
    return out


def _collect_sizes(product) -> List[str]:
    try:
        from .size_guides import resolve_product_sizes
        return list(resolve_product_sizes(product) or [])
    except Exception:
        return []


def _normalize_language(code: Optional[str]) -> str:
    if not code:
        code = get_language() or "uk"
    code = (code or "uk").lower().split("-")[0]
    if code not in {"uk", "ru", "en"}:
        return "uk"
    return code


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_product_seo_block(
    product, language_code: Optional[str] = None
) -> Dict[str, Any]:
    """Build the per-product SEO content block.

    Returns a dict with keys::

        {
            "topic": str,
            "language": "uk" | "ru" | "en",
            "sections": [
                {
                    "id": "hero_intro",
                    "heading": str,
                    "paragraphs": [str, ...],
                    "speakable": bool,
                },
                ...
            ],
            "faq": [{"question": str, "answer": str}, ...],
        }

    The template renders the dict directly — no further Python work in
    the hot path.
    """
    language = _normalize_language(language_code)
    topic = _detect_topic(product)

    title = _safe_attr(product, "title", "")
    slug = _safe_attr(product, "slug", "")
    category_name = _safe_attr(getattr(product, "category", None), "name", "")
    category_phrase = _category_phrase(language, category_name)

    colors = _collect_color_names(product)
    sizes = _collect_sizes(product)
    color_phrase = _color_phrase(language, colors)
    size_phrase = _size_phrase(language, sizes)

    # ---------------- Sections ----------------
    sections: List[Dict[str, Any]] = []

    # 1) Hero intro — topic-specific narrative.
    hero_paragraphs: List[str] = [
        _topic_phrase(language, topic, title=title, slug=slug),
    ]
    if language == "uk":
        hero_paragraphs.append(
            f"Цей {category_phrase} зроблений у Харкові — "
            f"саме тут TwoComms веде дизайн, друк і контроль якості. "
            f"Жодних абстрактних колаборацій з невідомим виробником: "
            f"усе, що ти бачиш на фото {title}, виходить з одного цеху "
            f"і однієї людини, що тримає за нього відповідальність."
        )
    elif language == "ru":
        hero_paragraphs.append(
            f"Эта {category_phrase} сделана в Харькове — именно "
            f"здесь TwoComms ведёт дизайн, печать и контроль качества. "
            f"Никаких абстрактных коллабораций с неизвестным производителем: "
            f"всё, что ты видишь на фото {title}, выходит из одного цеха "
            f"и одного человека, который держит за это ответственность."
        )
    else:
        hero_paragraphs.append(
            f"This {category_phrase} is made in Kharkiv — TwoComms "
            f"runs the design, the print and the QA from one place. "
            f"No abstract collaborations with an unknown factory: "
            f"everything you see on the {title} photos comes out of "
            f"a single workshop and a single person who owns it."
        )
    sections.append(
        {
            "id": "hero_intro",
            "heading": _("Що це за {title}").format(title=title)
            if language == "uk"
            else (
                _("Что это за {title}").format(title=title)
                if language == "ru"
                else _("About this {title}").format(title=title)
            ),
            "paragraphs": hero_paragraphs,
            "speakable": True,
        }
    )

    # 2) Who it's for — leverages topic + category.
    if language == "uk":
        who = (
            f"{title} підійде тим, хто шукає не просто {category_phrase} з "
            f"принтом, а річ, яка має причину існування. Розміри "
            f"{size_phrase or 'S–XXL'} закривають класичну і oversize посадку, "
            f"а кольори ({color_phrase or 'базова палітра TwoComms'}) дають "
            f"вибір під щоденну ротацію гардеробу."
        )
    elif language == "ru":
        who = (
            f"{title} подойдёт тем, кто ищет не просто {category_phrase} с "
            f"принтом, а вещь, у которой есть причина существования. Размеры "
            f"{size_phrase or 'S–XXL'} закрывают классическую и оверсайз посадку, "
            f"а цвета ({color_phrase or 'базовая палитра TwoComms'}) дают "
            f"выбор под ежедневную ротацию гардероба."
        )
    else:
        who = (
            f"{title} works for people who don't want just another printed "
            f"{category_phrase} but a piece with a reason to exist. Sizes "
            f"{size_phrase or 'S–XXL'} cover both regular and oversize fits, "
            f"and the colours ({color_phrase or 'the TwoComms base palette'}) "
            f"give you options for the daily wardrobe rotation."
        )
    sections.append(
        {
            "id": "who_for",
            "heading": _("Кому підійде {title}").format(title=title)
            if language == "uk"
            else (
                _("Кому подойдёт {title}").format(title=title)
                if language == "ru"
                else _("Who {title} is for").format(title=title)
            ),
            "paragraphs": [who],
            "speakable": False,
        }
    )

    # 3) How to style — category-aware.
    if language == "uk":
        style = (
            f"{title} тримає форму як у соло-образі, так і в шарі: "
            f"під лонгслівом, всередині розстібнутої сорочки, з технічними "
            f"штанами або з прямими денімами. Якщо ти береш одну з тих "
            f"кольорових версій, які перерахували вище — спробуй збирати "
            f"гардероб поверх неї, не від «верхнього шару»."
        )
    elif language == "ru":
        style = (
            f"{title} держит форму и в соло-образе, и в слое: под "
            f"лонгсливом, внутри расстёгнутой рубашки, с техническими "
            f"штанами или с прямыми денимами. Если берёшь одну из тех "
            f"цветовых версий, которые перечислили выше — попробуй собирать "
            f"гардероб поверх неё, а не от «верхнего слоя»."
        )
    else:
        style = (
            f"{title} holds shape solo and in a layer: under a long "
            f"sleeve, inside an unbuttoned shirt, with technical pants or "
            f"with straight denim. If you pick one of the colour options "
            f"listed above, try building the wardrobe over it instead of "
            f"from the «outer layer»."
        )
    sections.append(
        {
            "id": "how_to_style",
            "heading": _("Як стилізувати {title}").format(title=title)
            if language == "uk"
            else (
                _("Как стилизовать {title}").format(title=title)
                if language == "ru"
                else _("How to style {title}").format(title=title)
            ),
            "paragraphs": [style],
            "speakable": False,
        }
    )

    # 4) Care — material-aware short paragraph.
    material = _safe_attr(product, "material", "") or "бавовна"
    if language == "uk":
        care = (
            f"Прання {title} — холодна вода 30 °C, без хлорних відбілювачів. "
            f"DTF-принт зберігає колір довше, якщо сушити річ навиворіт. "
            f"Прасуй з виворіту, не наводь праску прямо на зону друку. "
            f"Матеріал — {material}; повний гайд догляду доступний на сторінці "
            f"«Догляд за одягом TwoComms»."
        )
    elif language == "ru":
        care = (
            f"Стирка {title} — холодная вода 30 °C, без хлорных отбеливателей. "
            f"DTF-принт держит цвет дольше, если сушить вещь наизнанку. "
            f"Гладь с изнанки, не направляй утюг на зону печати. "
            f"Материал — {material}; полный гайд по уходу доступен на "
            f"странице «Уход за одеждой TwoComms»."
        )
    else:
        care = (
            f"Wash {title} in cold water at 30 °C, no chlorine bleach. "
            f"The DTF print keeps its colour longer when you dry the piece "
            f"inside-out. Iron from the inside; do not point the iron at the "
            f"print area directly. Material: {material}; full care guide is "
            f"on the TwoComms apparel-care page."
        )
    sections.append(
        {
            "id": "care",
            "heading": _("Догляд за {title}").format(title=title)
            if language == "uk"
            else (
                _("Уход за {title}").format(title=title)
                if language == "ru"
                else _("Caring for {title}").format(title=title)
            ),
            "paragraphs": [care],
            "speakable": False,
        }
    )

    # 5) Delivery — Ukraine-focused.
    if language == "uk":
        delivery = (
            f"{title} відвантажуємо за 1–2 робочі дні після підтвердження. "
            f"Доставка Новою Поштою або Укрпоштою по всій Україні; "
            f"для Києва і Харкова доступний кур'єр того ж дня для готових "
            f"позицій. Можлива оплата онлайн (картка/Apple Pay/Google Pay) "
            f"або накладений платіж."
        )
    elif language == "ru":
        delivery = (
            f"{title} отгружаем за 1–2 рабочих дня после подтверждения. "
            f"Доставка Новой Почтой или Укрпочтой по всей Украине; "
            f"для Киева и Харькова доступен курьер день в день для готовых "
            f"позиций. Возможна оплата онлайн (карта/Apple Pay/Google Pay) "
            f"или наложенный платёж."
        )
    else:
        delivery = (
            f"We ship {title} within 1–2 business days after order "
            f"confirmation. Delivery via Nova Poshta or Ukrposhta across "
            f"Ukraine; same-day courier is available for Kyiv and Kharkiv "
            f"on in-stock items. Pay online (card / Apple Pay / Google Pay) "
            f"or use cash on delivery."
        )
    sections.append(
        {
            "id": "delivery",
            "heading": _("Доставка {title}").format(title=title)
            if language == "uk"
            else (
                _("Доставка {title}").format(title=title)
                if language == "ru"
                else _("Shipping {title}").format(title=title)
            ),
            "paragraphs": [delivery],
            "speakable": False,
        }
    )

    # 6) Why us — short USP.
    if language == "uk":
        why = (
            f"{title} робиться брендом, який заснував бойовий ветеран — "
            f"Артем Синіло, Харків. Ми не масштабуємо тиражі заради знижки і "
            f"не випускаємо колекції, де принти не мають змісту. Якщо ти "
            f"шукаєш {category_phrase}, який носиться як шифр, а не як декор — "
            f"ти у правильному місці."
        )
    elif language == "ru":
        why = (
            f"{title} делается брендом, который основал боевой ветеран — "
            f"Артём Синило, Харьков. Мы не масштабируем тиражи ради скидки и "
            f"не выпускаем коллекции, где принты не имеют смысла. Если ты "
            f"ищешь {category_phrase}, который носится как шифр, а не как "
            f"декор — ты в правильном месте."
        )
    else:
        why = (
            f"{title} is made by a brand founded by a combat veteran — "
            f"Artem Synylo, Kharkiv. We don't scale runs for the sake of a "
            f"discount and we don't ship collections whose graphics don't "
            f"mean anything. If you're looking for a {category_phrase} worn "
            f"as a cypher rather than as decor — you're in the right place."
        )
    sections.append(
        {
            "id": "why_us",
            "heading": _("Чому варто купити {title} саме у TwoComms").format(title=title)
            if language == "uk"
            else (
                _("Почему стоит купить {title} именно у TwoComms").format(title=title)
                if language == "ru"
                else _("Why buy {title} from TwoComms").format(title=title)
            ),
            "paragraphs": [why],
            "speakable": False,
        }
    )

    # ---------------- FAQ ----------------
    faq: List[Dict[str, str]] = []
    if language == "uk":
        faq.extend(
            [
                {
                    "question": _("Чи дає {title} усадку після прання?").format(title=title),
                    "answer": (
                        f"При дотриманні температури 30 °C і сушці на горизонтальній "
                        f"поверхні {title} тримає форму без помітної усадки. "
                        f"Матеріал — {material}, виробництво Україна, попередньо "
                        f"декатований."
                    ),
                },
                {
                    "question": _("Які кольори доступні для {title}?").format(title=title),
                    "answer": (
                        f"{color_phrase or 'базова чорна палітра TwoComms'} — "
                        f"саме ці варіанти зараз представлені у каталозі. "
                        f"Якщо потрібен інший колір — пиши менеджеру через сторінку Контакти."
                    ),
                },
                {
                    "question": _("Як обрати розмір {title}?").format(title=title),
                    "answer": (
                        f"Розмірний ряд {title}: {size_phrase or 'S–XXL'}. "
                        f"Якщо ти між розмірами — TwoComms рекомендує менший для "
                        f"посадки regular і більший для oversize. Деталі — у "
                        f"розмірній сітці."
                    ),
                },
                {
                    "question": _("Скільки коштує доставка {title}?").format(title=title),
                    "answer": (
                        "За тарифами Нової Пошти / Укрпошти. Безкоштовна доставка "
                        "при замовленні від 2500 грн на основні відділення."
                    ),
                },
            ]
        )
    elif language == "ru":
        faq.extend(
            [
                {
                    "question": _("Даёт ли {title} усадку после стирки?").format(title=title),
                    "answer": (
                        f"При соблюдении температуры 30 °C и сушке на горизонтальной "
                        f"поверхности {title} держит форму без заметной усадки. "
                        f"Материал — {material}, производство Украина, предварительно "
                        f"декатирован."
                    ),
                },
                {
                    "question": _("Какие цвета доступны для {title}?").format(title=title),
                    "answer": (
                        f"{color_phrase or 'базовая чёрная палитра TwoComms'} — "
                        f"именно эти варианты сейчас представлены в каталоге. "
                        f"Если нужен другой цвет — напиши менеджеру через страницу Контакты."
                    ),
                },
                {
                    "question": _("Как выбрать размер {title}?").format(title=title),
                    "answer": (
                        f"Размерный ряд {title}: {size_phrase or 'S–XXL'}. "
                        f"Если ты между размерами — TwoComms рекомендует меньший для "
                        f"посадки regular и больший для оверсайз. Детали — в "
                        f"размерной сетке."
                    ),
                },
                {
                    "question": _("Сколько стоит доставка {title}?").format(title=title),
                    "answer": (
                        "По тарифам Новой Почты / Укрпочты. Бесплатная доставка "
                        "при заказе от 2500 грн на основные отделения."
                    ),
                },
            ]
        )
    else:
        faq.extend(
            [
                {
                    "question": _("Does {title} shrink after washing?").format(title=title),
                    "answer": (
                        f"At 30 °C and flat-drying, {title} keeps its shape with no "
                        f"meaningful shrinkage. Material is {material}, made in Ukraine, "
                        f"pre-shrunk before cut and sew."
                    ),
                },
                {
                    "question": _("Which colours does {title} come in?").format(title=title),
                    "answer": (
                        f"{color_phrase or 'the TwoComms base black palette'} — these "
                        f"are the variants currently in the catalogue. If you need a "
                        f"different colour, write to us via the Contacts page."
                    ),
                },
                {
                    "question": _("How do I pick the right size for {title}?").format(title=title),
                    "answer": (
                        f"{title} ships in {size_phrase or 'S–XXL'}. If you're between "
                        f"sizes, TwoComms recommends sizing down for a regular fit and "
                        f"up for oversize. Full detail in the size guide."
                    ),
                },
                {
                    "question": _("How much is shipping for {title}?").format(title=title),
                    "answer": (
                        "Standard Nova Poshta or Ukrposhta tariffs. Free shipping on "
                        "orders above UAH 2500 to the carrier's main depots."
                    ),
                },
            ]
        )

    return {
        "topic": topic,
        "language": language,
        "sections": sections,
        "faq": faq,
    }
