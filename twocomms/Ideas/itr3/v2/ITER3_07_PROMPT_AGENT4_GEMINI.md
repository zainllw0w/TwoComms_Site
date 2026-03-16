# ITER3_07 — PROMPT для 4-го агента (Gemini 3.1 — Создатель ассетов)

Ты — AI-агент-дизайнер/фронтендер. У тебя есть доступ к репозиторию dtf.twocomms.shop и ты создаёшь **SVG-иконки**, CSS-анимации, и **микро-улучшения визуала компонентов** (без тяжёлых библиотек).

> **🎨 Творческая свобода:** Код и примеры ниже — это НАПРАВЛЕНИЕ и ОРИЕНТИР. Ты ДОЛЖЕН подумать, как сделать ЛУЧШЕ и КРАСИВЕЕ. Если видишь, что можно улучшить анимацию, сделать иконку изящнее, или придумать более элегантное CSS-решение — ДЕЛАЙ. Копируй дословно только если уверен, что вариант идеален.

> **Важно:** Сайт работает на удалённом сервере через SSH (либо напрямую на живых файлах проекта). Все файлы создавай в репозитории, используя тулзы (например, `write_to_file`).
> **📱 Mobile-first:** Большинство трафика — мобильный. Проверяй всё на 320/360/390px. Touch targets ≥ 44px.  
> **📋 Помощники:** Используй `ITER3_GLOSSARY.md` для терминов и `ITER3_FILE_MAP.md` для навигации по файлам проекта.

---

## 🛑 ДОГОВОРЁННОСТЬ ПО СИНХРОНИЗАЦИИ С AGENT 3 (ЧИТАТЬ ВНИМАТЕЛЬНО) 🛑

Твоя задача — **ТОЛЬКО** сгенерировать SVG-файлы и CSS-файлы.
**Agent 3** — это "Главный интегратор", который потом добавит их в HTML, подключит и настроит JS. 

**ТВОИ ОГРАНИЧЕНИЯ (ЧЕГО ДЕЛАТЬ НЕЛЬЗЯ):**
- ❌ **НЕ** редактируй HTML-шаблоны (`dtf/*.html`). Это работа Agent 3.
- ❌ **НЕ** редактируй backend-логику, `views.py` или структуру папок.
- ❌ **НЕ** редактируй `dtf.js` или тексты.
- ❌ **НЕ** запускай `collectstatic`.
- ❌ **НЕ** читай файлы `views.py` и `models.py` просто так. Сфокусируйся на CSS и SVG.

**ТВОЙ РЕЗУЛЬТАТ (HANDOVER FILE):**
Когда ты закончишь свою работу по созданию всех SVG-иконок и CSS-анимаций, ты **ОБЯЗАН** создать в папке `v2` (там где этот промпт) новый файл `ITER3_AGENT4_HANDOVER.md`.
В этом файле ты должен:
1. Вывести точный список всех путей к созданным SVG файлам.
2. Вывести точный список новых CSS-классов анимаций, которые ты добавил (чтобы Agent 3 знал, какие классы прописывать в HTML).
3. Написать любые краткие инструкции для Agent 3 (например: "Иконка icon-truck немного шире, дай ей padding-right").
Как только ты создашь этот файл, это послужит "зелёным светом" для Agent 3. Без него Agent 3 не сможет начать интеграцию!

---

## 0) Инструменты (используй по необходимости)

### Context7 (MCP)
Используй **Context7** для поиска лучших практик:
- SVG optimization techniques
- CSS animation performance (`transform`, `opacity`, `will-change`)
- `prefers-reduced-motion` accessibility patterns
- `stroke-dasharray` / `stroke-dashoffset` animation patterns
- `@media (pointer: coarse)` для mobile touch targets
- IntersectionObserver для lazy animation triggers

### Sequential Thinking (Встроенный MCP тул)
Используй Sequential Thinking (или внутренние рассуждения Gemini) при принятии решений по стилю иконок, выборе анимационных подходов, и планировании архитектуры CSS. Твоя сила — в разбиении сложных задач на шаги.

### Работа с файлами
Используй `write_to_file` для создания новых SVG иконок с нуля и `multi_replace_file_content` для внесения точечных изменений в существующие CSS файлы, если они уже есть.

---

## 1) Задача

Сделай набор **тонких line-иконок** в едином стиле + CSS-анимации + **CSS микро-улучшения для компонентов**.  
Иконки используются:
- в /order/ и /constructor/app/ (file scan, статусы, multi-step loader),
- в блоках доверия/преимуществ (лампочка "стабільне виробництво"),
- в mobile dock (Telegram),
- на /price/ (калькулятор), /quality/ (щит/гарантия), /faq/ (часы).

---

## 2) Жёсткие требования

1) Формат: чистые **inline SVG** (сохранить в `dtf/static/dtf/svg/` и инлайнить через `{% include %}`).
2) `viewBox="0 0 24 24"` для всех иконок.
3) `fill="none"`, `stroke="currentColor"`.
4) Единый stroke-стиль:
   - `stroke-width="1.8"` (одинаково для всех)
   - `stroke-linecap="round"`
   - `stroke-linejoin="round"`
5) Без встроенных цветов внутри SVG (цвет задаётся CSS через `color:`).
6) Оптимизация: минимум точек/путей, без лишних `<g>`, SVG-пак < 12 KB суммарно.
7) Анимации: только `transform`/`opacity`/`stroke-dashoffset`, обязателен fallback для `prefers-reduced-motion: reduce`.

---

## 3) Набор иконок (15 штук)

| # | Файл | Назначение | Используется |
|---|------|-----------|-------------|
| 1 | `icon-file.svg` | Файл/документ | Upload, проверка |
| 2 | `icon-scan.svg` | Скан-линия/проверка | Статус "Перевіряємо файл…" |
| 3 | `icon-check.svg` | Галочка | Статус "Все добре" |
| 4 | `icon-info.svg` | Инфо "i" | Статус "Є рекомендація" |
| 5 | `icon-warning.svg` | Предупреждение | Статус "Потрібна увага" |
| 6 | `icon-fix.svg` | Крест/инструмент | Статус "Потрібна правка" |
| 7 | `icon-bulb.svg` | Лампочка | Стабильность производства |
| 8 | `icon-truck.svg` | Доставка/посылка | Нова Пошта |
| 9 | `icon-sheet60.svg` | Лист/полотно | 60 см sheet |
| 10 | `icon-palette.svg` | Цвет/палитра | Качество |
| 11 | `icon-telegram.svg` | Бумажный самолётик | TG deep-link, dock |
| 12 | `icon-upload.svg` | Стрелка вверх в рамке | Dropzone, загрузка файла |
| 13 | `icon-clock.svg` | Часы | Сроки, "обычно до 30 минут" |
| 14 | `icon-shield.svg` | Щит с галочкой | Гарантия, trust-блок |
| 15 | `icon-calculator.svg` | Калькулятор | Страница /price/ |

> Все 15 — обязательны. Все в одном line-стиле.

---

## 4) Контракт интеграции с Agent3 (CODEX)

### 4.1 Naming convention (ОБЯЗАТЕЛЬНО следовать)

**SVG-файлы:**
```
dtf/static/dtf/svg/icon-{name}.svg
```

**CSS-классы:**
```css
.dtf-icon         /* базовый контейнер */
.dtf-icon-check   /* конкретная иконка */
.dtf-icon-animate /* добавляется JS при срабатывании */
```

### 4.2 HTML-шаблон (Который потом применит Agent 3)
*Эти примеры даны тебе только для понимания, как твои иконки будут использоваться. Ты сам HTML не правишь.*
```html
<span class="dtf-icon dtf-icon-check" aria-hidden="true">
  {% include "dtf/svg/icon-check.svg" %}
</span>
```

### 4.3 CSS-переменные (общие для проекта)
```css
:root {
  --dtf-accent: #3b82f6;
  --dtf-success: #22c55e;
  --dtf-warning: #eab308;
  --dtf-danger: #ef4444;
  --dtf-info: #3b82f6;
  --dtf-border: #e5e7eb;
}
```

### 4.4 Расположение CSS анимаций (Создай их)
```
dtf/static/dtf/css/components/icons.css       — базовые стили иконок
dtf/static/dtf/css/components/animations.css   — компонентные микро-анимации
```
**Ты (Agent 4)** создаёшь или обновляешь эти файлы.
Agent3 потом подключит эти файлы через `<link>` или `{% include %}` в рамках своей задачи.

---

## 5) Анимации для иконок (7 штук)

> **💡 CSS ниже — ОРИЕНТИР.** Ты можешь и должен сделать лучше: подобрать более приятные easing-кривые, тайминги, или придумать более элегантную анимацию. Копируй только если считаешь вариант идеальным.

### 5.1 `check-draw` (stroke-draw для icon-check)
```css
.dtf-icon-check .icon-path {
  stroke-dasharray: 30;
  stroke-dashoffset: 30;
}
.dtf-icon-check.dtf-icon-animate .icon-path {
  animation: check-draw 0.35s ease-out forwards;
}
@keyframes check-draw {
  to { stroke-dashoffset: 0; }
}
@media (prefers-reduced-motion: reduce) {
  .dtf-icon-check.dtf-icon-animate .icon-path {
    animation: none;
    stroke-dashoffset: 0;
  }
}
```

### 5.2 `scan-line` (движение линии для icon-scan)
```css
.dtf-icon-scan .scan-line {
  animation: scan-line 1.35s linear infinite;
}
@keyframes scan-line {
  0%   { transform: translateY(2px); opacity: 0.6; }
  100% { transform: translateY(20px); opacity: 0.2; }
}
@media (prefers-reduced-motion: reduce) {
  .dtf-icon-scan .scan-line { animation: none; opacity: 0.3; }
}
```

### 5.3 `soft-glow` (для icon-bulb и icon-telegram)
```css
.dtf-icon-bulb.dtf-icon-animate,
.dtf-icon-telegram.dtf-icon-animate {
  animation: soft-glow 0.4s ease-out;
}
@keyframes soft-glow {
  0%   { filter: drop-shadow(0 0 0 transparent); }
  50%  { filter: drop-shadow(0 0 6px var(--dtf-accent)); }
  100% { filter: drop-shadow(0 0 0 transparent); }
}
@media (prefers-reduced-motion: reduce) {
  .dtf-icon-bulb.dtf-icon-animate,
  .dtf-icon-telegram.dtf-icon-animate { animation: none; }
}
```

### 5.4 `upload-bounce` (для icon-upload — dropzone trigger)
```css
.dtf-icon-upload.dtf-icon-animate {
  animation: upload-bounce 0.5s cubic-bezier(0.34, 1.56, 0.64, 1);
}
@keyframes upload-bounce {
  0%   { transform: translateY(0); }
  40%  { transform: translateY(-6px); }
  100% { transform: translateY(0); }
}
@media (prefers-reduced-motion: reduce) {
  .dtf-icon-upload.dtf-icon-animate { animation: none; }
}
```

### 5.5 `truck-slide` (для icon-truck — статус "Відправка")
```css
.dtf-icon-truck.dtf-icon-animate {
  animation: truck-slide 0.6s ease-out;
}
@keyframes truck-slide {
  0%   { transform: translateX(-12px); opacity: 0; }
  100% { transform: translateX(0); opacity: 1; }
}
@media (prefers-reduced-motion: reduce) {
  .dtf-icon-truck.dtf-icon-animate { animation: none; opacity: 1; }
}
```

### 5.6 `pulse-ring` (для icon-shield — trust-блок)
```css
.dtf-icon-shield.dtf-icon-animate {
  position: relative;
}
.dtf-icon-shield.dtf-icon-animate::after {
  content: '';
  position: absolute;
  inset: -4px;
  border: 2px solid var(--dtf-success);
  border-radius: 50%;
  animation: pulse-ring 0.6s ease-out forwards;
  opacity: 0;
}
@keyframes pulse-ring {
  0%   { transform: scale(0.8); opacity: 0.6; }
  100% { transform: scale(1.3); opacity: 0; }
}
@media (prefers-reduced-motion: reduce) {
  .dtf-icon-shield.dtf-icon-animate::after { animation: none; display: none; }
}
```

### 5.7 `shimmer` (для icon-calculator и price-badge)
```css
.dtf-icon-calculator.dtf-icon-animate {
  position: relative;
  overflow: hidden;
}
.dtf-icon-calculator.dtf-icon-animate::after {
  content: '';
  position: absolute;
  top: 0; left: -100%;
  width: 60%; height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255,255,255,0.15), transparent);
  animation: icon-shimmer 1.5s ease-out;
}
@keyframes icon-shimmer {
  to { left: 150%; }
}
@media (prefers-reduced-motion: reduce) {
  .dtf-icon-calculator.dtf-icon-animate::after { animation: none; display: none; }
}
```

---

## 6) Примеры HTML использования

### File scan status
```html
<div class="file-scan" aria-live="polite">
  <span class="dtf-icon dtf-icon-scan" aria-hidden="true">
    {% include "dtf/svg/icon-scan.svg" %}
  </span>
  <span class="file-scan__text">Перевіряємо файл…</span>
</div>
```

### Multi-step loader (4 шага)
```html
<ol class="loader-steps">
  <li class="loader-step is-done">
    <span class="dtf-icon dtf-icon-check dtf-icon-animate">{% include "dtf/svg/icon-check.svg" %}</span>
    Файл отримано
  </li>
  <li class="loader-step is-active">
    <span class="dtf-icon dtf-icon-scan">{% include "dtf/svg/icon-scan.svg" %}</span>
    Перевірка файлу
  </li>
  <li class="loader-step">
    <span class="dtf-icon dtf-icon-file">{% include "dtf/svg/icon-file.svg" %}</span>
    Друк
  </li>
  <li class="loader-step">
    <span class="dtf-icon dtf-icon-truck">{% include "dtf/svg/icon-truck.svg" %}</span>
    Відправка
  </li>
</ol>
```

### Mobile dock Telegram
```html
<button class="dock-btn" data-action="telegram">
  <span class="dtf-icon dtf-icon-telegram">{% include "dtf/svg/icon-telegram.svg" %}</span>
  Telegram
</button>
```

### Trust block
```html
<div class="trust-item">
  <span class="dtf-icon dtf-icon-shield dtf-icon-animate" aria-hidden="true">
    {% include "dtf/svg/icon-shield.svg" %}
  </span>
  <span>Гарантія якості</span>
</div>
```

---

## 7) Важно

- Не трогай архитектуру проекта и Django-логику.
- Не добавляй зависимости.
- Итоговый SVG-пак < 12 KB суммарно.
- **Mobile:** все иконки видны на 320px, touch target ≥ 44px для интерактивных.
- **`ITER3_AGENT4_HANDOVER.md`**: Обязательно создай этот отчётный файл в конце для синхронизации.
- После завершения — сделай коммит (например, `git add -A` и `git commit -m "assets: SVG icon pack + CSS animations"`) и push, если требуется, ИЛИ просто заверши планирование, если так настроен твой пайплайн. Главный сигнал конца твоей зоны ответственности — файл Handover.

---

## 8) Component CSS micro-animations

> Этот CSS создаёшь ТЫ. Файл: `dtf/static/dtf/css/components/animations.css`  
> **💡 Код ниже — стартовая точка.** Улучшай: добавь свои находки, более изысканные easing-функции, может — другие визуальные приёмы, которые ты считаешь красивее. Отдай готовый красивый CSS файл. Главное — `prefers-reduced-motion` и performance.

### 8.1 Button hover
```css
.btn-primary {
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.btn-primary:hover {
  transform: scale(1.02);
  box-shadow: 0 4px 16px rgba(249, 115, 22, 0.25);
}
.btn-primary:active { transform: scale(0.98); }

.btn-secondary {
  transition: border-color 0.2s ease, transform 0.2s ease;
}
.btn-secondary:hover {
  border-color: var(--dtf-accent);
  transform: scale(1.01);
}

@media (pointer: coarse) {
  .btn-primary, .btn-secondary { min-height: 48px; }
}
@media (prefers-reduced-motion: reduce) {
  .btn-primary, .btn-secondary { transition: none; }
  .btn-primary:hover, .btn-secondary:hover { transform: none; }
}
```

### 8.2 Card entrance (fade-in-up)
```css
.work-card, .proof-card {
  opacity: 0;
  transform: translateY(20px);
  transition: opacity 0.5s ease-out, transform 0.5s ease-out;
}
.work-card.is-visible, .proof-card.is-visible {
  opacity: 1;
  transform: translateY(0);
}
.work-card:nth-child(2) { transition-delay: 0.1s; }
.work-card:nth-child(3) { transition-delay: 0.2s; }
.work-card:nth-child(4) { transition-delay: 0.3s; }

@media (prefers-reduced-motion: reduce) {
  .work-card, .proof-card { opacity: 1; transform: none; transition: none; }
}
```

### 8.3 Form input focus underline
```css
.form-group { position: relative; }
.form-group::after {
  content: '';
  position: absolute;
  bottom: 0; left: 50%; right: 50%;
  height: 2px;
  background: var(--dtf-accent, #f97316);
  transition: left 0.25s ease, right 0.25s ease;
}
.form-group:focus-within::after { left: 0; right: 0; }

@media (prefers-reduced-motion: reduce) {
  .form-group::after { transition: none; }
}
```

### 8.4 FAQ accordion
```css
.faq-answer {
  max-height: 0;
  overflow: hidden;
  transition: max-height 0.35s ease-out, opacity 0.25s ease-out;
  opacity: 0;
}
.faq-item.is-open .faq-answer {
  max-height: 200px;
  opacity: 1;
}
.faq-item.is-open {
  border-left: 3px solid var(--dtf-accent, #f97316);
}
@media (prefers-reduced-motion: reduce) {
  .faq-answer { transition: none; }
}
```

### 8.5 Price badge shimmer
```css
.price-badge {
  position: relative;
  overflow: hidden;
}
.price-badge::after {
  content: '';
  position: absolute;
  top: 0; left: -100%; width: 60%; height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255,255,255,0.1), transparent);
  animation: shimmer 4s ease-in-out infinite;
}
@keyframes shimmer {
  0%, 80%, 100% { left: -100%; }
  40% { left: 150%; }
}
@media (prefers-reduced-motion: reduce) {
  .price-badge::after { display: none; }
}
```

### 8.6 Mobile dock entrance
```css
.mobile-dock {
  transform: translateY(100%);
  transition: transform 0.35s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.mobile-dock.is-visible { transform: translateY(0); }

@media (prefers-reduced-motion: reduce) {
  .mobile-dock { transform: none; transition: none; }
}
```

### 8.7 Dropzone drag-over
```css
.dropzone.is-drag-over {
  animation: dropzone-pulse 0.8s ease-in-out infinite;
  border-color: var(--dtf-accent);
}
@keyframes dropzone-pulse {
  0%, 100% { opacity: 0.7; }
  50% { opacity: 1; }
}
@media (prefers-reduced-motion: reduce) {
  .dropzone.is-drag-over { animation: none; opacity: 1; }
}
```
