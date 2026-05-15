"""Phase 17z5 — build ``product_translations.json`` from hand-curated themes.

Usage::

    python data/build_product_translations.py \
        --dump  /tmp/twocomms_product_translations_dump.json \
        --out   data/product_translations.json

The output JSON is consumed by ``manage.py import_product_translations``.

How matching works
------------------
For every product on production we detect its product type (футболка /
худі / лонгслів) and theme from the Ukrainian title. We then assemble
RU + EN values for every translatable field using:

* ``PTYPES`` — product-type lexical forms (nom / gen)
* ``CARE``  — per-ptype care instructions
* ``SEO_TAIL`` / ``TARGET_TAIL`` / ``PTYPE_KW_TAIL`` — common closings
* The theme module — theme name, pitch, alt, target intro, kw seed

We then emit a ``by_id`` payload so the importer can apply translations
even when titles drift (eg legacy ``Футболка`` vs ``ФУТБОЛКА`` casing).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Make the sibling ``translations`` package importable when this script is
# executed directly.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from translations._constants import (  # type: ignore[import-not-found]  # noqa: E402
    CARE,
    PTYPE_KW_TAIL,
    PTYPES,
    SEO_TAIL,
    TARGET_TAIL,
)
from translations._categories import CATEGORIES  # type: ignore[import-not-found]  # noqa: E402
from translations._faq import ANSWERS, QUESTIONS  # type: ignore[import-not-found]  # noqa: E402
from translations._themes_business_skull import THEMES as _T_BUSINESS  # noqa: E402
from translations._themes_classic_holiday import THEMES as _T_CLASSIC  # noqa: E402
from translations._themes_collabs_misc import THEMES as _T_COLLABS  # noqa: E402
from translations._themes_kharkiv_war import THEMES as _T_KHARKIV  # noqa: E402

_THEME_MAPS = (_T_CLASSIC, _T_BUSINESS, _T_KHARKIV, _T_COLLABS)


# ---------------------------------------------------------------------------
# Theme detection: UA title (or part of it) → theme key
# ---------------------------------------------------------------------------
# Map normalized UA name → theme slot
def _build_theme_lookup() -> dict[str, dict]:
    lookup: dict[str, dict] = {}
    # Themed prints: use ``uk_name`` key
    for theme_map in _THEME_MAPS:
        for slot, payload in theme_map.items():
            keys = []
            if "uk_name" in payload:
                keys.append(payload["uk_name"].strip().lower())
            if "title" in payload and isinstance(payload["title"], dict):
                keys.append(payload["title"]["uk"].strip().lower())
            for k in keys:
                if k:
                    lookup[k] = payload
    return lookup


THEME_LOOKUP = _build_theme_lookup()


# ---------------------------------------------------------------------------
# Product type & theme extraction from UA title
# ---------------------------------------------------------------------------
def detect_ptype(title: str) -> str | None:
    t = title.lower().strip()
    if "лонгслів" in t or t.startswith("longsleeve"):
        return "longsleeve"
    if t.startswith("худі") or t.startswith("худи") or t.startswith("hoodie"):
        return "hoodie"
    if "футболка" in t or t.startswith("tshirt") or "tee" in t:
        return "tshirt"
    return None


def detect_theme(title: str) -> dict | None:
    """Find the matching theme payload for a product title."""
    # Try inside «» first
    m = re.search(r"[«\"\u201c](.+?)[»\"\u201d]", title)
    if m:
        candidate = m.group(1).strip().lower()
        if candidate in THEME_LOOKUP:
            return THEME_LOOKUP[candidate]
    # Try classic suffix (without quotes)
    bare = title.lower()
    if "класичн" in bare:
        if "футболка" in bare:
            return _T_CLASSIC.get("classic_tshirt")
        if "худі" in bare or "худи" in bare:
            return _T_CLASSIC.get("classic_hoodie")
        if "лонгслів" in bare:
            return _T_CLASSIC.get("classic_longsleeve")
    # Try whole-title substring lookup against theme keys (handles titles
    # like "Футболка 225ОШП" without quotes).
    for theme_key, payload in THEME_LOOKUP.items():
        if theme_key and theme_key in bare:
            return payload
    return None


# ---------------------------------------------------------------------------
# Per-product translation builder
# ---------------------------------------------------------------------------
LANGS = ("ru", "en")


def _theme_display_name(theme: dict, lang: str) -> str:
    """Return the theme display name for a given language."""
    if "title" in theme and isinstance(theme["title"], dict):
        return theme["title"].get(lang) or theme["title"].get("uk", "")
    key = f"{lang}_name"
    if key in theme:
        return theme[key]
    return ""


def build_product_translation(product: dict) -> dict:
    """Return field→lang→str for a single dumped product entry."""
    title_uk = product["title"]["uk"]
    ptype = detect_ptype(title_uk)
    theme = detect_theme(title_uk)
    out: dict[str, dict[str, str]] = {}

    if not ptype or not theme:
        return out  # cannot template, leave for manual override

    ptype_data = PTYPES[ptype]

    # Classic basics are detected by presence of ``uk_name`` absence AND
    # ``title`` presence in the theme payload. Themed prints expose
    # ``uk_name``/``ru_name``/``en_name`` keys.
    is_classic = "uk_name" not in theme

    for lang in LANGS:
        nom = ptype_data[lang]["nom"]
        gen = ptype_data[lang]["gen"]
        if is_classic:
            title = theme["title"].get(lang, "")
        else:
            theme_name = _theme_display_name(theme, lang)
            title = f"{nom} «{theme_name}»"

        pitch = theme.get("pitch", {}).get(lang, "")
        alt = theme.get("alt", {}).get(lang, "")
        target_intro = theme.get("target", {}).get(lang, "")
        kw_seed = theme.get("kw", {}).get(lang, "")

        # short_description, full description and seo_description
        if pitch:
            short = f"{nom} «{_theme_display_name(theme, lang) if not is_classic else ''}»".strip()
            short = short.replace("«»", "").strip()
            short = f"{short} TwoComms: {pitch}." if not is_classic else f"{title} TwoComms: {pitch}."
        else:
            short = ""

        alt_full = f"{title} TwoComms - {alt}." if alt else ""
        seo_title = theme.get("seo_title", {}).get(lang) or (
            f"{title} — {gen} TwoComms".replace("купити", "")  # fallback
        )
        if "seo_title" in theme:
            seo_title = theme["seo_title"].get(lang, seo_title)
        else:
            # Reconstruct the typical SEO title shape per language.
            if lang == "ru":
                seo_title = f"{title} — купить {gen} TwoComms"
            else:
                # EN reads more naturally without "buy <gen> TwoComms".
                seo_title = f"{title} — buy at TwoComms"

        seo_desc = f"{short} {SEO_TAIL[lang]}".strip()
        target_audience = (
            f"{target_intro} {TARGET_TAIL[lang]}".strip() if target_intro else ""
        )
        care = CARE[ptype][lang]
        keywords = f"{kw_seed}, {PTYPE_KW_TAIL[ptype][lang]}".strip(", ")

        out.setdefault("title", {})[lang] = title
        if short:
            out.setdefault("short_description", {})[lang] = short
        if alt_full:
            out.setdefault("main_image_alt", {})[lang] = alt_full
        if seo_title:
            out.setdefault("seo_title", {})[lang] = seo_title
        if seo_desc:
            out.setdefault("seo_description", {})[lang] = seo_desc
        if target_audience:
            out.setdefault("target_audience", {})[lang] = target_audience
        if care:
            out.setdefault("care_instructions", {})[lang] = care
        if keywords:
            out.setdefault("seo_keywords", {})[lang] = keywords

    return out


# ---------------------------------------------------------------------------
# FAQ builder
# ---------------------------------------------------------------------------
def build_faq_translation(entry: dict) -> dict:
    q_uk = entry["question"]["uk"].strip()
    a_uk = entry["answer"]["uk"].strip()
    payload: dict[str, dict[str, str]] = {}
    if q_uk in QUESTIONS:
        payload["question"] = QUESTIONS[q_uk]
    if a_uk in ANSWERS:
        payload["answer"] = ANSWERS[a_uk]
    return payload


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", required=True, help="Path to dump JSON")
    parser.add_argument("--out", required=True, help="Output JSON path")
    args = parser.parse_args()

    with open(args.dump, "r", encoding="utf-8") as fh:
        dump = json.load(fh)

    by_id_products: dict[str, dict] = {}
    untranslated: list[tuple[int, str]] = []

    for product in dump["products"]:
        translations = build_product_translation(product)
        if translations:
            by_id_products[str(product["id"])] = translations
        else:
            untranslated.append((product["id"], product["title"]["uk"]))

    by_id_faq: dict[str, dict] = {}
    untranslated_faq: list[tuple[int, str]] = []
    for entry in dump["faq"]:
        translations = build_faq_translation(entry)
        if translations:
            by_id_faq[str(entry["id"])] = translations
        else:
            untranslated_faq.append((entry["id"], entry["question"]["uk"][:60]))

    # Categories: keyed by UA name (a unique field per row).
    categories_by_name: dict[str, dict] = {}
    for cat in dump["categories"]:
        name_uk = cat["name"]["uk"].strip()
        if name_uk in CATEGORIES:
            categories_by_name[name_uk] = {
                field: lang_map
                for field, lang_map in CATEGORIES[name_uk].items()
                if isinstance(lang_map, dict)
            }

    payload = {
        "products": {},  # we use by_id for products to avoid title-conflict risk
        "categories": categories_by_name,
        "faq": {},
        "by_id": {
            "products": by_id_products,
            "faq": by_id_faq,
        },
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)

    print(
        f"Wrote {out_path}: {len(by_id_products)} products + "
        f"{len(categories_by_name)} categories + "
        f"{len(by_id_faq)} faq."
    )
    if untranslated:
        print(f"\nUntranslated products ({len(untranslated)}):")
        for pk, title in untranslated:
            print(f"  #{pk}  {title}")
    if untranslated_faq:
        print(f"\nUntranslated FAQ rows ({len(untranslated_faq)}):")
        seen: set[str] = set()
        for pk, q in untranslated_faq:
            if q in seen:
                continue
            seen.add(q)
            print(f"  #{pk}  {q}")


if __name__ == "__main__":
    main()
