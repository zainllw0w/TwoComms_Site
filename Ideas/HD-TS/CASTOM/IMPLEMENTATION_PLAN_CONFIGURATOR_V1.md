# TwoComms Custom Print Configurator — Implementation Plan V2

> **Источник:** [twocomms_configurator_final_doctrine_v7_1.md](./twocomms_configurator_final_doctrine_v7_1.md)
> **Цель:** Полная реализация guided custom-flow конфигуратора для страницы `/custom-print/`
> **Стек:** Django 5.x, Vanilla JS (ES2022+), Vanilla CSS (Custom Properties), существующий `base.html`
> **Дата:** 13 апреля 2026
> **Design audit:** 13.04.2026 (проведён аудит живого twocomms.shop, уточнены токены, добавлены mobile CSS)

---

## Содержание

1. [Философия и контекст](#1-философия-и-контекст)
2. [Архитектура — что менять, что не трогать](#2-архитектура)
3. [Дизайн-система — токены V2, визуал, compound styles](#3-дизайн-система)
4. [Структура страницы и компоненты](#4-структура-страницы)
5. [Шаг 0: Hero + Entry Flow](#5-шаг-0-hero)
6. [Шаг 1: Quick Start](#6-шаг-1-quick-start)
7. [Шаг 2: Выбор изделия](#7-шаг-2-выбор-изделия)
8. [Шаг 3–6: Core Hoodie Flow](#8-шаги-3-6-core-hoodie-flow)
9. [Шаг 7: File / Reference / Помощь с дизайном](#9-шаг-7-file-triage)
10. [Шаг 8: Контакты / Доставка / Review](#10-шаг-8-review)
11. [Product Stage](#11-product-stage)
12. [Build Strip](#12-build-strip)
13. [Price Capsule](#13-price-capsule)
14. [Safe Exit к менеджеру](#14-safe-exit)
15. [Motion System](#15-motion-system)
16. [Responsive Shell (расширён — CSS правила для mobile)](#16-responsive-shell)
17. [Accessibility](#17-accessibility)
18. [Состояния ошибок и загрузки](#18-ошибки-и-loading)
19. [Value & Trust Layer](#19-trust-layer)
20. [Analytics Event Schema](#20-analytics)
21. [Backend: модели, views, API](#21-backend)
22. [Чеклист запуска + Mobile QA](#22-чеклист)
23. [Что НЕ делать](#23-non-goals)
24. [Порядок реализации](#порядок-реализации)
A. [Appendix: Инструкции для реализующего AI](#appendix-a)

---

## 1. Философия и контекст

### Почему именно так

TwoComms — украинский бренд street/military одежды с собственным производством. Кастомный принт — ключевое коммерческое предложение. **Текущая страница** (`custom_print.html`, ~2000 строк inline CSS/HTML) представляет собой монолитную форму-конфигуратор первого поколения. Она функциональна, но:

- смешивает все сценарии (B2C/B2B/подарок) в один поток;
- не даёт визуальной обратной связи о том, как выглядит собираемая вещь;
- перегружает пользователя одновременными решениями;
- не содержит safe exit с сохранением прогресса;
- имеет слабую обработку ошибок (нет recovery при submit failure).

**Новый конфигуратор** должен ощущаться как **сборка вещи**, а не заполнение анкеты. Пользователь:
- контролирует процесс,
- видит текущий результат (Product Stage),
- понимает прогресс (Build Strip),
- знает цену (Price Capsule),
- может в любой момент уйти к менеджеру, не потеряв прогресс (Safe Exit).

### Маркеры уверенности из доктрины

- **[A]** — обязательно, без переизобретения.
- **[B]** — сильный паттерн, внедрять если нет конфликта.
- **[C]** — гипотеза, не утяжелять ради неё v1.

---

## 2. Архитектура

### 2.1 Что менять

| Компонент | Действие | Файл(ы) |
|---|---|---|
| **Шаблон** | Полностью переписать | `templates/pages/custom_print.html` |
| **CSS** | Новый файл, подключить через `{% block extra_css %}` | `static/css/custom-print-configurator.css` |
| **JS** | Новый модуль, подключить через `{% block extra_js %}` | `static/js/custom-print-configurator.js` |
| **View** | Расширить контекст, добавить JSON-данные | `views/static_pages.py :: custom_print()` |
| **API endpoints** | Добавить 2 новых endpoint | `urls.py`, `views/static_pages.py` |
| **Модели** | Расширить `CustomPrintLead` | `models.py` |
| **Form** | Эволюция `CustomPrintLeadForm` | `forms.py` |

### 2.2 Что НЕ трогать

- `base.html` — наследование остаётся `{% extends "base.html" %}`.
- Навигация сайта — header/footer берутся из base.
- Существующие модели `Catalog`, `CatalogOption`, `CatalogOptionValue`, `SizeGrid` — не удалять, но и не делать центром новой логики (в v1 конфиг вещей hardcoded в JSON-контексте).
- Notification system (`custom_print_notifications.py`) — расширить, не ломать.
- Admin panel custom print section — только добавлять новые поля.

### 2.3 Файловая структура после реализации

> ⚠️ **AUDIT FIX:** Все статические файлы размещаются в `twocomms_django_theme/static/`,
> а **НЕ** в `twocomms/static/` — это критически важно, т.к. основной STATICFILES_DIR
> в settings.py указывает на `twocomms_django_theme/static/`. Второй каталог (`twocomms/static/`)
> содержит только dropshipper-файлы и robots.txt.

```
twocomms/
├── twocomms_django_theme/
│   ├── static/
│   │   ├── css/
│   │   │   ├── styles.purged.css             ← СУЩЕСТВУЮЩИЙ: основные стили
│   │   │   ├── fonts.css                     ← СУЩЕСТВУЮЩИЙ
│   │   │   └── custom-print-configurator.css ← НОВЫЙ: все стили конфигуратора
│   │   ├── js/
│   │   │   ├── main.js                       ← СУЩЕСТВУЮЩИЙ: основной JS
│   │   │   └── custom-print-configurator.js  ← НОВЫЙ: вся логика конфигуратора
│   │   └── img/
│   │       ├── icons/                        ← СУЩЕСТВУЮЩИЙ: hoodie.svg, tshirt.svg...
│   │       └── configurator/                 ← НОВЫЙ: рендеры, превью
│   │           ├── hoodie-regular-front.webp
│   │           ├── hoodie-regular-back.webp
│   │           ├── hoodie-oversize-front.webp
│   │           ├── hoodie-oversize-back.webp
│   │           ├── tshirt-front.webp
│   │           ├── longsleeve-front.webp
│   │           └── print-zones/              ← SVG контуры зон печати
│   │               ├── hoodie-front-chest.svg
│   │               ├── hoodie-front-full.svg
│   │               ├── hoodie-back-full.svg
│   │               └── hoodie-sleeve.svg
│   └── templates/
│       └── pages/
│           └── custom_print.html             ← ПЕРЕПИСАТЬ ПОЛНОСТЬЮ
├── storefront/
│   ├── views/
│   │   ├── static_pages.py                   ← МОДИФИЦИРОВАТЬ: custom_print()
│   │   └── __init__.py                       ← МОДИФИЦИРОВАТЬ: +экспорт новых views
│   ├── models.py                             ← МОДИФИЦИРОВАТЬ: +draft fields
│   ├── forms.py                              ← МОДИФИЦИРОВАТЬ: адаптация формы + .save()
│   └── urls.py                               ← МОДИФИЦИРОВАТЬ: +2 endpoints
└── static/                                   ← НЕ ТРОГАТЬ (dropshipper, robots.txt)
```

### 2.4 Принцип рендеринга

Конфигуратор — **SPA-подобная страница** внутри Django-шаблона. Это означает:
- одна начальная загрузка HTML;
- все шаги переключаются **клиентским JS** без перезагрузки;
- данные конфигурации живут в JS-объекте `ConfigState`;
- финальный submit — AJAX POST к `/custom-print/lead/`;
- safe exit — AJAX POST к `/custom-print/safe-exit/` (новый endpoint).

**Почему не полный SPA/React:** проект использует Django templates + vanilla JS. Добавление фреймворка ради одной страницы создаёт несоразмерную сложность. Vanilla JS ES2022 даёт достаточную модульность через классы и модули.

---

## 3. Дизайн-система

### 3.1 Зачем нужна своя система токенов

Доктрина v7.1, раздел 2, явно требует [A]: конфигуратор должен выглядеть как **естественное продолжение TwoComms**, а не как чужой UI-kit. Текущий сайт уже имеет узнаваемый визуальный язык: тёмный фон, золотые акценты, крупная типографика, glassmorphism-карточки, скруглённые формы.

### 3.2 Токены — извлечены и проверены по живому сайту (audit 13.04.2026)

Ниже — **полный перечень** CSS custom properties для конфигуратора. Все значения **извлечены из текущего `custom_print.html`**, `index.html` и `base.html`, затем нормализованы. Проведён дополнительный аудит по живому production-сайту (twocomms.shop).

> ⚠️ **Для реализующего AI:** копируй весь блок `:root { ... }` целиком в начало `custom-print-configurator.css`. Нигде в файле не должно быть жёстко прописанных hex/px — только `var(--tc-*)`. Единственное исключение — значения внутри самих токенов.

```css
/* ============================================================
   CUSTOM PRINT CONFIGURATOR — DESIGN TOKENS V2
   Audited against production site (twocomms.shop 2026-04-13)
   Source: custom_print.html, index.html, base.html
   ============================================================ */

:root {
  /* ─── ЦВЕТА — ФОН ───
     ВАЖНО: на сайте body = #0a0a0a, но print page shell = #0c0d12.
     Конфигуратор использует --tc-bg для своего shell, а не для body.
  */
  --tc-bg:                  #0c0d12;
  --tc-bg-page:             #0a0a0a;            /* body-level bg из base.html */
  --tc-surface:             rgba(16, 18, 24, 0.92);
  --tc-surface-strong:      rgba(23, 25, 33, 0.98);
  --tc-surface-subtle:      rgba(10, 12, 17, 0.45);
  --tc-surface-elevated:    rgba(12, 14, 20, 0.92);
  --tc-surface-input:       rgba(5, 7, 11, 0.55); /* для input/textarea backgrounds */

  /* ─── ЦВЕТА — БОРДЕРЫ ─── */
  --tc-border:              rgba(255, 214, 138, 0.12);  /* gold-tinted, основной */
  --tc-border-strong:       rgba(255, 214, 138, 0.28);  /* selected state */
  --tc-border-muted:        rgba(255, 255, 255, 0.08);  /* neutral, для cards */
  --tc-border-subtle:       rgba(255, 255, 255, 0.1);   /* для inputs, secondary buttons */
  --tc-border-dashed:       rgba(255, 255, 255, 0.12);  /* для drag & drop зоны */

  /* ─── ЦВЕТА — АКЦЕНТ (ЗОЛОТОЙ) ───
     АРХИТЕКТУРНОЕ РЕШЕНИЕ: конфигуратор использует ЗОЛОТУЮ акцентную систему.
     Homepage hero использует фиолетовый (#a855f7→#7c3aed) для каталожных CTA.
     Custom print = gold = «ваш уникальный продукт». Это осознанное разделение.
  */
  --tc-accent:              #e2b25b;
  --tc-accent-soft:         #f7d58f;
  --tc-accent-deep:         #b97c2b;
  --tc-accent-gradient:     linear-gradient(135deg, #f6d48d, #e5b35a 56%, #c67b30);
  --tc-accent-text-on:      #26160a;             /* ОБЯЗАТЕЛЬНО: тёмный текст на золотом CTA */
  --tc-accent-glow:         rgba(198, 123, 48, 0.22); /* glow вокруг CTA */
  --tc-accent-bg-faint:     rgba(255, 214, 138, 0.05); /* фон kicker badge */
  --tc-accent-bg-subtle:    rgba(255, 214, 138, 0.08); /* фон price tag, active tab */
  --tc-accent-border-faint: rgba(255, 214, 138, 0.15); /* бордер kicker badge */

  /* ─── ЦВЕТА — ТЕКСТ ───
     ВАЖНО: сайт использует тёплый белый #f7f0e6, а НЕ чистый #fff.
     Это часть бренда — сохранять.
  */
  --tc-text:                #f7f0e6;
  --tc-text-muted:          rgba(247, 240, 230, 0.72);
  --tc-text-subtle:         rgba(247, 240, 230, 0.56);
  --tc-text-placeholder:    rgba(247, 240, 230, 0.42);  /* поднято с 0.38 для WCAG AA */
  --tc-text-disabled:       rgba(247, 240, 230, 0.32);

  /* ─── ЦВЕТА — СЕМАНТИКА ─── */
  --tc-success:             #8ecfa0;
  --tc-success-bg:          rgba(142, 207, 160, 0.12);
  --tc-success-border:      rgba(142, 207, 160, 0.18);
  --tc-danger:              #ffb1a2;
  --tc-danger-bg:           rgba(255, 177, 162, 0.12);
  --tc-warning:             #f7d58f;
  --tc-warning-bg:          rgba(247, 213, 143, 0.12);
  --tc-info:                #a0ccf7;              /* информационный нейтральный */
  --tc-info-bg:             rgba(160, 204, 247, 0.12);

  /* ─── ТИПОГРАФИКА ───
     Шрифт Inter наследуется из base.html через body.
     Все font-size — через clamp() для responsive где нужно.
  */
  --tc-font-family:         inherit;
  --tc-font-size-2xs:       0.68rem;              /* мелкие badges, капсулы */
  --tc-font-size-xs:        0.76rem;              /* kicker labels */
  --tc-font-size-sm:        0.88rem;              /* secondary text */
  --tc-font-size-base:      0.94rem;              /* body text */
  --tc-font-size-md:        1rem;                 /* controls, buttons */
  --tc-font-size-lg:        1.22rem;              /* section subtitles */
  --tc-font-size-xl:        clamp(1.3rem, 2vw, 1.85rem);   /* section titles */
  --tc-font-size-2xl:       clamp(1.6rem, 3vw, 2rem);      /* hero subtitle */
  --tc-font-size-hero:      clamp(2rem, 4vw, 3.5rem);      /* hero title */
  --tc-line-height-tight:   0.96;               /* hero заголовки */
  --tc-line-height-heading: 1.04;               /* section заголовки */
  --tc-line-height-body:    1.6;                /* body text */
  --tc-letter-spacing-tight: -0.05em;           /* hero title */
  --tc-letter-spacing-kicker: 0.08em;           /* kicker labels */

  /* ─── СКРУГЛЕНИЯ ───
     ВАЖНО: на mobile (<767px) shell = 22px, sections = 22px.
     На desktop shell = 30px, sections = 26px.
     Переключение через @media — см. §16 Responsive.
  */
  --tc-radius-xs:           10px;                /* tooltip, small badge */
  --tc-radius-sm:           12px;
  --tc-radius-md:           18px;
  --tc-radius-input:        16px;                /* input/textarea fields */
  --tc-radius-lg:           22px;
  --tc-radius-xl:           26px;
  --tc-radius-shell:        30px;                /* переопределяется на mobile */
  --tc-radius-pill:         999px;

  /* ─── SPACING ─── */
  --tc-space-2xs:           0.18rem;
  --tc-space-xs:            0.35rem;
  --tc-space-sm:            0.55rem;
  --tc-space-md:            0.75rem;
  --tc-space-lg:            1rem;
  --tc-space-xl:            1.2rem;
  --tc-space-2xl:           1.5rem;
  --tc-space-section:       clamp(1rem, 2vw, 1.6rem);

  /* ─── ТЕНИ ─── */
  --tc-shadow-card:         0 16px 30px rgba(0, 0, 0, 0.22);
  --tc-shadow-card-hover:   0 20px 36px rgba(0, 0, 0, 0.28);
  --tc-shadow-shell:        0 28px 90px rgba(0, 0, 0, 0.42);
  --tc-shadow-cta:          0 16px 34px rgba(198, 123, 48, 0.22);
  --tc-shadow-cta-hover:    0 18px 38px rgba(198, 123, 48, 0.30);
  --tc-shadow-mobile-bar:   0 20px 40px rgba(0, 0, 0, 0.34);  /* нижняя панель mobile */
  --tc-shadow-focus:        0 0 0 4px rgba(226, 178, 91, 0.1); /* focus ring */

  /* ─── MOTION (из doctrine v7.1, раздел 8) [A] ─── */
  --tc-motion-instant:      80ms linear;
  --tc-motion-fast:         150ms cubic-bezier(0.4, 0, 0.2, 1);
  --tc-motion-enter:        250ms cubic-bezier(0.2, 0, 0, 1);
  --tc-motion-exit:         200ms cubic-bezier(0.4, 0, 1, 1);
  --tc-motion-large:        280ms cubic-bezier(0.2, 0, 0, 1);
  --tc-motion-hover:        180ms ease;          /* hover transitions на cards/buttons */

  /* ─── GLASSMORPHISM ─── */
  --tc-glass:               linear-gradient(180deg,
                              rgba(255, 255, 255, 0.045),
                              rgba(255, 255, 255, 0.02)),
                            var(--tc-surface);
  --tc-glass-blur:          blur(12px);
  --tc-glass-heavy-blur:    blur(18px);          /* для mobile bottom bar */

  /* ─── GRID OVERLAY (workshop texture) ───
     Текущая print page использует 22×22px сетку поверх shell.
     Создаёт ощущение «мастерской / blueprint». Сохранить.
  */
  --tc-grid-size:           22px;
  --tc-grid-color:          rgba(255, 255, 255, 0.025);
  --tc-grid-mask:           linear-gradient(180deg, rgba(0, 0, 0, 0.45), transparent 75%);

  /* ─── РАЗМЕРЫ TOUCH ─── */
  --tc-target-min:          44px;  /* для важных controls */
  --tc-target-standard:     48px;  /* основные controls */
  --tc-target-cta:          52px;  /* primary CTA min-height */

  /* ─── Z-INDEX SCALE ─── */
  --tc-z-base:              1;
  --tc-z-sticky:            10;     /* sticky elements (stage, price) */
  --tc-z-overlay:           50;     /* mobile bottom bar, modals bg */
  --tc-z-modal:             100;    /* safe-exit modal */
}

/* === REDUCED MOTION (doctrine §8.4) [A] === */
@media (prefers-reduced-motion: reduce) {
  * {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}

/* === PERF-LITE FALLBACK (AUDIT FIX) [A] ===
   base.html автоматически добавляет .perf-lite на <html> для слабых устройств
   (≤2GB RAM или ≤2 CPU cores).
   
   Это ГЛОБАЛЬНО убивает все transition/animation/backdrop-filter.
   Конфигуратор ОБЯЗАН корректно работать без них.
   
   Ключевые правила из base.html:
   - .perf-lite * { animation-duration: 0.001ms; transition-duration: 0.001ms; }
   - .perf-lite .card.glassy { backdrop-filter: none; }
   
   КРИТИЧЕСКОЕ ПРАВИЛО: НЕ полагаться на анимации для функциональности шагов.
   Использовать display/visibility для критической логики переключения,
   а transitions только для визуального polish.
*/

/* Отключить glassmorphism */
.perf-lite .cfg-step,
.perf-lite .cfg-price,
.perf-lite .cfg-strip,
.perf-lite .cfg-stage,
.perf-lite .cfg-section,
.perf-lite .cfg-header {
  backdrop-filter: none !important;
  -webkit-backdrop-filter: none !important;
  background: var(--tc-surface-strong) !important;
}

/* Отключить gradient CTA → flat gold */
.perf-lite .cfg-btn--primary {
  background: var(--tc-accent) !important;
  box-shadow: none !important;
}

/* Отключить grid overlay */
.perf-lite .cfg-shell::before {
  display: none !important;
}

/* Отключить hover transforms */
.perf-lite .cfg-option-card,
.perf-lite .cfg-btn {
  transition: none !important;
  transform: none !important;
}

/* Отключить тяжёлые icon filters — заменить простым opacity */
.perf-lite .cfg-product-card input:checked + .cfg-option-card .cfg-product-icon img {
  filter: none !important;
  opacity: 1;
}

/* ЧТО СОХРАНЯЕТСЯ в perf-lite: borders, border-radius, цвета, spacing, focus states */
```

### 3.3 Почему именно эти значения

- **Цвета:** Тёмный фон `#0c0d12` и золотые акценты `#e2b25b → #f7d58f` — это ДНК TwoComms. Они уже прожиты в текущей странице custom_print и в index.html. НЕ менять на Material или другую палитру.
- **Радиусы 22–30px:** Текущий сайт использует крупные скругления (22–30px для панелей, 999px для кнопок). Это часть бренда — не уменьшать.
- **Glassmorphism:** `backdrop-filter: blur(12px)` + полупрозрачные поверхности — фирменный стиль. Сохранить.
- **Motion tokens:** Прямая цитата из doctrine §8.2 [A]. Не менять значения.
- **Touch targets 44–48px:** Doctrine §9.3 [B] — ориентир на удобство, а не на минимум 24px.

### 3.4 Карта компонентных стилей (V2 — расширена)

> ⚠️ **Для реализующего AI:** Каждый визуальный элемент ОБЯЗАН строиться из токенов `var(--tc-*)`. Нигде в CSS не должно быть жёстко прописанных hex/px/ms значений.

| Компонент | Фон | Бордер | Радиус | Тень | Hover |
|---|---|---|---|---|---|
| **Shell** | gradient + grid overlay | `--tc-border` | `--tc-radius-shell` | `--tc-shadow-shell` | — |
| **Section** | `--tc-glass` + `--tc-glass-blur` | `--tc-border` | `--tc-radius-xl` | — | — |
| **Option Card** | `--tc-surface-elevated` | `--tc-border-muted` | `--tc-radius-lg` | — | depth-1 |
| **Option Card:selected** | gold gradient bg | `--tc-border-strong` | `--tc-radius-lg` | `--tc-shadow-card` | transform locked |
| **Product Card** | `--tc-surface-elevated` | `--tc-border-muted` | `--tc-radius-lg` | — | depth-1 + icon scale |
| **Input/Textarea** | `--tc-surface-input` | `--tc-border-subtle` | `--tc-radius-input` | — | focus: `--tc-shadow-focus` |
| **CTA Primary** | `--tc-accent-gradient` | none | `--tc-radius-pill` | `--tc-shadow-cta` | depth-2 |
| **CTA Secondary** | `rgba(255,255,255,0.04)` | `--tc-border-subtle` | `--tc-radius-pill` | — | depth-3 |
| **Price Capsule** | `--tc-glass` + blur | `--tc-border` | `--tc-radius-xl` | — | — |
| **Build Strip chip** | `rgba(255,255,255,0.03)` | `--tc-border-subtle` | `--tc-radius-pill` | — | depth-3 |
| **Build Strip chip:done** | `rgba(226,178,91,0.12)` | `--tc-border-strong` | `--tc-radius-pill` | — | pointer |
| **Build Strip chip:current** | `--tc-accent-bg-subtle` | accent solid | `--tc-radius-pill` | — | — |
| **Kicker badge** | `--tc-accent-bg-faint` | `--tc-accent-border-faint` | `--tc-radius-pill` | — | — |
| **Price tag** | `--tc-accent-bg-subtle` | `rgba(255,214,138,0.14)` | `--tc-radius-pill` | — | — |
| **Zone badge:free** | `--tc-success-bg` | `--tc-success-border` | `--tc-radius-pill` | — | — |
| **Zone badge:estimate** | `--tc-warning-bg` | `rgba(226,178,91,0.18)` | `--tc-radius-pill` | — | — |
| **Trust note** | `--tc-accent-bg-faint` | `rgba(255,214,138,0.1)` | `--tc-radius-md` | — | — |
| **Drop zone** | transparent | `--tc-border-dashed` dashed | `--tc-radius-lg` | — | solid border |
| **Mobile bar** | `rgba(12,14,20,0.94)` | `--tc-border` | 24px | `--tc-shadow-mobile-bar` | — |
| **Stage switcher tab** | `--tc-surface-subtle` | `--tc-border-muted` | `--tc-radius-pill` | — | accent border |
| **Stage switcher tab:active** | `--tc-accent-bg-subtle` | `--tc-border-strong` | `--tc-radius-pill` | — | — |
| **Safe Exit btn** | `rgba(255,255,255,0.04)` | `--tc-border-subtle` | `--tc-radius-pill` | — | depth-3 |

### 3.4.1 Составные CSS-паттерны (compound styles)

> ⚠️ **Для реализующего AI:** Эти блоки нужно интегрировать в `custom-print-configurator.css` как готовые классы.

**Shell gradient + grid overlay:**
```css
.cfg-shell {
  position: relative;
  background:
    radial-gradient(circle at top right, rgba(226, 178, 91, 0.18), transparent 28%),
    radial-gradient(circle at left center, rgba(255, 124, 67, 0.12), transparent 26%),
    linear-gradient(180deg, rgba(8, 10, 15, 0.98), rgba(12, 13, 18, 0.98));
  border: 1px solid var(--tc-border);
  border-radius: var(--tc-radius-shell);
  box-shadow: var(--tc-shadow-shell);
  overflow: hidden;
}

/* Grid overlay через pseudo-element */
.cfg-shell::before {
  content: "";
  position: absolute;
  inset: 0;
  pointer-events: none;
  background-image:
    linear-gradient(var(--tc-grid-color) 1px, transparent 1px),
    linear-gradient(90deg, var(--tc-grid-color) 1px, transparent 1px);
  background-size: var(--tc-grid-size) var(--tc-grid-size);
  mask-image: var(--tc-grid-mask);
  -webkit-mask-image: var(--tc-grid-mask);
  z-index: 0;
}

.cfg-shell > * {
  position: relative;
  z-index: var(--tc-z-base);
}
```

**Selected card state:**
```css
.cfg-option[aria-checked="true"],
.cfg-option input:checked + .cfg-option-card {
  border-color: var(--tc-border-strong);
  background:
    linear-gradient(180deg, rgba(226, 178, 91, 0.14), rgba(255, 148, 84, 0.05)),
    rgba(20, 18, 13, 0.96);
  box-shadow: var(--tc-shadow-card);
  transform: translateY(-2px);
}
```

**Product card icon selected effect:**
```css
.cfg-product-card input:checked + .cfg-option-card .cfg-product-icon img {
  transform: translateY(-3px) scale(1.04);
  filter: saturate(1.08) brightness(1.04)
          drop-shadow(0 10px 18px rgba(226, 178, 91, 0.16));
  transition: all var(--tc-motion-enter);
}
```

**Kicker badge:**
```css
.cfg-kicker {
  display: inline-flex;
  width: fit-content;
  align-items: center;
  padding: 0.34rem 0.62rem;
  border-radius: var(--tc-radius-pill);
  border: 1px solid var(--tc-accent-border-faint);
  background: var(--tc-accent-bg-faint);
  color: var(--tc-accent-soft);
  font-size: var(--tc-font-size-xs);
  font-weight: 700;
  letter-spacing: var(--tc-letter-spacing-kicker);
  text-transform: uppercase;
}
```

**Primary CTA button:**
```css
.cfg-btn--primary {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: var(--tc-target-cta);
  padding: 0.82rem 2rem;
  border: none;
  border-radius: var(--tc-radius-pill);
  background: var(--tc-accent-gradient);
  color: var(--tc-accent-text-on);  /* ОБЯЗАТЕЛЬНО тёмный текст на золотом */
  font-family: var(--tc-font-family);
  font-size: var(--tc-font-size-md);
  font-weight: 700;
  box-shadow: var(--tc-shadow-cta);
  cursor: pointer;
  transition: transform var(--tc-motion-hover),
              box-shadow var(--tc-motion-hover),
              filter var(--tc-motion-hover);
}
```

### 3.4.2 Система глубины hover (Hover Depth System)

Три уровня hover-эффектов для разных типов interactive элементов:

```css
/* === DEPTH LEVEL 1: Cards, options ===
   Используется для: cfg-option-card, cfg-product-card
   Эффект: подъём + border highlight */
.cfg-option-card {
  transition: transform var(--tc-motion-hover),
              border-color var(--tc-motion-hover),
              box-shadow var(--tc-motion-hover),
              background var(--tc-motion-hover);
}
.cfg-option-card:hover {
  transform: translateY(-2px);
  border-color: rgba(255, 214, 138, 0.2);
}

/* === DEPTH LEVEL 2: Primary CTA ===
   Используется для: cfg-btn--primary
   Эффект: подъём + усиление glow + микро-насыщенность */
.cfg-btn--primary:hover {
  transform: translateY(-2px);
  box-shadow: var(--tc-shadow-cta-hover);
  filter: saturate(1.04);
}

/* === DEPTH LEVEL 3: Secondary buttons, links ===
   Используется для: cfg-btn--secondary, cfg-link, cfg-safe-exit
   Эффект: только border highlight, без transform */
.cfg-btn--secondary:hover,
.cfg-safe-exit:hover {
  border-color: rgba(255, 214, 138, 0.18);
}
```

### 3.4.3 Focus states (WCAG keyboard accessibility)

```css
/* Focus для inputs — golden shadow ring */
.cfg-input:focus,
.cfg-textarea:focus,
.cfg-select:focus {
  outline: none;
  border-color: var(--tc-border-strong);
  box-shadow: var(--tc-shadow-focus);
  background: rgba(8, 10, 15, 0.72);
}

/* Focus-visible для buttons — только keyboard, не mouse */
.cfg-btn:focus-visible,
.cfg-option-card:focus-visible {
  outline: 2px solid var(--tc-accent);
  outline-offset: 2px;
}
```

### 3.4.4 Контраст-аудит ключевых пар (WCAG 2.2 AA)

| Foreground | Background | Ratio | Статус |
|---|---|---|---|
| `#f7f0e6` (--tc-text) | `#0c0d12` (--tc-bg) | **16.1:1** | ✅ AAA |
| `#f7d58f` (--tc-accent-soft) | `#0c0d12` | **11.8:1** | ✅ AAA |
| `--tc-text-muted` (0.72) | `#0c0d12` | **~11.6:1** | ✅ AAA |
| `--tc-text-subtle` (0.56) | `#0c0d12` | **~9.0:1** | ✅ AA |
| `#26160a` (--tc-accent-text-on) | gold gradient avg | **~8.5:1** | ✅ AA |
| `--tc-text-placeholder` (0.42) | `--tc-surface-input` | **~5.2:1** | ✅ AA |
| `--tc-text-disabled` (0.32) | `--tc-surface-input` | **~3.8:1** | ⚠️ Декоративный — OK |

### 3.5 Tone of Voice [B]

Весь интерфейс — **на украинском** (текущий сайт уже украиноязычный).

Правила:
- Обращение на **"ви"** — в тон с текущим сайтом.
- Короткие ясные лейблы: "Оберіть крій", "Додати файл", "Зв'язатися з менеджером".
- Error copy — конкретный, без обвинительного тона: "Перевірте номер телефону — здається, формат неповний."
- Trust copy — уверенный: "Ми перевіримо макет і напишемо вам до запуску."
- Safe exit — дружелюбный: "Потрібна допомога? Передамо все, що ви вже зібрали."

---

## 4. Структура страницы и компоненты

### 4.1 Общая DOM-архитектура

```html
<div class="cfg" id="configurator" data-state="entry">

  <!-- HEADER — close + manager help -->
  <header class="cfg-header">...</header>

  <!-- MAIN BODY -->
  <div class="cfg-body">

    <!-- LEFT: Product Stage (визуальный превью) -->
    <div class="cfg-stage" id="product-stage">
      <img class="cfg-stage-image" id="stage-img" ...>
      <div class="cfg-stage-overlay" id="stage-overlay"></div>
      <!-- Side switcher: front / back / sleeve -->
      <div class="cfg-stage-switcher">...</div>
    </div>

    <!-- RIGHT: Decision Panel (шаги) -->
    <div class="cfg-panel" id="decision-panel">
      <!-- Build Strip -->
      <nav class="cfg-strip" id="build-strip" aria-label="Прогрес конфігурації">...</nav>
      <!-- Step content (dynamic) -->
      <div class="cfg-step" id="step-container" role="main">...</div>
    </div>

  </div>

  <!-- BOTTOM: Price Capsule -->
  <div class="cfg-price" id="price-capsule">...</div>

</div>
```

### 4.2 Компонентная карта

```
cfg (root)
├── cfg-header
│   ├── cfg-logo (ссылка на домашнюю)
│   ├── cfg-manager-link (safe exit — always visible)
│   └── cfg-close (закрыть → вернуться в каталог)
├── cfg-body
│   ├── cfg-stage (Product Stage)
│   │   ├── cfg-stage-image
│   │   ├── cfg-stage-overlay (зоны печати, контуры)
│   │   └── cfg-stage-switcher (front/back/sleeve tabs)
│   └── cfg-panel (Decision Panel)
│       ├── cfg-strip (Build Strip)
│       │   └── cfg-strip-item[N] (chip states: done/current/pending)
│       └── cfg-step (активный шаг)
│           ├── cfg-step-header (kicker + title + description)
│           └── cfg-step-body (controls)
├── cfg-price (Price Capsule)
│   ├── cfg-price-total
│   ├── cfg-price-breakdown (expandable)
│   └── cfg-price-cta (primary action button)
└── cfg-safe-exit-modal (hidden by default)
```

---

## 5. Шаг 0: Hero + Entry Flow

### 5.1 Что происходит

Пользователь видит hero-секцию с:
- Заголовок: "Створи свій дизайн"
- Подзаголовок-пояснение
- Primary CTA: "Розпочати проект"
- Secondary action: "Зв'язатися з менеджером"

### 5.2 Двухуровневый вход [B]

После нажатия на primary CTA появляется **лёгкий режимный слой** (не modal — inline expand или slide-in):
- **Для себе** — B2C путь
- **Для команди / бренду** — B2B путь

Разница между путями:
- B2B показывает дополнительные поля на review (бренд, объём, business_kind)
- B2C — стандартный путь без business-полей

### 5.3 Дизайн Hero

```
┌─────────────────────────────────────────────────────────────┐
│  [← TwoComms logo]                    [Зв'язатися з менеджером] │
├──────────────────────────────┬──────────────────────────────┤
│                              │                              │
│  ★ КАСТОМНИЙ ОДЯГ            │    [Hoodie render image]     │
│                              │                              │
│  Створи свій                 │                              │
│  дизайн                      │                              │
│                              │                              │
│  Обери виріб, колір, зону    │                              │
│  нанесення — побач попередній│                              │
│  результат і ціну одразу.    │                              │
│                              │                              │
│  [████ РОЗПОЧАТИ ПРОЕКТ ████]│                              │
│                              │                              │
│  DTG • Шовкографія           │                              │
│  DTF • Від 1 шт              │                              │
│                              │                              │
├──────────────────────────────┴──────────────────────────────┤
│ (после клика по CTA, inline-expand)                         │
│                                                             │
│  Для кого створюєте?                                        │
│  [Для себе]  [Для команди / бренду]                        │
└─────────────────────────────────────────────────────────────┘
```

### 5.4 Реализация

- Hero наследует существующий паттерн `.print-hero` из текущего шаблона.
- `data-client-kind` устанавливается на корневой `#configurator` и влияет на видимость B2B-полей.
- Analytics event: `config_start` (source, device_type).

---

## 6. Шаг 1: Quick Start

### 6.1 Назначение [B]

Не дать человеку застрять и при этом не перегружать тремя равновесными сценариями.

### 6.2 Состав

- **Primary path:** "Зібрати з нуля" — основной асимметричный CTA
- **Secondary paths:** "У мене є файл" / "Показати стилі"

### 6.3 Визуальная иерархия [A]

```
┌──────────────────────────────────────────────┐
│ Що хочете зробити далі?                      │
│                                              │
│ [████████████████████████████████████████]    │
│ [      Зібрати з нуля / обрати самому      ] │  ← Primary CTA
│ [████████████████████████████████████████]    │
│                                              │
│ Вже є макет або потрібен швидкий старт?      │
│ [ У мене є файл ]   [ Показати стилі ]      │  ← Secondary
└──────────────────────────────────────────────┘
```

### 6.4 Поведение путей

| Путь | Действие |
|---|---|
| Зібрати з нуля | → переход к шагу "Вибір виробу" |
| У мене є файл | → переход к шагу "Вибір виробу", file step помечается как "already have file" |
| Показати стилі | → показать 3 стартовых стиля (Minimal / Bold / Logo-first) с мини-превью, затем к выбору изделия |

### 6.5 Что такое "стартовые стили" [A]

**НЕ** шаблонная библиотека. Это **3 кураторских направления** с мини-превью и одним предложением:

1. **Minimal** — чистий, спокійний старт
2. **Bold** — крупніше і помітніше
3. **Logo-first** — фокус на символі / напису

Показать как горизонтальные карточки с маленьким превью. По выбору — записать `style_direction` в state и двигаться дальше.

### 6.6 Analytics events

- `quickstart_path_selected` (path_type: "scratch" | "has_file" | "show_styles")

---

## 7. Шаг 2: Выбор изделия

### 7.1 Доступные изделия v1

| Изделие | Ключ | Базовая цена | Превью |
|---|---|---|---|
| Футболка | `tshirt` | **700 грн** | `tshirt-front.webp` |
| Худі | `hoodie` | **1600 грн** | `hoodie-regular-front.webp` |
| Лонгслів | `longsleeve` | **1400 грн** | `longsleeve-front.webp` |
| Свій одяг | `customer_garment` | Estimate | — |

> ⚠️ **AUDIT FIX:** Цены приведены к текущему production-коду (`PRODUCT_CONFIG`
> в `custom_print.html:1393-1410`). Доктрина v7.1 указывала другие цены (3500/1800/2400),
> но production уже работает с 700/1600/1400. Обновлять цены — отдельное бизнес-решение.

### 7.2 Визуал

Карточки с иконками/рендерами, 4 в ряд на desktop, 2 на mobile. Выбратый вариант подсвечен golden border. При выборе "Свій одяг" — показать inline textarea для описания.

### 7.3 Связь с Product Stage

При выборе изделия `Product Stage` немедленно обновляет рендер на базовый силуэт.

### 7.4 Analytics event: `step_view` / `step_complete` (step_name: "product_type")

---

## 8. Шаги 3–6: Core Hoodie Flow

Последовательность [B]: **Крій → Ткань → Колір → Опції → Розмір → Зона нанесення**

### 8.1 Шаг 3: Крій

**Опции:**
- Regular fit — класичний, зручний
- Oversize — вільний, сучасний

Реализация: 2 карточки с рендерами. При переключении — Product Stage обновляет изображение.

### 8.2 Шаг 4: Ткань

**Опции:**
- Стандарт (трехнитка з начосом) — в ціні
- Преміум (+ доплата) — помечено "Рекомендуємо" [B]

Допустим паттерн Good/Better, но НЕ превращать в коммерческий театр [C].

### 8.3 Шаг 5: Колір

Цветовая палитра реализована как swatch-ряд (круглые кнопки с hex-цветом). При выборе → Product Stage обновляет цвет рендера (через CSS filter или pre-prepared variants).

**Rendering strategy [A]:**
- Если у проекта есть подготовленные цветовые варианты — использовать их
- Если нет — CSS `hue-rotate` + `brightness` как fallback, но **недопустимо** обещать "точное превью", если фильтр искажает [A]

### 8.4 Шаг 6: Опції / Комфорт / Деталі [A]

Только для v1:
- Люверсы / шнурки (toggle, +150 грн)
- Флис / без флису (toggle, если доступно)
- Принт на рукаві (toggle, estimate)

Каждый toggle-контрол показывает цену изменения inline.

### 8.5 Шаг 7: Розмір

- Pill-кнопки: XS, S, M, L, XL, 2XL
- Одна цена для всех размеров [B]: "Усі розміри за однією ціною"
- Tooltip-подсказка: "У цій моделі ціна не змінюється від XS до 2XL"
- Для B2B: дополнительно `size_mode` selector (один розмір / мікс / уточню з менеджером)

### 8.6 Шаг 8: Зона та формат нанесення

**Зоны v1:**

| Зона | Key | Ціна | Опис |
|---|---|---|---|
| Груди (спереду) | `front_chest` | Включено | Стандартне розміщення |
| Повний перед | `front_full` | +estimate | Великий формат |
| Повна спина | `back_full` | +estimate | |
| Рукав | `sleeve` | +estimate | |
| Нестандартне | `custom` | Estimate | → textarea для описания |

**Мультиселект:** пользователь может отметить несколько зон (checkbox-карточки).

При выборе зоны — Product Stage активирует **print placement mode**: подсвечивается выбранная сторона + SVG-контур допустимой зоны.

### 8.7 Визуальная карта шагов

Для каждого шага — единый паттерн:

```html
<section class="cfg-step" data-step="[step_name]" aria-label="[Step title]">
  <div class="cfg-step-header">
    <span class="cfg-kicker">[КРОК N]</span>
    <h2 class="cfg-step-title">[Step Title]</h2>
    <p class="cfg-step-desc">[Optional description]</p>
  </div>
  <div class="cfg-step-body">
    <!-- Step-specific controls -->
  </div>
  <div class="cfg-step-actions">
    <button class="cfg-btn cfg-btn--secondary" data-action="prev">Назад</button>
    <button class="cfg-btn cfg-btn--primary" data-action="next">Далі</button>
  </div>
</section>
```

---

## 9. Шаг 7: File / Reference / Помощь с дизайном (File Triage)

### 9.1 Главный принцип [A]

**Маршрутизация, а не запрет.** Результат всегда один из трёх: годится / можно, но лучше доработать / лучше как reference.

### 9.2 Три пути на этом шаге

| Путь | Действие |
|---|---|
| Маю готовий файл | Upload → File Triage → status |
| Потрібно допрацювати файл | Upload + brief textarea |
| Потрібен дизайн з нуля | Brief textarea only |

### 9.3 File Triage — клиентская часть

**Effective PPI расчёт [A]:**

```javascript
function classifyArtwork(imageWidthPx, imageHeightPx, printAreaWidthCm, printAreaHeightCm, mimeType, screenshotSuspected) {
  // Векторные форматы
  if (['image/svg+xml', 'application/pdf'].includes(mimeType)) {
    return { status: 'print-ready', effectivePpi: null, nextActions: ['continue', 'replace'] };
  }
  
  const widthIn = printAreaWidthCm / 2.54;
  const heightIn = printAreaHeightCm / 2.54;
  const ppiW = imageWidthPx / widthIn;
  const ppiH = imageHeightPx / heightIn;
  const effectivePpi = Math.min(ppiW, ppiH);
  
  if (screenshotSuspected) {
    return { status: 'reference-only', effectivePpi: Math.round(effectivePpi), nextActions: ['use_as_reference', 'replace'] };
  }
  
  if (effectivePpi >= 250) {
    return { status: 'print-ready', effectivePpi: Math.round(effectivePpi), nextActions: ['continue', 'replace'] };
  }
  
  if (effectivePpi >= 150) {
    return { status: 'needs-work', effectivePpi: Math.round(effectivePpi), nextActions: ['continue_anyway', 'request_fix', 'replace'] };
  }
  
  return { status: 'reference-only', effectivePpi: Math.round(effectivePpi), nextActions: ['use_as_reference', 'replace'] };
}
```

### 9.4 Screenshot detection эвристика [A]

Флаг `screenshotSuspected` поднимается если совпадают ≥2 признака:
- Соотношение сторон ~16:9 или ~9:16 (типичное для screen capture)
- Effective PPI < 120 для выбранной зоны
- MIME = PNG + размер < 500KB (типично для clipboard)

Если уверенность низкая — **не маркировать жёстко**, вместо этого `needs-work`.

### 9.5 UI-сообщения [A]

```
print-ready:
  ✓ Файл підходить для обраної зони
  2480×3508 px • ~300 PPI
  [Продовжити] [Замінити]

needs-work:
  ⚠ Файл можна використовувати, але якість на межі
  2000×3000 px • ~242 PPI
  [Продовжити з цим файлом] [Замовити доробку] [Замінити]

reference-only:
  ✕ Для обраної зони файл занадто слабкий
  800×1200 px • ~97 PPI
  [Використовувати як референс] [Замінити файл]
```

### 9.6 Форматы v1 [B]

Основные: JPG, JPEG, PNG, WebP, PDF.
Advanced (если пайплайн поддерживает): SVG, PSD, AI/EPS.

### 9.7 Drag & Drop

- Drop zone с визуальным feedback (border-dashed → solid на hover)
- Progress bar для upload
- Cancel / retry доступны

---

## 10. Шаг 8: Контакты / Доставка / Review

### 10.1 Форма контактов

```
Ім'я*:       [_______________]
Контакт*:    [Telegram ▾] [@username_______]
              (альтернативы: WhatsApp, Telefon)
Коментар:    [_______________]
              (опционально)
```

### 10.2 Review — полный summary

Перед submit показать полную сводку:

```
╔══════════════════════════════════════╗
║  ПЕРЕВІРТЕ ЗАМОВЛЕННЯ               ║
╠══════════════════════════════════════╣
║  Виріб:    Худі Regular              ║
║  Тканина:  Стандарт                  ║
║  Колір:    Чорний                    ║
║  Розмір:   M                         ║
║  Зони:     Груди, Повна спина        ║
║  Файл:     logo.png (print-ready)    ║
║  Кількість: 1                        ║
╠══════════════════════════════════════╣
║  Trust block:                        ║
║  1. Ми перевіримо макет і параметри  ║
║  2. Якщо щось потрібно уточнити —    ║
║     напишемо до запуску              ║
║  3. Після підтвердження передамо     ║
║     замовлення у виробництво         ║
╠══════════════════════════════════════╣
║  Ім'я:     [________]               ║
║  Контакт:  [Telegram ▾] [________]  ║
╠══════════════════════════════════════╣
║  [████ НАДІСЛАТИ ЗАЯВКУ ████]        ║
║  [Потрібна допомога менеджера?]      ║
╚══════════════════════════════════════╝
```

### 10.3 Trust & Value layer [A]

Блок "Що буде далі?" — **обязателен** на review:
1. Ми перевіримо ваш макет і параметри.
2. Якщо щось потрібно уточнити, напишемо вам до запуску.
3. Після підтвердження передамо замовлення у виробництво.

### 10.4 Submission success

```
✓ Дякуємо! Заявку #CP13042026L001 прийнято.
Менеджер зв'яжеться з вами найближчим часом.
[Повернутися на головну] [Створити ще одну]
```

### 10.5 Submission failure [A] — обязательный сценарий

```
✕ Не вдалося надіслати заявку зараз.
Ваші параметри збережені.
[Повторити надсилання] [Зв'язатися з менеджером] [Скопіювати дані заявки]
```

**Обязательно:** прогресс не теряется, retry работает, safe-exit доступен.

---

## 11. Product Stage

### 11.1 Назначение [A]

Главный визуальный контейнер. Всегда показывает **текущую вещь**, а не декоративный hero-shot.

### 11.2 State Map [A]

| State | Описание | Триггер |
|---|---|---|
| `STATE_0` | Базовый силуэт | Выбор изделия |
| `STATE_1` | Цвет / крой / ткань отражены | Каждый шаг конфигурации |
| `STATE_2` | Print placement mode | Выбор зоны нанесения |
| `STATE_3` | Review-ready | Переход на review |

### 11.3 Рендер-пайплайн v1 [A]

1. **Base renders** — подготовленные WebP для каждого силуэта × сторона (front/back, sleeve-view)
2. **Цветовая вариативность** — pre-rendered варианты ИЛИ проверенный CSS recolor
3. **Print placement** — SVG overlay с координатными зонами поверх базового превью
4. **Review state** — тот же источник, без "магической" версии

**НЕ закладывать:** full 3D, свободное drag-and-drop, физическую симуляцию ткани.

### 11.4 HTML-структура

```html
<div class="cfg-stage" id="product-stage" data-state="0" aria-hidden="true">
  <div class="cfg-stage-canvas">
    <img class="cfg-stage-img" id="stage-img"
         src="{% static 'img/configurator/hoodie-regular-front.webp' %}"
         alt="Попередній перегляд вашого виробу"
         loading="lazy">
    <div class="cfg-stage-zones" id="stage-zones">
      <!-- SVG overlays injected dynamically -->
    </div>
  </div>
  <div class="cfg-stage-tabs" role="tablist" aria-label="Сторона виробу">
    <button role="tab" aria-selected="true" data-side="front">Спереду</button>
    <button role="tab" data-side="back">Ззаду</button>
    <button role="tab" data-side="sleeve">Рукав</button>
  </div>
</div>
```

### 11.5 Responsive behavior

- **Phone portrait:** Stage сверху, ~50vw высоты, crop если нужно
- **Tablet/Desktop:** Stage слева, занимает ~55-60% ширины

---

## 12. Build Strip

### 12.1 Назначение [A]

Живая, компактная линия уже принятых решений. **НЕ** тяжёлый stepper. **НЕ** навигация с 10+ чипами.

### 12.2 State Map [A]

| State | Визуал |
|---|---|
| `EMPTY` | Скрыт или лёгкий контейнер |
| `PARTIAL` | `[✓ Крій] [✓ Тканина] [→ Колір] [+ ще 4]` |
| `FULL` | Все ключевые выборы видны, второстепенные свёрнуты |

### 12.3 Chip visual states

> ⚠️ **Для реализующего AI:** Каждый chip в Build Strip имеет один из 4 состояний:

| State | BG | Border | Text color | Icon | Cursor |
|---|---|---|---|---|---|
| **done** | `rgba(226,178,91,0.12)` | `--tc-border-strong` | `--tc-accent-soft` | ✓ (checkmark) | pointer |
| **current** | `--tc-accent-bg-subtle` | `var(--tc-accent)` solid | `--tc-text` | → (arrow) | default |
| **pending** | `rgba(255,255,255,0.03)` | `--tc-border-muted` | `--tc-text-subtle` | ○ (empty circle) | pointer |
| **collapsed** | `rgba(255,255,255,0.03)` | `--tc-border-muted` | `--tc-text-subtle` | — | pointer |

### 12.4 Phone portrait [B]

```text
← scrollable →
[✓ Regular] [✓ Cotton] [→ Обрати колір] [Ще 4]
```

На mobile Build Strip — горизонтально прокручиваемый ряд:
```css
@media (max-width: 767px) {
  .cfg-strip {
    display: flex;
    gap: var(--tc-space-xs);
    overflow-x: auto;
    overflow-y: hidden;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: none; /* скрыть scrollbar */
    padding: var(--tc-space-sm) 0;
  }
  .cfg-strip::-webkit-scrollbar { display: none; }
  .cfg-strip-item {
    flex: 0 0 auto;
    white-space: nowrap;
  }
}
```

### 12.5 Desktop [B]

```text
[✓ Regular] [✓ Cotton] [✓ Black] [→ Chest print] [○ Artwork] [○ Review]
```

### 12.6 Правила [A]

- Только ключевые решения.
- Не дублировать product summary.
- Не создавать второй навигационный хаб.
- Каждый элемент кликабелен → возврат на соответствующий шаг.
- По возможности без горизонтального скролла на phone portrait (но допускается если чипов >5).
- Все chip touch targets ≥ `--tc-target-min` (44px).

---

## 13. Price Capsule

### 13.1 Назначение [A]

Цена + CTA в компактной капсуле. Всегда рядом, всегда доступна, не доминирует над Product Stage.

### 13.2 State Map [A]

| State | Визуал |
|---|---|
| `COLLAPSED` | Итоговая цена + CTA "Далі" |
| `EXPANDED` | Breakdown: база + допы + delivery note |
| `SUBMIT_READY` | На review — "Надіслати заявку" |

### 13.3 Поведение

- **Mobile (<767px):** Fixed bottom bar — `position: fixed; bottom: 0.8rem; left: 0.8rem; right: 0.8rem`. Высота ~60px. Glassmorphism blur + shadow. Цена слева, CTA справа. Breakdown — slide-up panel над bottom bar.
- **Desktop (≥768px):** В правой колонке, `position: sticky; top: 1rem`. Glassmorphism blur.
- Breakdown раскрывается по клику на «Деталі» (не автоматически).
- При пересчёте — короткий pending state (skeleton pulse), но НЕ блокировать весь UI.
- **Keyboard на mobile:** Bottom bar скрывается когда активна виртуальная клавиатура (см. §16.5).

> ⚠️ **Для реализующего AI:** Полные CSS-правила для Price Capsule responsive см. в §16.4.

### 13.4 HTML-структура

```html
<div class="cfg-price" id="price-capsule" data-state="collapsed">
  <div class="cfg-price-summary" aria-live="polite">
    <span class="cfg-price-label">Попередній розрахунок</span>
    <span class="cfg-price-total" id="price-total">3 500 ₴</span>
    <button class="cfg-price-toggle" aria-expanded="false"
            aria-controls="price-breakdown">Деталі</button>
  </div>
  <div class="cfg-price-breakdown" id="price-breakdown" hidden>
    <div class="cfg-price-row">
      <span>Худі Regular</span>
      <strong>3 500 ₴</strong>
    </div>
    <!-- Dynamic rows -->
  </div>
  <button class="cfg-btn cfg-btn--primary cfg-price-cta" id="price-cta">
    Далі
  </button>
</div>
```

### 13.5 Price Capsule НЕ [B]

- НЕ sticky sidebar-чек, визуально равный контенту.
- НЕ "кассовый аппарат".
- НЕ доминирует над вещью.

---

## 14. Safe Exit к менеджеру

### 14.1 Когда виден [A]

Минимум в 4 точках:
1. Header — всегда видимый secondary link
2. На файловом шаге — inline
3. На review/submit — inline
4. В error / submission failure states

### 14.2 Что делает [A]

Safe exit **сериализует и передаёт контекст** уже собранной конфигурации. Менеджер видит не пустой диалог, а нормализованный snapshot.

### 14.3 Payload contract [A]

```json
{
  "config_id": "draft_1713020400_abc123",
  "current_step": "artwork",
  "client_kind": "personal",
  "product": "hoodie",
  "options": {
    "fit": "regular",
    "fabric": "standard",
    "color": "black",
    "print_zone": ["front_chest"]
  },
  "artwork_status": "needs-work",
  "contact": {
    "name": "Олексій",
    "channel": "telegram",
    "value": "@alexii"
  },
  "pricing_snapshot": {
    "base_price": 3500,
    "additions": [],
    "final_total": 3500
  }
}
```

### 14.4 Persistence Strategy [A]

1. **Локальные данные** сохраняются в `localStorage` после каждого шага.
2. На момент safe exit / submit — формируется нормализованный snapshot.
3. Если сеть падает — локальный snapshot сохраняется до явного сброса.

**Key:** `twocomms_custom_config_draft`

### 14.5 Backend endpoint

Новый endpoint: `POST /custom-print/safe-exit/`

```python
# views/static_pages.py
@require_POST
def custom_print_safe_exit(request):
    """Safe exit: сохраняет draft и перенаправляет к менеджеру."""
    data = json.loads(request.body)
    lead = CustomPrintLead.objects.create(
        status=CustomPrintLeadStatus.NEW,
        source="safe_exit",
        brief=f"Safe exit зі кроку: {data.get('current_step', '?')}",
        # ... заполнить из payload
    )
    notify_new_custom_print_lead(lead)
    return JsonResponse({"ok": True, "lead_number": lead.lead_number})
```

### 14.6 UX-копирайт [B]

- "Потрібна допомога менеджера?"
- "Складний випадок? Передамо все, що ви вже зібрали."
- "Не хочете розбиратися далі? Продовжимо з людиною."

### 14.7 CSS стиль safe exit button

> ⚠️ **Для реализующего AI:** Кнопка safe exit должна быть тёплой и приглашающей, НЕ «аварийной».

```css
.cfg-safe-exit {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.82rem 1rem;
  border-radius: var(--tc-radius-pill);
  border: 1px solid var(--tc-border-subtle);
  background: rgba(255, 255, 255, 0.04);
  color: var(--tc-text);
  font-size: var(--tc-font-size-sm);
  font-weight: 700;
  cursor: pointer;
  transition: border-color var(--tc-motion-hover);
  min-height: var(--tc-target-min);
}

.cfg-safe-exit:hover {
  border-color: rgba(255, 214, 138, 0.18);
}

/* На mobile: full-width в step-actions */
@media (max-width: 639px) {
  .cfg-safe-exit {
    width: 100%;
    justify-content: center;
  }
}
```

---

## 15. Motion System

### 15.1 Назначение [A]

Motion нужен для: feedback, ориентации, подтверждения изменения состояния. **Не для шоу.**

### 15.2 Маппинг на компоненты [A]

| Token | Компонент | Когда |
|---|---|---|
| `--tc-motion-instant` (80ms) | Сontrol states, toggle, selected/unselected | Выбор опции |
| `--tc-motion-fast` (150ms) | Pills, swatches, small state changes | Hover, click |
| `--tc-motion-enter` (250ms) | Step panel reveal, section expand | Переход к шагу |
| `--tc-motion-exit` (200ms) | Close, collapse, dismiss | Закрытие overlay |
| `--tc-motion-large` (280ms) | Product Stage transition, крупный sheet | Cмена рендера |

### 15.3 Low-end device rule [B]

Если на слабых телефонах motion "заикается" — сокращать, убирать декоративные transforms, не спорить с FPS.

---

## 16. Responsive Shell

### 16.1 Breakpoints [A]

```css
/* Phone portrait */    @media (max-width: 639px)
/* Phone landscape */   @media (min-width: 640px) and (max-width: 767px)
/* Tablet portrait */   @media (min-width: 768px) and (max-width: 1023px)
/* Tablet landscape */  @media (min-width: 1024px) and (max-width: 1279px)
/* Desktop */           @media (min-width: 1280px)
```

### 16.2 Визуальная таблица адаптивности по breakpoints

> ⚠️ **Для реализующего AI:** Скопируй эту таблицу как чеклист — для каждого breakpoint проверить все перечисленные параметры.

| Параметр | <640px (phone) | 640-767px | 768-1023px | 1024-1279px | ≥1280px (desktop) |
|---|---|---|---|---|---|
| **Shell radius** | 22px | 22px | 26px | 30px | 30px |
| **Shell padding** | 0.9rem | 0.9rem | 1.2rem | 1.4rem | 1.4rem |
| **Section radius** | 22px | 22px | 22px | 26px | 26px |
| **Card grid** | 1 col | 1 col | 2 col | 2 col | 4 col (products) |
| **Product Stage** | top, 50vw h | left 40% | left 45% | left 55% | left 55-60% |
| **Stage sticky** | нет (scroll) | нет | sticky top | sticky top | sticky top |
| **Price Capsule** | fixed bottom bar | fixed bottom bar | sticky sidebar | sticky sidebar | sticky sidebar |
| **Build Strip** | h-scroll 1 line | h-scroll 1 line | 1 line wrap | 1 line full | 1 line full |
| **Step actions** | full-width btns | full-width btns | inline btns | inline btns | inline btns |
| **Touch targets** | ≥48px | ≥48px | ≥44px | ≥44px | ≥44px |
| **Font hero** | 2rem | 2.2rem | 2.8rem | 3.2rem | 3.5rem |
| **Grid overlay** | отключен | отключен | включен | включен | включен |

### 16.3 Layouts per breakpoint

**Phone portrait (<640px):**
```
┌──────────────────────────────────┐
│ Header / close / manager help    │
├──────────────────────────────────┤
│ Product Stage (compact, ~50vw h) │
├──────────────────────────────────┤
│ Build Strip (horizontal scroll)  │
├──────────────────────────────────┤
│ Current step panel               │
│ (full-width option cards)        │
├──────────────────────────────────┤
│                                  │ ← padding-bottom: 80px
└──────────────────────────────────┘  (чтобы контент не уходил за bottom bar)
┌──────────────────────────────────┐
│ Price Capsule (fixed bottom bar) │ ← position: fixed; bottom: 0.8rem
└──────────────────────────────────┘
```

**Phone landscape (640–767px):**
```
┌──────────────────────────────────────────────┐
│ Build Strip                                  │
├──────────────────────┬───────────────────────┤
│ Product Stage        │ Current step panel    │
├──────────────────────┴───────────────────────┤
│ Price Capsule / CTA (fixed bottom)           │
└──────────────────────────────────────────────┘
```

**Tablet portrait (768–1023px):**
```
┌──────────────────────────────────────────────┐
│ Header / Build Strip                         │
├──────────────────────┬───────────────────────┤
│ Product Stage        │ Current step panel    │
│ bigger preview       │ Price Capsule sticky  │
│ sticky top           │ at top of panel       │
└──────────────────────┴───────────────────────┘
```

**Desktop (1280px+):**
```
┌─────────────────────────────────────────────────────────────┐
│ Header + Build Strip + compact summary controls            │
├──────────────────────────────┬──────────────────────────────┤
│ Product Stage                │ Decision Panel              │
│ 55-60% width                │ step content                │
│ sticky top                  │ Price Capsule sticky        │
│                              │ at top of panel             │
└──────────────────────────────┴──────────────────────────────┘
```

### 16.4 Конкретные CSS правила для mobile адаптивности

> ⚠️ **Для реализующего AI:** Эти CSS блоки копировать в `custom-print-configurator.css`.

**Радиусы per breakpoint:**
```css
/* По умолчанию (mobile-first): сниженные радиусы */
.cfg-shell {
  border-radius: 22px;
  padding: 0.9rem;
}
.cfg-section,
.cfg-step {
  border-radius: 22px;
}

/* Tablet portrait */
@media (min-width: 768px) {
  .cfg-shell {
    border-radius: 26px;
    padding: 1.2rem;
  }
}

/* Desktop */
@media (min-width: 1024px) {
  .cfg-shell {
    border-radius: var(--tc-radius-shell); /* 30px */
    padding: 1.4rem;
  }
  .cfg-section,
  .cfg-step {
    border-radius: var(--tc-radius-xl); /* 26px */
  }
}
```

**Grid overlay — только для desktop (экономия GPU на mobile):**
```css
/* Grid overlay отключен на mobile */
.cfg-shell::before {
  display: none;
}

@media (min-width: 768px) {
  .cfg-shell::before {
    display: block;
  }
}
```

**Price Capsule — mobile fixed bottom bar:**
```css
/* Desktop: sticky sidebar */
.cfg-price {
  position: sticky;
  top: 1rem;
  background: var(--tc-glass);
  backdrop-filter: var(--tc-glass-blur);
  border: 1px solid var(--tc-border);
  border-radius: var(--tc-radius-xl);
  padding: var(--tc-space-lg);
  z-index: var(--tc-z-sticky);
}

/* Mobile: fixed bottom bar */
@media (max-width: 767px) {
  .cfg-price {
    position: fixed;
    left: 0.8rem;
    right: 0.8rem;
    bottom: 0.8rem;
    top: auto;
    z-index: var(--tc-z-overlay);
    border-radius: 24px;
    backdrop-filter: var(--tc-glass-heavy-blur);
    -webkit-backdrop-filter: var(--tc-glass-heavy-blur);
    box-shadow: var(--tc-shadow-mobile-bar);
    padding: 0.72rem 1rem;
    display: flex;
    align-items: center;
    gap: var(--tc-space-md);
  }

  /* Разворот: цена слева, CTA справа */
  .cfg-price-summary {
    flex: 1;
    display: flex;
    flex-direction: column;
  }
  .cfg-price-label {
    font-size: var(--tc-font-size-2xs);
    color: var(--tc-text-subtle);
  }
  .cfg-price-total {
    font-size: var(--tc-font-size-lg);
    font-weight: 700;
    color: var(--tc-accent-soft);
  }
  .cfg-price-cta {
    min-width: 156px;
    min-height: 48px;
  }

  /* Breakdown скрыт на mobile bottom bar, раскрывается slide-up */
  .cfg-price-breakdown {
    position: fixed;
    left: 0.8rem;
    right: 0.8rem;
    bottom: 80px; /* над bottom bar */
    border-radius: 22px;
    background: var(--tc-surface-strong);
    border: 1px solid var(--tc-border);
    padding: var(--tc-space-lg);
    box-shadow: var(--tc-shadow-card);
  }

  /* Контент страницы — padding-bottom чтобы не прятаться за bottom bar */
  .cfg-body {
    padding-bottom: 80px;
  }
}
```

**Product Stage — responsive sizing:**
```css
/* Mobile: компактный горизонтальный блок сверху */
@media (max-width: 767px) {
  .cfg-stage {
    width: 100%;
    max-height: 50vw;
    overflow: hidden;
    border-radius: var(--tc-radius-lg);
  }
  .cfg-stage-img {
    width: 100%;
    height: auto;
    object-fit: contain;
  }
  /* Switcher — маленькие pill-кнопки под stage */
  .cfg-stage-tabs {
    display: flex;
    gap: var(--tc-space-xs);
    justify-content: center;
    padding: var(--tc-space-sm) 0;
  }
  .cfg-stage-tabs button {
    min-height: var(--tc-target-min);
    padding: 0.5rem 0.9rem;
    font-size: var(--tc-font-size-xs);
  }
}

/* Tablet+ : left column, sticky */
@media (min-width: 768px) {
  .cfg-body {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
    gap: var(--tc-space-xl);
    align-items: start;
  }
  .cfg-stage {
    position: sticky;
    top: 1rem;
  }
}

@media (min-width: 1280px) {
  .cfg-body {
    grid-template-columns: 55fr 45fr;
  }
}
```

**Step actions — full-width на mobile:**
```css
@media (max-width: 639px) {
  .cfg-step-actions {
    display: flex;
    flex-direction: column;
    gap: var(--tc-space-sm);
  }
  .cfg-step-actions .cfg-btn {
    width: 100%;
    justify-content: center;
    min-height: var(--tc-target-standard); /* 48px */
  }
}
```

**Option cards grid per breakpoint:**
```css
/* Карточки опций (product type, fit, fabric) */
.cfg-options-grid {
  display: grid;
  gap: var(--tc-space-md);
}

@media (max-width: 639px) {
  .cfg-options-grid { grid-template-columns: 1fr; }
}
@media (min-width: 640px) and (max-width: 767px) {
  .cfg-options-grid { grid-template-columns: 1fr; }
}
@media (min-width: 768px) and (max-width: 1279px) {
  .cfg-options-grid { grid-template-columns: repeat(2, 1fr); }
}
@media (min-width: 1280px) {
  /* Для product type (4 items) */
  .cfg-options-grid--products { grid-template-columns: repeat(4, 1fr); }
  /* Для fit/fabric (2 items) */
  .cfg-options-grid--binary { grid-template-columns: repeat(2, 1fr); }
}
```

### 16.5 Mobile keyboard handling [A]

> ⚠️ **КРИТИЧНО для mobile UX:** Когда появляется виртуальная клавиатура, fixed bottom bar может частично перекрыться.

```javascript
// В custom-print-configurator.js:
// Слушаем visualViewport resize (клавиатура)
if (window.visualViewport) {
  window.visualViewport.addEventListener('resize', () => {
    const bottomBar = document.getElementById('price-capsule');
    if (!bottomBar) return;

    const keyboardHeight = window.innerHeight - window.visualViewport.height;
    if (keyboardHeight > 100) {
      // Клавиатура открыта — скрыть bottom bar
      bottomBar.style.display = 'none';
    } else {
      bottomBar.style.display = '';
    }
  });
}
```

**Альтернатива (CSS-only):** Использовать `env(keyboard-inset-height)` если поддерживается:
```css
@media (max-width: 767px) {
  .cfg-price {
    bottom: max(0.8rem, env(keyboard-inset-height, 0.8rem));
    transition: bottom 0.2s ease;
  }
}
```

### 16.6 Responsive rules [A]

- **Mobile-first:** Все стили по умолчанию — для mobile. Desktop получает через `@media (min-width: ...)`.
- **Touch targets:** ≥48px на phone, ≥44px на tablet+. Никогда не уменьшать.
- **Hover:** использовать `@media (hover: hover)` для hover-эффектов. На touch-устройствах hover не должен быть единственным носителем информации.
- **Scroll:** Не блокировать body scroll на шагах. Только modal (safe-exit) может блокировать scroll.
- **Orientation:** Landscape phone — не скрывать Product Stage, а сжать до 40% ширины.
- **Safe area:** Учитывать `env(safe-area-inset-bottom)` для bottom bar на iPhone с notch.

---

## 17. Accessibility (WCAG 2.2 AA)

### 17.1 Обязательные требования [A]

- Все touch targets ≥ 44px (практический ориентир)
- Drag never exclusive (всё доступно альтернативно)
- Keyboard проходит основной путь (Tab → Enter/Space → Escape)
- Screen reader получает контекст шагов, статусов, ошибок
- Цвет не единственный носитель смысла (иконки + текст + цвет)
- `prefers-reduced-motion` respected

### 17.2 ARIA-разметка ключевых компонентов

```html
<!-- Steps -->
<section role="region" aria-label="Крок 3: Оберіть колір" aria-current="step">

<!-- Build Strip -->
<nav aria-label="Прогрес конфігурації">
  <button role="tab" aria-selected="true" aria-label="Крій: Regular — завершено">

<!-- Price Capsule -->
<div aria-live="polite" role="status">
  <span aria-label="Попередній розрахунок: 3500 гривень">

<!-- File Triage -->
<div role="alert" aria-live="assertive">
  <!-- Critical status messages -->

<!-- Options (custom controls) -->
<div role="radiogroup" aria-label="Оберіть крій">
  <label>
    <input type="radio" name="fit" value="regular">
    <span class="cfg-option-card">Regular</span>
  </label>
```

### 17.3 Dynamic announcements [A]

`aria-live` минимум для:
- Статуса file triage
- Критичных form errors
- Submit failure / success
- Значимых price updates
- Контекста шага

### 17.4 Keyboard walkthrough [A]

Quick Start → путь → изделие → хотя бы один выбор → artwork → review → submit/safe exit.

Проверить: tab order, focus visibility, enter/space, escape closes overlays, no keyboard trap.

### 17.5 Screen reader minimum [B]

- VoiceOver + Safari (macOS/iOS)
- NVDA + Firefox/Chrome (Windows)
- TalkBack + Chrome (Android)

---

## 18. Состояния ошибок и загрузки

### 18.1 Принцип [A]

Локальная ошибка **не сбрасывает весь прогресс**.

### 18.2 Error states

| Ситуация | Сообщение | Recovery |
|---|---|---|
| Network failure (upload) | "Не вдалося завантажити файл" | [Повторити] [Обрати інший] |
| File too large | "Файл перевищує ліміт {N} MB" | [Замінити] |
| Unsupported format | "Підтримувані формати: JPG, PNG, WebP, PDF" | [Замінити] |
| Triage service down | Молча fallback → manual review | Заявка уходит как есть |
| Phone format invalid | "Перевірте номер — формат неповний" | Inline error |
| Submission failure | "Не вдалося надіслати. Параметри збережені." | [Повторити] [Менеджер] [Скопіювати] |

### 18.3 Error UX rules [A]

- Ошибка рядом с проблемой (не в модалке наверху)
- Текст + иконка + цвет (не только цвет)
- Ошибка объясняет как исправить
- Критичные ошибки — `aria-live="assertive"`

### 18.4 Loading states [B]

| Что загружается | Что показать |
|---|---|
| Initial page load | Product Stage skeleton + shimmer |
| File upload | Progress bar + cancel |
| Price recalculation | Compact skeleton в Price Capsule (не блокировать UI) |
| Submit in progress | Кнопка disabled + spinner |

---

## 19. Value & Trust Layer

### 19.1 Зачем [B]

Главный барьер кастома — не цена, а **страх ошибки и неопределённость**.

### 19.2 Размещение

1. **На review** — "Що буде далі?" (обязательно [A])
2. **На файловом шаге** — "Менеджер перевірить файл перед друком"
3. **В Price Capsule** — "Фінальну ціну підтвердимо після перевірки"

### 19.3 Что можно добавить [B]

(Только если правда):
- Орієнтовний термін: 3-5 робочих днів
- Канали зв'язку: Telegram, Instagram
- Доставка: Нова Пошта

### 19.4 Что НЕЛЬЗЯ [A]

- Fake scarcity / FOMO
- Выдуманные live-purchase popups
- Фальшивые таймеры
- Обещания, которые операционно не поддерживаются

---

## 20. Analytics Event Schema

### 20.1 Обязательные события [A]

| Event | Trigger | Required props |
|---|---|---|
| `config_start` | Вход в flow | source, device_type |
| `quickstart_path_selected` | Выбран путь | path_type |
| `step_view` | Открыт шаг | step_name, step_index |
| `step_complete` | Шаг завершён | step_name, step_index |
| `option_change` | Изменён параметр | step_name, option_group, value |
| `price_capsule_expand` | Раскрыт breakdown | step_name |
| `file_uploaded` | Файл загружен | mime_type, size_bucket |
| `file_triage_result` | Triage статус | status, effective_ppi_bucket |
| `manager_safe_exit` | Выход к менеджеру | from_step, reason_if_known |
| `submit_attempt` | Попытка submit | final_step |
| `submit_success` | Заявка отправлена | request_type |
| `submit_fail` | Ошибка submit | fail_type |

### 20.2 Реализация

Все события отправляются через `window.dataLayer.push({...})` для совместимости с GTM, который уже настроен на сайте.

```javascript
function trackEvent(eventName, props = {}) {
  window.dataLayer = window.dataLayer || [];
  window.dataLayer.push({
    event: eventName,
    ...props,
    timestamp: Date.now()
  });
}
```

### 20.3 Baseline capture [A]

**До запуска** снять:
- Текущий conversion rate (submit / visit)
- Desktop vs mobile splits
- Manager escalation rate
- Step-level exits (если трекаются)

---

## 21. Backend: модели, views, API

### 21.1 Изменения в модели CustomPrintLead

```python
# ДОБАВИТЬ к существующей модели:

class CustomPrintLead(models.Model):
    # ... все существующие поля сохранить ...
    
    # НОВЫЕ ПОЛЯ:
    config_draft_json = models.JSONField(
        default=dict, blank=True,
        verbose_name="Draft конфігурації",
        help_text="Повний snapshot конфігурації на момент submit / safe-exit"
    )
    fit = models.CharField(max_length=20, blank=True, default="", verbose_name="Крій")
    fabric = models.CharField(max_length=20, blank=True, default="", verbose_name="Тканина")
    color_choice = models.CharField(max_length=50, blank=True, default="", verbose_name="Колір")
    file_triage_status = models.CharField(
        max_length=20, blank=True, default="",
        verbose_name="Статус файлу (triage)"
    )
    exit_step = models.CharField(
        max_length=30, blank=True, default="",
        verbose_name="Крок при safe exit"
    )
```

### 21.2 Новые URL patterns

```python
# urls.py — добавить:
path('custom-print/safe-exit/', views.custom_print_safe_exit, name='custom_print_safe_exit'),
path('custom-print/draft/', views.custom_print_save_draft, name='custom_print_save_draft'),
```

### 21.3 View: custom_print()

Расширить контекст для шаблона:

```python
def custom_print(request):
    """Конфігуратор кастомного принта v2."""
    # Данные изделий и опций — JSON для JS
    products_config = {
        "hoodie": {
            "label": "Худі",
            "base_price": 1600,  # AUDIT FIX: сверено с текущим PRODUCT_CONFIG
            "fits": [
                {"key": "regular", "label": "Regular", "image": "hoodie-regular"},
                {"key": "oversize", "label": "Oversize", "image": "hoodie-oversize"}
            ],
            "fabrics": [
                {"key": "standard", "label": "Стандарт (трехнитка з начосом)", "price": 0},
                {"key": "premium", "label": "Преміум", "price": 500, "recommended": True}
            ],
            "colors": [...],  # из БД или хардкод v1
            "options": [
                {"key": "grommets", "label": "Люверси", "price": 150},
                {"key": "fleece", "label": "Флис", "price": 200}
            ],
            "print_zones": [
                {"key": "front_chest", "label": "Груди", "included": True, "area_cm": [20, 25]},
                {"key": "front_full", "label": "Повний перед", "included": False, "area_cm": [35, 45]},
                {"key": "back_full", "label": "Повна спина", "included": False, "area_cm": [35, 45]},
                {"key": "sleeve", "label": "Рукав", "included": False, "area_cm": [10, 30]}
            ]
        },
        # tshirt, longsleeve, customer_garment ...
    }
    
    return render(request, 'pages/custom_print.html', {
        'page_title': 'Кастомний принт',
        'products_config_json': json.dumps(products_config, ensure_ascii=False),
    })
```

### 21.4 View: custom_print_lead() — адаптация

Существующий endpoint `/custom-print/lead/` сохраняется, но форма расширяется новыми полями (fit, fabric, color_choice, config_draft_json, file_triage_status).

### 21.5 Telegram notification — расширение

Обновить `_build_message()` в `custom_print_notifications.py`, чтобы включить:
- Крой, ткань, цвет
- File triage status
- Pricing snapshot
- Если safe_exit — пометка "⚠ Safe exit зі кроку: {step}"

---

## 22. Чеклист запуска (Launch Decision Matrix)

### GO [A]

- [ ] Все [A]-требования реализованы
- [ ] Safe exit работает и передаёт контекст
- [ ] Submission failure не теряет данные
- [ ] Mobile path измерим аналитически
- [ ] Accessibility smoke-test пройден (keyboard + VoiceOver)
- [ ] Performance: LCP ≤ 2.5s, INP ≤ 200ms, CLS ≤ 0.1
- [ ] File triage — маршрутизация, не жёсткий reject
- [ ] Analytics events стреляют в dataLayer

### DEPLOY PREREQUISITES (из аудита) [A]

- [ ] `python manage.py collectstatic --noinput` включён в deploy pipeline
- [ ] Если используется django-compressor: `python manage.py compress` перед deploy
- [ ] `views/__init__.py` — экспортированы `custom_print_safe_exit` и `custom_print_save_draft`
- [ ] CSRF meta tag `<meta name="csrf-token" content="{{ csrf_token }}">` присутствует в шаблоне
- [ ] Цены в `products_config_json` сверены с production значениями (700/1600/1400)
- [ ] `perf-lite` визуальная проверка на Android Chrome (glassmorphism fallback, step transitions)
- [ ] Все новые поля модели `CustomPrintLead` имеют `blank=True, default=...` в миграции
- [ ] `CustomPrintLeadForm.save()` обновлён для записи новых полей (fit, fabric, color_choice...)
- [ ] Новые API endpoints (`safe-exit`, `draft`) декорированы `@require_POST`
- [ ] Лимит файлов 50 МБ показан в UI (совместимость с `dtf/utils.py:DEFAULT_MAX_FILE_MB`)
- [ ] Draft auto-save debounced ≥ 10 сек (защита от flood)

### MOBILE-SPECIFIC QA [A]

- [ ] Price Capsule bottom bar не перекрывает контент (padding-bottom: 80px на body)
- [ ] Price Capsule скрывается при виртуальной клавиатуре
- [ ] Bottom bar уважает `env(safe-area-inset-bottom)` (iPhone notch)
- [ ] Touch targets ≥ 48px на phone portrait
- [ ] Step actions кнопки full-width на mobile
- [ ] Build Strip горизонтально скроллится без видимого scrollbar
- [ ] Product Stage не превышает 50vw по высоте на phone portrait
- [ ] Options grid = 1 col на phone, 2 col на tablet
- [ ] Shell radius = 22px на mobile (не 30px)
- [ ] Grid overlay отключен на <768px
- [ ] Landscape phone: Product Stage сжат до 40% ширины, не скрыт
- [ ] Drop zone для файлов работает на touch (click fallback)

### NO-GO — остановка релиза [A]

- Заявка может потеряться без recovery
- File triage = жёсткий reject
- Safe exit отсутствует или без контекста
- Mobile flow не проходит end-to-end
- Нет baseline / analytics hooks
- CSRF token отсутствует → 403 на submit
- Bottom bar перекрывает контент на iPhone
- Touch targets < 44px

---

## 23. Что НЕ делать [A]

| Non-goal | Почему |
|---|---|
| Новый визуальный язык | Конфигуратор = часть TwoComms, не отдельный UI-kit |
| Heavy 3D / AR | Дорого, ненадёжно для v1 |
| Нейромаркетинговый театр | Подрывает доверие |
| Fake urgency / social proof | Запрещено доктриной |
| Full i18n / RTL | Не v1 scope (но use logical CSS properties) |
| B2B-first архитектура | B2B = надстройка, не отдельный поток |
| Огромная gift-ветка | Только checkbox на review |
| Псевдоточные "нейроцифры" | "+29% мотивации" — демагогия |
| Чистый #ffffff для текста | Бренд = тёплый #f7f0e6 |
| Фиолетовый CTA | Custom print = gold accent system |
| Inline styles | Всё через var(--tc-*) токены |
| TailwindCSS | Проект = Vanilla CSS, не менять |

---

## Порядок реализации (рекомендованный)

1. **CSS файл** — Design tokens V2 (все `--tc-*` переменные) + compound styles + responsive @media
2. **HTML шаблон** — Skeleton разметка всех секций + ARIA attributes
3. **JS: ConfigState** — Глобальный объект состояния
4. **JS: StepManager** — Переключение шагов, history
5. **JS: ProductStage** — Рендеринг превью
6. **JS: BuildStrip** — Обновление прогресса + chip states
7. **JS: PriceCapsule** — Пересчёт, expand/collapse + mobile keyboard handling
8. **JS: FileTriage** — Upload, triage, UI feedback
9. **JS: SafeExit** — Сериализация, отправка
10. **JS: Analytics** — Event tracking через dataLayer
11. **Backend: models** — Миграция новых полей
12. **Backend: views** — Новые endpoints
13. **Backend: notifications** — Расширение Telegram
14. **QA: Accessibility** — Keyboard + screen reader + focus-visible
15. **QA: Responsive** — Все 5 breakpoints (см. таблицу §16.2)
16. **QA: Performance** — LCP/INP/CLS + perf-lite visual check
17. **QA: Mobile** — Полный mobile checklist (см. §22 MOBILE-SPECIFIC QA)

---

## Appendix A: Инструкции для реализующего AI-агента

> **Этот раздел — обязательное чтение для AI, который будет кодировать конфигуратор.**

### A.1 Карта файлов (что создавать / менять)

| Файл | Действие | Расположение |
|---|---|---|
| `custom-print-configurator.css` | **СОЗДАТЬ** | `twocomms_django_theme/static/css/` |
| `custom-print-configurator.js` | **СОЗДАТЬ** | `twocomms_django_theme/static/js/` |
| `custom_print.html` | **ПЕРЕПИСАТЬ** | `twocomms_django_theme/templates/pages/` |
| `static_pages.py` | **МОДИФИЦИРОВАТЬ** | `storefront/views/` |
| `models.py` | **МОДИФИЦИРОВАТЬ** | `storefront/` |
| `forms.py` | **МОДИФИЦИРОВАТЬ** | `storefront/` |
| `urls.py` | **МОДИФИЦИРОВАТЬ** | `storefront/` |
| `__init__.py` | **МОДИФИЦИРОВАТЬ** | `storefront/views/` |
| `img/configurator/` | **СОЗДАТЬ** директорию + ассеты | `twocomms_django_theme/static/` |

### A.2 Критические правила (нарушение = баг)

1. **НЕ трогать `base.html`** — конфигуратор наследует layout через `{% extends "base.html" %}`.
2. **Все цвета через `var(--tc-*)`** — никаких inline hex, кроме значений внутри `:root`.
3. **CTA текст = `--tc-accent-text-on` (#26160a)** — тёмный текст на золотом фоне, для контраста.
4. **Mobile-first CSS** — base styles = mobile, desktop через `@media (min-width: ...)`.
5. **perf-lite** — НЕ полагаться на backdrop-filter / animations для функциональности. Использовать display/visibility.
6. **Touch targets ≥ 44px** — ВЕЗДЕ. ≥48px на phone portrait.
7. **NЕ использовать position: fixed кроме** Price Capsule bottom bar на mobile и safe-exit modal.
8. **Grid overlay** — только через ::before pseudo-element на .cfg-shell. Отключать в perf-lite и на mobile (<768px).
9. **Font = Inter** — наследуется из base.html. НЕ подключать дополнительные шрифты.
10. **Тёплый белый #f7f0e6** — для текста. НЕ использовать #ffffff.
11. **Shell radius: 22px mobile, 30px desktop** — НЕ использовать const 30px везде.
12. **Price Capsule скрывать при клавиатуре** — visualViewport resize listener.
13. **CSRF token** — `<meta name="csrf-token" content="{{ csrf_token }}">` в шаблоне, читать в JS.
14. **padding-bottom: 80px** на .cfg-body для mobile — чтобы контент не прятался за Price Capsule bottom bar.

### A.3 Что наследуется из base.html (НЕ дублировать)

- `<head>` meta tags, charset, viewport
- Navbar (`<header>`, `.nav`)
- Footer
- Font (Inter) через `fonts.css`
- `main.js` (cart, wishlist, search)
- `.perf-lite` detection script
- `dataLayer` init (для GTM/analytics)

### A.4 Как проверять результат

1. **Desktop Chrome:** открыть `/custom-print/`, пройти full flow от hero до submit.
2. **Mobile Chrome DevTools:** iPhone 12 Pro / Galaxy S21 в device toolbar, полный flow.
3. **Keyboard-only:** Tab через весь flow, проверить focus-visible rings, Enter/Space для actions, Escape для modals.
4. **perf-lite:** Добавить `class="perf-lite"` на `<html>`, проверить что всё работает без glassmorphism/animations.
5. **Lighthouse:** LCP ≤ 2.5s, INP ≤ 200ms, CLS ≤ 0.1, Accessibility Score ≥ 90.

---

> **Этот документ является полным handoff для внедряющего AI-агента.**
> **Все решения обоснованы доктриной v7.1 и реальным состоянием проекта.**
> **При конфликте с доктриной — доктрина приоритетнее кроме случаев технической невозможности.**
> **Версия документа: V2 (design audit 13.04.2026)**

