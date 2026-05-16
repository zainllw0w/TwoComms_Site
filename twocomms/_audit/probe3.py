#!/usr/bin/env python3
"""Probe through curl subprocess - prod returns 500 to urllib but 200 to curl."""
import subprocess, sys
UA='Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36'

def fetch(url):
    p = subprocess.run([
        '/usr/bin/curl','-sS','-A',UA,'-L','--compressed',
        '-w', 'CODE=%{http_code} CT=%{content_type} URL=%{url_effective} SIZE=%{size_download}\n',
        '-o','/tmp/_body.bin',
        url,
    ], capture_output=True, text=True, timeout=30)
    return p.stdout, p.stderr

for url in [
    'https://www.twocomms.shop/',
    'https://www.twocomms.shop/sitemap.xml',
    'https://twocomms.shop/sitemap.xml',
    'https://www.twocomms.shop/robots.txt',
]:
    out, err = fetch(url)
    print(url, '->', out.strip(), err.strip())
