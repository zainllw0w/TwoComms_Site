#!/usr/bin/env python3
"""Convert multiline {# ... #} → {% comment %}...{% endcomment %} in Django templates.

Single-line {# #} are left untouched (they work correctly in Django).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# Match {# starting an open multi-line block (no closing #} on same line)
# and find the closing #} on a later line.
OPEN_RE = re.compile(r"\{#(?![^\n}]*#\})", re.MULTILINE)


def convert(text: str) -> tuple[str, int]:
    out_lines = []
    inside = False
    converted = 0
    for line in text.split("\n"):
        if not inside:
            m = OPEN_RE.search(line)
            if m:
                # detect indent
                indent = line[: m.start()]
                # remainder before {#
                before = line[: m.start()]
                after = line[m.end() :].rstrip()
                # check if #} is on same line (single-line)
                if "#}" in after:
                    # actually single-line — keep as-is
                    out_lines.append(line)
                    continue
                # multi-line opening
                inside = True
                converted += 1
                out_lines.append(f"{before}{{% comment %}}")
                rem = after.strip()
                if rem:
                    out_lines.append(f"{indent}  {rem}")
            else:
                out_lines.append(line)
        else:
            # inside multi-line — look for closing #}
            if "#}" in line:
                idx = line.index("#}")
                rem = line[:idx].rstrip()
                tail = line[idx + 2 :]
                # detect indent for endcomment
                stripped = line.lstrip()
                indent_len = len(line) - len(stripped)
                indent = line[:indent_len] if indent_len else ""
                if rem.strip():
                    out_lines.append(rem)
                out_lines.append(f"{indent}{{% endcomment %}}{tail}")
                inside = False
            else:
                out_lines.append(line)
    if inside:
        # safety: never happens in practice but keep stable behaviour
        out_lines.append("{% endcomment %}")
    return "\n".join(out_lines), converted


def main(argv):
    root = Path(argv[1] if len(argv) > 1 else ".")
    write = "--write" in argv
    files_changed = 0
    blocks_changed = 0
    for f in sorted(root.rglob("*.html")):
        text = f.read_text(encoding="utf-8", errors="replace")
        new, n = convert(text)
        if n:
            files_changed += 1
            blocks_changed += n
            print(f"[{n}] {f.relative_to(root)}")
            if write:
                f.write_text(new, encoding="utf-8")
    print(f"\nFiles affected: {files_changed}, blocks converted: {blocks_changed}")
    if not write:
        print("(dry run — pass --write to apply)")


if __name__ == "__main__":
    main(sys.argv)
