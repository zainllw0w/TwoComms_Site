#!/usr/bin/env python3
"""Show first 15 lines of every broken JSON-LD block in the given URL."""
import sys
import re
import urllib.request

URL = sys.argv[1] if len(sys.argv) > 1 else "https://twocomms.shop/delivery/"

with urllib.request.urlopen(URL) as r:
    html = r.read().decode("utf-8", errors="replace")

blocks = re.findall(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    html,
    re.DOTALL,
)
print(f"URL: {URL}\nTotal LD blocks: {len(blocks)}\n")

import json

for i, raw in enumerate(blocks):
    raw = raw.strip()
    print(f"--- Block {i} (len {len(raw)}) ---")
    try:
        d = json.loads(raw)
        if isinstance(d, dict):
            print(f"  OK type={d.get('@type')}")
        elif isinstance(d, list):
            print(f"  OK list of {len(d)}: " + ",".join(str(x.get('@type')) for x in d if isinstance(x, dict)))
    except json.JSONDecodeError as e:
        print(f"  ERROR: {e}")
        print("  Lines around error:")
        for li, line in enumerate(raw.split("\n")[:25], 1):
            print(f"  {li:3d}: {line!r}")
    print()
