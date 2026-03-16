# 🟡 FIX #8: Заборонені Терміни — preflight / QC

> **Severity:** MODERATE (але ВИСОКА СКЛАДНІСТЬ через пошук по всій кодобазі)
> **Дефект:** T-1 — Заборонені терміни залишаються в коді

---

## СУТЬ ПРОБЛЕМИ

За `ITER3_GLOSSARY.md` (рядки 64-68), заборонені терміни:
- `preflight` → замінити на `filecheck`
- `QC` → замінити на `check`
- `gang sheet` / `ганг-лист` → `лист 60 см` / `sheet 60 cm`
- `hot peel` → `гаряче зняття` / `peel while hot`
- `Knowledge Base` (з великих K/B) → `база знань` / `knowledge base`

### Де вони є зараз

```bash
# Пошук по шаблонах:
grep -rn "preflight\|QC\|gang.sheet\|ганг.лист\|hot.peel" twocomms/dtf/templates/
grep -rn "preflight\|QC\|gang.sheet\|ганг.лист\|hot.peel" twocomms/dtf/static/dtf/css/
grep -rn "preflight\|QC\|gang.sheet\|ганг.лист\|hot.peel" twocomms/dtf/static/dtf/js/
```

### Відомі місця:

| Термін | Файл | Рядок | Контекст |
|--------|------|-------|----------|
| `preflight` | `constructor_app.html` | ~159, 163, 213, 286 | `preflight-terms`, `preflight-badge-check` та ін. |
| `preflight` | `order.html` | ~105, 122, 155 | `preflight-terms`, `preflight-status` |
| `preflight` | `status.html` | Різні | `qc-badge-*` CSS класи |
| `QC` | `status.html` | Різні | `qc-badge-*` classes |
| `QC` | CSS файли | Різні | `.qc-*` CSS класи |
| `preflight` | `icons.css` | Різні | `.preflight-*` анумація |
| `preflight` | `animations.css` | Різні | Можливо є |
| `preflight` | `dtf.js` | Різні | JS селектори, data attributes |

---

## ЩО ЗРОБИТИ

### Крок 1: Повний пошук

Запустити:
```bash
grep -rn "preflight" twocomms/dtf/ --include="*.html" --include="*.css" --include="*.js"
grep -rn "QC\|qc-" twocomms/dtf/ --include="*.html" --include="*.css" --include="*.js"
```

### Крок 2: Замінити кожне входження

> [!CAUTION]
> ### ПРАВИЛА ЗАМІНИ:
> 1. **HTML data-атрибути:** `data-preflight="..."` → `data-filecheck="..."`
> 2. **CSS класи:** `.preflight-badge` → `.filecheck-badge`, `.qc-badge` → `.check-badge`
> 3. **JS селектори:** `'[data-preflight]'` → `'[data-filecheck]'`, `'.qc-badge'` → `'.check-badge'`
> 4. **HTML id=:** `id="preflight-..."` → `id="filecheck-..."`
> 5. **Текстовий контент:** `{% trans "Preflight" %}` → `{% trans "Перевірка файлу" %}` (або локалізований)
> 6. **НЕ ЧІПАТИ:** файли конфігурації, бекенд Python, назви SVG файлів (`step-preflight.svg` — це ім'я файлу, НЕ UI текст)

### Крок 3: Масова заміна (скрипт)

```bash
# Заміна в HTML шаблонах:
find twocomms/dtf/templates -name "*.html" -exec sed -i '' \
  -e 's/preflight-terms/filecheck-terms/g' \
  -e 's/preflight-badge/filecheck-badge/g' \
  -e 's/preflight-status/filecheck-status/g' \
  -e 's/data-preflight/data-filecheck/g' \
  -e 's/id="preflight-/id="filecheck-/g' \
  {} +

# Заміна в CSS:
find twocomms/dtf/static/dtf/css -name "*.css" -exec sed -i '' \
  -e 's/\.preflight-/.filecheck-/g' \
  -e 's/\.qc-/.check-/g' \
  {} +

# Заміна в JS:
find twocomms/dtf/static/dtf/js -name "*.js" -exec sed -i '' \
  -e 's/preflight/filecheck/g' \
  -e 's/\.qc-/.check-/g' \
  {} +
```

> [!WARNING]
> **ПІСЛЯ МАСОВОЇ ЗАМІНИ:** Обов'язково перевір вручну кожен файл! `sed` може зламати контент якщо термін зустрічається у неочікуваному контексті.

### Крок 4: Перевірити що нічого не зломалось

```bash
# Перевірка що всі CSS класи зв'язані:
grep -rn "filecheck" twocomms/dtf/templates/ --include="*.html" | head -20
grep -rn "filecheck" twocomms/dtf/static/ --include="*.css" | head -20
grep -rn "filecheck" twocomms/dtf/static/ --include="*.js" | head -20
```

### Крок 5: step-preflight.svg

Файл `step-preflight.svg` (у `static/dtf/assets/`) — це **ім'я файлу**, а не UI текст. НЕ ПЕРЕЙМЕНОВУВАТИ (бо це може зламати шляхи). Але якщо ім'я файлу використовується як `alt` текст десь — замінити текст `alt` на "Перевірка файлу".

---

## ПЕРЕВІРКА

1. `grep -rn "preflight" twocomms/dtf/templates/` — **0 результатів** (крім коментарів ASSET_REQUEST)
2. `grep -rn "QC\b" twocomms/dtf/templates/` — **0 результатів**
3. Відкрити constructor_app, order, status — перевірити що badge-и працюють і стилізовані правильно
4. Перевірити що JS selectors правильно знаходять елементи (не зламали функціональність)
