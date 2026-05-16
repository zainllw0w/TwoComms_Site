#!/usr/bin/env python3
"""Parse all twocomms.shop sitemaps, classify URLs, analyze slugs."""
import json
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "audit_data"
NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
NS_X = "{http://www.w3.org/1999/xhtml}"
NS_IMG = "{http://www.google.com/schemas/sitemap-image/1.1}"


def parse_urlset(path):
    """Return list of dicts: {loc, lastmod, hreflang:{lang:href}, changefreq, priority}."""
    if not path.exists():
        return []
    tree = ET.parse(path)
    root = tree.getroot()
    out = []
    for url in root.findall(f"{NS}url"):
        loc = url.findtext(f"{NS}loc")
        lastmod = url.findtext(f"{NS}lastmod")
        changefreq = url.findtext(f"{NS}changefreq")
        priority = url.findtext(f"{NS}priority")
        hreflang = {}
        for link in url.findall(f"{NS_X}link"):
            rel = link.get("rel")
            lang = link.get("hreflang")
            href = link.get("href")
            if rel == "alternate" and lang and href:
                hreflang[lang] = href
        images = []
        for img in url.findall(f"{NS_IMG}image"):
            iloc = img.findtext(f"{NS_IMG}loc")
            if iloc:
                images.append(iloc)
        out.append({
            "loc": loc,
            "lastmod": lastmod,
            "changefreq": changefreq,
            "priority": priority,
            "hreflang": hreflang,
            "images": images,
        })
    return out


def parse_index(path):
    tree = ET.parse(path)
    root = tree.getroot()
    return [{"loc": s.findtext(f"{NS}loc"), "lastmod": s.findtext(f"{NS}lastmod")}
            for s in root.findall(f"{NS}sitemap")]


SITEMAPS = {
    "static": "sitemap-static.xml",
    "products": "sitemap-products.xml",
    "product_variants": "sitemap-product-variants.xml",
    "categories": "sitemap-categories.xml",
    "color_categories": "sitemap-color-categories.xml",
    "images": "sitemap-images.xml",
}


def classify_locale(url):
    m = re.match(r"^https?://twocomms\.shop(/(ru|en))?(/.*)?$", url)
    if not m:
        return "unknown"
    if m.group(2):
        return m.group(2)
    return "uk"


def main():
    index = parse_index(DATA / "sitemap.xml")
    print("=== sitemap index ===")
    for item in index:
        print(item)

    by_section = {}
    for name, fname in SITEMAPS.items():
        urls = parse_urlset(DATA / fname)
        by_section[name] = urls
        # Locale split
        locales = defaultdict(int)
        for u in urls:
            locales[classify_locale(u["loc"])] += 1
        print(f"\n=== {name}: total={len(urls)} locales={dict(locales)} ===")
        if urls:
            print(f"  first loc: {urls[0]['loc']}")
            if urls[0].get("hreflang"):
                print(f"  first hreflang keys: {list(urls[0]['hreflang'].keys())}")

    # Save raw
    raw = {
        "index": index,
        "sections": {name: urls for name, urls in by_section.items()},
    }
    out_raw = ROOT / "03_urls_raw.json"
    out_raw.write_text(json.dumps(raw, ensure_ascii=False, indent=2))
    print(f"\nWrote {out_raw}")

    # Slug analysis on products sitemap
    product_urls = by_section.get("products", [])
    slug_re = re.compile(r"/product/([^/]+)/?$")
    slugs = []
    for u in product_urls:
        # Only canonical UA URL (no /ru/ /en/)
        loc = u["loc"]
        m = slug_re.search(loc.rstrip("/") + "/")
        if not m:
            continue
        if "/ru/" in loc or "/en/" in loc:
            continue
        slugs.append({"slug": m.group(1), "loc": loc})

    # Dedupe
    seen = set()
    uniq = []
    for s in slugs:
        if s["slug"] in seen:
            continue
        seen.add(s["slug"])
        uniq.append(s)
    print(f"\n=== unique product slugs: {len(uniq)} ===")

    out_slugs = ROOT / "audit_data/slugs.json"
    out_slugs.write_text(json.dumps(uniq, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
