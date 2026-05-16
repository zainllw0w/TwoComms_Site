#!/usr/bin/env python3
"""Analyze raw scan results: produce aggregations and feed the report builder."""
from __future__ import annotations

import collections
import json
import os
import re
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = json.load(open(os.path.join(HERE, "raw_results_filtered.json"), encoding="utf-8"))


def loc(url: str) -> str:
    p = urlparse(url).path
    if p.startswith("/ru/"):
        return "ru"
    if p.startswith("/en/"):
        return "en"
    return "uk"


def unloc_path(url: str) -> str:
    p = urlparse(url).path
    if p.startswith("/ru/") or p.startswith("/en/"):
        return p[3:]
    return p


# ---- Aggregations ----
total = len(DATA)
errors = [r for r in DATA if r.get("error")]
ok = [r for r in DATA if not r.get("error")]
issue_types = collections.Counter()
leak_field_buckets = collections.Counter()
leak_locale = collections.Counter()
indexable = sum(1 for r in ok if r.get("indexable"))
noindex = sum(1 for r in ok if not r.get("indexable"))

for r in DATA:
    for i in r.get("issues") or []:
        issue_types[i.get("type")] += 1
    for l in r.get("leaks") or []:
        # bucket: top-level field family
        f = l["field"].split("[", 1)[0].split(".", 1)[0]
        leak_field_buckets[f] += 1
        leak_locale[r["locale"]] += 1

print("=== TOTALS ===")
print(f"  scanned: {total}, ok: {len(ok)}, errors: {len(errors)}")
print(f"  indexable: {indexable}, noindex: {noindex}")
print(f"  issue types: {issue_types.most_common()}")
print(f"  leak field buckets: {leak_field_buckets.most_common()}")
print(f"  leaks by locale: {leak_locale.most_common()}")

# Hottest pages
hot = sorted(
    ok,
    key=lambda r: (-len(r.get("leaks") or []), -len(r.get("issues") or [])),
)[:50]
print()
print("=== TOP 20 hottest pages by leak count ===")
for r in hot[:20]:
    print(f"  {len(r.get('leaks') or []):3d}L {len(r.get('issues') or []):2d}I "
          f"[{r['locale']}] {r['url']}")

# Phrase clusters
phrase_counts: collections.Counter = collections.Counter()
phrase_origin: dict = {}
for r in ok:
    for l in r.get("leaks") or []:
        v = l.get("value") or ""
        # Нормализуем: первые 90 символов как phrase key.
        key = re.sub(r"\s+", " ", v).strip()[:90]
        phrase_counts[key] += 1
        phrase_origin.setdefault(key, []).append(
            (r["url"], l["field"], r["locale"]),
        )

print()
print("=== TOP 30 phrase clusters (cross-language repeating strings) ===")
for ph, c in phrase_counts.most_common(30):
    print(f"  {c:3d}× '{ph}'")

# Per-issue type breakdown by URL
print()
print("=== ISSUE BREAKDOWN ===")
critical_types = (
    "canonical_wrong", "canonical_missing",
    "hreflang_wrong", "hreflang_missing",
    "title_missing", "description_missing", "h1_missing", "h1_empty",
    "title_length", "description_length", "keywords_length",
    "fetch_error", "http_error",
)
for t in critical_types:
    urls = [r for r in DATA for i in (r.get("issues") or []) if i.get("type") == t]
    if not urls:
        continue
    print(f"  {t}: {len(urls)} pages")

# Cross-language leaks per locale: which pages leak how many?
print()
print("=== LEAK BY LOCALE (pages with > 0 leaks) ===")
by_locale = collections.defaultdict(list)
for r in ok:
    by_locale[r["locale"]].append(len(r.get("leaks") or []))
for k, vals in by_locale.items():
    nz = [v for v in vals if v]
    print(f"  {k}: {len(nz)}/{len(vals)} pages with leaks (max {max(vals or [0])}, avg {sum(vals)/max(len(vals),1):.1f})")

# Save aggregated output
out = {
    "totals": {
        "scanned": total, "ok": len(ok), "errors": len(errors),
        "indexable": indexable, "noindex": noindex,
    },
    "issue_types": dict(issue_types),
    "leak_field_buckets": dict(leak_field_buckets),
    "leaks_by_locale": dict(leak_locale),
    "hot_pages": [
        {
            "url": r["url"], "locale": r["locale"],
            "leaks": len(r.get("leaks") or []),
            "issues": len(r.get("issues") or []),
            "leak_summary": [
                {"field": l["field"], "value": l["value"][:120], "markers": l["markers"][:5]}
                for l in (r.get("leaks") or [])
            ][:10],
            "issue_summary": r.get("issues") or [],
        }
        for r in hot
    ],
    "phrase_clusters": [
        {
            "phrase": ph,
            "count": c,
            "examples": phrase_origin[ph][:8],
        }
        for ph, c in phrase_counts.most_common(50)
    ],
}
with open(os.path.join(HERE, "summary.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print()
print("summary -> _audit/summary.json")
