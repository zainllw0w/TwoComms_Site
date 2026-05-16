#!/usr/bin/env python3
import urllib.request, ssl, gzip, io
UA='Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36'
HEADERS = {
    'User-Agent': UA,
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'uk,ru;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive',
    'DNT': '1',
}
hosts = ['twocomms.shop', 'www.twocomms.shop']
paths = ['/', '/sitemap.xml', '/sitemap-static.xml', '/robots.txt']
ctx = ssl.create_default_context()
for h in hosts:
    for p in paths:
        url = f'https://{h}{p}'
        req = urllib.request.Request(url, headers=HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=20, context=ctx) as r:
                body = r.read()
                if r.headers.get('Content-Encoding') == 'gzip':
                    body = gzip.decompress(body)
                ct = r.headers.get('Content-Type','')
                print(f"{url:60s} HTTP {r.status} CT={ct} len={len(body)}")
        except urllib.error.HTTPError as e:
            print(f"{url:60s} HTTP {e.code} CT={e.headers.get('Content-Type','')}")
        except Exception as e:
            print(f"{url:60s} ERR {e}")
