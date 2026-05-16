#!/usr/bin/env python3
"""Summarize probe_results.json into a readable table."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    data = json.loads((ROOT / "audit_data/probe_results.json").read_text())
    print(f"{'STATUS':<6} {'ROBOTS':<32} {'CANONICAL':<70} {'TITLE'} ← URL")
    print("-" * 200)
    for r in data:
        url = r["url"]
        status = r["status"]
        robots = (r.get("robots") or "")[:30]
        canonical = (r.get("canonical") or "")[:68]
        title = (r.get("title") or "")[:80]
        print(f"{status:<6} {robots:<32} {canonical:<70} {title}  ← {url}")

    # Group: titles per base PDP & variants
    print("\n\n=== Title uniqueness for classic-tshirt path-URLs ===")
    base_titles = {}
    for r in data:
        if "/product/classic-tshirt" in r["url"]:
            base_titles[r["url"]] = r.get("title", "")
    for u, t in base_titles.items():
        print(f"  {u}\n    {t}")

    print("\n\n=== Title uniqueness for my-little-baby path-URLs ===")
    for r in data:
        if "/product/my-little-baby" in r["url"]:
            print(f"  {r['url']}\n    {r.get('title','')}")

    print("\n\n=== Title uniqueness for where-mi-present-ts path-URLs ===")
    for r in data:
        if "/product/where-mi-present-ts" in r["url"]:
            print(f"  {r['url']}\n    {r.get('title','')}")

    print("\n\n=== Hreflang sets (sample) ===")
    for r in data[:5]:
        print(f"\n  {r['url']}")
        for k, v in (r.get("hreflang") or {}).items():
            print(f"    {k}: {v}")

    print("\n\n=== Query-string facets ===")
    targets = ["?color=", "?fit=", "?size=", "?utm_", "?gclid", "?fbclid", "?page=", "/search/"]
    for r in data:
        if any(t in r["url"] for t in targets):
            print(f"  url={r['url']}")
            print(f"    status={r['status']} robots={r.get('robots')} canonical={r.get('canonical')}")
            print(f"    title={(r.get('title') or '')[:100]}")


if __name__ == "__main__":
    main()
