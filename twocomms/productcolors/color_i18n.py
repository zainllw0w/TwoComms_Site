"""Phase 17h — runtime translation map for ``Color.name``.

DB stores the canonical Ukrainian / Russian colour name as authored by
admins. We don't add ``modeltranslation`` to ``Color`` because:

* names are extremely short and constrained to a known palette,
* there is no SEO benefit (colour pages already have curated copy),
* a migration + admin tabs would add maintenance cost.

Instead this map is consulted by the ``translate_color`` template
filter (see ``storefront/templatetags/color_filters.py``) which returns
a localised string at render time. Unknown names pass through unchanged
so admins can still ship new shades without touching code.
"""

from __future__ import annotations

import re
from typing import Dict, Optional

# Canonical (lowercased) Ukrainian / Russian token → per-language label.
# Whenever a name like "Чорний + Білий" needs translation it is split on
# separators and each token is mapped individually, then re-joined with
# the same separator the admin used.
COLOR_I18N: Dict[str, Dict[str, str]] = {
    # ---------------- Achromatic ----------------
    "чорний":         {"uk": "Чорний",        "ru": "Чёрный",        "en": "Black"},
    "чорна":          {"uk": "Чорна",         "ru": "Чёрная",        "en": "Black"},
    "чёрный":         {"uk": "Чорний",        "ru": "Чёрный",        "en": "Black"},
    "черный":         {"uk": "Чорний",        "ru": "Чёрный",        "en": "Black"},
    "білий":          {"uk": "Білий",         "ru": "Белый",         "en": "White"},
    "біла":           {"uk": "Біла",          "ru": "Белая",         "en": "White"},
    "белый":          {"uk": "Білий",         "ru": "Белый",         "en": "White"},
    "сірий":          {"uk": "Сірий",         "ru": "Серый",         "en": "Gray"},
    "сіра":           {"uk": "Сіра",          "ru": "Серая",         "en": "Gray"},
    "серый":          {"uk": "Сірий",         "ru": "Серый",         "en": "Gray"},
    "світло-сірий":   {"uk": "Світло-сірий",  "ru": "Светло-серый",  "en": "Light gray"},
    "светло-серый":   {"uk": "Світло-сірий",  "ru": "Светло-серый",  "en": "Light gray"},
    "темно-сірий":    {"uk": "Темно-сірий",   "ru": "Тёмно-серый",   "en": "Dark gray"},
    "темно-серый":    {"uk": "Темно-сірий",   "ru": "Тёмно-серый",   "en": "Dark gray"},
    "графіт":         {"uk": "Графіт",        "ru": "Графит",        "en": "Graphite"},
    "графит":         {"uk": "Графіт",        "ru": "Графит",        "en": "Graphite"},
    "вугільний":      {"uk": "Вугільний",     "ru": "Угольный",      "en": "Charcoal"},
    "угольный":       {"uk": "Вугільний",     "ru": "Угольный",      "en": "Charcoal"},
    "сталевий":       {"uk": "Сталевий",      "ru": "Стальной",      "en": "Steel"},
    "стальной":       {"uk": "Сталевий",      "ru": "Стальной",      "en": "Steel"},
    "натуральний":    {"uk": "Натуральний",   "ru": "Натуральный",   "en": "Natural"},
    "натуральный":    {"uk": "Натуральний",   "ru": "Натуральный",   "en": "Natural"},
    # ---------------- Reds / pinks ----------------
    "червоний":       {"uk": "Червоний",      "ru": "Красный",       "en": "Red"},
    "червона":        {"uk": "Червона",       "ru": "Красная",       "en": "Red"},
    "красный":        {"uk": "Червоний",      "ru": "Красный",       "en": "Red"},
    "темно-червоний": {"uk": "Темно-червоний","ru": "Тёмно-красный", "en": "Dark red"},
    "темно-красный":  {"uk": "Темно-червоний","ru": "Тёмно-красный", "en": "Dark red"},
    "бордовий":       {"uk": "Бордовий",      "ru": "Бордовый",      "en": "Burgundy"},
    "бордовый":       {"uk": "Бордовий",      "ru": "Бордовый",      "en": "Burgundy"},
    "винний":         {"uk": "Винний",        "ru": "Винный",        "en": "Wine"},
    "винный":         {"uk": "Винний",        "ru": "Винный",        "en": "Wine"},
    "вишневий":       {"uk": "Вишневий",      "ru": "Вишнёвый",      "en": "Cherry"},
    "вишнёвый":       {"uk": "Вишневий",      "ru": "Вишнёвый",      "en": "Cherry"},
    "вишневый":       {"uk": "Вишневий",      "ru": "Вишнёвый",      "en": "Cherry"},
    "малиновий":      {"uk": "Малиновий",     "ru": "Малиновый",     "en": "Raspberry"},
    "малиновый":      {"uk": "Малиновий",     "ru": "Малиновый",     "en": "Raspberry"},
    "рожевий":        {"uk": "Рожевий",       "ru": "Розовый",       "en": "Pink"},
    "розовый":        {"uk": "Рожевий",       "ru": "Розовый",       "en": "Pink"},
    "пудровий":       {"uk": "Пудровий",      "ru": "Пудровый",      "en": "Powder"},
    "пудровый":       {"uk": "Пудровий",      "ru": "Пудровый",      "en": "Powder"},
    "кораловий":      {"uk": "Кораловий",     "ru": "Коралловый",    "en": "Coral"},
    "коралловый":     {"uk": "Кораловий",     "ru": "Коралловый",    "en": "Coral"},
    # ---------------- Oranges / yellows / browns ----------------
    "помаранчевий":   {"uk": "Помаранчевий",  "ru": "Оранжевый",     "en": "Orange"},
    "оранжевий":      {"uk": "Помаранчевий",  "ru": "Оранжевый",     "en": "Orange"},
    "оранжевый":      {"uk": "Помаранчевий",  "ru": "Оранжевый",     "en": "Orange"},
    "теракотовий":    {"uk": "Теракотовий",   "ru": "Терракотовый",  "en": "Terracotta"},
    "терракотовый":   {"uk": "Теракотовий",   "ru": "Терракотовый",  "en": "Terracotta"},
    "жовтий":         {"uk": "Жовтий",        "ru": "Жёлтый",        "en": "Yellow"},
    "жовта":          {"uk": "Жовта",         "ru": "Жёлтая",        "en": "Yellow"},
    "жёлтый":         {"uk": "Жовтий",        "ru": "Жёлтый",        "en": "Yellow"},
    "желтый":         {"uk": "Жовтий",        "ru": "Жёлтый",        "en": "Yellow"},
    "лимонний":       {"uk": "Лимонний",      "ru": "Лимонный",      "en": "Lemon"},
    "лимонный":       {"uk": "Лимонний",      "ru": "Лимонный",      "en": "Lemon"},
    "гірчичний":      {"uk": "Гірчичний",     "ru": "Горчичный",     "en": "Mustard"},
    "горчичный":      {"uk": "Гірчичний",     "ru": "Горчичный",     "en": "Mustard"},
    "коричневий":     {"uk": "Коричневий",    "ru": "Коричневый",    "en": "Brown"},
    "коричневый":     {"uk": "Коричневий",    "ru": "Коричневый",    "en": "Brown"},
    "шоколадний":     {"uk": "Шоколадний",    "ru": "Шоколадный",    "en": "Chocolate"},
    "шоколадный":     {"uk": "Шоколадний",    "ru": "Шоколадный",    "en": "Chocolate"},
    "кавовий":        {"uk": "Кавовий",       "ru": "Кофейный",      "en": "Coffee"},
    "кофейный":       {"uk": "Кавовий",       "ru": "Кофейный",      "en": "Coffee"},
    "бежевий":        {"uk": "Бежевий",       "ru": "Бежевый",       "en": "Beige"},
    "бежевая":        {"uk": "Бежева",        "ru": "Бежевая",       "en": "Beige"},
    "пісочний":       {"uk": "Пісочний",      "ru": "Песочный",      "en": "Sand"},
    "песочный":       {"uk": "Пісочний",      "ru": "Песочный",      "en": "Sand"},
    "кремовий":       {"uk": "Кремовий",      "ru": "Кремовый",      "en": "Cream"},
    "кремовый":       {"uk": "Кремовий",      "ru": "Кремовый",      "en": "Cream"},
    "молочний":       {"uk": "Молочний",      "ru": "Молочный",      "en": "Ivory"},
    "молочный":       {"uk": "Молочний",      "ru": "Молочный",      "en": "Ivory"},
    # ---------------- Greens ----------------
    "зелений":        {"uk": "Зелений",       "ru": "Зелёный",       "en": "Green"},
    "зелёный":        {"uk": "Зелений",       "ru": "Зелёный",       "en": "Green"},
    "зеленый":        {"uk": "Зелений",       "ru": "Зелёный",       "en": "Green"},
    "темно-зелений":  {"uk": "Темно-зелений", "ru": "Тёмно-зелёный", "en": "Dark green"},
    "темно-зелёный":  {"uk": "Темно-зелений", "ru": "Тёмно-зелёный", "en": "Dark green"},
    "темно-зеленый":  {"uk": "Темно-зелений", "ru": "Тёмно-зелёный", "en": "Dark green"},
    "світло-зелений": {"uk": "Світло-зелений","ru": "Светло-зелёный","en": "Light green"},
    "светло-зелёный": {"uk": "Світло-зелений","ru": "Светло-зелёный","en": "Light green"},
    "светло-зеленый": {"uk": "Світло-зелений","ru": "Светло-зелёный","en": "Light green"},
    "хакі":           {"uk": "Хакі",          "ru": "Хаки",          "en": "Khaki"},
    "хаки":           {"uk": "Хакі",          "ru": "Хаки",          "en": "Khaki"},
    "олива":          {"uk": "Олива",         "ru": "Олива",         "en": "Olive"},
    "оливковий":      {"uk": "Оливковий",     "ru": "Оливковый",     "en": "Olive"},
    "оливковый":      {"uk": "Оливковий",     "ru": "Оливковый",     "en": "Olive"},
    "м'ятний":        {"uk": "М'ятний",       "ru": "Мятный",        "en": "Mint"},
    "мятный":         {"uk": "М'ятний",       "ru": "Мятный",        "en": "Mint"},
    "смарагдовий":    {"uk": "Смарагдовий",   "ru": "Изумрудный",    "en": "Emerald"},
    "изумрудный":     {"uk": "Смарагдовий",   "ru": "Изумрудный",    "en": "Emerald"},
    "мілітарі":       {"uk": "Мілітарі",      "ru": "Милитари",      "en": "Military"},
    "милитари":       {"uk": "Мілітарі",      "ru": "Милитари",      "en": "Military"},
    "лісовий":        {"uk": "Лісовий",       "ru": "Лесной",        "en": "Forest"},
    "лесной":         {"uk": "Лісовий",       "ru": "Лесной",        "en": "Forest"},
    "ментол":         {"uk": "Ментол",        "ru": "Ментол",        "en": "Menthol"},
    "ментоловий":     {"uk": "Ментоловий",    "ru": "Ментоловый",    "en": "Menthol"},
    "ментоловый":     {"uk": "Ментоловий",    "ru": "Ментоловый",    "en": "Menthol"},
    # ---------------- Blues ----------------
    "синій":          {"uk": "Синій",         "ru": "Синий",         "en": "Blue"},
    "синяя":          {"uk": "Синя",          "ru": "Синяя",         "en": "Blue"},
    "синий":          {"uk": "Синій",         "ru": "Синий",         "en": "Blue"},
    "блакитний":      {"uk": "Блакитний",     "ru": "Голубой",       "en": "Light blue"},
    "голубой":        {"uk": "Блакитний",     "ru": "Голубой",       "en": "Light blue"},
    "темно-синій":    {"uk": "Темно-синій",   "ru": "Тёмно-синий",   "en": "Navy"},
    "тёмно-синий":    {"uk": "Темно-синій",   "ru": "Тёмно-синий",   "en": "Navy"},
    "темно-синий":    {"uk": "Темно-синій",   "ru": "Тёмно-синий",   "en": "Navy"},
    "морський":       {"uk": "Морський",      "ru": "Морской",       "en": "Navy"},
    "морской":        {"uk": "Морський",      "ru": "Морской",       "en": "Navy"},
    "джинсовий":      {"uk": "Джинсовий",     "ru": "Джинсовый",     "en": "Denim"},
    "джинсовый":      {"uk": "Джинсовий",     "ru": "Джинсовый",     "en": "Denim"},
    "індіго":         {"uk": "Індіго",        "ru": "Индиго",        "en": "Indigo"},
    "индиго":         {"uk": "Індіго",        "ru": "Индиго",        "en": "Indigo"},
    "бірюзовий":      {"uk": "Бірюзовий",     "ru": "Бирюзовый",     "en": "Turquoise"},
    "бирюзовый":      {"uk": "Бірюзовий",     "ru": "Бирюзовый",     "en": "Turquoise"},
    # ---------------- Purples ----------------
    "фіолетовий":     {"uk": "Фіолетовий",    "ru": "Фиолетовый",    "en": "Purple"},
    "фиолетовый":     {"uk": "Фіолетовий",    "ru": "Фиолетовый",    "en": "Purple"},
    "пурпурний":      {"uk": "Пурпурний",     "ru": "Пурпурный",     "en": "Crimson"},
    "пурпурный":      {"uk": "Пурпурний",     "ru": "Пурпурный",     "en": "Crimson"},
    "бузковий":       {"uk": "Бузковий",      "ru": "Сиреневый",     "en": "Lilac"},
    "сиреневый":      {"uk": "Бузковий",      "ru": "Сиреневый",     "en": "Lilac"},
    "лавандовий":     {"uk": "Лавандовий",    "ru": "Лавандовый",    "en": "Lavender"},
    "лавандовый":     {"uk": "Лавандовий",    "ru": "Лавандовый",    "en": "Lavender"},
    "сливовий":       {"uk": "Сливовий",      "ru": "Сливовый",      "en": "Plum"},
    "сливовый":       {"uk": "Сливовий",      "ru": "Сливовый",      "en": "Plum"},
    # ---------------- Tactical / specialty ----------------
    "кайот":          {"uk": "Кайот",         "ru": "Койот",         "en": "Coyote"},
    "койот":          {"uk": "Кайот",         "ru": "Койот",         "en": "Coyote"},
    "мультикам":      {"uk": "Мультикам",     "ru": "Мультикам",     "en": "Multicam"},
    "піксель":        {"uk": "Піксель",       "ru": "Пиксель",       "en": "Pixel"},
    "пиксель":        {"uk": "Піксель",       "ru": "Пиксель",       "en": "Pixel"},
    "марпат":         {"uk": "Марпат",        "ru": "Марпат",        "en": "MARPAT"},
    "флектарн":       {"uk": "Флектарн",      "ru": "Флектарн",      "en": "Flecktarn"},
    # ---------------- Metallics ----------------
    "золотий":        {"uk": "Золотий",       "ru": "Золотой",       "en": "Gold"},
    "золотой":        {"uk": "Золотий",       "ru": "Золотой",       "en": "Gold"},
    "срібний":        {"uk": "Срібний",       "ru": "Серебряный",    "en": "Silver"},
    "срібло":         {"uk": "Срібло",        "ru": "Серебро",       "en": "Silver"},
    "серебряный":     {"uk": "Срібний",       "ru": "Серебряный",    "en": "Silver"},
    "бронзовий":      {"uk": "Бронзовий",     "ru": "Бронзовый",     "en": "Bronze"},
    "бронзовый":      {"uk": "Бронзовий",     "ru": "Бронзовый",     "en": "Bronze"},
    "мідний":         {"uk": "Мідний",        "ru": "Медный",        "en": "Copper"},
    "медный":         {"uk": "Мідний",        "ru": "Медный",        "en": "Copper"},
    # ---------------- Compound prefixes ----------------
    "біло":           {"uk": "Біло",          "ru": "Бело",          "en": "White"},
    "бело":           {"uk": "Біло",          "ru": "Бело",          "en": "White"},
    "чорно":          {"uk": "Чорно",         "ru": "Чёрно",         "en": "Black"},
    "черно":          {"uk": "Чорно",         "ru": "Чёрно",         "en": "Black"},
    "сіро":           {"uk": "Сіро",          "ru": "Серо",          "en": "Gray"},
    "серо":           {"uk": "Сіро",          "ru": "Серо",          "en": "Gray"},
    "темно":          {"uk": "Темно",         "ru": "Тёмно",         "en": "Dark"},
    "тёмно":          {"uk": "Темно",         "ru": "Тёмно",         "en": "Dark"},
    "світло":         {"uk": "Світло",        "ru": "Светло",        "en": "Light"},
    "светло":         {"uk": "Світло",        "ru": "Светло",        "en": "Light"},
}

_SEPARATOR_RE = re.compile(r"([\s/+&,_–—-]+)")
_NOISE_TOKENS = frozenset({"і", "и", "and", "or", "та"})


def translate_color_name(name: Optional[str], lang: str) -> str:
    """Return *name* translated into *lang* (``uk`` / ``ru`` / ``en``).

    Unknown tokens pass through unchanged so an admin can ship a new
    shade without code changes. Compound names like
    ``"Чорний + Білий"`` are split on common separators and each token
    is translated independently before being re-joined.
    """
    if not name:
        return ""
    if lang not in ("ru", "en", "uk"):
        return name

    raw = name.strip()
    direct = COLOR_I18N.get(raw.lower())
    if direct:
        return direct.get(lang) or name

    parts = _SEPARATOR_RE.split(raw)
    if len(parts) <= 1:
        return name

    out: list[str] = []
    any_hit = False
    for chunk in parts:
        if not chunk:
            continue
        # Separator chunk (whitespace / + / etc.) — pass through as-is.
        if _SEPARATOR_RE.fullmatch(chunk):
            out.append(chunk)
            continue
        lower = chunk.lower()
        if lower in _NOISE_TOKENS:
            out.append(chunk)
            continue
        hit = COLOR_I18N.get(lower)
        if hit and hit.get(lang):
            any_hit = True
            translated = hit[lang]
            # Preserve original capitalisation hint: if the source token
            # was lowercase keep the translation lowercase, otherwise
            # uppercase its first letter so compound names read
            # naturally ("Чорно-білий" → "Black-white" in EN).
            if chunk[:1].islower():
                translated = translated[:1].lower() + translated[1:]
            out.append(translated)
        else:
            out.append(chunk)

    if not any_hit:
        return name
    return "".join(out)


__all__ = ["COLOR_I18N", "translate_color_name"]
