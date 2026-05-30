"""Quick SEO sanity check against the live site (post-deploy)."""
import re
import ssl
import urllib.request

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

URLS = [
    "https://twocomms.shop/?cb=verify1",
    "https://twocomms.shop/catalog/?cb=verify1",
]

for url in URLS:
    print(f"=== {url} ===")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15, context=CTX) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception as exc:
        print("  ERR:", exc)
        continue

    canon = re.findall(r'<link[^>]+rel="canonical"[^>]*>', html, re.I)
    print(f"  Canonical tags: {len(canon)}")

    icons = re.findall(
        r'<link[^>]+rel="(?:icon|shortcut icon|apple-touch-icon|mask-icon)"[^>]*>',
        html,
        re.I,
    )
    print(f"  Icon links (double-quoted): {len(icons)}")

    title = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    if title:
        text = title.group(1).strip()
        print(f"  Title ({len(text)} chars): {text!r}")

    desc = re.search(
        r'<meta[^>]+name="description"[^>]+content="([^"]+)"',
        html,
        re.I,
    )
    if desc:
        text = desc.group(1)
        print(f"  Description ({len(text)} chars): {text!r}")

    h1 = re.findall(r"<h1[^>]*>(.*?)</h1>", html, re.I | re.S)
    print(f"  H1 count: {len(h1)}")
    for h in h1[:1]:
        clean = re.sub(r"<[^>]+>", " ", h)
        clean = re.sub(r"\s+", " ", clean).strip()
        print(f"    {clean[:120]!r}")

    address = re.search(r"itemtype=\"https://schema\.org/PostalAddress\"", html, re.I)
    print(f"  PostalAddress marker in footer: {'YES' if address else 'NO'}")
    print()
