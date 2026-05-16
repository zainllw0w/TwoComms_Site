#!/usr/bin/env python3
"""Extract and analyze JSON-LD schema from HTML pages."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

LD_RE = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)


def parse_blocks(html: str) -> list:
    out = []
    for raw in LD_RE.findall(html):
        raw = raw.strip()
        try:
            data = json.loads(raw)
            out.append({"ok": True, "data": data, "raw_size": len(raw)})
        except json.JSONDecodeError as e:
            # try to recover from leading/trailing junk
            try:
                start = raw.index("{")
                end = raw.rindex("}")
                fixed = raw[start : end + 1]
                data = json.loads(fixed)
                out.append({"ok": True, "data": data, "raw_size": len(raw), "recovered": True})
            except Exception:
                out.append({"ok": False, "error": str(e), "raw_size": len(raw), "preview": raw[:120]})
    return out


def types_in(node) -> list[str]:
    """Walk the node and collect all @type values."""
    out = []
    if isinstance(node, dict):
        t = node.get("@type")
        if isinstance(t, str):
            out.append(t)
        elif isinstance(t, list):
            out.extend(t)
        for v in node.values():
            out.extend(types_in(v))
    elif isinstance(node, list):
        for it in node:
            out.extend(types_in(it))
    return out


def has_field_recursive(node, name: str) -> bool:
    if isinstance(node, dict):
        if name in node:
            return True
        return any(has_field_recursive(v, name) for v in node.values())
    if isinstance(node, list):
        return any(has_field_recursive(it, name) for it in node)
    return False


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("html_dir")
    ap.add_argument("--out", default="-")
    ns = ap.parse_args(argv[1:])

    rows = []
    for p in sorted(Path(ns.html_dir).glob("*.html")):
        html = p.read_text(encoding="utf-8", errors="replace")
        blocks = parse_blocks(html)
        all_types = []
        broken = 0
        product_node = None
        for b in blocks:
            if not b["ok"]:
                broken += 1
                continue
            data = b["data"]
            all_types.extend(types_in(data))
            # find Product
            if isinstance(data, dict):
                if data.get("@type") == "Product":
                    product_node = data
                if "@graph" in data and isinstance(data["@graph"], list):
                    for it in data["@graph"]:
                        if isinstance(it, dict) and it.get("@type") == "Product":
                            product_node = it
        rows.append({
            "page": p.name,
            "blocks_total": len(blocks),
            "blocks_broken": broken,
            "types": sorted(set(all_types)),
            "has_org": "Organization" in all_types,
            "has_website": "WebSite" in all_types,
            "has_breadcrumb": "BreadcrumbList" in all_types,
            "has_product": "Product" in all_types,
            "has_faqpage": "FAQPage" in all_types,
            "has_howto": "HowTo" in all_types,
            "has_aboutpage": "AboutPage" in all_types,
            "has_contactpage": "ContactPage" in all_types,
            "has_offercatalog": "OfferCatalog" in all_types,
            "has_person": "Person" in all_types,
            "has_review": "Review" in all_types,
            "has_aggregate": "AggregateRating" in all_types,
            "product_fields": sorted(product_node.keys()) if product_node else [],
        })

    out = []
    out.append(f"# Schema.org Audit\n\nPages: {len(rows)}\n\n")
    out.append("## Coverage matrix\n\n")
    cols = ["page", "blocks", "broken", "types"]
    out.append("| Page | Blocks | Broken | Types |\n|---|---|---|---|\n")
    for r in rows:
        out.append(f"| {r['page']} | {r['blocks_total']} | {r['blocks_broken']} | {', '.join(r['types'])} |\n")

    out.append("\n## Critical entity presence\n\n")
    out.append("| Page | Org | Site | Crumb | Prod | FAQ | HowTo | About | Contact | Offer | Person | Review | Rating |\n")
    out.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|\n")
    flags = ["has_org", "has_website", "has_breadcrumb", "has_product", "has_faqpage", "has_howto",
             "has_aboutpage", "has_contactpage", "has_offercatalog", "has_person", "has_review", "has_aggregate"]
    for r in rows:
        cells = ["✓" if r[f] else "—" for f in flags]
        out.append(f"| {r['page']} | " + " | ".join(cells) + " |\n")

    # Product fields detail
    products = [r for r in rows if r["has_product"]]
    if products:
        out.append("\n## Product schema field coverage\n\n")
        important_fields = [
            "@id", "name", "description", "image", "url", "sku", "mpn", "gtin",
            "gtin8", "gtin12", "gtin13", "gtin14", "brand", "manufacturer",
            "material", "color", "size", "category", "audience", "countryOfOrigin",
            "additionalProperty", "offers", "aggregateRating", "review",
            "isVariantOf", "hasVariant", "releaseDate", "dateModified", "inLanguage",
        ]
        out.append("| Page | " + " | ".join(important_fields) + " |\n")
        out.append("|" + "|".join(["---"] * (len(important_fields) + 1)) + "|\n")
        for r in products:
            cells = ["✓" if f in r["product_fields"] else "—" for f in important_fields]
            out.append(f"| {r['page']} | " + " | ".join(cells) + " |\n")

    if ns.out == "-":
        sys.stdout.write("".join(out))
    else:
        Path(ns.out).write_text("".join(out), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
