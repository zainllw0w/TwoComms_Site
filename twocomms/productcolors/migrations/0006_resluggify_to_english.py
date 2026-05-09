"""Phase 7.1 — re-slug variants whose slug is currently a Cyrillic
transliteration when a curated English name exists.

Background. Migration 0004 first filled ``ProductColorVariant.slug``
with bare ``slugify`` output (``''`` for Cyrillic → hex fallback).
0005 fixed that with transliteration (``chornyi``, ``kaiot``).
We now prefer English translations (``black``, ``coyote``) because
they're discoverable by international searchers and AI answer engines
out of the box.

This migration only rewrites slugs whose value matches the
deterministic transliteration of the colour name. Any slug an editor
set by hand is preserved verbatim.
"""

from __future__ import annotations

from django.db import migrations
from django.utils.text import slugify


# Inline copy of the English colour map. Keep in sync with
# ``productcolors.color_slug_map.COLOR_NAME_TO_EN_SLUG`` — migrations
# must remain importable forever, so we deliberately don't reach into
# application code from here.
_EN_MAP = {
    "чорний": "black", "чорна": "black", "чёрный": "black", "черный": "black",
    "білий": "white", "біла": "white", "белый": "white",
    "сірий": "gray", "сіра": "gray", "серый": "gray",
    "світло-сірий": "light-gray", "светло-серый": "light-gray",
    "темно-сірий": "dark-gray", "темно-серый": "dark-gray",
    "графіт": "graphite", "графит": "graphite",
    "вугільний": "charcoal", "угольный": "charcoal",
    "сталевий": "steel", "стальной": "steel",
    "натуральний": "natural", "натуральный": "natural",
    "червоний": "red", "червона": "red", "красный": "red",
    "темно-червоний": "dark-red", "темно-красный": "dark-red",
    "бордовий": "burgundy", "бордовый": "burgundy",
    "винний": "wine", "винный": "wine",
    "вишневий": "cherry", "вишнёвый": "cherry", "вишневый": "cherry",
    "малиновий": "raspberry", "малиновый": "raspberry",
    "рожевий": "pink", "розовый": "pink",
    "пудровий": "powder", "пудровый": "powder",
    "кораловий": "coral", "коралловый": "coral",
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
    "зелений": "green", "зелёный": "green", "зеленый": "green",
    "темно-зелений": "dark-green", "темно-зелёный": "dark-green", "темно-зеленый": "dark-green",
    "світло-зелений": "light-green", "светло-зелёный": "light-green", "светло-зеленый": "light-green",
    "хакі": "khaki", "хаки": "khaki",
    "олива": "olive", "оливковий": "olive", "оливковый": "olive",
    "м'ятний": "mint", "мятный": "mint",
    "смарагдовий": "emerald", "изумрудный": "emerald",
    "мілітарі": "military", "милитари": "military",
    "лісовий": "forest", "лесной": "forest",
    "синій": "blue", "синяя": "blue", "синий": "blue",
    "блакитний": "lightblue", "голубой": "lightblue",
    "темно-синій": "navy", "тёмно-синий": "navy", "темно-синий": "navy",
    "морський": "navy", "морской": "navy",
    "джинсовий": "denim", "джинсовый": "denim",
    "індіго": "indigo", "индиго": "indigo",
    "бірюзовий": "turquoise", "бирюзовый": "turquoise",
    "фіолетовий": "purple", "фиолетовый": "purple",
    "пурпурний": "crimson", "пурпурный": "crimson",
    "бузковий": "lilac", "сиреневый": "lilac",
    "лавандовий": "lavender", "лавандовый": "lavender",
    "сливовий": "plum", "сливовый": "plum",
    "кайот": "coyote", "койот": "coyote",
    "мультикам": "multicam", "піксель": "pixel", "пиксель": "pixel",
    "марпат": "marpat", "флектарн": "flecktarn",
    "золотий": "gold", "золотой": "gold",
    "срібний": "silver", "срібло": "silver", "серебряный": "silver",
    "бронзовий": "bronze", "бронзовый": "bronze",
    "мідний": "copper", "медный": "copper",
}

_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "h", "ґ": "g", "д": "d",
    "е": "e", "є": "ie", "ж": "zh", "з": "z", "и": "y", "і": "i",
    "ї": "i", "й": "i", "к": "k", "л": "l", "м": "m", "н": "n",
    "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
    "ь": "", "ю": "iu", "я": "ia", "ё": "e", "ы": "y", "э": "e",
    "ъ": "",
}


def _translit(value: str) -> str:
    out = []
    for ch in value or "":
        repl = _TRANSLIT.get(ch.lower())
        out.append(ch if repl is None else (repl.upper() if ch.isupper() else repl))
    return "".join(out)


def _translit_slug(name: str) -> str:
    return slugify(_translit(name or ""), allow_unicode=False).strip("-")


def _english_slug(name: str) -> str:
    """Match the lookup logic in productcolors.color_slug_map exactly."""
    if not name:
        return ""
    raw = name.strip().lower()
    direct = _EN_MAP.get(raw)
    if direct:
        return direct

    import re
    parts = [p for p in re.split(r"[\s/+&,_–—-]+", raw) if p and p not in ("і", "и", "and", "or", "та")]
    if not parts:
        return ""
    mapped = [_EN_MAP.get(p, p) for p in parts]
    if any(p in _EN_MAP for p in parts):
        return "-".join(mapped)
    return ""


def reslug_to_english(apps, schema_editor):
    ProductColorVariant = apps.get_model("productcolors", "ProductColorVariant")

    by_product: dict[int, list] = {}
    for variant in ProductColorVariant.objects.select_related("color").all():
        by_product.setdefault(variant.product_id, []).append(variant)

    for product_id, variants in by_product.items():
        # Snapshot all slugs that are NOT the deterministic transliteration
        # of their colour name — those are editor-curated and untouchable.
        taken: set[str] = set()
        for v in variants:
            translit = _translit_slug(getattr(v.color, "name", "") or "")
            translit_disambiguated = (
                f"{translit}-c" if translit and len(translit) <= 4 else translit
            )
            if v.slug and v.slug != translit and v.slug != translit_disambiguated:
                taken.add(v.slug)

        for variant in variants:
            color_name = getattr(variant.color, "name", "") or ""
            translit = _translit_slug(color_name)
            translit_disambiguated = (
                f"{translit}-c" if translit and len(translit) <= 4 else translit
            )

            if variant.slug not in (translit, translit_disambiguated):
                # Editor-curated — never touch.
                continue

            english = _english_slug(color_name)
            if not english:
                taken.add(variant.slug)
                continue
            if len(english) <= 4:
                english = f"{english}-c"

            candidate = english
            suffix = 2
            while candidate in taken:
                candidate = f"{english}-{suffix}"
                suffix += 1
            taken.add(candidate)

            if candidate != variant.slug:
                variant.slug = candidate
                variant.save(update_fields=["slug"])


def noop(apps, schema_editor):
    return None


class Migration(migrations.Migration):

    dependencies = [
        ("productcolors", "0005_resluggify_with_translit"),
    ]

    operations = [
        migrations.RunPython(reslug_to_english, noop),
    ]
