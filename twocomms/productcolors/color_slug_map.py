"""Ukrainian / Russian colour name → English URL slug.

Phase 7.1 — used by ``ProductColorVariant._generate_url_slug`` to
produce SEO-friendly slugs that match how international searchers and
LLM answer engines actually phrase colour queries (``black-tshirt`` is
far more discoverable than ``chornyi-tshirt``).

Falls back to transliteration via ``dtf.utils.build_slug`` when a
colour name is not in the map. Compound names like
"Чорний + Білий" are split on common separators and each part is
mapped individually, so ``black-white`` is produced even if the
literal compound key is missing.
"""

from __future__ import annotations

import re
from typing import Iterable, Optional

# Single-token map: lowercase Ukrainian / Russian → English slug-fragment.
# Ordering doesn't matter for lookup; entries are grouped by colour family
# for human auditing.
COLOR_NAME_TO_EN_SLUG: dict[str, str] = {
    # ---------------- Achromatic ----------------
    "чорний": "black",
    "чорна": "black",
    "чёрный": "black",
    "черный": "black",
    "білий": "white",
    "біла": "white",
    "белый": "white",
    "сірий": "gray",
    "сіра": "gray",
    "серый": "gray",
    "світло-сірий": "light-gray",
    "светло-серый": "light-gray",
    "темно-сірий": "dark-gray",
    "темно-серый": "dark-gray",
    "графіт": "graphite",
    "графит": "graphite",
    "вугільний": "charcoal",
    "угольный": "charcoal",
    "сталевий": "steel",
    "стальной": "steel",
    "натуральний": "natural",
    "натуральный": "natural",
    # ---------------- Reds / pinks ----------------
    "червоний": "red",
    "червона": "red",
    "красный": "red",
    "темно-червоний": "dark-red",
    "темно-красный": "dark-red",
    "бордовий": "burgundy",
    "бордовый": "burgundy",
    "винний": "wine",
    "винный": "wine",
    "вишневий": "cherry",
    "вишнёвый": "cherry",
    "вишневый": "cherry",
    "малиновий": "raspberry",
    "малиновый": "raspberry",
    "рожевий": "pink",
    "розовый": "pink",
    "пудровий": "powder",
    "пудровый": "powder",
    "кораловий": "coral",
    "коралловый": "coral",
    # ---------------- Oranges / yellows / browns ----------------
    "помаранчевий": "orange",
    "оранжевий": "orange",
    "оранжевый": "orange",
    "теракотовий": "terracotta",
    "терракотовый": "terracotta",
    "жовтий": "yellow",
    "жовта": "yellow",
    "жёлтый": "yellow",
    "желтый": "yellow",
    "лимонний": "lemon",
    "лимонный": "lemon",
    "гірчичний": "mustard",
    "горчичный": "mustard",
    "коричневий": "brown",
    "коричневый": "brown",
    "шоколадний": "chocolate",
    "шоколадный": "chocolate",
    "кавовий": "coffee",
    "кофейный": "coffee",
    "бежевий": "beige",
    "бежевая": "beige",
    "пісочний": "sand",
    "песочный": "sand",
    "кремовий": "cream",
    "кремовый": "cream",
    "молочний": "ivory",
    "молочный": "ivory",
    "слонова кістка": "ivory",
    "слоновая кость": "ivory",
    # ---------------- Greens ----------------
    "зелений": "green",
    "зелёный": "green",
    "зеленый": "green",
    "темно-зелений": "dark-green",
    "темно-зелёный": "dark-green",
    "темно-зеленый": "dark-green",
    "світло-зелений": "light-green",
    "светло-зелёный": "light-green",
    "светло-зеленый": "light-green",
    "хакі": "khaki",
    "хаки": "khaki",
    "олива": "olive",
    "оливковий": "olive",
    "оливковый": "olive",
    "м'ятний": "mint",
    "мятный": "mint",
    "смарагдовий": "emerald",
    "изумрудный": "emerald",
    "мілітарі": "military",
    "милитари": "military",
    "лісовий": "forest",
    "лесной": "forest",
    # ---------------- Blues ----------------
    "синій": "blue",
    "синяя": "blue",
    "синий": "blue",
    "блакитний": "lightblue",
    "голубой": "lightblue",
    "темно-синій": "navy",
    "тёмно-синий": "navy",
    "темно-синий": "navy",
    "морський": "navy",
    "морской": "navy",
    "джинсовий": "denim",
    "джинсовый": "denim",
    "індіго": "indigo",
    "индиго": "indigo",
    "бірюзовий": "turquoise",
    "бирюзовый": "turquoise",
    # ---------------- Purples ----------------
    "фіолетовий": "purple",
    "фиолетовый": "purple",
    "пурпурний": "crimson",
    "пурпурный": "crimson",
    "бузковий": "lilac",
    "сиреневый": "lilac",
    "лавандовий": "lavender",
    "лавандовый": "lavender",
    "сливовий": "plum",
    "сливовый": "plum",
    # ---------------- Tactical / specialty ----------------
    "кайот": "coyote",
    "койот": "coyote",
    "мультикам": "multicam",
    "піксель": "pixel",
    "пиксель": "pixel",
    "марпат": "marpat",
    "флектарн": "flecktarn",
    # ---------------- Metallics ----------------
    "золотий": "gold",
    "золотой": "gold",
    "срібний": "silver",
    "срібло": "silver",
    "серебряный": "silver",
    "бронзовий": "bronze",
    "бронзовый": "bronze",
    "мідний": "copper",
    "медный": "copper",
    # ---------------- Compound prefixes ----------------
    # Used when a colour name like "Біло-бордовий" or "Темно-зелений"
    # is split on the hyphen — the prefix alone needs to translate too.
    "біло": "white",
    "бело": "white",
    "чорно": "black",
    "черно": "black",
    "сіро": "gray",
    "серо": "gray",
    "темно": "dark",
    "тёмно": "dark",
    "світло": "light",
    "светло": "light",
    "ментол": "menthol",
    "ментоловий": "menthol",
    "ментоловый": "menthol",
}

# Slug bases that would collide with a real ``Product`` size code in
# path-style URLs. We append ``-c`` only for these — colour names like
# ``pink`` / ``blue`` / ``gold`` are never sizes and stay clean.
SIZE_RESERVED_SLUG_BASES = frozenset({
    "s", "m", "l",
    "xs", "xl", "xxs", "xxl", "xxxs", "xxxl", "xxxxl",
    "sm", "md", "lg",
})

# Tokens we always strip when splitting compound names.
_SEPARATOR_RE = re.compile(r"[\s/+&,_–—-]+")
_NOISE_TOKENS = frozenset({"і", "и", "and", "or", "та", "or", "from"})


def _split_tokens(name: str) -> list[str]:
    return [
        tok for tok in _SEPARATOR_RE.split((name or "").strip().lower())
        if tok and tok not in _NOISE_TOKENS
    ]


def english_slug_for_color_name(name: str) -> Optional[str]:
    """Return an English slug for a Ukrainian / Russian colour name.

    Single-token names are looked up directly in ``COLOR_NAME_TO_EN_SLUG``.
    Compound names (e.g. "Чорний + Білий") are split on common separators
    and each part is mapped individually, joined with ``-``. Returns
    ``None`` when no token matches so the caller can fall back to
    transliteration.
    """
    if not name:
        return None

    raw = name.strip().lower()
    direct = COLOR_NAME_TO_EN_SLUG.get(raw)
    if direct:
        return direct

    tokens = _split_tokens(raw)
    if not tokens:
        return None

    mapped: list[str] = []
    any_mapped = False
    for token in tokens:
        hit = COLOR_NAME_TO_EN_SLUG.get(token)
        if hit:
            mapped.append(hit)
            any_mapped = True
        else:
            mapped.append(token)

    if not any_mapped:
        return None

    return "-".join(mapped)


__all__ = ["COLOR_NAME_TO_EN_SLUG", "english_slug_for_color_name"]
