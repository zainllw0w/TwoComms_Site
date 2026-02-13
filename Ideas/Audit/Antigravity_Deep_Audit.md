# Мастер-Аудит: Консолидированный Анализ AI-Агентов
## dtf.twocomms.shop — Visual Effects Integration

**Дата:** 2026-02-09  
**Статус:** Финальная консолидация  
**Источники:** Opus 4.6 v1/v2, CODEX, Antigravity, Gemini 1.5 Pro, Effects.MD

---

## 🎯 Executive Summary

Проведён анализ **5 AI-агентов** с общим объёмом **4000+ строк** документации и **300+ уникальных идей**. Выявлен консенсус по архитектуре и критическим проблемам.

### Ключевые выводы

| Аспект | Консенсус всех агентов |
|--------|------------------------|
| **Архитектура** | Django + Vanilla JS + data-attributes + core.js |
| **React** | НЕ использовать в основном DTF-фронте |
| **Критический баг** | Конфликт FAB/Floating Dock/Mobile Dock |
| **Приоритет №1** | Multi-Step Loader для preflight |
| **SEO** | Весь текст в HTML до JS-исполнения |

---

## 📊 Матрица Агентов

| Агент | Строк | Идей | Сильная сторона | Уникальный вклад |
|-------|-------|------|-----------------|------------------|
| **Opus 4.6 v1** | 1155 | 30+ | Porting Contract | React→Vanilla JS таблица |
| **Opus 4.6 v2** | 1188 | 30+ | Sprint Roadmap | Celery интеграция |
| **CODEX** | 571 | 100 | Code Audit | Размеры файлов, техдолг |
| **Antigravity** | 215 | 100 | Page-by-Page | Конкретные эффекты на страницы |
| **Gemini 1.5** | 258 | 100 | Architecture | Web Components, Haptics |

---

## 🔴 Критические Проблемы

### 1. Конфликт нижнего правого угла
**Файл:** [base.html](file:///Users/zainllw0w/PycharmProjects/TwoComms/twocomms/dtf/templates/dtf/base.html#L255-L327)

```html
<!-- Конфликтующие элементы -->
<div class="dtf-fab" id="dtf-fab">              <!-- L255-260 -->
<nav class="dtf-floating-dock">                 <!-- L296-301 -->
<nav class="mobile-dock">                       <!-- L314-327 -->
```

> [!CAUTION]
> **Все 5 агентов** идентифицировали эту проблему как критическую.

**Решение (консенсус):**
```css
/* Убрать FAB, оставить Dock */
.dtf-fab { display: none; }
@media (min-width: 961px) {
  .dtf-floating-dock { display: grid; }
  .mobile-dock { display: none !important; }
}
@media (max-width: 960px) {
  .dtf-floating-dock { display: none !important; }
  .mobile-dock { display: grid; }
}
```

### 2. Vanish Input не очищает поле
**Файл:** [vanish-input.js](file:///Users/zainllw0w/PycharmProjects/TwoComms/twocomms/dtf/static/dtf/js/components/vanish-input.js)

Текущее поведение: shake + highlight  
Требуемое: invalid → анимация → очистка value → return placeholder

### 3. Legacy дубли в dtf.js
В `dtf.js` (81KB) остаются legacy-инициализаторы эффектов, при этом активна модульная схема через `core.js + effect.*`.

---

## ✅ Уже Реализовано

### JS Компоненты (21 файл)

| Компонент | Файл | Размер | Статус |
|-----------|------|--------|--------|
| Core Registry | `core.js` | 4.5KB | ✅ Работает |
| Compare | `effect.compare.js` | 2.5KB | ✅ Базовый |
| Stateful Button | `effect.stateful-button.js` | 4KB | ✅ Работает |
| Encrypted Text | `effect.encrypted-text.js` | 2.1KB | ✅ Работает |
| Tracing Beam | `effect.tracing-beam.js` | 1.5KB | ✅ Работает |
| Infinite Cards | `effect.infinite-cards.js` | 449B | ⚠️ Не SEO-safe |
| Floating Dock | `floating-dock.js` | 1.8KB | ⚠️ Конфликт |
| Multi-Step Loader | `multi-step-loader.js` | 1.4KB | ⚠️ Нет backend |
| Vanish Input | `vanish-input.js` | 1KB | ⚠️ Не очищает |

### CSS Компоненты (18 файлов)
Все эффекты имеют парные CSS-файлы.

---

## 🛠 Porting Contract: React → Vanilla JS

### Таблица соответствий (из Opus 4.6)

| React | Vanilla JS |
|-------|------------|
| `useState` | Замыкания + DOM |
| `useRef` | `document.querySelector` |
| `useEffect` | `DOMContentLoaded` + IntersectionObserver |
| `motion.div` | CSS transitions/animations |
| `AnimatePresence` | classList + transitionend |
| JSX условия | `innerHTML` / `template` |

### Шаблон эффекта

```javascript
// static/dtf/js/components/effect.{name}.js
(function () {
  const DTF = (window.DTF = window.DTF || {});

  function init{Name}(node, ctx) {
    if (!node) return null;
    if (ctx?.reducedMotion) {
      node.classList.add('is-static');
      return null;
    }
    // ... логика
    return function cleanup() { /* ... */ };
  }

  if (DTF.registerEffect) {
    DTF.registerEffect('{name}', '[data-effect~="{name}"]', init{Name});
  }
})();
```

---

## 📋 Приоритизированные Идеи

### Sprint 1 (Обязательно) — Недели 1-2

| ID | Идея | Источник | Файлы |
|----|------|----------|-------|
| S1-01 | Убрать FAB, оставить Dock | Все | base.html, dtf.css |
| S1-02 | Multi-Step Loader + Celery | Opus, CODEX | multi-step-loader.js |
| S1-03 | Compare dual-mode | CODEX | effect.compare.js |
| S1-04 | Vanish Input + clear | CODEX | vanish-input.js |
| S1-05 | SEO-safe Infinite Cards | CODEX, Opus | effect.infinite-cards.js |

### Sprint 2 (Рекомендовано) — Недели 3-4

| ID | Идея | Источник |
|----|------|----------|
| S2-01 | Tooltip Card для DTF-терминов | Antigravity |
| S2-02 | Images Badge в конструкторе | CODEX |
| S2-03 | Flip Words только в hero | Opus |
| S2-04 | Text Generate Effect в SLA | Gemini |
| S2-05 | Stateful Button везде | CODEX |

### Sprint 3 (Оптимизация) — Недели 5-6

| ID | Идея | Источник |
|----|------|----------|
| S3-01 | Lighthouse аудит | Opus |
| S3-02 | `prefers-reduced-motion` | Все |
| S3-03 | `noscript` fallbacks | Opus, CODEX |
| S3-04 | BlurHash для lazy-load | Antigravity |
| S3-05 | A/B флаги для эффектов | CODEX |

---

## 📈 Performance Budget

| Метрика | Лимит | Текущее |
|---------|-------|---------|
| **LCP** | < 2.5s | TBD |
| **CLS** | < 0.1 | TBD |
| **INP** | < 200ms | TBD |
| **JS Bundle** | < 150KB gzip | ~35KB (effects only) |
| **FPS** | 60fps | TBD |

---

## 🌐 SEO Checklist

- [ ] Весь текст в HTML до JS
- [ ] `noscript` fallbacks для анимаций
- [ ] `aria-hidden="true"` для дублированных элементов
- [ ] JSON-LD микроразметка
- [ ] Локальный хостинг шрифтов (опционально)

---

## ❓ Открытые Вопросы для Владельца

1. **Celery**: Настроен ли для background tasks?
2. **Контент**: Есть ли реальные отзывы/логотипы для Infinite Cards?
3. **Терминология**: Список DTF-терминов для Tooltip Cards?
4. **Изображения**: Есть ли "до/после" для Compare?
5. **Локализация**: Какой язык приоритетный (UK/RU/EN)?

---

## 📦 Промпт для Codex (Sprint 1)

```markdown
# CODEX Task: DTF Effects Sprint 1

## Context
- Stack: Django + Vanilla JS + HTMX
- Location: twocomms/dtf/static/dtf/js/components/
- Pattern: effect.{name}.js + effect.{name}.css

## Tasks

### 1. Fix FAB/Dock Conflict
File: base.html (L255-327)
Action: Hide .dtf-fab, keep .dtf-floating-dock (desktop) and .mobile-dock (mobile)
CSS: Add media queries to dtf.css

### 2. Multi-Step Loader Backend Integration
File: multi-step-loader.js
Action: Add polling to /api/task-status/{taskId}
Steps: ["Завантаження", "DPI", "Кольори", "Площа", "Превʼю"]

### 3. Compare Dual-Mode
File: effect.compare.js
Action: Add data-autoplay="true" for 2-cycle auto-sweep, then manual

### 4. Vanish Input Clear
File: vanish-input.js
Action: On invalid → animate → clear value → restore placeholder
Attribute: data-vanish-clear="true"

### 5. SEO-Safe Infinite Cards
File: effect.infinite-cards.js
Action: First track = SEO content, clone = aria-hidden
Template:
<section data-effect="infinite-cards">
  <div class="infinite-track">[content]</div>
  <div class="infinite-track" aria-hidden="true">[clone]</div>
</section>

## Verification
- [ ] No FAB visible on any breakpoint
- [ ] Loader steps match backend response
- [ ] Compare autoplay works then freezes
- [ ] Vanish clears invalid fields
- [ ] Infinite Cards pass SEO audit
```

---

## 🗂 Связанные Файлы

- [Effects.MD](file:///Users/zainllw0w/PycharmProjects/TwoComms/twocomms/Promt/Effects.MD) — Каталог компонентов
- [Opus 4.6 v1](file:///Users/zainllw0w/PycharmProjects/TwoComms/Ideas/Audit/opus%204.6%20v1.MD)
- [Opus 4.6 v2](file:///Users/zainllw0w/PycharmProjects/TwoComms/Ideas/Audit/opus%204.6%20v2.MD)
- [CODEX Report](file:///Users/zainllw0w/PycharmProjects/TwoComms/Ideas/CODEX_Report.md)
- [Antigravity Report](file:///Users/zainllw0w/PycharmProjects/TwoComms/Ideas/Antigravity_Report.md)
- [Gemini 1.5 Pro](file:///Users/zainllw0w/PycharmProjects/TwoComms/Ideas/Gemini_1.5_Pro.md)

---

*Сгенерировано Antigravity на основе анализа 5 AI-агентов*
