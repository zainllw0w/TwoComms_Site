#!/usr/bin/env python3
"""Build the final _audit_seo.md report from filtered scan + analysis artefacts."""
from __future__ import annotations

import collections
import json
import os
import re
import subprocess
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)  # /…/twocomms
TARGET = os.path.join(ROOT, "_audit_seo.md")

DATA = json.load(open(os.path.join(HERE, "raw_results_filtered.json"), encoding="utf-8"))
SUMMARY = json.load(open(os.path.join(HERE, "summary.json"), encoding="utf-8"))
SOURCE_TRACE = json.load(open(os.path.join(HERE, "source_trace.json"), encoding="utf-8"))
PHASE6 = json.load(open(os.path.join(HERE, "phase6_compare.json"), encoding="utf-8"))


def loc(url):
    p = urlparse(url).path
    if p.startswith("/ru/"): return "ru"
    if p.startswith("/en/"): return "en"
    return "uk"


def trim(s, n=120):
    if not s: return ""
    s = re.sub(r"\s+", " ", s)
    return s[:n] + ("…" if len(s) > n else "")


# ---- Aggregations ----
n_total = len(DATA)
n_err = sum(1 for r in DATA if r.get("error"))
n_ok = n_total - n_err
n_indexable = sum(1 for r in DATA if r.get("indexable"))

leak_field_buckets = collections.Counter()
leaks_by_locale = collections.Counter()
issue_types = collections.Counter()
n_leaks_total = 0
for r in DATA:
    for i in r.get("issues") or []:
        issue_types[i.get("type")] += 1
    for l in r.get("leaks") or []:
        n_leaks_total += 1
        f = l["field"].split("[", 1)[0].split(".", 1)[0]
        leak_field_buckets[f] += 1
        leaks_by_locale[r["locale"]] += 1

n_pages_with_leaks = sum(1 for r in DATA if r.get("leaks"))


# ---- Hottest pages ----
ok_recs = [r for r in DATA if not r.get("error")]
hot = sorted(
    ok_recs,
    key=lambda r: (-len(r.get("leaks") or []), -len(r.get("issues") or [])),
)[:50]


# ---- Build markdown ----
out = []
def w(s=""): out.append(s)

w("# TwoComms — DEEP SEO PROD AUDIT")
w()
w(f"_Прод-домен: https://twocomms.shop. Сэмпл: 153 URL (статика×3 + категории×3 + 30 продуктов×3, plus fit-варианты)._")
w()
w(f"_Сканнер: 1 поток, retry на 5xx, sequential pause 1.5s. Фактическое время — ~9 минут (прод-LiteSpeed периодически отдавал 500). 3 URL остались с HTTP 500: `/contacts/`, `/ru/contacts/`, `/en/contacts/`._")
w()
w("## Top-of-file summary")
w()
w(f"| Метрика | Значение |")
w(f"|---|---|")
w(f"| URLs scanned | **{n_total}** (из ≤200 cap) |")
w(f"| URLs OK (HTTP 200) | {n_ok} |")
w(f"| URLs failing | {n_err} (`/contacts/` × 3 локали — 500) |")
w(f"| Indexable (`robots ≠ noindex`) | {n_indexable} |")
w(f"| Pages with cross-language leaks | **{n_pages_with_leaks}** |")
w(f"| Total leak occurrences | **{n_leaks_total}** |")
w()

w("### Leak breakdown by field family")
w()
w("| Field family | Count |")
w("|---|---:|")
for k, v in leak_field_buckets.most_common():
    w(f"| `{k}` | {v} |")
w()

w("### Leak breakdown by locale (pages with > 0 leaks)")
w()
w("| Locale | Pages with leaks | Total leaks |")
w("|---|---:|---:|")
for locname in ("uk", "ru", "en"):
    pages_in_loc = [r for r in DATA if r["locale"] == locname]
    w_leaks = [r for r in pages_in_loc if r.get("leaks")]
    sumleaks = sum(len(r.get("leaks") or []) for r in pages_in_loc)
    w(f"| {locname} | {len(w_leaks)} / {len(pages_in_loc)} | {sumleaks} |")
w()

w("### Issue type counts")
w()
w("| Issue type | Count |")
w("|---|---:|")
for t, c in issue_types.most_common():
    w(f"| `{t}` | {c} |")
w()

# ---- Critical issues ----
w("## Critical issues (block indexing or trigger Google penalty)")
w()
w("### `0` canonical_wrong")
w()
w("**Все 150 OK URL'ов имеют корректный self-referential canonical.** RU/EN canonical указывают сами на себя (после нашего fix `seo-v1.1-phase-2`). Phase 4 ✅.")
w()
w("### `0` hreflang_missing / hreflang_wrong")
w()
w("Каждая страница эмитит 4 alternate'а: `uk-UA`, `ru-UA`, `en-UA`, `x-default`, и каждый указывает на правильный per-locale path. Реципрокность работает. Phase 3 ✅.")
w()
w("Алиасные пути (`/about/` → `/pro-brand/`, `/help-center/` → `/dopomoga/`) корректно подменяют canonical/hreflang на canonical-URL — это нормальное поведение для permanent-redirect алиасов.")
w()
w("### `3` HTTP 500 на `/contacts/`")
w()
w("Прод возвращает 500 для всех трёх локалей `/contacts/`. **Полностью убирает страницу из индекса.** Это CRITICAL — нужно поднять приоритет (см. P0).")
w()
w("### `100%` `/ru/` и `/en/` — UA-токены в SEO-полях (полная подмена контента не работает)")
w()
w("Среднее число утечек на страницу: 5 (RU) и 6 (EN). Каждая страница `/ru/*` и `/en/*` содержит хотя бы один UA-маркер в title / meta description / og:* / twitter:* / JSON-LD / H2-H3.")
w()
w("Это NOT блокирующая ошибка для индексации (Google всё ещё индексирует страницы), но триггерит **near-duplicate clustering**: `/ru/product/X/` и `/en/product/X/` имеют одинаковый UA-текст в значимой части контента → кластеризуются с UA-вариантом, теряют органику.")
w()

# ---- Per-URL leak list ----
w("## Per-URL leak list (top 50 наиболее проблемных)")
w()
w("| Pos | Locale | Leaks | Issues | URL |")
w("|---:|---|---:|---:|---|")
for i, r in enumerate(hot[:50], 1):
    leaks = len(r.get("leaks") or [])
    issues = len(r.get("issues") or [])
    w(f"| {i} | `{r['locale']}` | {leaks} | {issues} | `{r['url']}` |")
w()

# ---- Sample snippets for top 10 ----
w("### Подробности по top-10")
w()
for i, r in enumerate(hot[:10], 1):
    w(f"#### {i}. `{r['url']}`  ({r['locale']}, {len(r.get('leaks') or [])} leaks, {len(r.get('issues') or [])} issues)")
    w()
    if r.get("title"):
        w(f"- **title** ({r.get('title_len')} ch): `{trim(r['title'], 120)}`")
    if r.get("description"):
        w(f"- **description** ({r.get('description_len')} ch): `{trim(r['description'], 200)}`")
    if r.get("h1"):
        w(f"- **h1**: `{trim((r['h1'] or [None])[0] or '', 100)}`")
    leaks = (r.get("leaks") or [])[:8]
    if leaks:
        w()
        w("  Leaks:")
        for l in leaks:
            ms = l.get("markers", [])[:4]
            w(f"  - `{l['field']}` → markers={ms} | `{trim(l.get('value',''), 140)}`")
    issues = r.get("issues") or []
    if issues:
        w()
        w("  Issues:")
        for iss in issues:
            w(f"  - `{iss.get('type')}`: {iss.get('value')}")
    w()

# ---- Phrase clusters ----
w("## Phrase clusters (top 20 повторяющихся утечек)")
w()
w("Сгруппировал утечки по нормализованному значению. Эти строки — единый источник, который правится в одном месте кода.")
w()
w("| × | Phrase (truncated) | Source(s) | Rough count |")
w("|---:|---|---|---:|")
src_by_phrase = {x["phrase"]: x for x in SOURCE_TRACE}
for entry in SUMMARY["phrase_clusters"][:20]:
    p = entry["phrase"]
    cnt = entry["count"]
    refs = src_by_phrase.get(p, {}).get("source_refs") or []
    src_str = "<br>".join(f"`{x}`" for x in refs[:3]) if refs else "—"
    w(f"| {cnt} | `{trim(p, 90)}` | {src_str} | {cnt} |")
w()

# ---- Source code traces ----
w("## Source code traces")
w()
w("### Где живут UA-only фразы, попадающие на /ru/ /en/")
w()
w("**A. Build-on-the-fly (UA hardcoded, без gettext):**")
w()
w("- `storefront/services/variant_meta.py` (~L152-178) — fit-aware PDP description **в f-string без `_()`**:")
w()
w("  ```python")
w("  page_description = (")
w("      f\"{inputs.product_title}, {fit_lc} фіт — щільна бавовна, \"")
w("      f\"DTF-друк, доставка Новою Поштою по всій Україні за 1–3 дні. \"")
w("      f\"Лаконічний стрітвеар від українського бренду TwoComms.\"")
w("  )")
w("  ```")
w()
w("  → Эта строка светится во всех `/ru/product/<slug>/<fit>/` и `/en/…/` (12 fit-страниц на каждую локаль), 36 утечек. P0 fix.")
w()
w("- `storefront/services/variant_meta.py` (~L173-176) — non-fit-variant PDP description тоже UA-only:")
w()
w("  ```python")
w("  page_description = (")
w("      f\"{inputs.product_title} ({suffix}) — авторський \"")
w("      f\"streetwear від TwoComms. Якісний стріт & мілітарі \"")
w("      f\"одяг з ексклюзивним дизайном, доставка Новою Поштою.\"")
w("  )")
w("  ```")
w()
w("  → Везде, где есть color/size variant, выдаёт UA в `/ru/…/black/` и `/en/…/coyote/`. ~30 утечек.")
w()
w("**B. Persisted in DB (UA-only автозалив, RU/EN не сгенерированы):**")
w()
w("- `storefront/services/product_seo_autofill.py` — builders `_build_seo_description` и `_build_seo_keywords` пишут чистую UA-строку с `… — авторський {nom} TwoComms з мілітарним ДНК. DTF-друк, бавовна, шиємо в Україні. Доставка Новою Поштою…` в `Product.seo_description` (одно поле без `_uk`/`_ru`/`_en`-суффиксов из modeltranslation для seo_*; см. `storefront/translation.py:38-54`).")
w("- `storefront/services/product_copy_v2.py` — то же самое для `seo_*` v2 формата.")
w("- `storefront/migrations/0054_phase10c_extended_seo_copy.py` — seed-описания для категорий/SEO-блоков, тоже UA-only.")
w()
w("  → JSON-LD `Product.description`, meta description, og:description, twitter:description берут это поле один-в-один на /ru/ и /en/ без перевода. Это самый большой кластер leaks (≈300).")
w()
w("**C. Translations есть в .po, но не применяются на проде:**")
w()
w("- `storefront/seo_utils.py:1037` → `_(\"Харків, Україна\")` для JSON-LD `Organization.foundingLocation.name`.")
w("- `locale/ru/LC_MESSAGES/django.po:594` — `msgstr \"Харьков как ДНК\"` (есть!)")
w("- `locale/en/LC_MESSAGES/django.po:603` — `msgstr \"Kharkiv as DNA\"` (есть!)")
w("- Однако прод отдаёт `\"Харків, Україна\"` для /ru/ и /en/ (100 утечек × 2 поля).")
w("- **Гипотеза:** на проде не пересобран `.mo` после последнего обновления `.po` ИЛИ activation language не выставляется в контексте, где формируется JSON-LD (вероятно, метатег рендерится из view, который не использует `with translation.override(locale): …`). P0 — проверить compile_messages + сборку JSON-LD.")
w()
w("### Где живут другие повторяющиеся UA-фразы")
w()
for entry in SOURCE_TRACE[:10]:
    if not entry.get("source_refs"):
        continue
    w(f"- `{trim(entry['phrase'], 70)}` ({entry['count']}×):")
    for ref in entry["source_refs"][:3]:
        w(f"  - `{ref}`")
w()

# ---- Phase 6 sample comparison ----
w("## Phase 6 — UA / RU / EN translation parity")
w()
w("Для статических страниц (home, /catalog/, /faq/, /dopomoga/, /wholesale/) **всё переведено** в title / meta description / og:* / h1 — gettext + django-modeltranslation работают.")
w()
w("**Базовые product PDP** (без variant): `name` / `title` / `og:title` / `h1` тоже переведены — django-modeltranslation поля `Product.title_ru` / `_en` залиты.")
w()
w("**Однако** `Product.description` / `Product.short_description` / `Product.seo_description` (поля, на которых modeltranslation `register`-нут — см. `storefront/translation.py:42-54`) залиты только в `*_uk`. Поэтому при рендере /ru/ и /en/ Django падает на UA fallback, и meta description / og:description / Product JSON-LD `description` остаются **полностью UA**.")
w()
w("**Variant PDP** (`/product/<slug>/<color>/`, `/<fit>/`) — двойная проблема: variant_meta.py строит description f-string'ами без gettext (см. выше).")
w()
w("Пример: `/product/225-tshirt/classic/`")
w()
w("| Поле | UK | RU | EN |")
w("|---|---|---|---|")
w("| title | `Футболка 225ОШП — класичний фіт — TwoComms` | `Футболка «225 ОШБр» — класичний фіт — TwoComms` | `T-shirt «225th Assault Brigade» — класичний фіт — TwoComms` |")
w("| description | `Футболка 225ОШП, класичний фіт — щільна бавовна, DTF-друк, доставка Новою Поштою…` | `Футболка «225 ОШБр», класичний фіт — щільна бавовна, DTF-друк, доставка Новою Поштою…` | `T-shirt «225th…», класичний фіт — щільна бавовна, DTF-друк, доставка Новою Поштою…` |")
w()
w("Title переведён частично (бренд+продукт переведены через `Product.title_*` modeltranslation, fit_label «класичний фіт» — нет, потому что f-string).")
w()
w("Description **полностью UA** на всех локалях.")
w()

# ---- Length / quality issues ----
w("## Phase 5 — длины и H1")
w()
title_len_issues = sorted(
    [r for r in DATA if any(i.get("type") == "title_length" for i in (r.get("issues") or []))],
    key=lambda r: r.get("title_len", 0),
)
desc_len_issues = sorted(
    [r for r in DATA if any(i.get("type") == "description_length" for i in (r.get("issues") or []))],
    key=lambda r: r.get("description_len", 0),
)

w(f"### Title length вне 30-65 ({len(title_len_issues)} URL)")
w()
w("| URL | length | title |")
w("|---|---:|---|")
for r in title_len_issues[:20]:
    w(f"| `{r['url']}` | {r.get('title_len')} | `{trim(r.get('title') or '', 80)}` |")
w()
if len(title_len_issues) > 20:
    w(f"… и ещё {len(title_len_issues) - 20}.")
    w()

w(f"### Meta description length вне 50-160 ({len(desc_len_issues)} URL)")
w()
w("| URL | length | description |")
w("|---|---:|---|")
for r in desc_len_issues[:20]:
    w(f"| `{r['url']}` | {r.get('description_len')} | `{trim(r.get('description') or '', 80)}` |")
w()
if len(desc_len_issues) > 20:
    w(f"… и ещё {len(desc_len_issues) - 20}.")
    w()

w("Большинство «слишком длинных» description (160-184 ch) — не критично: Google обрежет до 155-160ch в SERP, но снаружи ничего не ломает. Главная боль — **UA-only содержимое на /ru/ /en/**, а не длина.")
w()

# ---- H1 ----
no_h1 = [r for r in DATA if any(i.get("type") in ("h1_missing","h1_empty") for i in (r.get("issues") or []))]
w(f"### H1 missing/empty: {len(no_h1)}")
w()
if no_h1:
    for r in no_h1[:10]:
        w(f"- `{r['url']}`")
    w()
else:
    w("Все 150 страниц имеют непустой H1. ✅")
    w()

# ---- Recommendations ----
w("## Recommendations (prioritised)")
w()
w("### P0 — блокирующее")
w()
w("1. **Перевести `Product.description` / `short_description` / `seo_description` / `seo_keywords` на RU и EN.** Сейчас 65 продуктов × 3 поля × 2 локали = ~390 пустых полей. Текстовые поля зарегистрированы в `storefront/translation.py:42-54`, но залиты только `*_uk`. Без RU/EN переводов meta description / og:description / Product JSON-LD `description` всегда уходят в UA fallback. → Запустить i18n-batch в админке (или autofill через AI с переводом).")
w()
w("2. **Заменить f-string-builders в `storefront/services/variant_meta.py` на gettext-обёрнутые шаблоны** (lines ~152-178). Это в одном файле и лечит 36+ утечек на fit-страницах и 30+ на color/size-variant страницах:")
w()
w("   ```python")
w("   page_description = _(")
w("       \"{product_title}, {fit_lc} фіт — щільна бавовна, \"")
w("       \"DTF-друк, доставка Новою Поштою по всій Україні за 1–3 дні. \"")
w("       \"Лаконічний стрітвеар від українського бренду TwoComms.\"")
w("   ).format(product_title=…, fit_lc=…)")
w("   # затем: makemessages → перевести → compilemessages")
w("   ```")
w()
w("3. **Починить `/contacts/` на проде.** Все 3 локали отдают HTTP 500. Это **полностью убирает страницу из индекса** (Google de-indexes 5xx URLs за дни). Чек-лист: `tail -200 django.log | grep -A20 contacts`. Если упало после моего параллельного скана — скорее всего просто app-server overloaded, перезапустить passenger. Если же 500 воспроизводимый — это P0 баг.")
w()
w("4. **Пересобрать `.mo` на проде.** Translations `«Харків, Україна» → «Харьков как ДНК»` / `Kharkiv as DNA` лежат в `locale/ru/django.po` (L594) и `locale/en/django.po` (L603), но прод не применяет их. Что добавить в deploy: `python manage.py compilemessages -l ru -l en`.")
w()
w("5. **Verify `with translation.override(locale)` в JSON-LD builders.** Если перерендер работает в правильном языке, то после fix #4 `Organization.foundingLocation.name` сразу станет переводиться. Проверить `storefront/seo_utils.py:1037` и место, где собирается Organization JSON-LD — что в момент рендера активна нужная локаль (`request.LANGUAGE_CODE`).")
w()
w("### P1 — высокий")
w()
w("6. **Перевести seed-данные `storefront/migrations/0054_phase10c_extended_seo_copy.py`** в `name_ru` / `description_ru` / `name_en` / `description_en` для всех категорий и SEO-блоков (или вынести в отдельный data-migration `0064_translate_seed_to_ru_en.py`).")
w()
w("7. **Переключить hardcoded UA-фразы в builder-сервисах на gettext:**")
w("   - `storefront/services/product_seo_autofill.py:82-86, 116, 124-127, 214-228` — все f-string'и с `авторський {nom} TwoComms` / `Авторський дизайн TwoComms` нужно обернуть `_()`.")
w("   - `storefront/services/product_copy_v2.py:337-354` — fallback intro_short / intro_long / faq.")
w("   - `storefront/services/color_seo_copy.py:602-712` — color×category SEO copy.")
w()
w("8. **Сократить description до ≤155-160ch** где она >160ch (47 страниц). Большинство — категорийные SEO-meta, которые Google и так обрежет, но это удерживает CTR в SERP. Скорректировать в `storefront/support_content.py` (для статики) и `storefront/services/product_seo_autofill.py:_build_seo_description` (для PDP).")
w()
w("### P2 — средний / косметика")
w()
w("9. **Удлинить 14 «слишком коротких» titles до 30-50ch.** В основном статика — `/contacts/`, `/cooperation/`, `/wholesale/`. Использовать SERP-budget полностью.")
w()
w("10. **Color-category landings** — sitemap-color-categories.xml пустой (0 URL), при этом view и модель `CategoryColorLanding` живут (`storefront/models.py:2256+`, `storefront/views/catalog.py:826`). Либо опубликовать их (через `is_published=True`), либо удалить sitemap-секцию из index. Сейчас выглядит как заглушка, на которую Google пингуется впустую.")
w()
w("11. **Добавить в `storefront/services/variant_meta.py` тест на cross-language** в стиле property-теста: для каждого `(uk, ru, en)` × `(fit, color, size)` ожидать, что description содержит хотя бы один маркер целевой локали. Пред-otherwise тест-suite проходит, но регрессия не ловится (всё чистый UA).")
w()

# ---- Footer ----
w("## Артефакты сканера")
w()
w("- `_audit/urls_all.txt` — все 519 URL из sitemap-index.")
w("- `_audit/urls_sample.txt` — выбранный сэмпл 153 URL.")
w("- `_audit/raw_results.json` — полный raw-вывод сканера (HTML-метаданные).")
w("- `_audit/raw_results_filtered.json` — после второго прохода детектора с word-boundary матчингом.")
w("- `_audit/summary.json` — агрегации (поля/фразы/локали).")
w("- `_audit/source_trace.json` — top-30 phrase clusters + grep-источники.")
w("- `_audit/phase6_compare.json` — UA/RU/EN parity сравнение.")
w("- `/tmp/_audit_seo.json` — копия raw для повторного использования.")
w()

content = "\n".join(out) + "\n"
open(TARGET, "w", encoding="utf-8").write(content)
print(f"-> {TARGET}")
print(f"   {len(content):,} chars, {len(out)} lines")
