"""Phase 7.1 finalisation — fully re-generate every auto-generated
``ProductColorVariant.slug`` using the latest rules:

* Compound prefixes (``бело-`` / ``темно-`` / ``світло-``) translate.
* Size-collision rule applies only to the explicit reserved set
  (``s/m/l/xs/xl/xxs/xxl/xxxl/...``), so colours like ``pink`` /
  ``blue`` / ``gold`` keep their clean 4-letter slugs.
* Per-product uniqueness preserved via numeric ``-N`` suffixes.

Slugs that contain only Cyrillic characters or look like a previous
auto-generated form are replaced. Anything that already matches the
deterministic output of the new algorithm is left alone.
"""

from __future__ import annotations

import re

from django.db import migrations
from django.utils.text import slugify


_EN_MAP = {
    # ---- Achromatic ----
    "чорний": "black", "чорна": "black", "чёрный": "black", "черный": "black",
    "білий": "white", "біла": "white", "белый": "white",
    "сірий": "gray", "сіра": "gray", "серый": "gray",
    "світло-сірий": "light-gray", "светло-серый": "light-gray",
    "темно-сірий": "dark-gray", "темно-серый": "dark-gray",
    "графіт": "graphite", "графит": "graphite",
    "вугільний": "charcoal", "угольный": "charcoal",
    "сталевий": "steel", "стальной": "steel",
    "натуральний": "natural", "натуральный": "natural",
    # ---- Reds / pinks ----
    "червоний": "red", "червона": "red", "красный": "red",
    "темно-червоний": "dark-red", "темно-красный": "dark-red",
    "бордовий": "burgundy", "бордовый": "burgundy",
    "винний": "wine", "винный": "wine",
    "вишневий": "cherry", "вишнёвый": "cherry", "вишневый": "cherry",
    "малиновий": "raspberry", "малиновый": "raspberry",
    "рожевий": "pink", "розовый": "pink",
    "пудровий": "powder", "пудровый": "powder",
    "кораловий": "coral", "коралловый": "coral",
    # ---- Oranges / yellows / browns ----
    "помаранчевий": "orange", "оранжевий": "orange", "оранжевый": "orange",
    "теракотовий": "terracotta", "терракотовый": "terracotta",
    "жовтий": "yellow", "жовта": "yellow", "жёлтый": "yellow", "желтый": "yellow",
    "лимонний": "lemon", "лимонный": "lemon",
    "гірчичний": "mustard", "горчичный": "mustard",
    "коричневий": "brown", "коричневый": "brown",
    "шоколадний": "chocolate", "шоколадный": "chocolate",
    "кавовий": "coffee", "кофейный": "coffee",
    "бежевий": "beige", "бежевая": "beige",
    "пісочний": "sand", "песочный": "sand",
    "кремовий": "cream", "кремовый": "cream",
    "молочний": "ivory", "молочный": "ivory",
    # ---- Greens ----
    "зелений": "green", "зелёный": "green", "зеленый": "green",
    "темно-зелений": "dark-green", "темно-зелёный": "dark-green", "темно-зеленый": "dark-green",
    "світло-зелений": "light-green", "светло-зелёный": "light-green", "светло-зеленый": "light-green",
    "хакі": "khaki", "хаки": "khaki",
    "олива": "olive", "оливковий": "olive", "оливковый": "olive",
    "м'ятний": "mint", "мятный": "mint",
    "смарагдовий": "emerald", "изумрудный": "emerald",
    "мілітарі": "military", "милитари": "military",
    "лісовий": "forest", "лесной": "forest",
    # ---- Blues ----
    "синій": "blue", "синяя": "blue", "синий": "blue",
    "блакитний": "lightblue", "голубой": "lightblue",
    "темно-синій": "navy", "тёмно-синий": "navy", "темно-синий": "navy",
    "морський": "navy", "морской": "navy",
    "джинсовий": "denim", "джинсовый": "denim",
    "індіго": "indigo", "индиго": "indigo",
    "бірюзовий": "turquoise", "бирюзовый": "turquoise",
    # ---- Purples ----
    "фіолетовий": "purple", "фиолетовый": "purple",
    "пурпурний": "crimson", "пурпурный": "crimson",
    "бузковий": "lilac", "сиреневый": "lilac",
    "лавандовий": "lavender", "лавандовый": "lavender",
    "сливовий": "plum", "сливовый": "plum",
    # ---- Tactical / specialty ----
    "кайот": "coyote", "койот": "coyote",
    "мультикам": "multicam", "піксель": "pixel", "пиксель": "pixel",
    "марпат": "marpat", "флектарн": "flecktarn",
    # ---- Metallics ----
    "золотий": "gold", "золотой": "gold",
    "срібний": "silver", "срібло": "silver", "серебряный": "silver",
    "бронзовий": "bronze", "бронзовый": "bronze",
    "мідний": "copper", "медный": "copper",
    # ---- Compound prefixes ----
    "біло": "white", "бело": "white",
    "чорно": "black", "черно": "black",
    "сіро": "gray", "серо": "gray",
    "темно": "dark", "тёмно": "dark",
    "світло": "light", "светло": "light",
    "ментол": "menthol", "ментоловий": "menthol", "ментоловый": "menthol",
}

_SIZE_RESERVED = {
    "s", "m", "l",
    "xs", "xl", "xxs", "xxl", "xxxs", "xxxl", "xxxxl",
    "sm", "md", "lg",
}

_SEPARATOR_RE = re.compile(r"[\s/+&,_–—-]+")
_NOISE_TOKENS = {"і", "и", "and", "or", "та"}
_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "h", "ґ": "g", "д": "d",
    "е": "e", "є": "ie", "ж": "zh", "з": "z", "и": "y", "і": "i",
    "ї": "i", "й": "i", "к": "k", "л": "l", "м": "m", "н": "n",
    "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
    "ь": "", "ю": "iu", "я": "ia", "ё": "e", "ы": "y", "э": "e",
    "ъ": "",
}


def _english_slug(name: str) -> str:
    if not name:
        return ""
    raw = name.strip().lower()
    direct = _EN_MAP.get(raw)
    if direct:
        return direct
    parts = [p for p in _SEPARATOR_RE.split(raw) if p and p not in _NOISE_TOKENS]
    if not parts:
        return ""
    mapped = [_EN_MAP.get(p, p) for p in parts]
    if any(p in _EN_MAP for p in parts):
        return "-".join(mapped)
    return ""


def _translit_slug(name: str) -> str:
    out = []
    for ch in name or "":
        repl = _TRANSLIT.get(ch.lower())
        out.append(ch if repl is None else (repl.upper() if ch.isupper() else repl))
    return slugify("".join(out), allow_unicode=False).strip("-")


def _expected_slug(name: str, hex_value: str) -> str:
    base = _english_slug(name) or _translit_slug(name)
    if not base and hex_value:
        base = slugify(hex_value.lstrip("#"), allow_unicode=False).strip("-")
    if not base:
        base = "color"
    if base.lower() in _SIZE_RESERVED:
        base = f"{base}-c"
    return base


def _is_auto_generated(slug: str, name: str, hex_value: str) -> bool:
    """Heuristic: treat slugs that look like prior algorithm output as
    safe to overwrite. Editor-curated slugs typically don't contain
    Cyrillic and don't equal earlier deterministic forms.
    """
    if not slug:
        return True
    # Any slug containing Cyrillic is from a half-translated compound
    # (e.g. ``бело-burgundy``) — auto-generated and unsafe to keep.
    if re.search(r"[А-Яа-яҐЄІЇґєії]", slug):
        return True
    expected = _expected_slug(name, hex_value)
    if slug == expected:
        return True
    # Old algorithm outputs we've shipped:
    if slug == _translit_slug(name) or slug == f"{_translit_slug(name)}-c":
        return True
    en = _english_slug(name)
    if en and slug == f"{en}-c":  # over-eager <=4 disambiguation in 0006
        return True
    return False


def normalize_slugs(apps, schema_editor):
    ProductColorVariant = apps.get_model("productcolors", "ProductColorVariant")

    by_product: dict[int, list] = {}
    for variant in ProductColorVariant.objects.select_related("color").all():
        by_product.setdefault(variant.product_id, []).append(variant)

    for product_id, variants in by_product.items():
        # Phase 1: snapshot editor-curated slugs as taken so we never
        # collide with them when re-generating auto slugs.
        taken: set[str] = set()
        for v in variants:
            color_name = getattr(v.color, "name", "") or ""
            hex_value = getattr(v.color, "primary_hex", "") or ""
            if not _is_auto_generated(v.slug, color_name, hex_value):
                taken.add(v.slug)

        for variant in variants:
            color_name = getattr(variant.color, "name", "") or ""
            hex_value = getattr(variant.color, "primary_hex", "") or ""
            if not _is_auto_generated(variant.slug, color_name, hex_value):
                continue

            base = _expected_slug(color_name, hex_value)
            candidate = base
            suffix = 2
            while candidate in taken:
                candidate = f"{base}-{suffix}"
                suffix += 1
            taken.add(candidate)

            if candidate != variant.slug:
                variant.slug = candidate
                variant.save(update_fields=["slug"])


def noop(apps, schema_editor):
    return None


class Migration(migrations.Migration):

    dependencies = [
        ("productcolors", "0006_resluggify_to_english"),
    ]

    operations = [
        migrations.RunPython(normalize_slugs, noop),
    ]
