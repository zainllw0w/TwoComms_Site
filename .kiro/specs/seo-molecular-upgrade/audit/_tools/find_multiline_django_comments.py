#!/usr/bin/env python3
"""Find multiline {# ... #} comments in Django templates.

Django's {# #} is single-line ONLY — anything spanning multiple lines
LEAKS into the rendered HTML and can break JSON-LD, JS, CSS, etc.
Use {% comment %}...{% endcomment %} for multiline.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".")

# Find all {# ... that has no #} on the same line.
PROBLEM_RE = re.compile(r"\{#(?![^\n}]*#\}).*?$", re.MULTILINE)

count = 0
for f in ROOT.rglob("*.html"):
    text = f.read_text(encoding="utf-8", errors="replace")
    matches = list(PROBLEM_RE.finditer(text))
    if not matches:
        continue
    print(f"\n=== {f.relative_to(ROOT)} ({len(matches)} multiline {{# blocks) ===")
    for m in matches[:10]:
        line_no = text[: m.start()].count("\n") + 1
        snippet = text[m.start() : m.start() + 80].replace("\n", " ")
        print(f"  line {line_no}: {snippet}…")
        count += 1

print(f"\nTotal multiline {{# #}} occurrences: {count}")
