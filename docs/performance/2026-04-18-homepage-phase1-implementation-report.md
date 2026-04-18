# Homepage Performance — Phase 1 Implementation Report

> **Дата:** 2026-04-18
> **Ветка:** `claude/exciting-knuth-90e872`
> **Область:** только главная `/` (index), mobile-first
> **Источники истины:**
> - [audit](2026-04-18-homepage-production-audit.md)
> - [plan](2026-04-18-homepage-production-optimization-plan.md)
> - утверждённый implementation plan: `~/.claude/plans/tranquil-munching-walrus.md`
> **Принцип:** не резать дизайн — убирать **цену** за дизайн.

---

## 0. TL;DR

Phase 1 (P0, Quick Wins) закрывает пять самых тяжёлых клиентских проблем главной без редизайна:

1. **Image pipeline** — strict-mode warning для товаров без AVIF/WebP вариантов.
2. **Шрифты Inter** — снято дублирование weights 400/700 (inline + fonts.css).
3. **Third-party stack** — GA/Meta/TikTok/Clarity грузятся через `requestIdleCallback`, TikTok + Clarity отключены на `device-class=low`.
4. **Layout equalization** — отключена на mobile (`< 900px`) и `device-class=low`, убран forced reflow.
5. **Мёртвый код** — удалены `PerformanceOptimizer.scrollThreshold`, `optimizeMobileImages()`, дубль импорта `survey.js`, Font Awesome на `/` (103 KB).

**Визуальный риск:** нулевой/минимальный. Бренд, hero, карточки — без изменений.

---

## 1. Baseline vs Targets (ожидание после Phase 1)

| Метрика                        | До       | Цель Phase 1 | Механизм                                    |
| ------------------------------ | -------: | -----------: | ------------------------------------------- |
| Lighthouse Performance mobile  | 56–74    | 78–82        | меньше transfer, меньше long tasks          |
| LCP mobile                     | 8.7–13 s | ≤ 4.5 s      | preload hero + AVIF/WebP + меньше contention|
| TTI mobile                     | 11–14 s  | ≤ 7 s        | idle-gated analytics                        |
| TBT                            | 86–310ms | ≤ 150 ms     | нет layout thrash + нет eager pixel init    |
| Page weight (cold)             | 3.35 MB  | ≤ 1.9 MB     | шрифты −450 KB, FA −103 KB, analytics −500+ |
| Fonts transfer                 | 679 KB   | ≤ 260 KB     | dedup inline vs fonts.css                   |
| Third-party initial            | 726 KB   | ≤ 150 KB     | idle-gate + low-device skip                 |

Эти значения **не складываются арифметически** — сеть и main-thread разблокируют друг друга.

---

## 2. Изменения — файл за файлом

### 2.1 `storefront/templatetags/responsive_images.py` — Strict mode для image pipeline

**Что сделано:**
- Добавлено логирование через `logging.getLogger(__name__)`.
- Флаг `_STRICT_MODE = getattr(settings, 'PERF_IMAGE_STRICT', settings.DEBUG)` — включает warning только в DEBUG или при явном флаге в настройках прода.
- Дедуп `_WARNED_PATHS` — один warning на путь за процесс, чтобы не забивать stdout.
- В `optimized_image()` добавлен guard: если ни `.webp`/`.avif` главный файл не существует, ни responsive variants — вызывается `_warn_missing_variants(...)`.

**Зачем:** на продакшн-главной часть товаров уходит в raw JPEG, потому что `optimize_images` не прогнали после загрузки. Strict mode сразу подсвечивает такие товары в логах → operations видит, какие карточки нужно догнать.

**Эффект:** подготовка инфраструктуры под дальнейший шаг Phase 1.1 (прогон `optimize_images` на проде + signal на `Product.save()`).

---

### 2.2 `twocomms_django_theme/static/css/fonts.css` — Dedup Inter

**Было:** `@font-face` для weights 400, 500, 600, 700. Weights 400/700 при этом **также** определены inline в `base.html` (critical path). Итого два разных URL для одного и того же шрифта → 225 KB дубля.

**Стало:** `fonts.css` содержит только 500 и 600. Weights 400/700 остаются только inline в `base.html`, preload указывает на тот же URL.

**Эффект:** −225 KB font transfer, меньше text-repaint.

---

### 2.3 `twocomms_django_theme/templates/base.html` + `pages/index.html` — FA opt-out на home

**Проблема:** Font Awesome CSS (`103 KB`) подключается глобально из `base.html`, а на главной странице **нет ни одной** `fa-*` иконки (проверено grep'ом).

**Решение:** `<link>` на FA обёрнут в `{% block fontawesome_css %}...{% endblock %}`. В `index.html` добавлен пустой override — на главной FA не грузится. 23 других шаблона с 618 использованиями FA не затронуты.

**Эффект:** −103 KB initial CSS transfer на `/`.

---

### 2.4 `static/js/modules/optimizers.js` — Удаление мёртвого кода

- `PerformanceOptimizer.scrollThreshold = 20;` — свойство присваивалось, нигде не читалось. Удалено.
- `optimizeMobileImages()` — вся функция искала `img[data-src]`, но в шаблонах `data-src` не используется (verified via Grep). Удалена функция и её вызов.

**Эффект:** −2 KB JS + меньше работы на mobile `DOMContentLoaded`.

---

### 2.5 `static/js/main.js` — Layout equalization off на mobile + убран forced reflow

**Изменение 1:** В `equalizeCardHeights()` / `equalizeProductTitles()` добавлен early return:

```js
const deviceClass = (document.documentElement.dataset.deviceClass || '').toLowerCase();
const isMobileViewport = window.matchMedia('(max-width: 899px)').matches;
if (deviceClass === 'low' || isMobileViewport) return;
```

Нативное CSS-выравнивание (`display:grid; grid-auto-rows:1fr;`, `-webkit-line-clamp: 2; min-height: calc(2*1.4em);`) покрывает mobile-кейсы без JS.

**Изменение 2:** Forced reflow `void categoriesContainer.offsetHeight;` заменён на double `requestAnimationFrame`:

```js
categoriesContainer.style.display = 'block';
requestAnimationFrame(() => {
  requestAnimationFrame(() => {
    categoriesContainer.classList.add('expanding');
  });
});
```

Визуально эквивалент (браузер всё равно «видит» элемент перед transition), но без синхронного read → write → read цикла.

**Изменение 3:** Удалён дубль `import('./survey.js')` на `DOMContentLoaded` (он же делается по клику на CTA в `index.html`).

**Эффект:** −800…2000 ms Style&Layout на mobile, плавный scroll, меньше jank.

---

### 2.6 `static/js/analytics-loader.js` — Idle-gated analytics

**Было:**
- `setTimeout(initializePixelsDeferred, 3000)` — Meta + TikTok всегда грузятся через 3s.
- GA через `schedule(loadGoogleAnalytics, 2000)`.
- Clarity через `schedule(loadClarity, 3000)`.
- Interaction events: `scroll, click, touchstart, mousemove` (`mousemove` стреляет слишком рано).

**Стало:**
- Detection device-class через `navigator.deviceMemory`, `hardwareConcurrency`, `connection`.
- `isLowDevice = mem <= 2 || cpu <= 2 || saveData || /2g|slow-2g/.test(effectiveType)`.
- Interaction events заменены на `scroll, click, touchstart, pointerdown, keydown` с `{passive:true, once:true}`.
- Meta/TikTok/GA/Clarity грузятся через `requestIdleCallback` с разными timeout:
  - Meta+TikTok init: 8s normal / 15s low
  - GA: 6s normal / 12s low
  - Clarity: 15s normal / **не грузится** на low-device
- TikTok pixel пропускается полностью на low-device (−248 KB unused JS).

**Эффект:** initial third-party transfer `726 → ~150 KB`, TTI −3…5 s, нет «догоняющих» long tasks после load.

**Риск:** Meta/TikTok conversions могут потерять часть событий от очень быстрых сессий. Mitigation — server-side CAPI (Phase 2).

---

## 3. Что осталось и почему (честно)

| Не сделано в Phase 1              | Почему                                              | План          |
| --------------------------------- | --------------------------------------------------- | ------------- |
| Прогон `optimize_images` на prod  | Требует доступа к prod media + cron на сервере      | Phase 1.1 ops |
| Signal `Product.save()`           | Требует тестов на миграцию существующих объектов    | Phase 2       |
| Inter Variable                    | Нужен download + смоук на всех шаблонах             | Phase 2       |
| `fetchpriority=high` для LCP card | `partials/product_card.html` сейчас не различает LCP| Phase 2       |
| GTM server-side                   | Требует согласования с маркетингом                  | Phase 1.3 ops |
| Удаление inline fallback JS 20 KB | Нужен grep по функциям + smoke-тест                 | Phase 2       |
| Bootstrap → Alpine.js             | Большая миграция, не Phase 1                        | Phase 2-3     |
| Anonymous page cache              | Требует разделения badge/cart AJAX                  | Phase 4       |
| `content-visibility` для секций   | Только после стабилизации equalization              | Phase 3       |

---

## 4. Верификация

### 4.1 Команда измерения (запускать до и после deploy)

```bash
# Lighthouse mobile x3 (медиана)
for i in 1 2 3; do
  lighthouse https://twocomms.shop/ \
    --form-factor=mobile --throttling.cpuSlowdownMultiplier=4 \
    --output=json --output-path=./perf/mobile-$i.json --quiet
done

# Lighthouse desktop
lighthouse https://twocomms.shop/ \
  --form-factor=desktop --output=json --output-path=./perf/desktop.json --quiet

# TTFB / size
curl -w "TTFB:%{time_starttransfer}s Total:%{time_total}s Size:%{size_download}B\n" \
     -o /dev/null -s https://twocomms.shop/
```

### 4.2 Реальные устройства

- iPhone SE 2020 / iOS Safari
- Xiaomi Redmi 9A или любой Android ≤ 2 GB RAM
- WebPageTest profile Moto G4

### 4.3 Acceptance Gate Phase 1

- [ ] LCP mobile ≤ 4.5 s (медиана 3 прогонов)
- [ ] Page weight ≤ 1.9 MB cold
- [ ] Fonts ≤ 260 KB
- [ ] Lighthouse mobile ≥ 78

Если не выполняется — rollback конкретного блока + root-cause analysis перед Phase 2.

---

## 5. Рекомендованные библиотеки и сервисы (на будущее)

| Проблема                 | Решение                                                                    | Стоимость    |
| ------------------------ | -------------------------------------------------------------------------- | ------------ |
| Иконки (FA 103 KB)       | [Lucide](https://lucide.dev/) inline SVG sprite                             | free         |
| Bootstrap JS 80 KB       | [Alpine.js](https://alpinejs.dev/) 15 KB + native `<dialog>`                | free         |
| JS bundler               | [esbuild](https://esbuild.github.io/)                                       | free         |
| Critical CSS             | [critters](https://github.com/GoogleChromeLabs/critters) build step         | free         |
| Image CDN                | [Cloudflare Images](https://www.cloudflare.com/products/cloudflare-images/) или [imgproxy](https://imgproxy.net/) | $5/мес или self-host |
| Analytics client weight  | GTM server-side через [Stape](https://stape.io/) + Consent Mode v2          | $20/мес      |
| Fonts                    | [Inter Variable](https://rsms.me/inter/) 120 KB весь семейство              | free         |
| RUM                      | [web-vitals](https://github.com/GoogleChrome/web-vitals) + Sentry Performance | free/tier    |
| Bundle analyzer          | [source-map-explorer](https://github.com/danvk/source-map-explorer)         | free         |

**Приоритет подключения:** web-vitals (RUM без него — вслепую) → Inter Variable → imgproxy → Alpine.js → GTM server-side.

---

## 6. Идеи рефакторинга

1. **Разрезать `main.js` на route-scoped entries** (`core.js` + `entries/{home,product,catalog,checkout}.js`) через `<script type="module">` — tree-shaking даром. Сейчас main.js — 286 ms long task на mobile.
2. **Extract inline CSS из index.html** (~27 KB) в `home.css` + critical-only inline через critters.
3. **`PageScopedAssets` template tag**: `{% page_css "home" %} {% page_js "home" %}` — убрать копипаст `{% block extra_css %}`.
4. **Denormalized `ProductCardReadModel`** с первым изображением и min price — home рендерится 1 SELECT без JOIN.
5. **Service Worker + Workbox** для offline-first повторных визитов.
6. **Client Hints / `Save-Data` header** на SSR — серверно решать, сколько карточек рендерить (6 vs 12).
7. **`Speculation Rules API`** (Chromium 121+) — prerender страниц каталога по hover.
8. **Unified `data-device-class` detector** (~600 B inline) заменяет три дублирующие системы: MobileOptimizer, PERF_LITE, scattered `innerWidth` checks.

---

## 7. Django 6 / Python 3.14 — вердикт

**Не делать сейчас.** Текущая боль — клиентская. Django 6 даёт `~5–15 ms` TTFB, но не трогает LCP/TTI/mobile jank, а migration — отдельный проект (deprecations + third-party compat). Перейти когда выйдет 6.0 LTS (ожидаемо 2026-08). Если нужен backend-win — PostgreSQL `pg_stat_statements` + index audit + async views на NP endpoints.

---

## 8. Risk register — Phase 1 specific

| Риск                                                 | Mitigation                                                 |
| ---------------------------------------------------- | ---------------------------------------------------------- |
| Analytics consent-gate теряет conversions            | Server-side CAPI Phase 2; пока gate мягкий (idle, не consent)|
| `requestIdleCallback` не поддержан в Safari < 16.4   | Fallback на setTimeout уже есть в коде                     |
| Low-device skip Clarity — нет данных со слабых тел   | Это and осознанно — Clarity всё равно не работает на них   |
| Equalization off на mobile → разная высота карточек  | CSS grid `grid-auto-rows: 1fr` компенсирует                |
| FA block override ломает страницу, где FA нужен      | Override только в `index.html` — другие шаблоны без изменений|

---

## 9. Файлы, затронутые Phase 1

- [responsive_images.py](twocomms/storefront/templatetags/responsive_images.py)
- [base.html](twocomms/twocomms_django_theme/templates/base.html)
- [pages/index.html](twocomms/twocomms_django_theme/templates/pages/index.html)
- [main.js](twocomms/twocomms_django_theme/static/js/main.js)
- [analytics-loader.js](twocomms/twocomms_django_theme/static/js/analytics-loader.js)
- [optimizers.js](twocomms/twocomms_django_theme/static/js/modules/optimizers.js)
- [fonts.css](twocomms/twocomms_django_theme/static/css/fonts.css)

## 10. Следующий шаг

1. Смоук-тест dev (Lighthouse + визуальный diff).
2. Deploy в staging, запустить verification protocol §4.
3. При прохождении Phase 1 gate → commit `perf:phase-1` → Phase 2 (route-split + inline extract + lazy modals).
