#!/usr/bin/env python3
"""List all untranslated + fuzzy entries from a .po file."""
import sys
import polib

po = polib.pofile(sys.argv[1])
untrans = [e for e in po if (not e.translated() or 'fuzzy' in e.flags) and not e.obsolete and e.msgid]
print(f"Total entries: {len(po)}")
print(f"Untranslated/fuzzy: {len(untrans)}")
for e in untrans:
    flag = ''
    if 'fuzzy' in e.flags:
        flag = '[F]'
    if not e.translated():
        flag = (flag or '') + '[U]'
    print(f"{flag} | {repr(e.msgid)[:200]}")
