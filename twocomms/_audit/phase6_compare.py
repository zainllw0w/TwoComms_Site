#!/usr/bin/env python3
"""Phase 6: одно UA URL и его RU/EN counterparts — сравниваем title/description/JSON-LD."""
import json, os
HERE=os.path.dirname(os.path.abspath(__file__))
data=json.load(open(os.path.join(HERE,'raw_results_filtered.json'),encoding='utf-8'))

# индексируем по unloc-path
from urllib.parse import urlparse

def split(u):
    p=urlparse(u).path
    if p.startswith('/ru/'): return 'ru', p[3:]
    if p.startswith('/en/'): return 'en', p[3:]
    return 'uk', p

bypath={}
for r in data:
    loc, p = split(r['url'])
    bypath.setdefault(p, {})[loc]=r

# Take 6 representative paths.
samples=[
    '/',
    '/catalog/hoodie/',
    '/about/',  # alias for pro-brand
    '/faq/',
    '/dopomoga/',
    '/wholesale/',
]
# Plus 4 product PDPs from the actually scanned set.
prods=[p for p in bypath if p.startswith('/product/') and bypath[p].get('uk')][:6]
samples += prods[:4]

out=[]
for p in samples:
    triple = bypath.get(p, {})
    if not (triple.get('uk') and triple.get('ru') and triple.get('en')):
        out.append({'path':p,'note':'incomplete triple','locales':list(triple.keys())})
        continue
    diff = {}
    for field in ('title', 'description', 'og_title', 'og_description', 'h1'):
        diff[field] = {
            'uk': triple['uk'].get(field),
            'ru': triple['ru'].get(field),
            'en': triple['en'].get(field),
            'ru_same_as_uk': triple['ru'].get(field) == triple['uk'].get(field),
            'en_same_as_uk': triple['en'].get(field) == triple['uk'].get(field),
        }
    # JSON-LD Product.name
    def find_product_name(rec):
        for blk in rec.get('json_ld', []) or []:
            blocks = blk if isinstance(blk, list) else [blk]
            for b in blocks:
                if isinstance(b, dict) and b.get('@type') == 'Product':
                    return b.get('name')
        return None
    # raw_results_filtered не содержит json_ld отдельно (только types).
    # Ищем по leaks: если есть jsonld Product.name leak, сравним title.
    out.append({'path':p,'diff':diff})

json.dump(out, open(os.path.join(HERE,'phase6_compare.json'),'w',encoding='utf-8'), ensure_ascii=False, indent=2)

# Pretty print
for entry in out:
    print(f"\n=== {entry.get('path')} ===")
    if entry.get('note'):
        print('  ', entry['note'], entry.get('locales'))
        continue
    for f, d in entry['diff'].items():
        same_ru = '⚠ NOT TRANSLATED' if d['ru_same_as_uk'] else '✓ translated'
        same_en = '⚠ NOT TRANSLATED' if d['en_same_as_uk'] else '✓ translated'
        if isinstance(d['uk'], list): uk = (d['uk'] or [None])[0]
        else: uk = d['uk']
        if isinstance(d['ru'], list): ru = (d['ru'] or [None])[0]
        else: ru = d['ru']
        if isinstance(d['en'], list): en = (d['en'] or [None])[0]
        else: en = d['en']
        print(f"  {f}: uk={(uk or '')[:80]!r}")
        print(f"        ru={(ru or '')[:80]!r}  [{same_ru}]")
        print(f"        en={(en or '')[:80]!r}  [{same_en}]")
