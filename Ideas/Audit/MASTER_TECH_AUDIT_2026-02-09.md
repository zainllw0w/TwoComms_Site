# MASTER TECH AUDIT — DTF Effects & Components

**Дата:** 2026-02-09  
**Проект:** `dtf.twocomms.shop` (частина монорепозиторію TwoComms)  
**Джерела:** CODEX Final Tech Audit + Antigravity Deep Gap Analysis  
**Призначення:** Єдиний еталонний документ для Opus 4.6 та coding-agent

---

## Зміст

1. [Що було перевірено](#1-що-було-перевірено)
2. [Поточний стан проекту](#2-поточний-стан-проекту)
3. [Оцінка звітів агентів](#3-оцінка-звітів-агентів)
4. [Fact-Check Matrix](#4-fact-check-matrix)
5. [Глибокий Gap-Аналіз Ефектів](#5-глибокий-gap-аналіз-ефектів)
6. [Маппінг Компонентів](#6-маппінг-компонентів)
7. [Критичні Обмеження](#7-критичні-обмеження)
8. [Пріоритетний Roadmap](#8-пріоритетний-roadmap)
9. [Для Opus 4.6](#9-для-opus-46)
10. [Технічний Пакет для Coding-Agent](#10-технічний-пакет-для-coding-agent)
11. [Референси](#11-референси)
12. [Фінальні Висновки](#12-фінальні-висновки)

---

## 1. Що було перевірено

### 1.1 Локальні джерела

**Звіти та ідеї:**
- `Ideas/Audit/opus 4.6 v1.MD` (1155 рядків)
- `Ideas/Audit/opus 4.6 v2.MD` (1188 рядків)
- `Ideas/CODEX_Report.md` (571 рядків, 100 ідей)
- `Ideas/Antigravity_Report.md` (215 рядків, 100 ідей)
- `Ideas/Gemini_1.5_Pro.md` (258 рядків)
- `twocomms/Ideas/Claude-4-Sonnet.md`

**Каталог референсів:**
- `twocomms/Promt/Effects.MD` (1591 рядків, 16+ компонентів)

**Фактичний код DTF:**
```
twocomms/dtf/
├── templates/dtf/*.html
├── static/dtf/js/components/*
├── static/dtf/css/components/*
├── static/dtf/js/dtf.js
├── views.py
├── forms.py
├── preflight/engine.py
└── urls.py
```

**Технічна документація:**
- `specs/dtf-codex/CHECKLIST.md`
- `specs/dtf-codex/EVIDENCE.md`
- `specs/dtf-codex/QA.md`
- `specs/dtf-codex/DEPLOY.md`

### 1.2 Серверна перевірка (production, SSH)

| Параметр | Значення |
|----------|----------|
| Branch | `codex/codex-refactor-v1` |
| Commit | `d355a47` |
| `python manage.py check` | ✅ Без помилок |
| `DEBUG` | `False` |
| DB Engine | `django.db.backends.mysql` (localhost:3306) |
| Celery config | ✅ Присутній |
| Celery workers | ❌ Не знайдені |
| Redis broker | ❌ DNS не резолвиться |
| Cron tasks | ✅ Активні |

> [!CAUTION]
> **Celery + Redis на production НЕ ПРАЦЮЄ!**  
> Broker DNS error: `Name or service not known`  
> Backend polling для Multi-Step Loader неможливий без інфра-фікса.

---

## 2. Поточний стан проекту

### 2.1 Загальна стадія

**Проект НЕ в стадії прототипу.** Це робочий DTF-піддомен з реалізацією основних бізнес-сценаріїв:

- ✅ Landing / Каталог / Ціни / Вимоги / Якість / Блог
- ✅ Order і lead-flow
- ✅ Constructor MVP з збереженням сесії
- ✅ Preflight-аналіз файлів
- ✅ Sample flow
- ✅ Cabinet routes
- ✅ Host-aware robots/sitemap

**Стадія:** «Робоча продуктова база + незавершена уніфікація UI-effect layer»

### 2.2 Архітектура Frontend

**Підхід:** Django SSR + progressive enhancement через JS

```
twocomms/dtf/static/dtf/js/components/
├── core.js           # Effect registry + HTMX lifecycle
├── _utils.js         # Utility functions
└── effect.*.js       # Individual effects
```

**HTMX інтеграція:**
- `htmx:afterSwap` — реініціалізація ефектів після swap
- `htmx:beforeCleanupElement` — cleanup перед видаленням

### 2.3 Архітектура Backend

**Preflight Engine** (`twocomms/dtf/preflight/engine.py`) перевіряє:
- Magic bytes + extension
- Розмір файлу
- DPI (72, 150, 300)
- Alpha/margins
- Color mode (RGB, CMYK)
- PDF: single-page, media box

---

## 3. Оцінка звітів агентів

### 3.1 Практична цінність

| Звіт | Сильні сторони | Обмеження | Вердикт |
|------|----------------|-----------|---------|
| **CODEX_Report.md** | Приземлений аудит реального коду | Може бути застарілим | 🟢 **Висока вага** |
| **Claude-4-Sonnet.md** | Каталогізація, 100 ідей | React-орієнтоване мислення | 🟡 Backlog ідей |
| **Antigravity_Report.md** | Креатив, long-term wow-фічі | React+Vite рекомендації | 🟡 Експериментальні ідеї |
| **Gemini_1.5_Pro.md** | Performance budget, UX-психологія | Web Components занадто радикально | 🟡 Вибірково |
| **opus v1.MD** | Глибока консолідація | Не завершений | ⚠️ Incomplete |
| **opus v2.MD** | Завершена версія, структура | Технічні неточності | 🟡 Потребує fact-check |

### 3.2 Важливий факт про v1/v2

- **v1** — обривається в блоці Sprint 1 / ЗАДАЧА 2
- **v2** — повніша, містить розділ «Промпт-заготовка»
- Це дві спроби однієї консолідації, не два різних проекти

**Висновок:** Використовувати v2 як базу після сверки з реальним кодом.

---

## 4. Fact-Check Matrix

### 4.1 Критичні розбіжності

| Claim (opus v1/v2) | Статус | Коментар |
|--------------------|--------|----------|
| Multi-Step Loader «не реалізований» | ❌ Частково неправильно | Є спрощена версія в `multi-step-loader.js` |
| Flip Words «не реалізований» | ❌ Неправильно | Працює через `data-flip-words` + `initFlipWords` в `dtf.js` |
| Dotted Glow потребує IntersectionObserver | ❌ Вже реалізовано | `effect.dotted-glow.js` вже використовує IO |
| BG Beams потребує IntersectionObserver | ❌ Вже реалізовано | `effect.bg-beams.js` вже використовує IO |
| Основний файл: `effect.floating-dock.js` | ❌ Неправильний шлях | Фактично `floating-dock.js` |
| Compare потребує touch-action | ⚠️ Частково є | CSS `.compare-media` має `touch-action: pan-y` |
| Legacy cleanup в `dtf.js` | ✅ Актуально | `initCompare`, `initTracingBeam` не викликаються |
| Backend polling через Celery | ⚠️ Блоковано | Celery/Redis не працює на production |

### 4.2 Дублікати файлів

> [!WARNING]
> В проекті є «подвійні» файли (`bg-beams.js` і `effect.bg-beams.js`), що збільшує ризик рассинхронізації.

---

## 5. Глибокий Gap-Аналіз Ефектів

### 5.1 Зведена таблиця

| Ефект | Поточні рядки | Оригінал | Реалізовано | Чого не вистачає | Оцінка |
|-------|---------------|----------|-------------|------------------|--------|
| **Compare** | 75 JS + 10 CSS | React + Framer + Sparkles | Базовий слайдер | Autoplay, 3D, sparkles | ⚠️ 40% |
| **Floating Dock** | 51 JS + 51 CSS | React + mouseX Motion | Фіксований nav | macOS magnification | ❌ 20% |
| **Multi-Step Loader** | 42 JS | React state | Fake timer | Backend polling, modal | ❌ 15% |
| **Vanish Input** | 33 JS | React + Canvas | CSS toggle | Particle, cycling | ❌ 10% |
| **Infinite Cards** | 18 JS | Framer Motion scroll | Тільки клас | ВСЕ (пустушка) | ❌ 5% |
| **Encrypted Text** | 76 JS | Character scramble | Scramble animation | — | ✅ 85% |
| **Tracing Beam** | 48 JS | SVG path + scroll | Progress bar | SVG beam | ⚠️ 50% |
| **Stateful Button** | 131 JS | State machine | Loading/success/error | — | ✅ 90% |
| **Sparkles** | 37 JS | Random particles | 4 статичні точки | Random generation | ❌ 20% |
| **BG Beams** | 35 JS | SVG beams | Клас toggle | Візуальні beams | ❌ 10% |
| **Dotted Glow** | 33 JS | Animated dot grid | Клас toggle | Dot grid, glow | ❌ 10% |
| **Flip Words** | in dtf.js | Framer Motion | Працює | Винести в модуль | ⚠️ 70% |

### 5.2 Детальний розбір критичних ефектів

#### Compare (40%)

**Поточна реалізація:**
```javascript
// effect.compare.js (75 рядків)
const apply = (value) => {
  media.style.setProperty('--compare', `${pct}%`);
};
```

**Чого не вистачає:**

| Фіча | Пріоритет | Складність |
|------|-----------|------------|
| Autoplay режим | 🔴 Високий | Середня |
| Hover vs Drag mode | 🔴 Високий | Низька |
| 3D perspective | 🟡 Середній | Низька |
| Sparkles overlay | 🟢 Низький | Висока |

**Рекомендація:** ✏️ ДОРОБИТИ — autoplay + hover mode

---

#### Multi-Step Loader (15%) ⚠️ BLOCKED

**Поточна реалізація:**
```javascript
// multi-step-loader.js (42 рядки) — FAKE!
input.addEventListener('change', () => {
  setStep(host, 2);
  window.setTimeout(() => setStep(host, 3), 260);
  window.setTimeout(() => setStep(host, 4), 520);
});
```

**Чого не вистачає:**

| Фіча | Пріоритет | Статус |
|------|-----------|--------|
| Backend polling | 🔴 Критично | ⚠️ BLOCKED (Celery) |
| Modal overlay | 🔴 Високий | Можна зробити |
| Animated indicator | 🟡 Середній | Можна зробити |

**Рекомендація:** ⚠️ ЧЕКАЄ ІНФРА-ФІКС або sync честний flow

---

#### Vanish Input (10%)

**Поточна реалізація:**
```javascript
// vanish-input.js (33 рядки)
field.classList.add('is-vanish');
window.setTimeout(() => field.classList.remove('is-vanish'), 420);
```

**Чого не вистачає:**

| Фіча | Пріоритет | Складність |
|------|-----------|------------|
| Cycling placeholders | 🔴 Високий | Низька |
| Очистка поля | 🔴 Високий | Низька |
| Canvas particle | 🟡 Середній | Висока |

**Рекомендація:** ✏️ ДОРОБИТИ — cycling + clear, particle опціонально

---

#### Infinite Cards (5%)

**Поточна реалізація:**
```javascript
// effect.infinite-cards.js (18 рядків) — ПУСТУШКА!
node.classList.add('infinite-cards-ready');
return null;
```

**Оригінал (Effects.MD):**
- Framer Motion infinite scroll
- `direction`: "left" | "right"
- `speed`: "fast" | "normal" | "slow"
- `pauseOnHover`

**Рекомендація:** 🔄 СТВОРИТИ ЗАНОВО — код бесполезний

---

### 5.3 Template Usage Statistics

По `twocomms/dtf/templates/dtf/*.html`:

| Effect | Використань |
|--------|-------------|
| `compare` | 6 |
| `bg-beams` | 4 |
| `dotted-glow` | 4 |
| `encrypted-text` | 3 |
| `tracing-beam` | 3 |
| `vanish-input` | 3 |
| `multi-step-loader` | 2 |
| `infinite-cards` | 1 |
| `sparkles` | 1 |

**Висновок:** Ядро візуальної мови вже є. Дефіцит не в «додати 20 ефектів», а в доведенні поточних до production-grade.

---

## 6. Маппінг Компонентів

### 6.1 Effects.MD → Поточний стан

| Aceternity Component | Статус | Файл | Наступний крок |
|---------------------|--------|------|----------------|
| Compare | ✅ Базово | `effect.compare.js` | +autoplay, +hover mode |
| Floating Dock | ✅ Спрощено | `floating-dock.js` | Вирішити FAB конфлікт |
| Multi-Step Loader | ⚠️ Спрощено | `multi-step-loader.js` | Чекає Celery |
| Vanish Input | ⚠️ Мінімум | `vanish-input.js` | +cycling, +clear |
| Infinite Cards | ❌ Пустушка | `effect.infinite-cards.js` | Переписати |
| Encrypted Text | ✅ Готово | `effect.encrypted-text.js` | — |
| Tracing Beam | ✅ Готово | `effect.tracing-beam.js` | Опц. SVG |
| Dotted Glow | ⚠️ IO only | `effect.dotted-glow.js` | +CSS ефект |
| BG Beams | ⚠️ IO only | `effect.bg-beams.js` | +CSS ефект |
| Sparkles | ⚠️ Статично | `sparkles.js` | +random gen |
| Stateful Button | ✅ Готово | `effect.stateful-button.js` | — |
| Flip Words | ✅ Готово | `dtf.js` (legacy) | Винести в модуль |
| Tooltip Card | ❌ Немає | — | Для термінів |
| Images Badge | ❌ Немає | — | Для file manager |
| Cover | ❌ Немає | — | Декоративний |
| Animated Tooltip | ❌ Немає | — | Низький пріоритет |
| Sidebar | ❌ Немає | — | Для кабінету |
| Text Generate | ❌ Немає | — | Для trust блоків |

---

## 7. Критичні Обмеження

### 7.1 Інфраструктура

> [!CAUTION]
> **Celery/Redis Status:**
> - Celery config в settings ✅
> - Broker DNS error ❌
> - Workers не знайдені ❌

**Наслідок:** Плани «реального polling» ненадійні. Потрібно:
1. Вирішити інфра prerequisite, АБО
2. Прийняти sync/fake-step стратегію

### 7.2 Техборг Frontend

- Legacy функції в `dtf.js` (`initCompare`, `initTracingBeam`) не викликаються
- Дублі файлів `effect.*` та старі версії
- Ризик: різні агенти розвиватимуть різні версії одного ефекту

### 7.3 UX Конфлікт Right-Bottom Corner

У `base.html` одночасно присутні:
- `#dtf-fab`
- `nav[data-floating-dock]`
- `nav.mobile-dock`

**Це підтверджена проблема** з декількох звітів.

---

## 8. Пріоритетний Roadmap

### Sprint 1 — Quick Wins (без блокерів)

| # | Задача | Файли | Складність | Вплив |
|---|--------|-------|------------|-------|
| 1 | **FAB/Dock Conflict** | `base.html`, `floating-dock.*` | Середня | 🔴 Критично |
| 2 | **Infinite Cards** | `effect.infinite-cards.*` | Середня | 🔴 Високий |
| 3 | **Vanish Input** | `vanish-input.*` | Низька | 🔴 Високий |
| 4 | **Legacy Cleanup** | `dtf.js` | Низька | 🟡 Середній |
| 5 | **Flip Words → module** | NEW `effect.flip-words.js` | Низька | 🟡 Середній |

### Sprint 2 — Enhancements

| # | Задача | Файли | Складність |
|---|--------|-------|------------|
| 1 | Compare Autoplay | `effect.compare.js` | Середня |
| 2 | Compare Hover Mode | `effect.compare.js` | Низька |
| 3 | Stateful Button coverage | forms | Низька |

### Sprint 3+ — After Infra Fix

| # | Задача | Залежність |
|---|--------|------------|
| 1 | Multi-Step Loader v2 | Celery/Redis |
| 2 | Tracing Beam SVG | Немає |
| 3 | Sparkles Generator | Немає |
| 4 | BG Beams Visual | Немає |

---

## 9. Для Opus 4.6

### 9.1 Дослідницькі Теми

**Business/UX:**
1. Психотипи DTF-аудиторії (новачки vs профі)
2. Моделювання конверсії по сценаріях
3. Ліміт motion-ефектів на сторінку

**Internet Research:**
1. Паттерни B2B/B2B2C print-services
2. SEO-safe підходи для JS-animations
3. Haptics/audio — що реально для MVP

**Інфраструктура:**
1. Варіанти async progress під cPanel/shared-host
2. Prerequisites для backend polling loader

### 9.2 Питання для Opus 4.6

1. Які 3 UX-механіки дають максимальний приріст довіри?
2. Мінімальний motion-набір для кожної сторінки?
3. Copy-framework для preflight WARN/FAIL?
4. Формат screen vs print порівняння?
5. Real-time progress чи staged sync flow?
6. SEO-ризики поточних ефектів?
7. Метрики успіху для UX-фіч?
8. Адаптація під новачків/профі?
9. Web Components — long-term чи зараз?
10. Top-5 A/B гіпотез для DTF?

### 9.3 Готовий Промпт для Opus 4.6

```text
Ти отримуєш PDF "MASTER_TECH_AUDIT_2026-02-09" по проекту dtf.twocomms.shop.

Твоя роль: senior research + business + technical analyst.

ВАЖЛИВО:
1) Не переказуй документ. Роби наступний рівень аналізу.
2) Перевіряй гіпотези інтернет-ресерчем із джерелами.
3) Висновки у форматі для coding-agent.

Контекст:
- Стек: Django + Vanilla JS + HTMX + CSS
- Реалізовані: order, constructor MVP, preflight, sample, cabinet
- Effect-layer частково legacy
- MySQL активний, Celery config є але не працює

Видай 6 блоків:

БЛОК 1. Verification Matrix
БЛОК 2. Market/UX Research (з джерелами)
БЛОК 3. Behavioral Model (новачок vs профі)
БЛОК 4. Forecast & Scenarios (A/B/C на 90 днів)
БЛОК 5. Pre-Codex Technical Prep
БЛОК 6. Final Prompt Pack для coding-agent

Обмеження:
- Не React/Next/Web Components як short-term
- Враховуй cPanel/shared hosting
- Якість > складність

Формат: markdown, таблиці, "Top-15 Questions for Owner"
```

---

## 10. Технічний Пакет для Coding-Agent

### 10.1 Component Contracts

#### Infinite Cards

```yaml
selector: '[data-effect~="infinite-cards"]'
data_attributes:
  data-direction: "left" | "right" (default: "left")
  data-speed: "slow" | "normal" | "fast" (default: "normal")
  data-pause-on-hover: "true" | "false" (default: "true")
html_structure:
  container: .infinite-track
  items: .infinite-item
seo_requirements:
  first_track: real content
  cloned_track: aria-hidden="true"
reduced_motion: animation: none
cleanup: remove clone on htmx:beforeCleanupElement
```

#### Vanish Input

```yaml
selector: '[data-vanish-input]'
data_attributes:
  data-placeholders: JSON array ["hint1", "hint2"]
  data-cycle-duration: ms (default: 3000)
  data-vanish-clear: "true" | "false" (default: "true")
events_emitted:
  - vanish:start
  - vanish:complete
animation: shake + optional particle burst
reduced_motion: skip visual effects, keep clear
```

#### FAB/Dock Unified

```yaml
components:
  - "#dtf-fab": quick action button
  - "nav[data-floating-dock]": desktop nav
  - "nav.mobile-dock": mobile nav
visibility_rules:
  mobile (<768px): mobile-dock visible, dock hidden, FAB optional
  desktop (>=768px): dock visible, mobile-dock hidden, no FAB
z_index_hierarchy:
  modal: 9999
  dock: 1000
  FAB: 999
breakpoint_source: CSS custom property --dtf-breakpoint-md
```

### 10.2 Event Contracts

| Event | Emitter | Payload |
|-------|---------|---------|
| `effect:init` | core.js | `{ name, node }` |
| `effect:cleanup` | core.js | `{ name, node }` |
| `vanish:start` | vanish-input.js | `{ field }` |
| `vanish:complete` | vanish-input.js | `{ field, cleared }` |
| `loader:step` | multi-step-loader.js | `{ step, total }` |
| `loader:complete` | multi-step-loader.js | `{ success }` |

### 10.3 QA Gates

- [ ] Lighthouse Performance > 90
- [ ] Lighthouse Accessibility > 95
- [ ] CLS < 0.1
- [ ] LCP < 2.5s
- [ ] `prefers-reduced-motion` respected
- [ ] No-JS fallback functional
- [ ] HTMX re-init after swap
- [ ] Mobile touch works
- [ ] Screen reader tested

---

## 11. Референси

**HTMX:**
- https://htmx.org/events/
- `htmx:afterSwap`, `htmx:beforeCleanupElement`

**Web Performance:**
- https://web.dev/articles/vitals

**CSS:**
- https://developer.mozilla.org/en-US/docs/Web/CSS/touch-action

**Aceternity:**
- https://ui.aceternity.com/docs/installation

**JavaScript SEO:**
- https://developers.google.com/search/docs/crawling-indexing/javascript/javascript-seo-basics

---

## 12. Фінальні Висновки

1. **Проект у робочій фазі** — не прототип, потрібна стабілізація
2. **Celery блокер** — real-time progress неможливий без інфра-фікса
3. **opus v1/v2 корисні** як каркас, але містять неточності
4. **Пріоритет** = доведення існуючих ефектів до production-grade
5. **FAB/Dock конфлікт** — вирішити в Sprint 1
6. **Не додавати 20 ефектів** — довести поточні до якості

---

**Документ готовий для передачі Opus 4.6 або coding-agent.**
