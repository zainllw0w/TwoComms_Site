#!/usr/bin/env python3
import urllib.request, sys
UA='Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36'
paths = [
    '/', '/uk/', '/ru/', '/en/',
    '/about', '/about/', '/ru/about/', '/en/about/',
    '/faq/', '/ru/faq/', '/en/faq/',
    '/catalog/hoodie/', '/ru/catalog/hoodie/', '/en/catalog/hoodie/',
    '/sitemap.xml', '/sitemap-static.xml', '/sitemap-products.xml',
    '/sitemap-categories.xml', '/sitemap-color-categories.xml',
    '/sitemap-product-variants.xml', '/sitemap-images.xml',
    '/robots.txt',
]
for p in paths:
    url = 'https://twocomms.shop' + p
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            body = r.read()
            print(f"{p:40s} HTTP {r.status} len={len(body)}")
    except urllib.error.HTTPError as e:
        body = e.read()[:80]
        print(f"{p:40s} HTTP {e.code} body0={body!r}")
    except Exception as e:
        print(f"{p:40s} ERR {e}")
