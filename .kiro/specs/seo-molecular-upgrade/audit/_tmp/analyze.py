#!/usr/bin/env python3
"""SEO content analyzer for TwoComms audit. Outputs JSON metrics per page."""
import json, os, re, sys
from pathlib import Path
from collections import Counter
from bs4 import BeautifulSoup, Comment

PAGES_DIR = Path("/tmp/seo_audit/pages")
OUT_DIR = Path("/Users/zainllw0w/TwoComms/site/.kiro/specs/seo-molecular-upgrade/audit/_tmp")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# UA + RU + EN stop words (selective, brand-relevant)
STOP_WORDS = set("""
а аби або абсолютно ад але аж аль б ба би бажано без більш більше близько бо буде будемо будете будеш будуть будь буду будучи буду була були було бути в вам вами вас ваш ваша ваше ваші великі вже взагалі ви від відповідно відсотки відтак візьми вільно він вище ві вмі вно во вона вона воно во вони впрост все всередині всі всім всього всі всю всю всякий вс втім вы га ге де декілька десь для дня до досить дуже е є його ж за й як які якій або те то ті та такий такі тобто тобто також тому тут тіл тільки тут уже усе усі усім усієї усього усьому усю чи чим що щоб
а или но что как когда где зачем здесь там этот эта это эти каждый каждую каждое каких какого которая которой которое которые которых наш наши нашему нашими нашего ваш ваша ваше ваши за из под над без для до на в по с со меня тебя его ее их нас вас них мне тебе ему ей им нам вам ним вы он она оно они мы ты я не ни же ли бы бы то ка тут так этот эта это эти такой такая такое такие был была было были будет будут есть нет да или
the a an of and or to in on at for with from by is are was were be been being this that these those it its his her their our your my we you they i he she them us as at if so but not no do does did will would can could should may might shall about into out over under up down very more most some any all each every other another such only own same than then now also only just upon
""".split())

# дополнительно отсечем коммерческие/брендовые мусорные токены
NOISE_TOKENS = set("""
twocomms shop product catalog category menu item items add cart buy now uah ua ru en ть ть ная ная грн kg cm мл г кг см мм
""".split())

def extract_text(soup, drop_template_chrome=True):
    """Extract visible body text excluding scripts/styles/header/footer/nav and common chrome."""
    soup = BeautifulSoup(str(soup), "lxml")  # clone
    for el in soup(["script", "style", "noscript", "template", "svg", "iframe"]):
        el.decompose()
    if drop_template_chrome:
        for sel in [
            "header", "footer", "nav", "aside", "dialog",
            "[role=navigation]", "[role=banner]", "[role=contentinfo]",
            "[class*=navbar]", "[class*=site-footer]", "[class*=site-header]",
            "[class*=footer-]", "[class*=header-]",
            "[class*=cart-]", "[class*=auth-]", "[class*=login]", "[class*=signup]",
            "[class*=lang-]", "[class*=language]", "[class*=switcher]",
            "[class*=offcanvas]", "[class*=modal]", "[class*=drawer]",
            "[class*=menu-]", "[class*=dropdown]",
            "[class*=cookie]", "[id*=cookie]",
            "[class*=breadcrumb]",
            "[class*=mobile-nav]", "[class*=bottom-nav]", "[class*=top-bar]",
            "[class*=sidebar]", "[class*=floating]", "[class*=toast]",
            "[class*=announcement]", "[class*=banner-bar]",
            "[class*=newsletter]",
        ]:
            for el in soup.select(sel):
                el.decompose()
        # also drop search bar / chat widgets
        for sel in ["[class*=search-form]", "[class*=chat-widget]", "[class*=fbpx]"]:
            for el in soup.select(sel):
                el.decompose()
    # Remove HTML comments
    for c in soup.find_all(string=lambda x: isinstance(x, Comment)):
        c.extract()
    # Prefer <main> if present and substantial
    main = soup.find("main")
    if main and len(main.get_text(strip=True)) > 200:
        text_root = main
    else:
        text_root = soup.body or soup
    text = text_root.get_text(separator=" ", strip=True)
    text = re.sub(r"\s+", " ", text)
    return text

def get_full_visible_text(soup):
    """Visible text including chrome (for word-count baseline)."""
    soup = BeautifulSoup(str(soup), "lxml")
    for el in soup(["script", "style", "noscript", "template", "svg"]):
        el.decompose()
    return re.sub(r"\s+", " ", soup.get_text(separator=" ", strip=True))

def tokenize(text):
    text = text.lower()
    # Replace non-letter chars with spaces (keep cyrillic, latin, digits)
    text = re.sub(r"[^a-zа-яёіїєґ0-9'’\- ]+", " ", text)
    tokens = [t for t in text.split() if len(t) >= 3]
    tokens = [t for t in tokens if t not in STOP_WORDS and t not in NOISE_TOKENS]
    tokens = [t for t in tokens if not t.isdigit()]
    return tokens

def shingle(tokens, n=5):
    return set(tuple(tokens[i:i+n]) for i in range(len(tokens) - n + 1))

def jaccard(a, b):
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0

def analyze_page(name, path, html):
    soup = BeautifulSoup(html, "lxml")
    metrics = {"name": name, "path": path}

    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""
    metrics["title"] = title
    metrics["title_len"] = len(title)

    md = soup.find("meta", attrs={"name": "description"})
    meta_desc = md.get("content", "").strip() if md else ""
    metrics["meta_desc"] = meta_desc
    metrics["meta_desc_len"] = len(meta_desc)

    canonical = soup.find("link", attrs={"rel": "canonical"})
    metrics["canonical"] = canonical.get("href") if canonical else None

    h1s = [h.get_text(" ", strip=True) for h in soup.find_all("h1")]
    metrics["h1_count"] = len(h1s)
    metrics["h1"] = h1s[0] if h1s else None
    metrics["h1_all"] = h1s

    h2s = [h.get_text(" ", strip=True) for h in soup.find_all("h2")]
    metrics["h2_count"] = len(h2s)
    metrics["h2_first5"] = h2s[:5]

    h3s = [h.get_text(" ", strip=True) for h in soup.find_all("h3")]
    metrics["h3_count"] = len(h3s)

    body_text = extract_text(soup, drop_template_chrome=True)
    full_text = get_full_visible_text(soup)
    metrics["body_text"] = body_text
    metrics["full_text"] = full_text
    metrics["word_count"] = len(body_text.split())
    metrics["full_word_count"] = len(full_text.split())

    metrics["html_bytes"] = len(html.encode("utf-8"))
    metrics["text_bytes"] = len(full_text.encode("utf-8"))
    if metrics["html_bytes"]:
        metrics["text_to_html_ratio_pct"] = round(metrics["text_bytes"] / metrics["html_bytes"] * 100, 1)
    else:
        metrics["text_to_html_ratio_pct"] = 0

    tokens = tokenize(body_text)
    metrics["tokens_count_after_stopwords"] = len(tokens)
    counter = Counter(tokens)
    metrics["top15_keywords"] = counter.most_common(15)

    # Internal/external links
    internal = 0
    external = 0
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith("tel:") or href.startswith("mailto:") or href.startswith("javascript:") or href.startswith("#"):
            continue
        if href.startswith("/") or "twocomms.shop" in href:
            internal += 1
        elif href.startswith("http://") or href.startswith("https://"):
            external += 1
    metrics["internal_links"] = internal
    metrics["external_links"] = external

    imgs = soup.find_all("img")
    metrics["img_count"] = len(imgs)
    metrics["img_no_alt"] = sum(1 for i in imgs if not i.get("alt", "").strip())

    # FAQ block detection
    has_faq_visible = bool(re.search(r"(?i)(faq|часті\s+запитан|питанн[яі]\s*[-—]?\s*відповід|popular questions|питанн[яі])", body_text))
    has_faqpage_schema = False
    speakable_present = False
    schemas = []
    for s in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(s.string or "{}")
        except Exception:
            try:
                data = json.loads(re.sub(r",\s*([\]\}])", r"\1", s.string or "{}"))
            except Exception:
                continue
        schemas.append(data)
    def collect_types(obj, acc):
        if isinstance(obj, dict):
            t = obj.get("@type")
            if isinstance(t, list):
                acc.update(t)
            elif isinstance(t, str):
                acc.add(t)
            for v in obj.values():
                collect_types(v, acc)
        elif isinstance(obj, list):
            for v in obj:
                collect_types(v, acc)
    types = set()
    for sc in schemas:
        collect_types(sc, types)
        if "speakable" in json.dumps(sc, ensure_ascii=False).lower():
            speakable_present = True
    has_faqpage_schema = "FAQPage" in types
    metrics["schema_types"] = sorted(types)
    metrics["faq_visible"] = has_faq_visible
    metrics["faq_schema"] = has_faqpage_schema
    metrics["speakable"] = speakable_present

    # First paragraph (lead block)
    main = soup.find("main") or soup.body or soup
    first_p = None
    for p in main.find_all(["p"]):
        txt = p.get_text(" ", strip=True)
        if len(txt) > 60:
            first_p = txt
            break
    metrics["first_paragraph"] = first_p
    metrics["first_p_len"] = len(first_p) if first_p else 0

    # Heuristic page type from name
    if name == "home":
        ptype = "home"
    elif name == "catalog-root":
        ptype = "catalog-root"
    elif name.startswith("cat-"):
        ptype = "category"
    elif name.startswith("pdp-"):
        ptype = "pdp"
    elif name.startswith("sup-"):
        ptype = "support"
    elif name.startswith("search"):
        ptype = "search"
    elif name.startswith("filter"):
        ptype = "filter"
    else:
        ptype = "other"
    metrics["page_type"] = ptype

    return metrics


def main():
    pages = {}
    for p in sorted(PAGES_DIR.glob("*.html")):
        name = p.stem
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            html = f.read()
        if "Server Error (500)" in html and len(html) < 500:
            # Skip but record stub
            pages[name] = {"name": name, "path": "?", "error": "HTTP 500"}
            continue
        with open("/Users/zainllw0w/TwoComms/site/.kiro/specs/seo-molecular-upgrade/audit/_tmp/fetch_list.txt") as fl:
            mp = dict(line.strip().split("|", 1) for line in fl if line.strip())
        path = mp.get(name, "?")
        try:
            m = analyze_page(name, path, html)
            pages[name] = m
        except Exception as e:
            pages[name] = {"name": name, "path": path, "error": str(e)}

    # Save raw analyses
    with open(OUT_DIR / "metrics.json", "w", encoding="utf-8") as f:
        # strip large texts before save
        export = {}
        for k, v in pages.items():
            v = dict(v)
            for big in ("body_text", "full_text"):
                if big in v:
                    v[big + "_preview"] = v[big][:400]
                    del v[big]
            export[k] = v
        json.dump(export, f, ensure_ascii=False, indent=2)

    # Compute pairwise shingle similarity for PDPs + Categories
    def text_for_sim(name):
        return pages[name].get("body_text") if "body_text" in pages[name] else ""

    pdp_names = sorted([k for k, v in pages.items() if v.get("page_type") == "pdp"])
    cat_names = sorted([k for k, v in pages.items() if v.get("page_type") in ("category", "catalog-root")])
    sup_names = sorted([k for k, v in pages.items() if v.get("page_type") == "support"])

    # Recompute body_text now (we trimmed earlier for save). Re-run analyzer in-memory cache:
    # Already have body_text from analyze_page invocation; cache before strip:
    # Actually we deleted from export only; original `pages[name]['body_text']` was set in analyze_page inside loop and exists still.

    def matrix(names):
        toks = {n: tokenize(pages[n].get("body_text", "")) for n in names}
        shings = {n: shingle(toks[n], 5) for n in names}
        out = []
        for a in names:
            row = []
            for b in names:
                if a == b:
                    row.append(1.0)
                else:
                    row.append(round(jaccard(shings[a], shings[b]), 3))
            out.append({"row": a, "values": dict(zip(names, row))})
        return out

    sim = {
        "pdps": matrix(pdp_names),
        "categories": matrix(cat_names),
        "support": matrix(sup_names),
    }
    with open(OUT_DIR / "similarity.json", "w", encoding="utf-8") as f:
        json.dump(sim, f, ensure_ascii=False, indent=2)

    # Boilerplate detection: split body texts into 3-sentence chunks (roughly), find chunks repeated across 5+ pages
    chunks_index = {}
    def split_chunks(text, n_words=12, stride=6):
        words = text.split()
        for i in range(0, max(0, len(words) - n_words + 1), stride):
            yield " ".join(words[i:i+n_words])
    for name, page in pages.items():
        if "body_text" not in page:
            continue
        seen_local = set()
        for ch in split_chunks(page["body_text"], 14, 7):
            if ch in seen_local:
                continue
            seen_local.add(ch)
            chunks_index.setdefault(ch, set()).add(name)
    boilerplate = [(ch, sorted(s)) for ch, s in chunks_index.items() if len(s) >= 5]
    boilerplate.sort(key=lambda x: -len(x[1]))
    with open(OUT_DIR / "boilerplate.json", "w", encoding="utf-8") as f:
        json.dump([{"text": ch, "pages": ps, "page_count": len(ps)} for ch, ps in boilerplate[:200]],
                  f, ensure_ascii=False, indent=2)

    # Repeated H2 across pages
    h2_index = {}
    for name, page in pages.items():
        for h2 in (page.get("h2_first5") or [])[:50]:
            h2_index.setdefault(h2.strip().lower(), set()).add(name)
    rep_h2 = [(t, sorted(s)) for t, s in h2_index.items() if len(s) >= 3]
    rep_h2.sort(key=lambda x: -len(x[1]))
    with open(OUT_DIR / "repeated_h2.json", "w", encoding="utf-8") as f:
        json.dump([{"text": t, "pages": ps} for t, ps in rep_h2], f, ensure_ascii=False, indent=2)

    # Repeated meta descriptions
    md_index = {}
    for name, page in pages.items():
        md = (page.get("meta_desc") or "").strip()
        if md:
            md_index.setdefault(md, []).append(name)
    rep_md = [(md, ps) for md, ps in md_index.items() if len(ps) >= 2]
    rep_md.sort(key=lambda x: -len(x[1]))
    with open(OUT_DIR / "repeated_meta.json", "w", encoding="utf-8") as f:
        json.dump([{"meta": md, "pages": ps} for md, ps in rep_md], f, ensure_ascii=False, indent=2)

    print(f"Analyzed {len(pages)} pages")
    print(f"PDP similarity matrix: {len(pdp_names)}×{len(pdp_names)}")
    print(f"Category similarity matrix: {len(cat_names)}×{len(cat_names)}")
    print(f"Boilerplate chunks repeated 5+ pages: {len(boilerplate)}")
    print(f"Repeated H2 (3+ pages): {len(rep_h2)}")
    print(f"Repeated meta-desc (2+ pages): {len(rep_md)}")

if __name__ == "__main__":
    main()
