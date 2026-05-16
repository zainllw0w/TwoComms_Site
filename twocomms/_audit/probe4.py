#!/usr/bin/env python3
"""Diagnose: which header makes the difference between 500 and 200."""
import subprocess
UA='Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36'

def run(args):
    p = subprocess.run(args, capture_output=True, text=True, timeout=30)
    return p.stdout.strip(), p.stderr.strip()

cases = [
    ['/usr/bin/curl','-sS','-A',UA,'-w','%{http_code}\n','-o','/dev/null','https://twocomms.shop/'],
    ['/usr/bin/curl','-sS','-A',UA,'--compressed','-w','%{http_code}\n','-o','/dev/null','https://twocomms.shop/'],
    ['/usr/bin/curl','-sS','-A',UA,'--compressed','-L','-w','%{http_code} %{url_effective}\n','-o','/dev/null','https://twocomms.shop/'],
    ['/usr/bin/curl','-sS','-A',UA,'-H','Accept-Encoding: gzip, deflate, br','-w','%{http_code}\n','-o','/dev/null','https://twocomms.shop/'],
    ['/usr/bin/curl','-sS','-A',UA,'--http2','-w','%{http_code}\n','-o','/dev/null','https://twocomms.shop/'],
    ['/usr/bin/curl','-sS','-A',UA,'--http1.1','-w','%{http_code}\n','-o','/dev/null','https://twocomms.shop/'],
]
for c in cases:
    out, err = run(c)
    print(' '.join(c[1:6]), '...', out, '|', err[:120])
