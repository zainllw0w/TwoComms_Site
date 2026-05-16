#!/usr/bin/env python3
"""Analyze parsed JSON-LD: collect matrix, find dupes, count node types per page,
   summarize @id graph, find duplicate FAQ Question entries, missing @id, etc."""
import json
from collections import defaultdict
from pathlib import Path

PARSED = Path("/tmp/seo_audit/schema/parsed")

def collect(node, types_count, ids_with_types):
    if isinstance(node, dict):
        t = node.get("@type")
        if isinstance(t, str):
            types_count[t] = types_count.get(t, 0) + 1
        elif isinstance(t, list):
            for x in t:
                if isinstance(x, str):
                    types_count[x] = types_count.get(x, 0) + 1
        if "@id" in node:
            i = node["@id"]
            t_str = t if isinstance(t, str) else (",".join(t) if isinstance(t, list) else "")
            ids_with_types.setdefault(i, []).append(t_str)
        for v in node.values():
            collect(v, types_count, ids_with_types)
    elif isinstance(node, list):
        for v in node:
            collect(v, types_count, ids_with_types)

def find_questions(node, out):
    if isinstance(node, dict):
        if node.get("@type") == "Question":
            out.append(node.get("name"))
        for v in node.values():
            find_questions(v, out)
    elif isinstance(node, list):
        for v in node:
            find_questions(v, out)

def main():
    rows = []
    all_ids_global = defaultdict(set)  # id -> {page}
    id_type_conflicts = defaultdict(set)  # id -> set(types)
    duplicate_faq_pages = []
    pages_with_broken = []
    pages_no_id_top = []

    for f in sorted(PARSED.glob("*.json")):
        slug = f.stem
        data = json.load(f.open())
        types_count = {}
        ids_with_types = {}
        broken = []
        for b in data:
            if b["parse_error"]:
                broken.append(b["index"])
                continue
            collect(b["parsed"], types_count, ids_with_types)
            # check FAQ duplicates
            if isinstance(b["parsed"], dict) and b["parsed"].get("@type") == "FAQPage":
                qs = []
                find_questions(b["parsed"], qs)
                if len(qs) != len(set(qs)):
                    duplicate_faq_pages.append((slug, len(qs), len(set(qs))))
        if broken:
            pages_with_broken.append((slug, broken))

        # check top-level CollectionPage / WebPage for @id
        for b in data:
            p = b["parsed"]
            if not p:
                continue
            nodes = p.get("@graph") if isinstance(p, dict) and "@graph" in p else [p] if isinstance(p, dict) else p if isinstance(p, list) else []
            for n in (nodes if isinstance(nodes, list) else []):
                if isinstance(n, dict) and n.get("@type") in ("CollectionPage", "WebPage", "AboutPage", "ContactPage", "FAQPage"):
                    if "@id" not in n:
                        pages_no_id_top.append((slug, n.get("@type"), n.get("name")))

        for i, ts in ids_with_types.items():
            for t in ts:
                if t:
                    id_type_conflicts[i].add(t)
            all_ids_global[i].add(slug)

        rows.append({
            "slug": slug,
            "types_count": types_count,
            "ids": list(ids_with_types.keys()),
            "broken": broken,
        })

    # report
    print("=== PAGES WITH PARSE ERRORS ===")
    for slug, idxs in pages_with_broken:
        print(f"  {slug:<32} block_indexes={idxs}")
    print()
    print("=== FAQPage WITH DUPLICATE QUESTIONS ===")
    for slug, total, unique in duplicate_faq_pages:
        print(f"  {slug:<32} total={total} unique={unique} duplicates={total-unique}")
    print()
    print("=== Top-level WebPage-like nodes WITHOUT @id ===")
    for slug, t, name in pages_no_id_top:
        print(f"  {slug:<32} type={t:<18} name={name}")
    print()
    print("=== @id used with multiple @type values (conflict) ===")
    for i, ts in id_type_conflicts.items():
        if len(ts) > 1:
            print(f"  {i} -> {ts}")
    print()
    print("=== @id usage frequency (cross-page) ===")
    for i, pages in sorted(all_ids_global.items(), key=lambda x: -len(x[1])):
        print(f"  {i:<60} on {len(pages)} pages")
    print()
    print("=== Per-page type counts ===")
    for r in rows:
        keys = sorted(r["types_count"].keys())
        print(f"  {r['slug']:<32} {r['types_count']}")

if __name__ == "__main__":
    main()
