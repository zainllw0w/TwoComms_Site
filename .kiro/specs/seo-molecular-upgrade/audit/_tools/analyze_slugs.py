#!/usr/bin/env python3
"""Analyze product slugs for SEO issues."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def issues(slug):
    out = []
    if slug.startswith("-"):
        out.append("starts_with_hyphen")
    if slug.endswith("-"):
        out.append("ends_with_hyphen")
    if any(c.isupper() for c in slug):
        out.append("uppercase")
    if "_" in slug:
        out.append("underscore")
    if "--" in slug:
        out.append("double_hyphen")
    if not re.fullmatch(r"[a-z0-9-]+", slug):
        out.append("invalid_chars")
    if len(slug) > 60:
        out.append("over_60_chars")
    if len(slug) < 4:
        out.append("too_short")
    return out


# Heuristic misspellings for TwoComms products
MISSPELLS = {
    # ts/tshort variants
    "ts": ("tshirt", "abbreviated_garment_suffix"),
    "tshort": ("tshirt", "typo"),
    "tsht": ("tshirt", "typo"),
    "trsht": ("tshirt", "typo"),
    "hd": ("hoodie", "abbreviated_garment_suffix"),
    "ls": ("longsleeve", "abbreviated_garment_suffix"),
    # word-level typos
    "clasic": ("classic", "typo"),
    "buisness": ("business", "typo"),
    "beliveidea": ("believe-idea", "spaceless_compound"),
    "gbs": ("grabs", "abbreviated_word"),
    "kha": ("kharkiv", "abbreviated_word"),
    "pojuy": ("pofuy", "transliteration_inconsistency"),  # debatable
    "shee": ("face", "obscure_word"),  # internal joke; not a meaningful slug for SEO
    "dff": ("", "draft_placeholder"),
}


def detect_misspellings(slug):
    notes = []
    parts = slug.split("-")
    for p in parts:
        if p in MISSPELLS:
            target, kind = MISSPELLS[p]
            notes.append(f"{p}→{target} ({kind})")
    return notes


# Suggested rewrite map (manually curated based on slug + title context)
def suggest(slug, title):
    # General principle: lowercase, hyphenated, full words, brand+motif+garment
    # Map titles → keywords
    return None  # we'll fill manually below


def main():
    slugs = json.loads((ROOT / "audit_data/slugs.json").read_text())
    inv = json.loads((ROOT / "_tmp_inventory.json").read_text())
    title_by_slug = {p["slug"]: p["title"] for p in inv["products"]}

    results = []
    for s in slugs:
        slug = s["slug"]
        problems = issues(slug)
        miss = detect_misspellings(slug)
        title = title_by_slug.get(slug, "?")
        if problems or miss:
            results.append({
                "slug": slug,
                "title": title,
                "issues": problems,
                "misspell": miss,
            })

    print(f"Total slugs analyzed: {len(slugs)}")
    print(f"Slugs with issues:    {len(results)}")
    print()
    for r in results:
        print(f"  {r['slug']:48s}  issues={r['issues']}  miss={r['misspell']}  title={r['title']}")

    out = ROOT / "audit_data/slug_issues.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
