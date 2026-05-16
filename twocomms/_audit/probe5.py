#!/usr/bin/env python3
"""Узнаём, каких header'ов urllib хватает чтобы получить 200."""
import urllib.request, gzip, ssl
UA='Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36'
ctx = ssl.create_default_context()

cases = [
    {'User-Agent': UA},                               # минимально
    {'User-Agent': UA, 'Accept-Encoding': 'gzip'},    # с gzip
    {'User-Agent': UA, 'Accept-Encoding': 'identity'},# без сжатия
    {'User-Agent': 'curl/8.4.0'},                     # curl-like
    {'User-Agent': UA, 'Accept-Encoding':'gzip, deflate, br'},  # br
]

for h in cases:
    url = 'https://twocomms.shop/'
    req = urllib.request.Request(url, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=20, context=ctx) as r:
            body = r.read()
            ce = r.headers.get('Content-Encoding')
            if ce == 'gzip':
                body = gzip.decompress(body)
            print(f"{h} -> HTTP {r.status} CE={ce} len={len(body)}")
    except urllib.error.HTTPError as e:
        print(f"{h} -> HTTP {e.code}")
    except Exception as e:
        print(f"{h} -> ERR {e}")
