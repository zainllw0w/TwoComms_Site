#!/usr/bin/env python3
"""Сформировать сэмпл из ~200 URL: вся статика×3 локали, категории×3, 30 продуктов×3."""
import os, random, json, re

BASE = 'https://twocomms.shop'
HERE = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(HERE, 'urls_all.txt')) as f:
    urls = [u.strip() for u in f if u.strip()]

def split(u):
    """Возвращает (locale, path-after-locale)."""
    rest = u[len(BASE):]
    if rest.startswith('/ru/'): return 'ru', rest[3:]
    if rest.startswith('/en/'): return 'en', rest[3:]
    return 'uk', rest

# индексируем по path
by_locale = {'uk': set(), 'ru': set(), 'en': set()}
for u in urls:
    loc, path = split(u)
    by_locale[loc].add(path)

# Стандартные «статические» сегменты (фактически встречающиеся в sitemap)
STATIC_SEGMENTS = [
    '/', '/catalog/', '/catalog/hoodie/', '/catalog/tshirts/', '/catalog/long-sleeve/',
    '/contacts/', '/cooperation/', '/custom-print/', '/delivery/',
    '/doglyad-za-odyagom/', '/dopomoga/', '/faq/',
    '/mapa-saytu/', '/novyny/', '/polityka-konfidentsiynosti/',
    '/povernennya-ta-obmin/', '/pro-brand/', '/rozmirna-sitka/',
    '/umovy-vykorystannya/', '/vidstezhennya-zamovlennya/', '/wholesale/',
]
CATEGORY_SEGMENTS = ['/catalog/', '/catalog/hoodie/', '/catalog/tshirts/', '/catalog/long-sleeve/']

# Все продукты (UA уровень) — берем из urls_all
products = sorted({p for p in by_locale['uk'] if p.startswith('/product/')})
random.seed(42)
sample_products = sorted(random.sample(products, min(30, len(products))))

selected = set()
for seg in STATIC_SEGMENTS:
    selected.add(BASE + seg)
    selected.add(BASE + '/ru' + seg)
    selected.add(BASE + '/en' + seg)
# Категории уже включены в STATIC, но добавим явно (на случай).
for seg in CATEGORY_SEGMENTS:
    selected.add(BASE + seg)
    selected.add(BASE + '/ru' + seg)
    selected.add(BASE + '/en' + seg)
# Продукты
for seg in sample_products:
    selected.add(BASE + seg)
    selected.add(BASE + '/ru' + seg)
    selected.add(BASE + '/en' + seg)

selected = sorted(selected)
out = os.path.join(HERE, 'urls_sample.txt')
with open(out, 'w', encoding='utf-8') as f:
    f.writelines(u + '\n' for u in selected)

print(f"sample: {len(selected)} URLs (static×3 + cats×3 + 30 products×3)")
print(f"  -> {out}")
