#!/usr/bin/env python3
"""Собрать URL-ы из sitemap-index TwoComms и положить плоский список в _audit/urls_all.txt."""
import urllib.request, gzip, ssl, re, json, sys, os, random
from xml.etree import ElementTree as ET

UA='Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36'
HEADERS = {'User-Agent': UA, 'Accept-Encoding': 'identity'}
ctx = ssl.create_default_context()

def fetch(url, attempts=6):
    last = None
    for i in range(attempts):
        req = urllib.request.Request(url, headers=HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
                body = r.read()
                if r.headers.get('Content-Encoding') == 'gzip':
                    body = gzip.decompress(body)
                return body, r.status, dict(r.headers)
        except Exception as e:
            last = e
            import time
            time.sleep(1.5 * (i + 1))
    raise last

def find_locs(xml_bytes):
    """Парсим sitemap или sitemap-index, возвращаем список <loc>."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return re.findall(rb'<loc>([^<]+)</loc>', xml_bytes)
    ns = root.tag.split('}')[0].lstrip('{') if '}' in root.tag else ''
    out = []
    for el in root.iter():
        tag = el.tag.split('}')[-1]
        if tag == 'loc' and el.text:
            out.append(el.text.strip())
    return out

def main():
    out_dir = os.path.dirname(os.path.abspath(__file__))
    body, code, headers = fetch('https://twocomms.shop/sitemap.xml')
    print(f"sitemap.xml HTTP {code} len={len(body)}")
    children = find_locs(body)
    print(f"  child sitemaps: {len(children)}")
    all_urls = set()
    children_used = []
    for child in children:
        try:
            cb, cc, _ = fetch(child)
        except Exception as e:
            print(f"  skip {child}: {e}")
            continue
        locs = find_locs(cb)
        print(f"  {child} -> {len(locs)} urls")
        children_used.append((child, len(locs)))
        for l in locs:
            all_urls.add(l)
    with open(os.path.join(out_dir, 'urls_all.txt'), 'w', encoding='utf-8') as f:
        for u in sorted(all_urls):
            f.write(u + '\n')
    with open(os.path.join(out_dir, 'sitemap_index.json'), 'w', encoding='utf-8') as f:
        json.dump({'children': children_used, 'total_urls': len(all_urls)}, f, ensure_ascii=False, indent=2)
    print(f"TOTAL: {len(all_urls)} urls saved -> _audit/urls_all.txt")

if __name__ == '__main__':
    main()
