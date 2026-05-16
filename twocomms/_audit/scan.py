#!/usr/bin/env python3
"""
DEEP SEO PROD AUDIT scanner. Реализует фазы 2-5:
  • качает HTML из urls_sample.txt параллельно (8 потоков),
  • парсит мета-теги, JSON-LD, hreflang, canonical, H1/H2/H3,
  • детектит cross-language утечки на /uk/ /ru/ /en/,
  • валидирует каноникал и hreflang,
  • проверяет длины title/description/keywords и наличие H1.

Выход: /tmp/_audit_seo.json (raw) и _audit/scan_summary.json (агрегаты).
"""
from __future__ import annotations

import concurrent.futures as cf
import gzip
import html as _html
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse as up
import urllib.request
from html.parser import HTMLParser

# ---- HTTP ----
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
)
HEADERS = {"User-Agent": UA, "Accept-Encoding": "identity"}
CTX = ssl.create_default_context()


def fetch(url: str, attempts: int = 8) -> tuple[str, int, dict]:
    """Fetch с экспоненциальным backoff на 429/500/502/503."""
    last: Exception | None = None
    delay = 0.4
    for i in range(attempts):
        req = urllib.request.Request(url, headers=HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=30, context=CTX) as r:
                body = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    body = gzip.decompress(body)
                return body.decode("utf-8", errors="replace"), r.status, dict(r.headers)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504):
                last = e
                time.sleep(delay)
                delay = min(delay * 2.0, 30.0)
                continue
            return e.read().decode("utf-8", errors="replace"), e.code, dict(e.headers or {})
        except Exception as e:
            last = e
            time.sleep(delay)
            delay = min(delay * 2.0, 30.0)
    if isinstance(last, urllib.error.HTTPError):
        try:
            return last.read().decode("utf-8", errors="replace"), last.code, dict(last.headers or {})
        except Exception:
            return "", last.code, {}
    raise last  # type: ignore


# ---- HTML parser (минимальный, без bs4) ----
ATTR_RE = re.compile(
    r"""([A-Za-z_:][-A-Za-z0-9_:]*)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))""")


def parse_attrs(attr_str: str) -> dict:
    """Простой парсер атрибутов тега <link ...>."""
    out = {}
    for m in ATTR_RE.finditer(attr_str):
        name = m.group(1).lower()
        val = m.group(2) or m.group(3) or m.group(4) or ""
        out[name] = _html.unescape(val)
    return out


HEAD_RE = re.compile(r"<head\b[^>]*>(.*?)</head>", re.S | re.I)
BODY_RE = re.compile(r"<body\b[^>]*>(.*?)</body>", re.S | re.I)
HTML_LANG_RE = re.compile(r"<html\b[^>]*\blang\s*=\s*['\"]([^'\"]+)['\"]", re.I)
META_RE = re.compile(r"<meta\b([^>]*?)/?>", re.S | re.I)
LINK_RE = re.compile(r"<link\b([^>]*?)/?>", re.S | re.I)
TITLE_RE = re.compile(r"<title\b[^>]*>(.*?)</title>", re.S | re.I)
JSONLD_RE = re.compile(
    r"<script\b[^>]*\btype\s*=\s*['\"]application/ld\+json['\"][^>]*>(.*?)</script>",
    re.S | re.I,
)
H1_RE = re.compile(r"<h1\b[^>]*>(.*?)</h1>", re.S | re.I)
H2_RE = re.compile(r"<h2\b[^>]*>(.*?)</h2>", re.S | re.I)
H3_RE = re.compile(r"<h3\b[^>]*>(.*?)</h3>", re.S | re.I)
TAG_RE = re.compile(r"<[^>]+>")


def strip_tags(s: str) -> str:
    s = TAG_RE.sub(" ", s)
    s = _html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def extract(html: str) -> dict:
    out: dict = {}
    head_m = HEAD_RE.search(html)
    head = head_m.group(1) if head_m else html
    body_m = BODY_RE.search(html)
    body = body_m.group(1) if body_m else html

    # html lang
    m = HTML_LANG_RE.search(html)
    out["html_lang"] = m.group(1) if m else None

    # title
    t = TITLE_RE.search(head)
    out["title"] = strip_tags(t.group(1)) if t else None

    # meta
    metas = []
    for mm in META_RE.finditer(head):
        a = parse_attrs(mm.group(1))
        metas.append(a)
    out["_metas"] = metas

    def meta_by_name(name: str) -> str | None:
        for a in metas:
            if a.get("name", "").lower() == name.lower():
                return a.get("content")
        return None

    def meta_by_prop(prop: str) -> str | None:
        for a in metas:
            if a.get("property", "").lower() == prop.lower():
                return a.get("content")
        return None

    out["meta_description"] = meta_by_name("description")
    out["meta_keywords"] = meta_by_name("keywords")
    out["meta_robots"] = meta_by_name("robots")
    out["og_title"] = meta_by_prop("og:title")
    out["og_description"] = meta_by_prop("og:description")
    out["og_url"] = meta_by_prop("og:url")
    out["og_image_alt"] = meta_by_prop("og:image:alt")
    out["og_type"] = meta_by_prop("og:type")
    out["og_locale"] = meta_by_prop("og:locale")
    out["twitter_title"] = meta_by_name("twitter:title")
    out["twitter_description"] = meta_by_name("twitter:description")

    # links
    canonical = None
    hreflangs: list[tuple[str, str]] = []  # (lang, href) — только rel=alternate
    for lm in LINK_RE.finditer(head):
        a = parse_attrs(lm.group(1))
        rel = (a.get("rel") or "").lower()
        if rel == "canonical":
            canonical = a.get("href")
        elif rel == "alternate" and a.get("hreflang"):
            hreflangs.append((a["hreflang"].lower(), a.get("href", "")))
    out["canonical"] = canonical
    out["hreflang"] = hreflangs

    # JSON-LD
    json_lds = []
    for jm in JSONLD_RE.finditer(html):
        raw = jm.group(1).strip()
        try:
            data = json.loads(raw)
        except Exception as e:
            json_lds.append({"_raw": raw[:200], "_error": str(e)})
            continue
        json_lds.append(data)
    out["json_ld"] = json_lds

    # H1/H2/H3 первые 3
    out["h1"] = [strip_tags(m.group(1)) for m in list(H1_RE.finditer(body))[:3]]
    out["h2"] = [strip_tags(m.group(1)) for m in list(H2_RE.finditer(body))[:3]]
    out["h3"] = [strip_tags(m.group(1)) for m in list(H3_RE.finditer(body))[:3]]

    return out


# ---- Локаль ----
def detect_locale(url: str) -> str:
    parsed = up.urlparse(url)
    parts = parsed.path.lstrip("/").split("/", 1)
    if parts and parts[0] in ("ru", "en"):
        return parts[0]
    return "uk"


# ---- Cross-language detector ----
RU_ONLY_LETTERS = set("ёЁыъэЭ")
UA_ONLY_LETTERS = set("єЄіІїЇґҐ")
ANY_CYR = re.compile(r"[\u0400-\u04FF]")

# Слова-индикаторы (RU-only / UA-only).
# Никаких омографов: оба языка пишут «магазин», «доставка», «оптом».
# Удалены, чтобы не плодить false-positives.
UA_WORDS = [
    # UA-only: не встречается в RU.
    "бавовна",        # RU: хлопок
    "ЗСУ",            # RU: ВСУ
    "Збройні",        # RU: Вооружённые
    "Кошик",          # RU: Корзина
    "сторінк",        # RU: страница
    "знайти",         # RU: найти
    "купити",         # RU: купить
    "вартіст",        # RU: стоимость
    "сорочк",         # RU: рубашка
    "майстерн",       # RU: мастерская
    "вибір",          # RU: выбор
    "запитан",        # RU: вопрос
    "відповід",       # RU: ответ
    "співпрац",       # RU: сотрудничество
    "безкоштовн",     # RU: бесплатно
    "зв'язок",        # RU: связь
    "одяг",           # RU: одежда
    "відстеженн",     # RU: отслеживание
    "повернен",       # RU: возврат
    "обмін",          # RU: обмен
    "вашого",         # RU: вашего  (UA writes «вашого», but RU «вашего», so диф минимально без -ого/-его)
    "більше",         # RU: больше
    "майбут",         # RU: будущ
    "сьогодні",       # RU: сегодня
    "розмір",         # RU: размер
    "кольори",        # RU: цвета
]
RU_WORDS = [
    "хлопок", "хлопка", "хлопковая",
    "ВСУ", "Вооружённ", "Вооруженн",
    "корзин",          # UA: кошик
    "размер",           # UA: розмір
    "цвета",            # UA: кольори
    "возврат",          # UA: повернення
    "отслеж",           # UA: відстеж
    "обмен",            # UA: обмін
    "страниц",          # UA: сторінк
    "найти",            # UA: знайти
    "купить", "купите",  # UA: купити
    "стоимост",         # UA: вартість
    "рублей", "рубль",  # currency
    "рубашк",           # UA: сорочк
    "мастерск",         # UA: майстерн
    "выбор",            # UA: вибір
    "вопрос",           # UA: запитан
    "ответ",            # UA: відповід (но UA пишет «відповідь» — будет ловиться по букве і)
    "сотруднич",        # UA: співпрац
    "благодар",         # UA: вдячн
    "спасибо",          # UA: дякуємо
    "вашего",           # UA: вашого
    "больше",           # UA: більше
    "будущ",            # UA: майбут
    "сегодня",          # UA: сьогодні
    "бесплатн",         # UA: безкоштовн
    "одежд",            # UA: одяг
    "русский",
]


def _word_match(word: str, text: str) -> bool:
    """Соответствие слова с учётом границ — иначе «знайти» ловит «найти»."""
    pattern = r"(?<![А-Яа-яЁёЇїІіЄєҐґ\w])" + re.escape(word) + r"(?![А-Яа-яЁёЇїІіЄєҐґ\w])"
    return bool(re.search(pattern, text, flags=re.IGNORECASE))


def has_ru_only(s: str) -> list[str]:
    """Возвращает список совпадений RU-only маркеров в строке."""
    out = []
    for ch in s:
        if ch in RU_ONLY_LETTERS:
            out.append(ch)
            break
    for w in RU_WORDS:
        if _word_match(w, s):
            out.append(w)
    return out


def has_ua_only(s: str) -> list[str]:
    out = []
    for ch in s:
        if ch in UA_ONLY_LETTERS:
            out.append(ch)
            break
    for w in UA_WORDS:
        if _word_match(w, s):
            out.append(w)
    return out


def has_any_cyr(s: str) -> bool:
    return bool(ANY_CYR.search(s or ""))


def detect_leaks(locale: str, value: str | None) -> tuple[bool, list[str]]:
    """Проверяет одно строковое значение на cross-language утечку."""
    if not value:
        return False, []
    s = str(value)
    leaks: list[str] = []
    if locale == "uk":
        # ru-only буквы или слова → утечка
        ru = has_ru_only(s)
        if ru:
            leaks.extend(["ru:" + str(x) for x in ru])
    elif locale == "ru":
        ua = has_ua_only(s)
        if ua:
            leaks.extend(["ua:" + str(x) for x in ua])
    elif locale == "en":
        # любые кириллические символы недопустимы
        if has_any_cyr(s):
            # извлечём само "слово"
            words = re.findall(r"[А-Яа-яЁёЇїІіЄєҐґ][А-Яа-яЁёЇїІіЄєҐґ\-']*", s)
            leaks.extend(["cyr:" + w for w in words[:5]])
    return bool(leaks), leaks


def walk_jsonld(node, fields: list[tuple[str, str]], path: str = ""):
    """Идём по JSON-LD и собираем (path, string_value) для строковых полей."""
    if isinstance(node, dict):
        for k, v in node.items():
            child = f"{path}.{k}" if path else k
            if isinstance(v, str):
                fields.append((child, v))
            else:
                walk_jsonld(v, fields, child)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            child = f"{path}[{i}]"
            if isinstance(v, str):
                fields.append((child, v))
            else:
                walk_jsonld(v, fields, child)


def per_url_audit(url: str, html: str, status: int) -> dict:
    locale = detect_locale(url)
    if status >= 400:
        return {
            "url": url,
            "locale": locale,
            "status": status,
            "error": True,
            "leaks": [],
            "issues": [{"type": "http_error", "value": status}],
        }
    e = extract(html)
    leaks: list[dict] = []
    issues: list[dict] = []

    def check(field: str, value):
        if value is None:
            return
        ok, ls = detect_leaks(locale, value)
        if ok:
            leaks.append({"field": field, "value": value[:200], "markers": ls[:8]})

    # Базовые поля
    check("title", e.get("title"))
    check("meta_description", e.get("meta_description"))
    check("meta_keywords", e.get("meta_keywords"))
    check("og_title", e.get("og_title"))
    check("og_description", e.get("og_description"))
    check("og_image_alt", e.get("og_image_alt"))
    check("twitter_title", e.get("twitter_title"))
    check("twitter_description", e.get("twitter_description"))
    for i, h in enumerate(e.get("h1", [])):
        check(f"h1[{i}]", h)
    for i, h in enumerate(e.get("h2", [])):
        check(f"h2[{i}]", h)
    for i, h in enumerate(e.get("h3", [])):
        check(f"h3[{i}]", h)

    # JSON-LD walk
    INTERESTING_TYPES = {
        "Product", "BreadcrumbList", "FAQPage", "AboutPage",
        "CollectionPage", "WebPage", "ItemList", "Organization",
    }
    for idx, blk in enumerate(e.get("json_ld", [])):
        if isinstance(blk, list):
            blocks = blk
        else:
            blocks = [blk]
        for j, b in enumerate(blocks):
            if not isinstance(b, dict):
                continue
            t = b.get("@type")
            if isinstance(t, list):
                t_str = ",".join(str(x) for x in t)
            else:
                t_str = str(t) if t else ""
            tag = f"jsonld[{idx}][{j}]:{t_str}"
            fields: list[tuple[str, str]] = []
            walk_jsonld(b, fields)
            for path, val in fields:
                # Игнорируем URL-ы и системные поля (currency, sku и т.п.).
                low = path.lower()
                if any(x in low for x in (
                    "url", "@id", "@context", "@type", "image",
                    "sku", "mpn", "gtin", "price", "currency",
                    "availability", "itemcondition", "encoding",
                )):
                    continue
                if val.startswith(("http://", "https://", "/")):
                    continue
                ok, ls = detect_leaks(locale, val)
                if ok:
                    leaks.append({
                        "field": f"{tag}.{path}",
                        "value": val[:200],
                        "markers": ls[:8],
                    })

    # ---- Phase 3: hreflang ----
    expected_locales = {"uk-ua", "ru-ua", "en-ua", "x-default"}
    hreflangs = e.get("hreflang") or []
    seen = {h.lower() for h, _ in hreflangs}
    missing = expected_locales - seen
    if missing:
        issues.append({"type": "hreflang_missing", "value": sorted(missing)})

    base = "https://twocomms.shop"
    parsed = up.urlparse(url)
    rest = parsed.path
    # путь без локали:
    if rest.startswith("/ru/") or rest.startswith("/en/"):
        unlocalized = rest[3:]
    else:
        unlocalized = rest
    expected_uk = base + unlocalized
    expected_ru = base + "/ru" + unlocalized
    expected_en = base + "/en" + unlocalized
    expected_xdef = base + unlocalized
    expected_map = {
        "uk-ua": expected_uk,
        "ru-ua": expected_ru,
        "en-ua": expected_en,
        "x-default": expected_xdef,
    }
    href_map = {h.lower(): href for h, href in hreflangs}
    for lang, exp in expected_map.items():
        actual = href_map.get(lang)
        if actual is None:
            continue
        # Допускаем www./query-параметры? Нет, у TwoComms canonical чистый.
        if actual.split("?")[0].rstrip("/") != exp.split("?")[0].rstrip("/"):
            issues.append({
                "type": "hreflang_wrong",
                "value": {"lang": lang, "expected": exp, "actual": actual},
            })

    # ---- Phase 4: canonical self-referential ----
    canonical = e.get("canonical")
    if canonical is None:
        issues.append({"type": "canonical_missing"})
    else:
        # canonical должен совпадать с самим URL (без query)
        own_url_self = base + parsed.path
        if canonical.split("?")[0].rstrip("/") != own_url_self.rstrip("/"):
            issues.append({
                "type": "canonical_wrong",
                "value": {"expected": own_url_self, "actual": canonical},
            })

    # ---- Phase 5: длины и H1 ----
    title = e.get("title") or ""
    if not title:
        issues.append({"type": "title_missing"})
    elif not (30 <= len(title) <= 65):
        issues.append({"type": "title_length", "value": len(title)})

    desc = e.get("meta_description") or ""
    if not desc:
        issues.append({"type": "description_missing"})
    elif not (50 <= len(desc) <= 160):
        issues.append({"type": "description_length", "value": len(desc)})

    kw = e.get("meta_keywords") or ""
    if kw and not (30 <= len(kw) <= 150):
        issues.append({"type": "keywords_length", "value": len(kw)})

    if not e.get("h1"):
        issues.append({"type": "h1_missing"})
    elif not (e["h1"][0]).strip():
        issues.append({"type": "h1_empty"})

    # noindex?
    robots = (e.get("meta_robots") or "").lower()
    indexable = "noindex" not in robots

    return {
        "url": url,
        "locale": locale,
        "status": status,
        "error": False,
        "html_lang": e.get("html_lang"),
        "indexable": indexable,
        "robots": e.get("meta_robots"),
        "title": e.get("title"),
        "title_len": len(title),
        "description": desc,
        "description_len": len(desc),
        "keywords": kw,
        "keywords_len": len(kw),
        "canonical": canonical,
        "hreflang": hreflangs,
        "h1": e.get("h1"),
        "h2": e.get("h2"),
        "h3": e.get("h3"),
        "og_title": e.get("og_title"),
        "og_description": e.get("og_description"),
        "og_image_alt": e.get("og_image_alt"),
        "twitter_title": e.get("twitter_title"),
        "twitter_description": e.get("twitter_description"),
        "json_ld_types": [
            (b.get("@type") if isinstance(b, dict) else
             [x.get("@type") for x in b if isinstance(x, dict)])
            for b in e.get("json_ld", [])
        ],
        "leaks": leaks,
        "issues": issues,
    }


# ---- main ----
def main():
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "urls_sample.txt")) as f:
        urls = [u.strip() for u in f if u.strip()]
    print(f"scanning {len(urls)} URLs sequentially (1 worker, 1.5s pause, retry-aware)...")

    results: list[dict] = []
    failures: list[tuple[str, str]] = []

    def task(u: str) -> dict:
        try:
            html, status, headers = fetch(u)
            return per_url_audit(u, html, status)
        except Exception as e:
            return {
                "url": u,
                "locale": detect_locale(u),
                "status": -1,
                "error": True,
                "exception": repr(e),
                "leaks": [],
                "issues": [{"type": "fetch_error", "value": repr(e)}],
            }

    t0 = time.time()
    for i, u in enumerate(urls, 1):
        results.append(task(u))
        time.sleep(1.5)
        if i % 10 == 0:
            print(f"  {i}/{len(urls)} ({time.time()-t0:.1f}s)")
    print(f"done in {time.time()-t0:.1f}s")

    out_raw = "/tmp/_audit_seo.json"
    try:
        with open(out_raw, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"raw -> {out_raw}")
    except Exception as e:
        # /tmp может быть запрещён, fallback в _audit/
        out_raw = os.path.join(here, "raw_results.json")
        with open(out_raw, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"raw fallback -> {out_raw}")

    # Дублируем в _audit/raw_results.json для удобства последующего grep'а.
    with open(os.path.join(here, "raw_results.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # Кратко по проверке.
    n = len(results)
    n_err = sum(1 for r in results if r.get("error"))
    n_with_leaks = sum(1 for r in results if r.get("leaks"))
    n_issues = sum(len(r.get("issues") or []) for r in results)
    print(f"summary: {n} urls, {n_err} fetch/HTTP errors, {n_with_leaks} pages with leaks, {n_issues} issues total")


if __name__ == "__main__":
    main()
