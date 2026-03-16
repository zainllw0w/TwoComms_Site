# 🔧 ITER3 V3 — Мастер-Промт для Agent3 (Codex): Полное Исправление Всех Дефектов

> **Версія:** 3.0 | **Дата:** 2026-03-04
> **Для кого:** Agent3 (Codex) — виконавець, який буде виправляти всі дефекти
> **Джерело:** Аналіз `ITER3_DEFECTS_GLOBAL.md` + `ITER3_AUDIT_REPORT.md` + код проекту
> **Контекст:** Цей документ — ЄДИНЕ джерело правди для Agent3. Він не має пропустити ЖОДЕН пункт.

> [!CAUTION]
> **Обов'язково використовуй:**
> 1. **Sequential Thinking MCP** — для розбиття складних задач на кроки
> 2. **Context7 MCP** — для перевірки best practices і документації
> 3. **Глосарій** → `ITER3_GLOSSARY.md` — для всіх термінів
> 4. **File Map** → `ITER3_FILE_MAP.md` — для розуміння структури проекту

---

## 📋 ЗМІСТ І ПОСЛІДОВНІСТЬ ВИКОНАННЯ

Виконуй задачі **СТРОГО** в цьому порядку. Кожна задача має свій окремий файл з деталями:

| # | Дефект | Пріоритет | Файл деталей | Складність |
|---|--------|-----------|--------------|------------|
| 1 | 🔴 Dot Distortion — repulsion physics | CRITICAL | `01_FIX_DOT_DISTORTION.md` | Середня |
| 2 | 🔴 Лампочка → homepage | CRITICAL | `02_FIX_ICON_BULB.md` | Низька |
| 3 | 🟡 CSS анімації — timing + JS тригери | MAJOR | `03_FIX_ANIMATIONS.md` | Середня |
| 4 | 🟡 SVG іконки — інтеграція 7 невикориста­них | MAJOR | `04_FIX_SVG_INTEGRATION.md` | Низька |
| 5 | 🟡 Card entrance — CSS↔JS sync | MAJOR | `05_FIX_CARD_ENTRANCE.md` | Низька |
| 6 | 🟡 Rotator bar — 3+ фрази | MODERATE | `06_FIX_ROTATOR.md` | Середня |
| 7 | 🟡 Telegram prefill — контекстні тексти | MODERATE | `07_FIX_TG_PREFILL.md` | Низька |
| 8 | 🟡 Заборонені терміни preflight/QC | MODERATE | `08_FIX_FORBIDDEN_TERMS.md` | Висока |
| 9 | 🟢 FAQ format unification | MINOR | `09_FIX_FAQ_FORMAT.md` | Середня |
| 10 | 🔴 Image Compare Slider — баги | CRITICAL | `10_FIX_COMPARE_SLIDER.md` | Середня |

---

## 🏗️ ЗАГАЛЬНІ ПРАВИЛА ДЛЯ AGENT3

### Безпека змін
- **ТІЛЬКИ** `twocomms/dtf/` — ніяких backend змін
- Після кожної групи змін — `python manage.py collectstatic --noinput`
- Оновлювати `?v=` версію CSS/JS лінків у `base.html`
- Не ламати існуючий layout — перевіряти на 320/360/390px

### Performance бюджет
- Анімації — ТІЛЬКИ `transform`, `opacity`, `filter` (обережно)
- `prefers-reduced-motion: reduce` — обов'язково для всіх анімацій
- Touch targets ≥ 44×44px
- Dot background ≤ 620 dots на mobile (tier 2)

### Термінологія (Глосарій)
- **ЗАБОРОНЕНО в UI:** `preflight`, `gang sheet`, `ганг-лист`, `hot peel`, `QC`, `Knowledge Base`, `Safe area` (англ. в UA/RU)
- **ЗА КАНОНІЧНИМИ термінами** — дивись `ITER3_GLOSSARY.md`

### Код і стиль
- Vanilla JS, ES5-сумісний (без стрілкових функцій у нових модулях, якщо вони потрібні для IE fallback)
- CSS — через існуючу token-систему (`tokens.css`)
- SVG іконки — через `{% include 'dtf/svg/icon-NAME.svg' %}`
- Трьохмовність — UA/RU/EN у кожному шаблоні через `{% if current_lang == ... %}`

---

## 📁 ФАЙЛОВА МАПА (Ключові файли)

```
twocomms/dtf/
├── templates/dtf/
│   ├── base.html           ← header, footer, dock (ГЛОБАЛЬНЕ)
│   ├── index.html           ← homepage (proof-grid, compare slider, lens, FAQ, works)
│   ├── faq.html             ← FAQ page (окрема від homepage FAQ)
│   ├── constructor_app.html ← конструктор (icon-bulb НЕПРАВИЛЬНО тут)
│   ├── order.html           ← форма замовлення (icon-bulb НЕПРАВИЛЬНО тут)
│   ├── status.html          ← статус замовлення (QC класи)
│   ├── price.html           ← прайс
│   ├── quality.html         ← якість (compare slider)
│   ├── gallery.html         ← галерея (compare slider)
│   └── effects_lab.html     ← лабораторія ефектів (3 compare modes)
├── static/dtf/
│   ├── js/
│   │   ├── dtf.js           ← головний JS (dot distortion, card reveal, lens, FAQ, rotator)
│   │   └── components/
│   │       ├── effect.compare.js  ← image compare slider
│   │       └── effect.images-badge.js ← images badge (folder hover)
│   ├── css/
│   │   ├── dtf.css          ← основний CSS
│   │   ├── tokens.css       ← дизайн-токени
│   │   └── components/
│   │       ├── icons.css        ← іконні анімації (timing НЕПРАВИЛЬНИЙ)
│   │       ├── animations.css   ← компонентні анімації (CSS↔JS розрив)
│   │       └── effect.compare.css ← стилі compare slider
│   └── svg/
│       ├── icon-bulb.svg     ← лампочка (+ ще 14 іконок)
│       ├── icon-file.svg     ← НЕВИКОРИСТАНА
│       ├── icon-scan.svg     ← НЕВИКОРИСТАНА
│       ├── icon-truck.svg    ← НЕВИКОРИСТАНА
│       ├── icon-sheet60.svg  ← НЕВИКОРИСТАНА
│       ├── icon-palette.svg  ← НЕВИКОРИСТАНА
│       ├── icon-clock.svg    ← НЕВИКОРИСТАНА
│       └── icon-calculator.svg ← НЕВИКОРИСТАНА
```

---

## 🔍 АЛГОРИТМ РОБОТИ

```
1. Прочитай цей файл повністю
2. Прочитай ITER3_GLOSSARY.md і ITER3_FILE_MAP.md
3. Для кожного дефекту (в порядку пріоритету):
   a. Прочитай файл деталей (01_FIX_*.md, 02_FIX_*.md, ...)
   b. Використай Sequential Thinking MCP для планування
   c. Прочитай поточний код (файли вказані в деталях)
   d. Внеси зміни
   e. Перевір на 3 мовах (UA/RU/EN)
   f. Перевір на мобільному viewport (320/360/390px)
4. Після всіх змін:
   a. collectstatic
   b. Оновити ?v= у base.html
   c. Створити HANDOVER файл
```

---

## 📊 DEFINITION OF DONE

Коли ВСЕ нижче = ✅, задача виконана:

- [ ] Dot distortion — repulsion physics працює (точки тікають від курсора)
- [ ] Dot distortion — staticField працює (точки відштовхуються навіть при нерухомій миші)
- [ ] Icon-bulb на homepage в секції `why-us` біля тексту "Стабільне виробництво"
- [ ] Icon-bulb анімація: blink 200-260ms, інтервал 7-9 сек, НЕ infinite loop
- [ ] Всі 15 SVG іконок використовуються де це логічно
- [ ] CSS анімації іконок — НЕ infinite (крім дихання), тригер через JS/IntersectionObserver
- [ ] Card entrance — CSS і JS таргетують ОДНАКОВІ класи
- [ ] Rotator — мінімум 3 фрази, JS ротація, 3 мови
- [ ] Telegram prefill — різний текст для кожної сторінки (K4)
- [ ] `preflight` замінено на `filecheck` у data-атрибутах і CSS-класах
- [ ] `QC` замінено на `check` у CSS-класах
- [ ] FAQ page — той самий формат що на homepage (`faq-item`/`faq-q`/`faq-a`)
- [ ] Image compare slider — правильна поведінка всіх 3 режимів
- [ ] Lens (збільшувальне скло) — правильне масштабування, без зміщення, без zoom замість заміни
- [ ] `collectstatic` виконано
- [ ] `?v=` оновлено у `base.html`
- [ ] Всі зміни перевірені на 320/360/390px
- [ ] `prefers-reduced-motion` працює для всіх нових анімацій
