#!/usr/bin/env python3
"""Fetch HTML pages from twocomms.shop and extract all JSON-LD blocks.

Outputs:
  /tmp/seo_audit/schema/raw/<slug>.html        — raw HTML
  /tmp/seo_audit/schema/parsed/<slug>.json     — list of parsed JSON-LD blocks (with parse error info)
  /tmp/seo_audit/schema/summary.json           — global summary {url, slug, types[], errors[], blocks_count}
"""
import json
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from html import unescape
from pathlib import Path

ROOT = Path("/tmp/seo_audit/schema")
RAW = ROOT / "raw"
PARSED = ROOT / "parsed"
RAW.mkdir(parents=True, exist_ok=True)
PARSED.mkdir(parents=True, exist_ok=True)

PAGES = {
    "home":            "https://twocomms.shop/",
    "catalog-root":    "https://twocomms.shop/catalog/",
    "cat-tshirts":     "https://twocomms.shop/catalog/tshirts/",
    "cat-hoodie":      "https://twocomms.shop/catalog/hoodie/",
    "cat-long-sleeve": "https://twocomms.shop/catalog/long-sleeve/",
    "pdp-classic-tshirt":      "https://twocomms.shop/product/classic-tshirt/",
    "pdp-hoodie-classic":      "https://twocomms.shop/product/hoodie-classic/",
    "pdp-longsleeve-classic":  "https://twocomms.shop/product/longsleeve-classic/",
    "pdp-my-little-baby":      "https://twocomms.shop/product/my-little-baby/",
    "pdp-where-mi-present-ts": "https://twocomms.shop/product/where-mi-present-ts/",
    "pdp-in-shee":             "https://twocomms.shop/product/in-shee/",
    "var-classic-tshirt-black":     "https://twocomms.shop/product/classic-tshirt/black/",
    "var-classic-tshirt-oversize":  "https://twocomms.shop/product/classic-tshirt/oversize/",
    "var-my-little-baby-coyote":    "https://twocomms.shop/product/my-little-baby/coyote/",
    "pdp-ru-classic-tshirt":   "https://twocomms.shop/ru/product/classic-tshirt/",
    "pdp-en-classic-tshirt":   "https://twocomms.shop/en/product/classic-tshirt/",
    "delivery":           "https://twocomms.shop/delivery/",
    "pro-brand":          "https://twocomms.shop/pro-brand/",
    "contacts":           "https://twocomms.shop/contacts/",
    "cooperation":        "https://twocomms.shop/cooperation/",
    "custom-print":       "https://twocomms.shop/custom-print/",
    "wholesale":          "https://twocomms.shop/wholesale/",
    "dopomoga":           "https://twocomms.shop/dopomoga/",
    "faq":                "https://twocomms.shop/faq/",
    "rozmirna-sitka":     "https://twocomms.shop/rozmirna-sitka/",
    "doglyad-za-odyagom": "https://twocomms.shop/doglyad-za-odyagom/",
    "vidstezhennya":      "https://twocomms.shop/vidstezhennya-zamovlennya/",
    "mapa-saytu":         "https://twocomms.shop/mapa-saytu/",
    "novyny":             "https://twocomms.shop/novyny/",
    "povernennya":        "https://twocomms.shop/povernennya-ta-obmin/",
    "privacy":            "https://twocomms.shop/polityka-konfidentsiynosti/",
    "terms":              "https://twocomms.shop/umovy-vykorystannya/",
}

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15"

SCRIPT_RE = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)

def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "uk,en;q=0.7"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read()
        try:
            return body.decode("utf-8")
        except UnicodeDecodeError:
            return body.decode("latin-1", errors="replace")

def collect_types(node, out):
    if isinstance(node, dict):
        t = node.get("@type")
        if isinstance(t, str):
            out.add(t)
        elif isinstance(t, list):
            for x in t:
                if isinstance(x, str):
                    out.add(x)
        for v in node.values():
            collect_types(v, out)
    elif isinstance(node, list):
        for v in node:
            collect_types(v, out)

def collect_ids(node, out):
    if isinstance(node, dict):
        i = node.get("@id")
        if isinstance(i, str):
            out.add(i)
        for v in node.values():
            collect_ids(v, out)
    elif isinstance(node, list):
        for v in node:
            collect_ids(v, out)

def process(slug, url):
    rec = {"slug": slug, "url": url, "blocks": [], "errors": [], "types": [], "ids": [], "raw_status": "ok"}
    try:
        html = fetch(url)
    except Exception as e:
        rec["raw_status"] = "fetch-error"
        rec["errors"].append(f"fetch: {e!r}")
        return rec
    (RAW / f"{slug}.html").write_text(html, encoding="utf-8")
    blocks = SCRIPT_RE.findall(html)
    rec["blocks_count"] = len(blocks)
    types_set = set()
    ids_set = set()
    parsed_blocks = []
    for idx, block in enumerate(blocks):
        cleaned = block.strip()
        cleaned_decoded = unescape(cleaned)
        item = {"index": idx, "raw": cleaned, "parsed": None, "parse_error": None}
        try:
            parsed = json.loads(cleaned)
            item["parsed"] = parsed
            collect_types(parsed, types_set)
            collect_ids(parsed, ids_set)
        except json.JSONDecodeError as e1:
            try:
                parsed = json.loads(cleaned_decoded)
                item["parsed"] = parsed
                item["parse_error"] = f"only-after-html-decode: {e1}"
                collect_types(parsed, types_set)
                collect_ids(parsed, ids_set)
            except Exception as e2:
                item["parse_error"] = f"original={e1!r}; decoded={e2!r}"
                rec["errors"].append(f"block{idx}: {e2}")
        parsed_blocks.append(item)
    rec["types"] = sorted(types_set)
    rec["ids"] = sorted(ids_set)
    (PARSED / f"{slug}.json").write_text(json.dumps(parsed_blocks, ensure_ascii=False, indent=2), encoding="utf-8")
    return rec

def main():
    summary = {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(process, slug, url): slug for slug, url in PAGES.items()}
        for fut in as_completed(futures):
            r = fut.result()
            summary[r["slug"]] = r
            print(f"[{r['raw_status']}] {r['slug']:<32} blocks={r.get('blocks_count', 0):<2} types={r['types']}")
    (ROOT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWrote {len(summary)} pages summary to {ROOT / 'summary.json'}")

if __name__ == "__main__":
    main()
