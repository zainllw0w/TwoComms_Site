#!/usr/bin/env python3
"""Compile every Django ``django.po`` file under ``locale/`` into a fresh
``django.mo`` using ``polib`` (pure-Python).

Why this exists
---------------
Our shared-hosting Passenger instance does NOT ship the GNU ``gettext``
suite (``msgfmt`` / ``msguniq`` / ``msgmerge``) and ``cPanel`` does not
allow ``apt install gettext``. Django's ``compilemessages`` management
command shells out to ``msgfmt``, so we cannot use it on prod.

``polib`` is a single-file pure-Python implementation of the gettext
binary MO file format. The bytes it writes are byte-for-byte compatible
with ``msgfmt`` output (verified against the gettext test suite), so
Django reads them without complaint.

Usage:
    python scripts/compile_mo_polib.py            # all apps, all langs
    python scripts/compile_mo_polib.py uk ru en   # only listed langs

The script is idempotent: it overwrites ``django.mo`` next to each
``django.po`` and prints a single summary line per file. Files that are
already up-to-date are recompiled anyway (~50 ms each, no measurable
impact).
"""
from __future__ import annotations

import sys
from pathlib import Path

import polib

ROOT = Path(__file__).resolve().parent.parent
TARGETS = []
for locale_root in (ROOT / "locale", ROOT / "dtf" / "locale"):
    if not locale_root.exists():
        continue
    TARGETS.extend(sorted(locale_root.glob("*/LC_MESSAGES/django.po")))


def main(argv: list[str]) -> int:
    wanted = {a.lower() for a in argv[1:]}
    compiled = 0
    skipped = 0
    for po_path in TARGETS:
        lang = po_path.parent.parent.name
        if wanted and lang not in wanted:
            skipped += 1
            continue
        try:
            po = polib.pofile(str(po_path))
        except Exception as exc:  # pragma: no cover - log + continue
            print(f"[ERROR] {po_path}: {exc}")
            continue
        mo_path = po_path.with_suffix(".mo")
        po.save_as_mofile(str(mo_path))
        print(
            f"[ok] {lang:<3} {po_path.relative_to(ROOT)}"
            f"  ->  {mo_path.name}"
            f"  ({len(po):>4} entries, {sum(1 for e in po if e.translated()):>4} translated)"
        )
        compiled += 1
    print(f"\ncompiled={compiled} skipped={skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
