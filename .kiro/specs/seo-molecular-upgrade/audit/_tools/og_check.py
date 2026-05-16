#!/usr/bin/env python3
"""Check OG/canonical/title for PDP and variant pages."""
import re
from pathlib import Path

RAW = Path("/tmp/seo_audit/schema/raw")

def og(slug):
    html = (RAW / f"{slug}.html").read_text(encoding="utf-8")
    m = lambda pat: (re.search(pat, html, re.IGNORECASE) or [None, None])
    title_tag = re.search(r'<title>([^<]+)</title>', html, re.IGNORECASE)
    og_title = re.search(r'<meta\s+property="og:title"[^>]*content="([^"]+)"', html, re.IGNORECASE)
    og_url   = re.search(r'<meta\s+property="og:url"[^>]*content="([^"]+)"', html, re.IGNORECASE)
    og_img   = re.search(r'<meta\s+property="og:image"[^>]*content="([^"]+)"', html, re.IGNORECASE)
    og_desc  = re.search(r'<meta\s+property="og:description"[^>]*content="([^"]+)"', html, re.IGNORECASE)
    canon    = re.search(r'<link\s+rel="canonical"[^>]*href="([^"]+)"', html, re.IGNORECASE)
    print(f"== {slug} ==")
    print(f"  <title>     : {title_tag.group(1) if title_tag else None}")
    print(f"  og:title    : {og_title.group(1) if og_title else None}")
    print(f"  og:url      : {og_url.group(1) if og_url else None}")
    print(f"  og:image    : {og_img.group(1) if og_img else None}")
    if og_desc:
        d = og_desc.group(1)
        print(f"  og:desc     : {d[:120]}{'…' if len(d) > 120 else ''}")
    else:
        print(f"  og:desc     : None")
    print(f"  canonical   : {canon.group(1) if canon else None}")
    print()

for s in ["pdp-classic-tshirt", "var-classic-tshirt-black", "var-classic-tshirt-oversize",
          "pdp-my-little-baby", "var-my-little-baby-coyote",
          "pdp-ru-classic-tshirt", "pdp-en-classic-tshirt",
          "home", "cat-tshirts", "pro-brand"]:
    og(s)
