#!/usr/bin/env python3
"""Probe URLs: HTTP status, canonical, robots, title, hreflang."""
import json
import re
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UA = "Mozilla/5.0 (compatible; TwoCommsAuditor/1.0; +audit)"


def fetch(url, allow_redirects=True, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
    try:
        if allow_redirects:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                return {
                    "url": url,
                    "final_url": resp.geturl(),
                    "status": resp.status,
                    "headers": dict(resp.headers),
                    "body": body,
                }
        else:
            class NoRedirect(urllib.request.HTTPRedirectHandler):
                def redirect_request(self, *args, **kwargs):
                    return None
            opener = urllib.request.build_opener(NoRedirect)
            with opener.open(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                return {
                    "url": url,
                    "final_url": resp.geturl(),
                    "status": resp.status,
                    "headers": dict(resp.headers),
                    "body": body,
                }
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")[:8000]
        except Exception:
            pass
        return {
            "url": url,
            "final_url": getattr(e, "url", url),
            "status": e.code,
            "headers": dict(e.headers) if e.headers else {},
            "body": body,
            "error": "HTTPError",
        }
    except Exception as e:
        return {"url": url, "status": -1, "error": str(e), "body": "", "final_url": url, "headers": {}}


def extract_meta(body):
    out = {}
    m = re.search(r"<title[^>]*>(.*?)</title>", body, re.DOTALL | re.IGNORECASE)
    if m:
        out["title"] = re.sub(r"\s+", " ", m.group(1)).strip()
    m = re.search(r'<meta\s+name=["\']description["\']\s+content=["\']([^"\']*)["\']', body, re.IGNORECASE)
    if m:
        out["meta_description"] = m.group(1)[:300]
    m = re.search(r'<meta\s+name=["\']robots["\']\s+content=["\']([^"\']*)["\']', body, re.IGNORECASE)
    if m:
        out["robots"] = m.group(1)
    m = re.search(r'<link\s+rel=["\']canonical["\']\s+href=["\']([^"\']*)["\']', body, re.IGNORECASE)
    if m:
        out["canonical"] = m.group(1)
    hreflangs = {}
    for hm in re.finditer(r'<link\s+rel=["\']alternate["\']\s+hreflang=["\']([^"\']+)["\']\s+href=["\']([^"\']+)["\']', body, re.IGNORECASE):
        hreflangs[hm.group(1)] = hm.group(2)
    # Reverse order also
    for hm in re.finditer(r'<link\s+rel=["\']alternate["\']\s+href=["\']([^"\']+)["\']\s+hreflang=["\']([^"\']+)["\']', body, re.IGNORECASE):
        hreflangs[hm.group(2)] = hm.group(1)
    out["hreflang"] = hreflangs
    m = re.search(r'<meta\s+property=["\']og:title["\']\s+content=["\']([^"\']*)["\']', body, re.IGNORECASE)
    if m:
        out["og_title"] = m.group(1)[:200]
    m = re.search(r'<h1[^>]*>(.*?)</h1>', body, re.DOTALL | re.IGNORECASE)
    if m:
        out["h1"] = re.sub(r"<[^>]+>", "", m.group(1))[:200].strip()
    out["x_robots_tag_header"] = ""  # filled in caller
    return out


def probe(url, follow=True):
    r = fetch(url, allow_redirects=follow)
    meta = {}
    if r.get("body"):
        meta = extract_meta(r["body"])
    meta["x_robots_tag_header"] = r.get("headers", {}).get("X-Robots-Tag", "") or r.get("headers", {}).get("x-robots-tag", "")
    return {
        "url": url,
        "status": r["status"],
        "final_url": r.get("final_url"),
        "title": meta.get("title"),
        "meta_description": meta.get("meta_description"),
        "robots": meta.get("robots"),
        "canonical": meta.get("canonical"),
        "hreflang": meta.get("hreflang"),
        "og_title": meta.get("og_title"),
        "h1": meta.get("h1"),
        "x_robots_tag_header": meta.get("x_robots_tag_header"),
        "error": r.get("error"),
    }


def main():
    urls_to_probe = [
        # PDPs
        "https://twocomms.shop/product/classic-tshirt/",
        "https://twocomms.shop/product/hoodie-classic/",
        "https://twocomms.shop/product/longsleeve-classic/",
        "https://twocomms.shop/product/my-little-baby/",
        "https://twocomms.shop/product/where-mi-present-ts/",
        "https://twocomms.shop/product/in-shee/",
        # Path-URL variants — classic-tshirt
        "https://twocomms.shop/product/classic-tshirt/black/",
        "https://twocomms.shop/product/classic-tshirt/black/m/",
        "https://twocomms.shop/product/classic-tshirt/black/m/oversize/",
        "https://twocomms.shop/product/classic-tshirt/m/",
        "https://twocomms.shop/product/classic-tshirt/m/oversize/",
        # Path-URL variants — my-little-baby (has 2 colors)
        "https://twocomms.shop/product/my-little-baby/black/",
        "https://twocomms.shop/product/my-little-baby/coyote/",
        "https://twocomms.shop/product/my-little-baby/black/m/",
        "https://twocomms.shop/product/my-little-baby/coyote/m/",
        "https://twocomms.shop/product/my-little-baby/black/m/oversize/",
        # Path-URL variants — where-mi-present-ts
        "https://twocomms.shop/product/where-mi-present-ts/black/",
        "https://twocomms.shop/product/where-mi-present-ts/coyote/",
        "https://twocomms.shop/product/where-mi-present-ts/black/m/",
        "https://twocomms.shop/product/where-mi-present-ts/coyote/m/",
        # Categories
        "https://twocomms.shop/catalog/",
        "https://twocomms.shop/catalog/tshirts/",
        "https://twocomms.shop/catalog/hoodie/",
        "https://twocomms.shop/catalog/long-sleeve/",
        # Query-string facets
        "https://twocomms.shop/catalog/?color=black",
        "https://twocomms.shop/catalog/tshirts/?color=black",
        "https://twocomms.shop/catalog/?color=coyote",
        "https://twocomms.shop/catalog/?page=2",
        "https://twocomms.shop/catalog/tshirts/?page=2",
        "https://twocomms.shop/product/classic-tshirt/?color=black",
        "https://twocomms.shop/product/classic-tshirt/?fit=oversize",
        "https://twocomms.shop/product/classic-tshirt/?size=m",
        "https://twocomms.shop/?utm_source=test&utm_medium=audit",
        "https://twocomms.shop/product/classic-tshirt/?utm_source=test",
        "https://twocomms.shop/?gclid=abc123",
        "https://twocomms.shop/?fbclid=xyz789",
        # Search
        "https://twocomms.shop/search/?q=футболка",
        "https://twocomms.shop/search/",
        # Static / locales
        "https://twocomms.shop/",
        "https://twocomms.shop/ru/",
        "https://twocomms.shop/en/",
        "https://twocomms.shop/ru/catalog/",
        "https://twocomms.shop/en/catalog/",
        "https://twocomms.shop/ru/product/classic-tshirt/",
        "https://twocomms.shop/en/product/classic-tshirt/",
        # Possibly-404 / dead routes
        "https://twocomms.shop/blog/",
        "https://twocomms.shop/blog/feed/",
        "https://twocomms.shop/news/feed/",
        "https://twocomms.shop/avtory/",
        "https://twocomms.shop/avtory/twocomms/",
        "https://twocomms.shop/team/",
        "https://twocomms.shop/help/",
        "https://twocomms.shop/dopomoga/feed/",
        "https://twocomms.shop/llms.txt",
        "https://twocomms.shop/llms-full.txt",
        # Trailing slash consistency
        "https://twocomms.shop/catalog",  # without trailing slash
        "https://twocomms.shop/product/classic-tshirt",  # without trailing slash
        # case sensitivity
        "https://twocomms.shop/Catalog/",
        "https://twocomms.shop/PRODUCT/classic-tshirt/",
        # known static routes
        "https://twocomms.shop/contacts/",
        "https://twocomms.shop/delivery/",
        "https://twocomms.shop/povernennya-ta-obmin/",
        "https://twocomms.shop/faq/",
        "https://twocomms.shop/dopomoga/",
        "https://twocomms.shop/rozmirna-sitka/",
        "https://twocomms.shop/doglyad-za-odyagom/",
        "https://twocomms.shop/vidstezhennya-zamovlennya/",
        "https://twocomms.shop/mapa-saytu/",
        "https://twocomms.shop/cooperation/",
        "https://twocomms.shop/wholesale/",
        "https://twocomms.shop/custom-print/",
        "https://twocomms.shop/novyny/",
        "https://twocomms.shop/pro-brand/",
    ]

    out = []
    for i, url in enumerate(urls_to_probe):
        result = probe(url, follow=True)
        out.append(result)
        print(f"[{i+1}/{len(urls_to_probe)}] {result['status']:>4}  {url}", flush=True)
        time.sleep(0.15)

    out_path = ROOT / "audit_data/probe_results.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
