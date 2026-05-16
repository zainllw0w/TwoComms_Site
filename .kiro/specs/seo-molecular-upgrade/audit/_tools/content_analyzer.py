#!/usr/bin/env python3
"""
Content density analyzer for SEO audit.

Extracts visible text from HTML pages, computes:
- word count (visible)
- text-to-html ratio
- top-30 word frequency (after stop-word filtering)
- heading hierarchy
- whether page contains TL;DR / FAQ / lists
- estimated unique-content density (n-gram shingle hash)

Usage:
    python3 content_analyzer.py <html_dir> [--out <out_md>]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

# ------- text extraction -------

SCRIPT_RE = re.compile(r"<script\b[^>]*>.*?</script>", re.DOTALL | re.IGNORECASE)
STYLE_RE = re.compile(r"<style\b[^>]*>.*?</style>", re.DOTALL | re.IGNORECASE)
COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")

# Crude visible-text extractor. Good enough for SEO density audit.
def extract_visible_text(html: str) -> str:
    h = SCRIPT_RE.sub(" ", html)
    h = STYLE_RE.sub(" ", h)
    h = COMMENT_RE.sub(" ", h)
    h = TAG_RE.sub(" ", h)
    # decode common HTML entities we care about
    h = (
        h.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&laquo;", "«")
        .replace("&raquo;", "»")
        .replace("&mdash;", "—")
        .replace("&ndash;", "–")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
    )
    h = WS_RE.sub(" ", h)
    return h.strip()


def title_of(html: str) -> str:
    m = re.search(r"<title>([^<]+)</title>", html)
    return m.group(1).strip() if m else ""


def meta_desc_of(html: str) -> str:
    m = re.search(
        r'<meta[^>]+name=["\']description["\'][^>]*content=["\']([^"\']+)["\']',
        html,
        re.IGNORECASE,
    )
    return m.group(1).strip() if m else ""


def meta_keywords_of(html: str) -> str:
    m = re.search(
        r'<meta[^>]+name=["\']keywords["\'][^>]*content=["\']([^"\']+)["\']',
        html,
        re.IGNORECASE,
    )
    return m.group(1).strip() if m else ""


def headings_of(html: str) -> dict:
    out = {}
    for level in range(1, 7):
        items = re.findall(rf"<h{level}\b[^>]*>(.*?)</h{level}>", html, re.DOTALL | re.IGNORECASE)
        cleaned = []
        for it in items:
            t = TAG_RE.sub(" ", it)
            t = WS_RE.sub(" ", t).strip()
            if t:
                cleaned.append(t)
        out[f"h{level}"] = cleaned
    return out


# ------- stop words -------

STOP = set(
    """
    і й та чи то це що як де коли чому який яка яке які або але хіба
    же ж бо щоб такий така таке такі мені тобі йому її його їх ми ви
    вони він вона воно ти ваш наш на у в з с до по від від ра при для
    про про про без по зо для між над під через одна один одне на
    та те ті то цю ці цю цей цей ця ці цим цією цими цьому цій ці
    """.split()
) | set(
    "a an the and or of to in for is are was were be been being have has had do does did "
    "this that these those with from at by as on it its they them you your we us our".split()
) | set(
    "и в во не на я он она оно мы вы они их его её ему ей с со к ко по при за из у "
    "о об но или а же ли ну да тот эта это эти такой такая такое что когда где как почему".split()
)


def normalize_word(w: str) -> str:
    return w.lower().strip(".,;:!?'\"«»()[]{}—–-")


WORD_RE = re.compile(r"[A-Za-zА-Яа-яІіЇїЄєҐґ][A-Za-zА-Яа-яІіЇїЄєҐґ\-]{2,}")


def words_of(text: str) -> list[str]:
    return [
        normalize_word(w)
        for w in WORD_RE.findall(text)
        if normalize_word(w) and normalize_word(w) not in STOP and len(normalize_word(w)) >= 3
    ]


def shingles(words: list[str], n: int = 5) -> set[str]:
    out = set()
    for i in range(len(words) - n + 1):
        sh = " ".join(words[i : i + n])
        out.add(hashlib.sha1(sh.encode()).hexdigest()[:16])
    return out


# ------- main analyser -------

def analyze_page(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8", errors="replace")
    text = extract_visible_text(raw)
    headings = headings_of(raw)
    ws = words_of(text)
    return {
        "path": str(path.name),
        "html_size": len(raw),
        "text_size": len(text),
        "text_to_html_ratio": round(len(text) / max(1, len(raw)) * 100, 1),
        "word_count": len(ws),
        "unique_word_count": len(set(ws)),
        "title": title_of(raw),
        "title_len": len(title_of(raw)),
        "meta_desc": meta_desc_of(raw),
        "meta_desc_len": len(meta_desc_of(raw)),
        "meta_keywords": meta_keywords_of(raw),
        "h1": headings["h1"],
        "h2_count": len(headings["h2"]),
        "h3_count": len(headings["h3"]),
        "h2": headings["h2"][:8],
        "top_words": Counter(ws).most_common(20),
        "shingles": shingles(ws, 5),
        "has_faq_marker": ("FAQ" in raw) or ("Поширені" in raw) or ("Часто" in raw),
        "has_lists": raw.count("<ul") + raw.count("<ol"),
        "has_tables": raw.count("<table"),
        "has_tldr": "tldr" in raw.lower() or "коротко" in raw.lower(),
    }


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("html_dir")
    ap.add_argument("--out", default="-")
    ns = ap.parse_args(argv[1:])

    pages = []
    for p in sorted(Path(ns.html_dir).glob("*.html")):
        try:
            pages.append(analyze_page(p))
        except Exception as e:
            print(f"FAIL: {p.name}: {e}", file=sys.stderr)

    # cross-page shingle overlap = how much text is duplicated across pages
    by_name = {p["path"]: p for p in pages}
    overlaps = []
    names = list(by_name.keys())
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = by_name[names[i]], by_name[names[j]]
            if not a["shingles"] or not b["shingles"]:
                continue
            inter = a["shingles"] & b["shingles"]
            min_size = min(len(a["shingles"]), len(b["shingles"]))
            if min_size == 0:
                continue
            ratio = len(inter) / min_size
            if ratio >= 0.20:
                overlaps.append((names[i], names[j], round(ratio * 100, 1), len(inter), min_size))

    output = []
    output.append(f"# Content Density Audit\n")
    output.append(f"Pages analyzed: {len(pages)}\n\n")

    output.append("## Page-by-page metrics\n\n")
    output.append("| Page | HTML | Text | Ratio% | Words | Unique | Title len | Desc len | H1 | H2 | H3 |\n")
    output.append("|---|---|---|---|---|---|---|---|---|---|---|\n")
    for p in pages:
        h1 = (p["h1"][0] if p["h1"] else "—")[:40]
        output.append(
            f"| {p['path']} | {p['html_size']} | {p['text_size']} | {p['text_to_html_ratio']} | "
            f"{p['word_count']} | {p['unique_word_count']} | {p['title_len']} | {p['meta_desc_len']} | "
            f"{h1} | {p['h2_count']} | {p['h3_count']} |\n"
        )

    output.append("\n## Top words per page (excl. stopwords, len>=3)\n\n")
    for p in pages:
        output.append(f"**{p['path']}** — {p['word_count']} words / {p['unique_word_count']} unique\n\n")
        line = ", ".join(f"{w} ({c})" for w, c in p["top_words"])
        output.append(f"  {line}\n\n")

    output.append("\n## Title / meta description matrix\n\n")
    output.append("| Page | Title | Description |\n|---|---|---|\n")
    for p in pages:
        t = (p["title"] or "—").replace("|", "\\|")[:80]
        d = (p["meta_desc"] or "—").replace("|", "\\|")[:140]
        output.append(f"| {p['path']} | {t} | {d} |\n")

    if overlaps:
        output.append("\n## Cross-page content overlap (>=20%)\n\n")
        output.append("Note: overlap is computed on 5-word shingles after stop-word filtering and includes navigation/footer.\n\n")
        output.append("| Page A | Page B | Overlap % | Shared shingles | Smaller side |\n|---|---|---|---|---|\n")
        for a, b, r, sh, mn in sorted(overlaps, key=lambda x: -x[2]):
            output.append(f"| {a} | {b} | {r} | {sh} | {mn} |\n")
    else:
        output.append("\n## Cross-page overlap: none above 20%\n\n")

    out_text = "".join(output)
    if ns.out == "-":
        sys.stdout.write(out_text)
    else:
        Path(ns.out).write_text(out_text, encoding="utf-8")
        print(f"wrote {ns.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
