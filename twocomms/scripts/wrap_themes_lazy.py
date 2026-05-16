#!/usr/bin/env python3
"""Phase 17v helper — wrap THEMES dict string values with gettext_lazy.

This is a one-shot transform of ``storefront/services/_product_themes.py``.
It is destructive and should be run once after pulling.

Behaviour: rewrites the following keys' values in each theme entry:
  * intro_short, intro_long, audience  (paren-wrapped multi-line strings)
  * faq  (tuple of two strings — question, answer)
  * kw   (list of strings)
  * alt_short  (single inline string)

Each string is wrapped with ``_( ... )`` (gettext_lazy alias).
The ``ids`` set is left untouched.

After wrapping, run ``manage.py makemessages -l ru -l en`` to extract.
"""
from __future__ import annotations

import re
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "storefront" / "services" / "_product_themes.py"


def concat_string_block(lines: list[str], start_idx: int):
    parts: list[str] = []
    pat = re.compile(r'^\s*"((?:[^"\\]|\\.)*)"\s*$')
    i = start_idx
    while i < len(lines):
        m = pat.match(lines[i])
        if not m:
            break
        parts.append(m.group(1))
        i += 1
    if not parts:
        return None, start_idx
    return "".join(parts), i - 1


def main() -> None:
    text = SRC.read_text()
    if "from django.utils.translation import gettext_lazy as _" not in text:
        text = text.replace(
            '"""Theme table for product_copy_v2.',
            'from django.utils.translation import gettext_lazy as _\n\n\n'
            '"""Theme table for product_copy_v2.',
            1,
        )
    lines = text.split("\n")
    out: list[str] = []
    n = len(lines)
    i = 0
    while i < n:
        line = lines[i]

        # 1) Multi-line paren block: "<key>": (
        m1 = re.match(r'^(\s+)"(intro_short|intro_long|audience)":\s*\(\s*$', line)
        if m1:
            indent, key = m1.group(1), m1.group(2)
            joined, end_idx = concat_string_block(lines, i + 1)
            close = lines[end_idx + 1] if end_idx + 1 < n else ""
            if joined is not None and re.match(r'^\s*\)(,?)\s*$', close):
                trail = close.strip()
                out.append(f'{indent}"{key}": _(')
                out.append(f'{indent}    "{joined}"')
                out.append(f'{indent}{trail}')
                i = end_idx + 2
                continue

        # 2) faq tuple: "faq": (
        m4 = re.match(r'^(\s+)"faq":\s*\(\s*$', line)
        if m4:
            indent = m4.group(1)
            j = i + 1
            qparts: list[str] = []
            aparts: list[str] = []
            active = qparts
            close_idx = None
            while j < n:
                ln = lines[j]
                if re.match(r'^\s*\)(,?)\s*$', ln):
                    close_idx = j
                    break
                m_piece = re.match(r'^\s*"((?:[^"\\]|\\.)*)"(\s*,)?\s*$', ln)
                if m_piece:
                    active.append(m_piece.group(1))
                    if m_piece.group(2):
                        active = aparts
                    j += 1
                    continue
                break
            if close_idx is not None and qparts and aparts:
                q = "".join(qparts)
                a = "".join(aparts)
                # Inner double-quotes already escaped as \"; we don't need to re-escape.
                trail = lines[close_idx].strip()
                out.append(f'{indent}"faq": (')
                out.append(f'{indent}    _("{q}"),')
                out.append(f'{indent}    _("{a}"),')
                out.append(f'{indent}{trail}')
                i = close_idx + 1
                continue

        # 3) inline alt_short
        m2 = re.match(r'^(\s+)"(alt_short)":\s*"((?:[^"\\]|\\.)*)"(\s*,?)\s*$', line)
        if m2:
            indent, key, val, comma = m2.group(1), m2.group(2), m2.group(3), m2.group(4)
            out.append(f'{indent}"{key}": _("{val}"){comma.strip()}')
            i += 1
            continue

        # 4) kw list (single or multi-line)
        m3 = re.match(r'^(\s+)"kw":\s*\[\s*(.*)$', line)
        if m3:
            indent = m3.group(1)
            accum = m3.group(2)
            j = i
            end_j = None
            while j < n:
                if "]" in accum:
                    end_j = j
                    break
                j += 1
                if j < n:
                    accum += "\n" + lines[j]
            if end_j is not None:
                pre = accum[: accum.rindex("]")]
                post = accum[accum.rindex("]"):]  # `]` plus optional `,`
                strings = re.findall(r'"((?:[^"\\]|\\.)*)"', pre)
                wrapped = ", ".join(f'_("{s}")' for s in strings)
                out.append(f'{indent}"kw": [{wrapped}{post.rstrip()}')
                i = end_j + 1
                continue

        out.append(line)
        i += 1

    SRC.write_text("\n".join(out))
    print(f"OK — rewrote {SRC}")


if __name__ == "__main__":
    main()
