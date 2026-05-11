"""Phase 19g (2026-05-10) — colour-aware long-form SEO copy for catalog screens.

Covers three contexts (a single service so the catalog view has one
entry point):

1. ``/catalog/`` (no category, no colour) — brand-level catalogue
   landing copy with internal links to all three category pages +
   the most stocked colour filters.

2. ``/catalog/?color=<slug>`` (cross-category colour filter) — copy
   focused on the chosen colour with internal links into every
   category filtered by the same colour.

3. ``/catalog/<category>/?color=<slug>`` (category × colour) — copy
   focused on the category-colour intersection (e.g. *чорне худі*),
   with HF / MF / LF query chips and links to the alternative
   categories of the same colour.

Each block returns ``{h2, paragraphs, queries}`` where ``queries`` is
``[{label, url, freq: 'hf'|'mf'|'lf'}]``. The template renders the
paragraphs as ``<p>`` and the queries as a chip strip. Copy is
written by hand — no AI generation runtime — to guarantee that the
text is unique per (category, colour) cell and never collides with
the per-category description (Phase 10 / 10b).

The catalog view passes a ``color_seo_copy`` context variable; the
template (``partials/catalog_color_seo.html``) renders it inside the
existing ``catalog-category-description`` panel so the styling stays
consistent with per-category descriptions.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from django.utils.translation import gettext_lazy as _


# ---------------------------------------------------------------------------
# Curated palettes. Hand-written copy for the colours the catalogue
# stocks most: чорний, кайот, олива, сірий, білий. Other colours fall
# back to a templated paragraph that still carries category links and
# a sensible chip strip — never empty.
# ---------------------------------------------------------------------------

_BLACK = {
    "name_uk": "чорний",
    "name_uk_adj_n": "чорне",        # худі
    "name_uk_adj_f": "чорна",        # футболка
    "name_uk_adj_m": "чорний",       # лонгслів
    "name_uk_adj_pl": "чорні",       # принти
    "tone_paragraph": (
        "Чорний — найуніверсальніший колір у гардеробі вуличного стилю: "
        "він не сперечається з принтом, легко комбінується з джинсами, карго "
        "й мілітарі-аксесуарами, і однаково доречний у місті, на концерті чи "
        "у форматі smart-casual. У TwoComms ми друкуємо принти на щільному "
        "чорному поліci так, щоб композиція не «світилася» через тканину навіть "
        "після десятка прань — це різниця між дешевим мерчем і одягом, "
        "який служить роками."
    ),
    "queries_seed": [
        # high-frequency
        ("Купити чорне худі", "/catalog/hoodie/?color=black", "hf"),
        ("Чорна футболка з принтом", "/catalog/tshirts/?color=black", "hf"),
        ("Чорний лонгслів", "/catalog/long-sleeve/?color=black", "hf"),
        # mid-frequency
        ("Чорне худі ЗСУ", "/catalog/hoodie/?color=black", "mf"),
        ("Чорна футболка унісекс", "/catalog/tshirts/?color=black", "mf"),
        ("Чорний український стрітвір", "/catalog/?color=black", "mf"),
        # long-tail
        ("Чорне худі з тризубом купити Київ", "/catalog/hoodie/?color=black", "lf"),
        ("Чорна футболка з патріотичним принтом", "/catalog/tshirts/?color=black", "lf"),
        ("Чорний лонгслів мілітарі стиль", "/catalog/long-sleeve/?color=black", "lf"),
        ("Чорний одяг донат ЗСУ", "/catalog/?color=black", "lf"),
    ],
}

_COYOTE = {
    "name_uk": "кайот",
    "name_uk_adj_n": "кайотове",
    "name_uk_adj_f": "кайотова",
    "name_uk_adj_m": "кайотовий",
    "name_uk_adj_pl": "кайотові",
    "tone_paragraph": (
        "Кайот — мілітарний відтінок, який поєднує тепло пісочного та "
        "стриманість оливи. Це саме той колір, що носять військові, "
        "інженери та люди, які цінують дискретність у вуличному вбранні. "
        "TwoComms друкує принти на кайоті з підвищеним контрастом, щоб "
        "графіка читалася навіть у похмуру погоду, а самі тканини добираємо "
        "щільніші: вони витримують щоденні навантаження, не «дають усадки» "
        "після першого прання й залишаються в кольорі без вицвітання."
    ),
    "queries_seed": [
        ("Купити кайотове худі", "/catalog/hoodie/?color=coyote", "hf"),
        ("Кайотова футболка ЗСУ", "/catalog/tshirts/?color=coyote", "hf"),
        ("Кайотовий лонгслів", "/catalog/long-sleeve/?color=coyote", "hf"),
        ("Худі мілітарі кайот", "/catalog/hoodie/?color=coyote", "mf"),
        ("Футболка кайот унісекс", "/catalog/tshirts/?color=coyote", "mf"),
        ("Кайотовий одяг донат", "/catalog/?color=coyote", "mf"),
        ("Кайотове худі з тризубом купити Харків", "/catalog/hoodie/?color=coyote", "lf"),
        ("Кайотова футболка з патріотичним принтом ЗСУ", "/catalog/tshirts/?color=coyote", "lf"),
        ("Подарунок захиснику кайот мерч", "/catalog/?color=coyote", "lf"),
    ],
}

_OLIVE = {
    "name_uk": "олива",
    "name_uk_adj_n": "оливкове",
    "name_uk_adj_f": "оливкова",
    "name_uk_adj_m": "оливковий",
    "name_uk_adj_pl": "оливкові",
    "tone_paragraph": (
        "Оливковий — класичний мілітарний колір, який стає основою для "
        "патріотичного стрітверу і чудово грає з графікою у білих, "
        "кайотових і червоних акцентах. Олива не вицвітає на сонці так "
        "швидко, як темно-зелені фарби, тому одяг у цьому кольорі довго "
        "тримає товарний вигляд. Усі моделі TwoComms у оливі — це "
        "100% бавовна або щільні поліcі без синтетичного блиску."
    ),
    "queries_seed": [
        ("Купити оливкове худі", "/catalog/hoodie/?color=olive", "hf"),
        ("Оливкова футболка з принтом", "/catalog/tshirts/?color=olive", "hf"),
        ("Оливковий лонгслів", "/catalog/long-sleeve/?color=olive", "hf"),
        ("Худі олива ЗСУ", "/catalog/hoodie/?color=olive", "mf"),
        ("Оливкова футболка унісекс", "/catalog/tshirts/?color=olive", "mf"),
        ("Олива одяг український бренд", "/catalog/?color=olive", "mf"),
        ("Оливкове худі мілітарі стиль", "/catalog/hoodie/?color=olive", "lf"),
        ("Оливкова футболка з тризубом", "/catalog/tshirts/?color=olive", "lf"),
        ("Оливковий лонгслів streetwear купити", "/catalog/long-sleeve/?color=olive", "lf"),
    ],
}

_GREY = {
    "name_uk": "сірий",
    "name_uk_adj_n": "сіре",
    "name_uk_adj_f": "сіра",
    "name_uk_adj_m": "сірий",
    "name_uk_adj_pl": "сірі",
    "tone_paragraph": (
        "Сірий — нейтральна база, яка робить будь-який принт "
        "виразнішим і не втомлює око. Його легко «зчитувати» з джинсами, "
        "хакі-штанами або чорними карго, тому сірі худі й футболки "
        "TwoComms лідирують у замовленнях у міжсезоння. Ми тримаємо два "
        "відтінки — світлий меланж і темний графіт — щоб клієнт міг "
        "обрати посадку під свій тон шкіри й освітлення."
    ),
    "queries_seed": [
        ("Купити сіре худі", "/catalog/hoodie/?color=grey", "hf"),
        ("Сіра футболка з принтом", "/catalog/tshirts/?color=grey", "hf"),
        ("Сірий лонгслів", "/catalog/long-sleeve/?color=grey", "hf"),
        ("Худі сірий меланж", "/catalog/hoodie/?color=grey", "mf"),
        ("Футболка сіра унісекс", "/catalog/tshirts/?color=grey", "mf"),
        ("Сірий стрітвір TwoComms", "/catalog/?color=grey", "mf"),
        ("Сіре худі з тризубом купити Україна", "/catalog/hoodie/?color=grey", "lf"),
        ("Сіра футболка ЗСУ донат", "/catalog/tshirts/?color=grey", "lf"),
        ("Сірий лонгслів патріотичний принт", "/catalog/long-sleeve/?color=grey", "lf"),
    ],
}

_WHITE = {
    "name_uk": "білий",
    "name_uk_adj_n": "біле",
    "name_uk_adj_f": "біла",
    "name_uk_adj_m": "білий",
    "name_uk_adj_pl": "білі",
    "tone_paragraph": (
        "Білий — колір, що не пробачає компромісів у якості друку: "
        "слабка фарба «втрачається», а пухкий сітч-друк дає матовий "
        "відбиток, який швидко вицвітає. TwoComms друкує на білому "
        "технологією DTF з повним нанесенням базового шару, тому "
        "ілюстрації виглядають насиченими навіть на фото у "
        "природному світлі. Білий ідеальний для фотоконтенту в "
        "Instagram і для весняно-літнього вуличного стилю."
    ),
    "queries_seed": [
        ("Купити білу футболку з принтом", "/catalog/tshirts/?color=white", "hf"),
        ("Біле худі", "/catalog/hoodie/?color=white", "hf"),
        ("Білий лонгслів", "/catalog/long-sleeve/?color=white", "hf"),
        ("Біла футболка ЗСУ", "/catalog/tshirts/?color=white", "mf"),
        ("Худі біле жіноче", "/catalog/hoodie/?color=white", "mf"),
        ("Білий одяг український бренд", "/catalog/?color=white", "mf"),
        ("Біла футболка з тризубом купити Львів", "/catalog/tshirts/?color=white", "lf"),
        ("Біле худі з патріотичним принтом", "/catalog/hoodie/?color=white", "lf"),
        ("Білий лонгслів streetwear купити", "/catalog/long-sleeve/?color=white", "lf"),
    ],
}

_CURATED: Dict[str, Dict[str, Any]] = {
    "black": _BLACK,
    "coyote": _COYOTE,
    "olive": _OLIVE,
    "grey": _GREY,
    "gray": _GREY,
    "white": _WHITE,
}


# ---------------------------------------------------------------------------
# Generic colour fallback. Used when the colour slug isn't curated above
# (e.g. "navy" or any unique shade). Pulls the human-readable colour
# name from the chip data passed in by the view so we don't print the
# slug to end users.
# ---------------------------------------------------------------------------

def _generic_color_copy(color_slug: str, color_label: str) -> Dict[str, Any]:
    label = (color_label or color_slug or "вибраний").strip()
    label_lower = label.lower()
    return {
        "name_uk": label_lower,
        "name_uk_adj_n": label_lower,
        "name_uk_adj_f": label_lower,
        "name_uk_adj_m": label_lower,
        "name_uk_adj_pl": label_lower,
        "tone_paragraph": (
            f"Колір «{label}» у каталозі TwoComms — це вибір для тих, "
            "хто хоче відійти від базової палітри, але не готовий "
            "поступатися якістю принту. Ми друкуємо на цьому відтінку "
            "DTF-технологією з підвищеним базовим шаром, тому ілюстрація "
            "не «провалюється» у тон тканини й залишається насиченою "
            "після десятків прань."
        ),
        "queries_seed": [
            (f"Купити {label_lower} худі", f"/catalog/hoodie/?color={color_slug}", "hf"),
            (f"{label.capitalize()} футболка з принтом",
             f"/catalog/tshirts/?color={color_slug}", "hf"),
            (f"{label.capitalize()} лонгслів",
             f"/catalog/long-sleeve/?color={color_slug}", "hf"),
            (f"{label.capitalize()} стрітвір TwoComms",
             f"/catalog/?color={color_slug}", "mf"),
            (f"{label.capitalize()} одяг ЗСУ донат",
             f"/catalog/?color={color_slug}", "mf"),
            (f"{label.capitalize()} футболка з тризубом купити Україна",
             f"/catalog/tshirts/?color={color_slug}", "lf"),
            (f"{label.capitalize()} худі з патріотичним принтом",
             f"/catalog/hoodie/?color={color_slug}", "lf"),
        ],
    }


# ---------------------------------------------------------------------------
# General catalog (no category, no colour). Brand-level landing copy.
# ---------------------------------------------------------------------------

GENERAL_CATALOG_SEO_COPY: Dict[str, Any] = {
    "h2": _("Каталог одягу TwoComms — український стрітвір з характером"),
    "paragraphs": [
        _(
            "TwoComms — це український бренд одягу, який створює стрітвір "
            "у трьох ключових категоріях: <a href=\"/catalog/hoodie/\">худі</a>, "
            "<a href=\"/catalog/tshirts/\">футболки</a> й "
            "<a href=\"/catalog/long-sleeve/\">лонгсліви</a>. Усі моделі ми "
            "розробляємо в Україні, друкуємо принти на власному обладнанні "
            "за технологією DTF і підбираємо тканини так, щоб одяг витримував "
            "щоденне носіння, прання й любий клімат — від літньої спеки до "
            "сирої осені."
        ),

        _(
            "Кожен товар у каталозі доступний у кількох кольорах: класичний "
            "<a href=\"/catalog/?color=black\">чорний</a> для тих, хто шукає "
            "універсальну базу під будь-який принт; "
            "<a href=\"/catalog/?color=coyote\">кайот</a> і "
            "<a href=\"/catalog/?color=olive\">олива</a> для прихильників "
            "мілітарної естетики; нейтральний "
            "<a href=\"/catalog/?color=grey\">сірий</a> і чистий "
            "<a href=\"/catalog/?color=white\">білий</a> для весняно-літніх "
            "образів. Усі кольори перевіряються на стійкість до УФ та "
            "перфектне зберігання форми навіть після 30+ циклів прання."
        ),

        _(
            "Більшість принтів TwoComms — це авторські ілюстрації на тему "
            "патріотизму, ЗСУ, української історії та сучасної поп-культури. "
            "Ми передаємо частину прибутку на підтримку Збройних Сил України, "
            "тому кожна покупка — це одночасно вибір якісного одягу й вклад у "
            "перемогу. На сторінці кожного товару ви знайдете розмірну сітку, "
            "детальні фото матеріалу, відгуки клієнтів і прозору інформацію "
            "про склад тканини."
        ),

        _(
            "Якщо ви не знайшли потрібну графіку — спробуйте розділ "
            "<a href=\"/custom-print/\">«Власний принт»</a>: ми надрукуємо "
            "будь-яку ілюстрацію на обраній моделі від однієї одиниці. "
            "Доставка по Україні — Новою Поштою на відділення або в "
            "поштомат за 1–2 дні. Оплата — карткою через Monobank/LiqPay "
            "або накладеним платежем. Усі товари мають 14 днів на повернення, "
            "якщо не підійшов розмір."
        ),
    ],
    "queries": [
        # HF
        {"label": "Купити худі", "url": "/catalog/hoodie/", "freq": "hf"},
        {"label": "Купити футболку з принтом", "url": "/catalog/tshirts/", "freq": "hf"},
        {"label": "Купити лонгслів", "url": "/catalog/long-sleeve/", "freq": "hf"},
        {"label": "Український стрітвір", "url": "/catalog/", "freq": "hf"},
        # MF
        {"label": "Худі ЗСУ", "url": "/catalog/hoodie/?color=coyote", "freq": "mf"},
        {"label": "Чорна футболка з тризубом", "url": "/catalog/tshirts/?color=black", "freq": "mf"},
        {"label": "Кайотовий лонгслів", "url": "/catalog/long-sleeve/?color=coyote", "freq": "mf"},
        {"label": "Оливкове худі мілітарі", "url": "/catalog/hoodie/?color=olive", "freq": "mf"},
        # LF
        {"label": "Подарунок захиснику український бренд",
         "url": "/catalog/?color=coyote", "freq": "lf"},
        {"label": "Худі з патріотичним принтом купити Київ",
         "url": "/catalog/hoodie/?color=black", "freq": "lf"},
        {"label": "Футболка ЗСУ донат на ЗСУ Україна",
         "url": "/catalog/tshirts/?color=coyote", "freq": "lf"},
        {"label": "Власний принт на одязі від 1 одиниці",
         "url": "/custom-print/", "freq": "lf"},
    ],
}


# ---------------------------------------------------------------------------
# Builder.
# ---------------------------------------------------------------------------

_CATEGORY_LABELS = {
    # match by lowercase slug substring → human-readable category noun
    "hoodie": "худі",
    "hudi": "худі",
    "khudi": "худі",
    "tshirt": "футболки",
    "tshirts": "футболки",
    "futbolki": "футболки",
    "futbolky": "футболки",
    "long": "лонгсліви",
    "longsleeve": "лонгсліви",
    "longslivy": "лонгсліви",
    "longslivi": "лонгсліви",
}


def _category_label(category) -> str:
    if category is None:
        return "одяг"
    slug = (getattr(category, "slug", "") or "").lower()
    for token, label in _CATEGORY_LABELS.items():
        if token in slug:
            return label
    return (getattr(category, "name", "") or "одяг").lower()


def _build_color_paragraphs(color_data: Dict[str, Any], category) -> List[str]:
    cat_label = _category_label(category)
    color_name = color_data["name_uk"]
    color_adj_n = color_data["name_uk_adj_n"]

    paragraphs: List[str] = [color_data["tone_paragraph"]]

    if category is None:
        # Cross-category landing copy.
        paragraphs.append(
            f"У каталозі TwoComms ви знайдете {color_adj_n} "
            f"<a href=\"/catalog/hoodie/?color={color_data.get('slug', '')}\">худі</a>, "
            f"<a href=\"/catalog/tshirts/?color={color_data.get('slug', '')}\">футболки</a> "
            f"та <a href=\"/catalog/long-sleeve/?color={color_data.get('slug', '')}\">"
            f"лонгсліви</a> з авторськими принтами. Усі моделі шиємо в "
            "Україні з натуральних тканин, друкуємо DTF-технологією й "
            f"перевіряємо на стійкість кольору до прання. {color_adj_n.capitalize()} "
            "одяг легко комбінувати з джинсами, карго-штанами та "
            "мілітарними аксесуарами."
        )
        paragraphs.append(
            f"Якщо вас цікавить конкретний принт у {color_name} — "
            f"скористайтесь сторінкою <a href=\"/custom-print/\">«Власний "
            f"принт»</a>: ми надрукуємо будь-яку ілюстрацію на обраній "
            f"моделі від однієї одиниці. Доставка Новою Поштою по всій "
            "Україні — 1–2 дні; оплата карткою або накладеним платежем; "
            "повернення впродовж 14 днів, якщо не підійшов розмір."
        )
    else:
        # Category × colour landing copy.
        paragraphs.append(
            f"У категорії «{cat_label}» {color_adj_n} TwoComms — це "
            "поєднання якісної тканини, насиченого друку й продуманої "
            "посадки. Ми використовуємо щільні полотна, так що принт "
            "не просвічується, а сам одяг тримає форму після десятків "
            f"прань. Звертайте увагу на розмірну сітку — {cat_label} у "
            "TwoComms ідуть у двох посадках: класична та оверсайз."
        )
        paragraphs.append(
            f"Подивіться також {color_adj_n} <a href=\"/catalog/?color="
            f"{color_data.get('slug', '')}\">в інших категоріях</a> або "
            f"оберіть інший відтінок цієї ж категорії — "
            f"<a href=\"/catalog/{getattr(category, 'slug', '')}/\">"
            f"{cat_label} TwoComms</a>. Якщо потрібен конкретний принт — "
            f"скористайтесь сторінкою <a href=\"/custom-print/\">"
            "«Власний принт»</a>: ми надрукуємо вашу ілюстрацію на "
            "обраній моделі від однієї одиниці."
        )

    return paragraphs


def _build_queries_from_seed(color_data: Dict[str, Any]) -> List[Dict[str, str]]:
    return [
        {"label": label, "url": url, "freq": freq}
        for (label, url, freq) in color_data.get("queries_seed", [])
    ]


def _load_override(scope: str, color_slug: str, category) -> Optional[Dict[str, Any]]:
    """Phase 19h: try to load an admin-managed override row.

    Returns the curated payload merged with override fields (only the
    non-empty fields override the defaults), or ``None`` when no
    override exists / DB is not yet migrated.
    """
    try:  # late import — avoids circular import with models.
        from ..models import CatalogColorSeoOverride
    except Exception:
        return None
    try:
        qs = CatalogColorSeoOverride.objects.filter(
            scope=scope,
            color_slug=(color_slug or "").lower(),
            is_active=True,
        )
        if category is None:
            qs = qs.filter(category__isnull=True)
        else:
            qs = qs.filter(category=category)
        row = qs.first()
    except Exception:
        # Migration not applied yet, or DB error — silently bypass so
        # the curated palette still renders.
        return None
    if row is None:
        return None
    return {
        "h2": (row.h2 or "").strip(),
        "body_html": (row.body_html or "").strip(),
        "queries_json": list(row.queries_json or []),
    }


def _split_html_paragraphs(body_html: str) -> List[str]:
    """Split admin-entered ``<p>...</p>`` HTML into paragraph strings."""
    import re as _re
    if not body_html:
        return []
    chunks = _re.findall(r"<p[^>]*>(.*?)</p>", body_html, flags=_re.S | _re.I)
    if chunks:
        return [c.strip() for c in chunks if c.strip()]
    # No <p> tags — treat the entire blob as a single paragraph.
    return [body_html.strip()]


def build_catalog_color_seo(
    *,
    category: Optional[Any],
    selected_color_slugs: Optional[List[str]],
    available_colors: Optional[List[Dict[str, Any]]] = None,
) -> Optional[Dict[str, Any]]:
    """Return ``{h2, paragraphs, queries}`` for the given catalog state.

    Args:
        category: ``Category`` instance or ``None`` for /catalog/ root.
        selected_color_slugs: list of colour slugs from
            ``parse_color_filter`` (single or multi-select).
        available_colors: chip dicts with ``slug``/``label`` to resolve
            human-readable colour names for non-curated slugs.

    Returns:
        dict ready for the template, or ``None`` when no copy applies
        (per-category catalog with no colour filter — that screen
        already has ``category.description``).
    """
    color_slug = (selected_color_slugs or [None])[0]
    if color_slug is None and category is not None:
        # /catalog/<category>/ without colour filter — let the existing
        # category description handle SEO. Returning None lets the
        # template skip the new block cleanly.
        return None

    if color_slug is None:
        # /catalog/ root — brand-level copy. Phase 19h: admin override
        # via CatalogColorSeoOverride(scope="general", color_slug="").
        override = _load_override("general", "", None)
        if override is not None:
            return _merge_curated_with_override(
                base_h2=GENERAL_CATALOG_SEO_COPY["h2"],
                base_paragraphs=GENERAL_CATALOG_SEO_COPY["paragraphs"],
                base_queries=GENERAL_CATALOG_SEO_COPY["queries"],
                override=override,
                color_slug="",
            )
        return {
            "h2": GENERAL_CATALOG_SEO_COPY["h2"],
            "paragraphs": GENERAL_CATALOG_SEO_COPY["paragraphs"],
            "queries": GENERAL_CATALOG_SEO_COPY["queries"],
            "color_slug": "",
        }

    # Resolve a human-readable label for the colour, used by the
    # generic fallback. We prefer the chip label (matches what the
    # user clicked) over the slug itself.
    color_label = ""
    for chip in available_colors or []:
        if (chip.get("slug") or "") == color_slug:
            color_label = chip.get("label") or ""
            break

    color_data = _CURATED.get(color_slug.lower())
    if color_data is None:
        color_data = _generic_color_copy(color_slug, color_label)
    color_data = dict(color_data)
    color_data["slug"] = color_slug

    cat_label = _category_label(category)
    if category is None:
        h2 = (
            f"{color_data['name_uk_adj_m'].capitalize()} одяг TwoComms — "
            f"стрітвір у відтінку «{color_data['name_uk']}»"
        )
    else:
        h2 = (
            f"{color_data['name_uk_adj_n'].capitalize()} {cat_label} "
            f"TwoComms — український стрітвір з принтом"
        )

    base_paragraphs = _build_color_paragraphs(color_data, category)
    base_queries = _build_queries_from_seed(color_data)

    # Phase 19h: admin override (scope=brand for /catalog/?color=…,
    # scope=category for /catalog/<cat>/?color=…). Only non-empty
    # fields override the curated palette.
    scope = "category" if category is not None else "brand"
    override = _load_override(scope, color_slug, category)
    if override is not None:
        return _merge_curated_with_override(
            base_h2=h2,
            base_paragraphs=base_paragraphs,
            base_queries=base_queries,
            override=override,
            color_slug=color_slug,
        )

    return {
        "h2": h2,
        "paragraphs": base_paragraphs,
        "queries": base_queries,
        "color_slug": color_slug,
    }


def _merge_curated_with_override(
    *,
    base_h2: str,
    base_paragraphs: List[str],
    base_queries: List[Dict[str, str]],
    override: Dict[str, Any],
    color_slug: str,
) -> Dict[str, Any]:
    """Merge curated palette with non-empty override fields."""
    h2 = override.get("h2") or base_h2
    body_html = override.get("body_html") or ""
    paragraphs = _split_html_paragraphs(body_html) if body_html else base_paragraphs
    queries_override = override.get("queries_json") or []
    if queries_override:
        # Validate and pass through only well-shaped chips.
        queries: List[Dict[str, str]] = []
        for chip in queries_override:
            if not isinstance(chip, dict):
                continue
            label = (chip.get("label") or "").strip()
            url = (chip.get("url") or "").strip()
            freq = (chip.get("freq") or "mf").strip().lower()
            if not label or not url:
                continue
            if freq not in {"hf", "mf", "lf"}:
                freq = "mf"
            queries.append({"label": label, "url": url, "freq": freq})
        if queries:
            base_queries = queries
    return {
        "h2": h2,
        "paragraphs": paragraphs,
        "queries": base_queries,
        "color_slug": color_slug,
    }
