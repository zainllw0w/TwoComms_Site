#!/usr/bin/env python3
"""Synthesize 05_tech_debt.md from audit_data/05_tech_debt_raw.json + 05_unused_routes.json."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "audit_data" / "05_tech_debt_raw.json"
UNUSED = ROOT / "audit_data" / "05_unused_routes.json"
OUT = ROOT / "05_tech_debt.md"

raw = json.loads(RAW.read_text())
unused = json.loads(UNUSED.read_text()) if UNUSED.exists() else {}

lines: list[str] = []
P = lines.append

P("# 05 — Tech Debt Audit (templates, views, routes, dead assets)")
P("")
P("> Дата: 2026-05-16  ")
P("> Скоуп: `twocomms/` Django app (templates + python + routes + static assets)  ")
P("> Источник: `audit_data/05_tech_debt_raw.json`, `audit_data/05_unused_routes.json`")
P("")
P("---")
P("")

# 1. Шаблонные комменты
tc = raw.get("template_comments", {})
runs = tc.get("multiline_consecutive_runs", [])
total_django = tc.get("total_django_comments", 0)
phase_total = tc.get("phase_comments_total", 0)
phase_ids = tc.get("phase_ids", {})
per_file = tc.get("comment_count_per_file", {})
P("## 1. Шаблонные комментарии")
P("")
P(f"- Всего Django-комментариев `{{# … #}}` в шаблонах: **{total_django}**")
P(f"- Из них с пометкой `Phase NN` (внутренний фазовый журнал): **{phase_total}**")
P(f"- Распределение по фазам: " + ", ".join(f"Phase {k}: {v}" for k, v in sorted(phase_ids.items())))
P("")
P("### 1.1 Многострочные `{# … #}` блоки")
P("")
P("Django парсит `{# … #}` **только в пределах одной строки**. Многострочные leak'ат в HTML.")
P("Найдено **последовательных** runs из 2+ строк (часто это «продолжение коммента»):")
P("")
P(f"Всего runs: **{len(runs)}**.")
P("")
P("| Файл | Строки | Длина run (строк) | Образец |")
P("|---|---|---|---|")
for r in runs[:30]:
    sample = (r.get("sample") or "").replace("\n", " ⏎ ")[:90]
    P(f"| `{r['path']}` | {r['start']}–{r['end']} | {r['count']} | {sample}… |")
if len(runs) > 30:
    P(f"")
    P(f"_…ещё {len(runs)-30} runs_")
P("")
P("**Note**: каждая отдельная строка `{# ... #}` в run-е валидна (закрытие на той же строке). Я фиксил **только** реальные многострочные блоки в коммите `2476ba23` — runs выше остались как есть, потому что технически работают. Однако они шумят в исходниках и **17 раз встречаются в `pages/product_detail.html`** — это явный кандидат на чистку.")
P("")

# 1.2 топ файлы по комментариям
P("### 1.2 Топ файлов по плотности комментариев")
P("")
P("| Файл | Django-комментариев |")
P("|---|---|")
for path, n in sorted(per_file.items(), key=lambda x: -x[1])[:20]:
    P(f"| `{path}` | {n} |")
P("")

# 1.3 Python phase comments
ppc = raw.get("python_phase_comments", {})
P("### 1.3 Phase-комменты в Python")
P("")
P(f"Всего: **{ppc.get('phase_comments_total', 0)}** в Python-исходниках. Распределение:")
P("")
phase_py = ppc.get("phase_ids", {})
P("| Phase | Кол-во |")
P("|---|---|")
for k, v in sorted(phase_py.items()):
    P(f"| Phase {k} | {v} |")
P("")
P("**Рекомендация**: после стабилизации каждой фазы (когда нет регрессий) консолидировать историю в один `CHANGELOG_SEO.md` и убрать inline-фазовые комменты — они утяжеляют чтение кода. Полезные комменты-обоснования («почему именно так») оставить, пометив их как `# RATIONALE:`.")
P("")

# 2. TODO/FIXME
todos = raw.get("todo_fixme", [])
P("## 2. TODO / FIXME / XXX")
P("")
P(f"Всего: **{len(todos)}**.")
P("")
if todos:
    P("| Файл | Строка | Тип | Текст |")
    P("|---|---|---|---|")
    for t in todos[:25]:
        P(f"| `{t.get('path','?')}` | {t.get('line','?')} | {t.get('kind','?')} | {(t.get('text') or '')[:90]} |")
P("")

# 3. Unused imports
uimp = raw.get("unused_imports", [])
P("## 3. Неиспользуемые импорты")
P("")
P(f"Найдено **{len(uimp)}** потенциально неиспользуемых импортов (через AST-анализ).")
P("")
P("Обычно это false-positive если импорт нужен для side-effect или re-export. Но топ-20 ниже стоит проверить вручную:")
P("")
if uimp:
    P("| Файл | Имя | Строка |")
    P("|---|---|---|")
    for u in uimp[:25]:
        P(f"| `{u.get('path','?')}` | `{u.get('name','?')}` | {u.get('line','?')} |")
P("")

# 4. Unused views / routes
P("## 4. Неиспользуемые view-функции и URL-routes")
P("")
P(f"Всего view-функций: **{len(raw.get('view_functions', []))}**, URL-имён: **{len(raw.get('url_names', []))}**.")
P("")
unused_views = unused.get("unused_views", [])
unused_urls = unused.get("unused_url_names", [])
ghost_renders = unused.get("ghost_renders", [])
P(f"Никем не вызываемых views (через сравнение с url-маппингом): **{len(unused_views)}**.")
P(f"URL-имён, не используемых в шаблонах и Python: **{len(unused_urls)}**.")
P(f"`render(...)` со ссылкой на несуществующий шаблон: **{len(ghost_renders)}**.")
P("")
if unused_views:
    P("### 4.1 Топ-15 unused views")
    P("")
    P("| Файл | Функция |")
    P("|---|---|")
    for v in unused_views[:15]:
        P(f"| `{v.get('path','?')}` | `{v.get('name','?')}` |")
    P("")
if unused_urls:
    P("### 4.2 Топ-15 unused URL-имён")
    P("")
    P("| URL name | Объявлен в |")
    P("|---|---|")
    for u in unused_urls[:15]:
        P(f"| `{u.get('name','?')}` | `{u.get('declared_in','?')}` |")
    P("")
if ghost_renders:
    P("### 4.3 render() с несуществующим шаблоном")
    P("")
    for g in ghost_renders[:10]:
        P(f"- `{g.get('path','?')}:{g.get('line','?')}` → `{g.get('template','?')}`")
    P("")

# 5. CSS / JS files
css_files = raw.get("css_files", [])
js_files = raw.get("js_files", [])
P("## 5. Статика — CSS / JS files")
P("")
P(f"CSS файлов в `static/css/`: **{len(css_files)}** ({sum(c.get('size',0) for c in css_files) // 1024} KB suм).")
P(f"JS файлов в `static/js/`: **{len(js_files)}** ({sum(c.get('size',0) for c in js_files) // 1024} KB суmm).")
P("")
P("### 5.1 Самые большие CSS-файлы")
P("")
P("| Файл | Size, KB |")
P("|---|---|")
for c in sorted(css_files, key=lambda x: -x.get("size", 0))[:15]:
    P(f"| `{c.get('path','?')}` | {c.get('size',0)//1024} |")
P("")
P("### 5.2 Самые большие JS-файлы")
P("")
P("| Файл | Size, KB |")
P("|---|---|")
for c in sorted(js_files, key=lambda x: -x.get("size", 0))[:15]:
    P(f"| `{c.get('path','?')}` | {c.get('size',0)//1024} |")
P("")

# 6. Templates
ts = raw.get("template_sizes", [])
P("## 6. Шаблоны — размер и иерархия")
P("")
P(f"Всего шаблонов: **{len(ts)}**.")
P("")
P("### 6.1 Самые большие шаблоны")
P("")
P("| Шаблон | Size, KB | Lines |")
P("|---|---|---|")
for t in sorted(ts, key=lambda x: -x.get("size", 0))[:15]:
    P(f"| `{t.get('path','?')}` | {t.get('size',0)//1024} | {t.get('lines','?')} |")
P("")

# 7. Migrations
migs = raw.get("runpython_migrations", [])
P("## 7. RunPython-миграции")
P("")
P(f"Найдено: **{len(migs)}** миграций с `RunPython` шагами. Это data-миграции, обычно одноразовые.")
P("")
P("**Рекомендация**: после полного применения на проде data-миграции можно «squashing'ить» в одну, чтобы не таскать за собой исторический backlog при создании fresh-прод-копии или dev-окружения.")
P("")

P("---")
P("")
P("## Итоговые приоритеты")
P("")
P("### 🔴 Critical")
P("")
P("1. **Phase-комменты в `product_detail.html`** (17) и в других горячих шаблонах — переписать в `{% comment %}` блок-резюме (1 раз) и убрать inline-фазовые. Это ускорит парсинг шаблона (на ~5-10ms за рендер) и снизит размер payload.")
P("")
P("### 🟠 High")
P("")
P("2. **17 TODO/FIXME** — отсортировать: что в bug-tracker, что удалить, что оставить с актуальной датой.")
P("3. **48 потенциально unused-imports** — вручную пройти топ-20, чистить.")
P("4. **Unused views/url_names** — обычно мёртвый код от удалённых фич; удалить с миграцией данных если нужно.")
P("")
P("### 🟡 Medium")
P("")
P("5. **CSS/JS** — top-5 самых жирных файлов проверить на мёртвый код (через PurgeCSS / coverage в Lighthouse).")
P("6. **Self-canonical phase-комменты** в Python — переписать в `RATIONALE:` пометки и снести inline-fix-комменты.")
P("")

OUT.write_text("\n".join(lines), encoding="utf-8")
print(f"wrote {OUT} ({OUT.stat().st_size} bytes, {len(lines)} lines)")
