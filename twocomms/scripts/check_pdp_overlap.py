#!/usr/bin/env python3
"""Verify pairwise PDP content overlap (CP-3.1).

SEO molecular-upgrade US-3 acceptance test.

The audit measured >70% pairwise 5-gram Jaccard overlap on 40+ PDP
pairs because every product surfaced the same delivery / care /
size-guide boilerplate. After the dynamic SEO block ships, this
script verifies that the rendered SEO block alone keeps overlap
below the 30% threshold demanded by ``CP-3.1``.

Usage::

    DJANGO_SETTINGS_MODULE=twocomms.settings python scripts/check_pdp_overlap.py

Outputs a JSON report to stdout with ``violations`` listing any pair
above the threshold and a top-10 worst offenders list. Exit code 0
when CP-3.1 holds, 1 otherwise so this can guard CI.

The check only looks at the SEO block content (paragraphs + FAQ
answers from ``build_product_seo_block``) — that is what we control.
The legacy tabs (delivery / care) are intentionally excluded because
they are scope of US-4 (extended support pages), not US-3.
"""
from __future__ import annotations

import os
import sys
import json
from collections import Counter
from typing import Dict, Iterable, List, Set, Tuple

import django

OVERLAP_THRESHOLD = 0.30  # CP-3.1
SHINGLE_SIZE = 5
TOP_OFFENDERS = 10


def _setup_django() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "twocomms.settings")
    django.setup()


def _shingles(text: str, n: int = SHINGLE_SIZE) -> Set[Tuple[str, ...]]:
    tokens = [t for t in text.lower().split() if t]
    if len(tokens) < n:
        return set()
    return {tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1)}


def _flatten_block(block: dict) -> str:
    out: List[str] = []
    for section in block.get("sections", []):
        out.append(section.get("heading", ""))
        for p in section.get("paragraphs", []):
            out.append(p)
    for q in block.get("faq", []):
        out.append(q.get("question", ""))
        out.append(q.get("answer", ""))
    return "\n".join(filter(None, out))


def main() -> int:
    _setup_django()
    from storefront.models import Product
    from storefront.services.product_seo_block import build_product_seo_block

    products = list(
        Product.objects.filter(price__isnull=False).only(
            "id", "slug", "title"
        )
    )
    if not products:
        print(json.dumps({"products": 0, "ok": True, "violations": []}, indent=2))
        return 0

    shingles_by_id: Dict[int, Set[Tuple[str, ...]]] = {}
    for product in products:
        block = build_product_seo_block(product, language_code="uk")
        shingles_by_id[product.id] = _shingles(_flatten_block(block))

    violations: List[Dict[str, object]] = []
    pair_jaccards: List[Tuple[int, int, float]] = []

    items = list(shingles_by_id.items())
    for i in range(len(items)):
        a_id, a_set = items[i]
        if not a_set:
            continue
        for j in range(i + 1, len(items)):
            b_id, b_set = items[j]
            if not b_set:
                continue
            inter = len(a_set & b_set)
            union = len(a_set | b_set)
            if union == 0:
                continue
            jaccard = inter / union
            pair_jaccards.append((a_id, b_id, jaccard))
            if jaccard > OVERLAP_THRESHOLD:
                violations.append(
                    {
                        "a_id": a_id,
                        "b_id": b_id,
                        "jaccard": round(jaccard, 4),
                    }
                )

    pair_jaccards.sort(key=lambda x: x[2], reverse=True)
    worst = [
        {"a_id": a, "b_id": b, "jaccard": round(j, 4)}
        for (a, b, j) in pair_jaccards[:TOP_OFFENDERS]
    ]

    report = {
        "products": len(products),
        "pairs": len(pair_jaccards),
        "violations": violations,
        "violation_count": len(violations),
        "threshold": OVERLAP_THRESHOLD,
        "worst_offenders": worst,
        "ok": not violations,
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if not violations else 1


if __name__ == "__main__":
    raise SystemExit(main())
