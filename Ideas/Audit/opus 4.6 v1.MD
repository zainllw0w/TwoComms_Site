📋 КОНСОЛИДИРОВАННЫЙ МЕГА-ОТЧЁТ: Стратегический анализ визуальных эффектов для dtf.twocomms.shop
Назначение документа: Единый источник истины для всех AI-агентов. На основе этого отчёта агенты продолжают итерации анализа, сравнения идей и генерации финального промпта для Codex.

СОДЕРЖАНИЕ
Контекст проекта и методология исследований
Карта агентов: кто, что и как сделал
Дефрагментация знаний: консенсус и расхождения
Принятое архитектурное решение
Контракт портирования React → Vanilla JS
Покомпонентный разбор эффектов Aceternity UI
SEO, производительность и Core Web Vitals
Психология дизайна и UX-стратегия
Интеграция в Django: файловая структура и core.js
Консолидированный ТОП идей из всех агентов
Дорожная карта внедрения (Sprint'ы)
Точные спецификации задач для Codex
Риски и их митигация
Открытые вопросы к владельцу
Промпт-заготовка для следующего этапа
1. КОНТЕКСТ ПРОЕКТА И МЕТОДОЛОГИЯ
1.1. О проекте
dtf.twocomms.shop — субдомен, самостоятельная платформа для:

Продажи DTF-пленки (Direct-to-Film)
Нанесения принтов на одежду
Партнёрского взаимодействия с швейными фабриками, брендами и B2B-клиентами
Ключевое отличие от основного домена twocomms.shop (бренд одежды): DTF-субдомен — это сервисная платформа с конструктором, проверкой макетов, калькулятором стоимости и системой заказа.

Стек: Python Django (бэкенд) + Vanilla JS + HTMX + CSS (фронтенд). Никакого React/Next.js/Angular.

1.2. Цепочка исследований
Этап	Участники	Задача
1	Claude 4 Sonnet, CODEX (OpenAI), Gemini 1.5 Pro	Анализ effects.md, генерация 100 идей каждый, план интеграции в Django
2	GPT-5.2 Pro (ChatGPT)	Сравнительный анализ всех трёх агентов
3	Gemini 3 Pro (Google)	Независимый стратегический отчёт с фокусом на Aceternity UI, Next.js 15, Tailwind v4
4	Claude Opus 4	Мета-анализ ВСЕХ предыдущих отчётов, консолидация v1
5	Claude 4 Sonnet ("Antigravity")	Гибридный подход React+Vite в Django, 100 идей по страницам
6	Claude Opus 4	Мега-отчёт v2 с контрактом портирования и точными спецификациями
7 (текущий)	Консолидация	Объединение v1 и v2 в единый документ
1.3. Источники
PDF 1 (ChatGPT): Сравнительный анализ Claude 4 Sonnet vs CODEX vs Gemini 1.5 Pro
PDF 2 (Gemini 3 Pro): Стратегический отчёт по модернизации с Aceternity UI
effects.md: Исходный код компонентов Aceternity UI (28 страниц, 16+ компонентов)
Контекстуальные данные: Структура Django-проекта, бизнес-требования владельца
2. КАРТА АГЕНТОВ
2.1. Профили агентов
🔵 Claude 4 Sonnet (1-й запуск) — «Системный архитектор»
Подход: Портирование React-компонентов на Vanilla JS + CSS
Сильные стороны:
Ровно 100 идей в табличном формате с приоритетами — готовый backlog
Каждая идея привязана к конкретному компоненту, странице и приоритету
Выявил конфликт FAB-кнопки менеджера с Floating Dock
Указал зависимости и размер каждого компонента (в KB)
Внимание к accessibility (a11y)
Слабые стороны:
Не провёл глубокий аудит существующего кода
Меньше внимания рефакторингу legacy-кода
Нет чёткого плана по спринтам
🟢 CODEX (OpenAI) — «Практичный инженер»
Подход: Vanilla JS с глубочайшим аудитом текущей кодовой базы
Сильные стороны:
Самый глубокий аудит: просмотрел Django-шаблоны, статические файлы, JS/CSS
Подсчитал точное количество использований (6× compare, 4× bg-beams и т.д.)
Выявил 3 критические проблемы: конфликт FAB/Dock/mobile, дублирование legacy-кода в dtf.js, несоответствие Vanish Input бизнес-требованиям
Оценка трудоёмкости (простые 1-2 дня, средние 3-5, сложные 5-10)
Замерил размеры скриптов (raw и gzip)
Разбил план на 3 спринта
Слабые стороны:
Идеи описаны текстом без табличной структуры
Не предложил архитектурных инноваций на будущее
🟡 Gemini 1.5 Pro (Google) — «Визионер-инноватор»
Подход: Радикальный — Web Components (Custom Elements) + Shadow DOM + тактильный/звуковой отклик
Сильные стороны:
100 идей сгруппированы по психологическим паттернам (доверие, контроль, геймификация)
Предложил нативные Web Components (<dtf-dock>) с Shadow DOM
Концепция «сенсорного веба»: вибрация при drag-and-drop, микро-звуки
Жёсткий бюджет производительности: CLS < 0.1, INP < 200ms, JS < 150KB gzip, 60fps
Предложил заменить framer-motion (~30KB) на Motion One (~5KB)
Рабочий код Web Component'а и функции vibrate()
Идея пасхалок (Konami Code → скидка)
Реал-тайм индикаторы (очередь заказов, остаток пленки)
Слабые стороны:
Концептуальный анализ без деталей файлов/страниц
Web Components требуют значительного рефакторинга
Haptic feedback и звуки — экспериментальны, могут раздражать
Идеи (3D-вьювер на Three.js, EyeDropper API) требуют больших ресурсов
⚪ GPT-5.2 Pro (ChatGPT) — «Арбитр»
Подход: Сравнительный анализ трёх агентов
Вердикт: CODEX — самый реалистичный; Claude — лучший справочник; Gemini — лучший источник стратегического вдохновения
Сильные стороны: Структурированное сравнение по 6 критериям
Слабые стороны: Не добавил собственных технических рекомендаций, не анализировал effects.md
🔴 Gemini 3 Pro (Google) — «Технический стратег»
Подход: Глубокий анализ 5 ключевых компонентов + план миграции на Next.js 15 + Tailwind v4
Сильные стороны:
Критически проанализировал предыдущие отчёты, нашёл пробелы
Детально разобрал Compare, Multi-Step Loader, Infinite Moving Cards, Floating Dock, Vanish Input
Указал на проблему устаревшего стека Tailwind v3 в предыдущих отчётах
Архитектура «листовых компонентов» для изоляции клиентского кода
Учёл DTF-специфику: Gang Sheets, DPI-проверка, RGB vs CMYK
Глубокий анализ проблемы CLS от текстовых эффектов
Touch-action: none для решения конфликта свайпов
Слабые стороны:
Ориентирован на Next.js 15, а проект на Django
Не учитывал что сайт УЖЕ на Django + Vanilla JS
🟣 Claude 4 Sonnet ("Antigravity") — «Гибридный архитектор»
Подход: React + Vite как "Frontend Layer" внутри Django
Сильные стороны:
100 идей разбиты по конкретным страницам (Landing, Constructor, Gallery, Price, Blog, Cabinet, Cart)
Единственный агент, давший архитектуру для тяжёлых React-компонентов (3D вьювер)
Ценные идеи: Odometer-эффект для цены, BlurHash для ленивой загрузки, Shared Element Transition
Слабые стороны:
Рекомендует React + Vite — противоречит консенсусу остальных 4 агентов
Не проводил аудит существующего кода
Не учитывает что проект УЖЕ имеет рабочую vanilla-инфраструктуру
2.2. Финальный рейтинг полезности
Критерий	CODEX	Claude 4 (1-й)	Gemini 1.5	Gemini 3	GPT-5.2	Antigravity
Аудит существующего кода	⭐⭐⭐⭐⭐	⭐⭐⭐	⭐⭐	⭐⭐	⭐	⭐⭐
Практичность рекомендаций	⭐⭐⭐⭐⭐	⭐⭐⭐⭐	⭐⭐⭐	⭐⭐⭐⭐	⭐⭐⭐	⭐⭐⭐
Инновационность идей	⭐⭐⭐	⭐⭐⭐	⭐⭐⭐⭐⭐	⭐⭐⭐⭐	⭐⭐	⭐⭐⭐⭐
SEO-грамотность	⭐⭐⭐⭐	⭐⭐⭐⭐	⭐⭐⭐	⭐⭐⭐⭐⭐	⭐⭐⭐	⭐⭐⭐
Структурированность	⭐⭐⭐⭐	⭐⭐⭐⭐⭐	⭐⭐⭐⭐	⭐⭐⭐⭐	⭐⭐⭐⭐	⭐⭐⭐⭐
Понимание DTF-бизнеса	⭐⭐⭐⭐⭐	⭐⭐⭐⭐	⭐⭐⭐⭐	⭐⭐⭐⭐⭐	⭐⭐⭐	⭐⭐⭐
2.3. Оптимальная стратегия использования
Взять план CODEX как основу → дополнить идеями Claude 4 → использовать бюджет производительности Gemini 1.5 → учесть технические нюансы Gemini 3 (адаптированные под Django) → взять каталог идей по страницам от Antigravity.

3. ДЕФРАГМЕНТАЦИЯ ЗНАНИЙ
3.1. Полный консенсус (поддержан всеми агентами)
Пункт	Поддержка
Vanilla JS лучше React для текущего проекта	Claude ✅, CODEX ✅, Gemini (частично) ✅, GPT ✅
FAB-кнопка менеджера конфликтует с Floating Dock	Все 6 агентов ✅
Multi-Step Loader обязателен для загрузки файлов	Все агенты ✅
Compare обязателен для демонстрации качества	Все агенты ✅
Infinite Moving Cards для социального доказательства	Все агенты ✅
SEO требует отдельного внимания при анимациях	Все агенты ✅
Производительность — приоритет	Все агенты ✅
Мобильная адаптация критична	Все агенты ✅
3.2. Точки расхождения
Вопрос	Claude 4	CODEX	Gemini 1.5	Gemini 3	Antigravity
Архитектура фронтенда	Vanilla JS + CSS	Vanilla JS + CSS	Web Components	Next.js 15 + React	React + Vite в Django
Библиотека анимаций	framer-motion → Vanilla	framer-motion → Vanilla	Motion One (~5KB)	framer-motion	framer-motion
Haptic feedback	Не упоминает	Не упоминает	✅ Обязательно	Не упоминает	Не упоминает
Звуковые эффекты	Не упоминает	Не упоминает	✅ Опционально	Не упоминает	Не упоминает
3D-эффекты	Ограниченно	Ограниченно	Three.js вьювер	Критикует за FPS	Поддерживает
Переход на другой стек	Нет	Нет	Web Components	Next.js 15	React + Vite
3.3. Уникальные ценные находки каждого агента
Claude 4 Sonnet:

Табличный формат идей с приоритетами — готовый backlog
Подробные плюсы/минусы для каждого компонента
Внимание к accessibility (a11y)
CODEX:

Количественный аудит (сколько раз каждый эффект используется)
Обнаружение legacy-дублей в dtf.js (initCompare, initTracingBeam)
Оценка размеров файлов и запаса по бандлу (~17KB gzip суммарно)
Спринтовый план с метками «обязательный сценарий»
Gemini 1.5 Pro:

Группировка идей по психологическим паттернам
Бюджет производительности (CLS < 0.1, INP < 200ms)
Концепция пасхалок (Konami Code → скидка)
Идея реал-тайм индикаторов (очередь заказов, остаток пленки)
Gemini 3 Pro:

Глубокий анализ проблемы CLS от текстовых эффектов
touch-action: none для решения конфликта свайпов
Архитектура «листовых компонентов» (изоляция клиентского кода)
Привязка к DTF-специфике: Gang Sheets, DPI-проверка, RGB vs CMYK
Antigravity:

100 идей разбиты по конкретным страницам — удобная структура для backlog
Odometer-эффект для цены, BlurHash, Shared Element Transition
Единственная архитектура для будущих тяжёлых React-компонентов (3D вьювер)
4. АРХИТЕКТУРНОЕ РЕШЕНИЕ
4.1. Вердикт: Django + Vanilla JS — ПРИНЯТО
Аргументы ЗА:

Проект уже построен на Django — менять бэкенд нецелесообразно
HTMX уже используется и отлично работает с Django
Vanilla JS даёт максимальный контроль над размером бандла
Нет overhead'а от React runtime (~40KB min+gzip)
Компоненты Aceternity UI — в основном CSS-анимации + JS-логика, портируемые
SEO-friendly: Django рендерит HTML на сервере, JS добавляет интерактивность прогрессивно
Аргументы ПРОТИВ React/Next.js:

Полная перестройка фронтенда — месяцы работы
Потеря преимуществ серверного рендеринга Django
Увеличение сложности деплоя (два сервера)
React hydration может конфликтовать с Django-шаблонами
Аргументы ПРОТИВ Web Components (Gemini 1.5):

Shadow DOM усложняет отладку стилей
Требует рефакторинга ВСЕХ существующих эффектов
Минимальный выигрыш при текущем масштабе проекта
Исключение: Предложение Antigravity (React + Vite) полезно ТОЛЬКО для будущего 3D-вьювера, но не для основных эффектов.

4.2. Архитектурная схема
text

┌──────────────────────────────────────────┐
│                DJANGO                     │
│  (серверный рендеринг HTML-шаблонов)     │
│                                           │
│  base.html → подключает:                 │
│    ├── dtf.css (основные стили)           │
│    ├── effects/*.css (стили эффектов)     │
│    ├── core.js (реестр эффектов)          │
│    ├── _utils.js (утилиты: cn, throttle) │
│    └── components/effect.*.js (модули)    │
│                                           │
│  Шаблоны используют data-attributes:     │
│    <div data-effect="compare"             │
│         data-first-image="..."            │
│         data-second-image="...">          │
│    </div>                                 │
│                                           │
│  core.js при DOMContentLoaded:           │
│    → Находит [data-effect]               │
│    → Вызывает соответствующий init()     │
│    → Поддерживает HTMX re-init          │
└──────────────────────────────────────────┘
4.3. Ключевые принципы
Прогрессивное улучшение: Без JS сайт показывает статический контент
Модульность: Каждый эффект — отдельный файл effect.{name}.js + effects/{name}.css
Идемпотентная инициализация: Повторный вызов init() не дублирует эффект
HTMX-совместимость: Re-init при htmx:afterSwap
Lazy-loading эффектов: Тяжёлые эффекты подгружаются только при видимости (IntersectionObserver)
4.4. Что взять от Gemini 3 Pro (Next.js отчёт) для Django
Рекомендация Gemini 3	Адаптация для Django
"use client" изоляция	Не нужна — Django рендерит всё на сервере
Tailwind v4 @theme	Можно использовать CSS Custom Properties без Tailwind
React 19 overrides	Нерелевантно
IntersectionObserver для lazy-load	✅ Полностью применимо
touch-action: none для свайпов	✅ Полностью применимо
WebP для изображений	✅ Полностью применимо
Синхронизация Loader с реальным API	✅ Адаптировать через fetch/WebSocket
aria-hidden для дубликатов	✅ Полностью применимо
Z-Index стратегия	✅ Полностью применимо
5. КОНТРАКТ ПОРТИРОВАНИЯ REACT → VANILLA JS
Этот раздел критически важен для Codex и любого coding-агента.

5.1. Общие зависимости Aceternity UI и их замены
text

React (useState, useRef, useEffect)  →  Vanilla: DOM API + класс/closure
motion/react (framer-motion)         →  CSS transitions/animations + requestAnimationFrame
clsx + tailwind-merge (cn())         →  Простая функция cn() в _utils.js
@tabler/icons-react                  →  SVG иконки инлайн или sprite
5.2. Таблица соответствий
React-концепция	Vanilla-аналог	Пример
useState(value)	Переменная в closure + DOM-обновление	let isVisible = false;
useRef(null)	document.querySelector() или параметр node	const el = node.querySelector('.inner');
useEffect(() => {}, [deps])	Инициализация в init()	Код в теле initEffect(node)
AnimatePresence	CSS transition + classList.toggle	.tooltip { transition: opacity 0.3s; }
motion.div с initial/animate/exit	CSS keyframes или JS requestAnimationFrame	@keyframes fadeIn { ... }
onMouseEnter/Move/Leave	addEventListener('mouseenter/mousemove/mouseleave')	Идентично
onTouchStart/End	addEventListener('touchstart/touchend')	Идентично
JSX {isVisible && <div>}	el.style.display = isVisible ? '' : 'none'	Условное отображение
className={cn("base", conditional)}	el.classList.toggle('active', condition)	Динамические классы
style={{ top: position.y }}	el.style.top = position.y + 'px'	Инлайн стили
React.Children / {children}	Просто innerHTML / контент внутри элемента	—
5.3. Шаблон JS-модуля эффекта
JavaScript

// static/dtf/js/components/effect.{name}.js
(function () {
  'use strict';
  
  const DTF = (window.DTF = window.DTF || {});

  /**
   * @param {HTMLElement} node — контейнер с data-effect="{name}"
   * @param {Object} ctx — контекст { reducedMotion: boolean }
   * @returns {Function|null} cleanup function
   */
  function init{Name}(node, ctx) {
    if (!node) return null;
    
    // 1. Проверка reduced-motion
    if (ctx && ctx.reducedMotion) {
      node.classList.add('is-static');
      return null;
    }
    
    // 2. Чтение конфигурации из data-attributes
    const config = { /* ... */ };
    
    // 3. Создание внутренней DOM-структуры (если нужно)
    
    // 4. Привязка событий
    const handlers = {};
    
    // 5. Cleanup function
    return function cleanup() {
      // removeEventListener, cancelAnimationFrame, etc.
    };
  }

  // Регистрация в реестре
  if (DTF.registerEffect) {
    DTF.registerEffect('{name}', '[data-effect~="{name}"]', init{Name});
  }
})();
5.4. Шаблон CSS-модуля эффекта
CSS

/* static/dtf/css/effects/{name}.css */

/* === Base State (no JS, no animation) === */
[data-effect~="{name}"] {
  min-height: var(--effect-{name}-height, auto);
  position: relative;
  overflow: hidden;
}

/* === Animated State === */
[data-effect~="{name}"].is-initialized {
  /* Стили после инициализации JS */
}

/* === Static/Reduced Motion State === */
[data-effect~="{name}"].is-static,
@media (prefers-reduced-motion: reduce) {
  [data-effect~="{name}"] {
    animation: none !important;
    transition: none !important;
  }
}

/* === Animations === */
@keyframes {name}-enter {
  from { /* ... */ }
  to { /* ... */ }
}
5.5. Шаблон Django template include
HTML

<!-- templates/dtf/includes/_{name}.html -->
{% comment %}
  Компонент: {Name}
  Использование: {% include 'dtf/includes/_{name}.html' with param1=value1 %}
  Требует: effect.{name}.js, effects/{name}.css
{% endcomment %}

<div data-effect="{name}"
     {% if param1 %}data-param1="{{ param1 }}"{% endif %}
     class="{name}-container"
     {% if aria_label %}aria-label="{{ aria_label }}"{% endif %}>
  
  <!-- Контент, доступный БЕЗ JS (SEO-safe) -->
  {{ content }}
  
</div>

<noscript>
  <div class="{name}-noscript">
    {{ content }}
  </div>
</noscript>
6. ПОКОМПОНЕНТНЫЙ РАЗБОР ЭФФЕКТОВ
6.1. Матрица принятия решений
Компонент	Статус	Действие	Приоритет	Сложность портирования
Compare	✅ Реализован (6×)	Доработать: dual-mode, touch-action	🔴 Критический	🟡 Средняя
Multi-Step Loader	❌ Не реализован	Создать с нуля, привязать к Celery	🔴 Критический	🔴 Сложная
Floating Dock	⚠️ Конфликт с FAB	Исправить: удалить FAB, оставить Dock	🔴 Критический	🔴 Сложная (magnification)
Vanish Input	⚠️ Частично	Доработать: очистка + placeholder cycling	🟡 Высокий	🔴 Сложная (Canvas частицы)
Infinite Moving Cards	⚠️ Частично (1×)	Доработать: SEO-safe, больше контента	🟡 Высокий	🟢 Простая
Tooltip Card	❌ Не реализован	Создать	🟡 Высокий	🟡 Средняя
Stateful Button	✅ Реализован	Расширить на все формы	🟡 Высокий	🟢 Простая
Images Badge	❌ Не реализован	Создать	🟡 Высокий	🟢 Простая
Flip Words	❌ Не реализован	Создать	🟢 Средний	🟢 Простая
Text Generate Effect	❌ Не реализован	Создать	🟢 Средний	🟢 Простая
Encrypted Text	✅ Реализован (3×)	Проверить SEO, reduced-motion	🟢 Низкий	🟢 Простая
Tracing Beam	✅ Реализован (3×)	Оптимизировать	🟢 Низкий	🟡 Средняя
Dotted Glow	✅ Реализован (4×)	Оптимизировать (IntersectionObserver)	🟢 Низкий	🟢 Простая
BG Beams	✅ Реализован (4×)	Оптимизировать	🟢 Низкий	🟢 Простая
Sparkles	✅ Реализован (1×)	Оптимизировать	🟢 Низкий	🟢 Простая
Loaders (5 вариантов)	❌ Не реализован	Создать (чистый CSS)	🟢 Средний	🟢 Простая
Cover	❌ Не реализован	Отложить (Sprint 3+)	🟢 Низкий	🟡 Средняя
Sidebar	❌ Не реализован	Отложить (Sprint 3+)	🟢 Низкий	🟡 Средняя
Animated Tooltip	❌ Не реализован	Отложить (Sprint 3+)	🟢 Низкий	🟢 Простая
6.2. Детальный разбор каждого компонента
⭐ Compare (Слайдер До/После) — КРИТИЧЕСКИЙ
Статус: Уже реализован (6 использований)

Бизнес-ценность для DTF:

Демонстрация «макет на экране» vs «отпечаток на ткани»
Сравнение разрешений: 72 DPI vs 300 DPI (обучение клиента)
DTF vs шелкография (конкурентное преимущество)
RGB на экране vs реальный цвет на ткани (управление ожиданиями)
Оригинал React (из effects.md):

Два изображения наложены друг на друга
Ползунок или hover управляет clip-path/маской
Режимы: hover, drag
Autoplay с настраиваемой длительностью
Sparkles-эффект на ручке
Технические нюансы портирования:

text

- Контейнер с position: relative
- Первое изображение — полноразмерное
- Второе изображение — clip через overflow: hidden + width в %
- Ползунок — absolute позиционирование
- MouseMove/TouchMove → обновление ширины clip
- Autoplay — setInterval + ease function
Что доработать:

Dual-mode (CODEX): auto-sweep 2-3 цикла → переход на ручной режим
touch-action: pan-y на контейнере (Gemini 3) — вертикальный скролл работает, горизонтальный перехватывается
WebP изображения с srcset для responsive
Lazy-load для второго изображения (скрыто маской)
SEO: alt-тексты на обоих изображениях. <noscript> fallback с обоими картинками рядом.

Accessibility: aria-label на ручке слайдера, role="slider", aria-valuemin/max/now.

⭐ Multi-Step Loader — КРИТИЧЕСКИЙ
Статус: Не реализован

Почему критически важен:
Клиент загружает файл (иногда сотни мегабайт), и стандартный спиннер вызывает тревогу. Multi-Step Loader превращает ожидание в демонстрацию компетентности:

text

Этап 1: «📤 Завантаження файлу на захищений сервер...» (реальный прогресс)
Этап 2: «🔍 Перевірка роздільності (DPI)...»
Этап 3: «🎨 Аналіз колірного профілю...»
Этап 4: «📐 Розрахунок площі та вартості...»
Этап 5: «✅ Генерація превʼю для підтвердження...»
Оригинал React (из effects.md):

Массив loadingStates: [{text: "..."}]
Полноэкранный overlay
Текущий шаг подсвечен, предыдущие — галочка, следующие — серые
Анимация переключения (slide up)
Настраиваемые: duration, loop, value
Связь с бэкендом:

text

Этап на фронте          →  Django Celery Task
"Завантаження файлу"    →  xhr.upload.onprogress
"Перевірка DPI"         →  task.step = 'dpi'
"Аналіз кольорів"      →  task.step = 'colors'
"Розрахунок площі"     →  task.step = 'area'
"Генерація превʼю"     →  task.step = 'preview'
Техническая реализация:

JavaScript

class MultiStepLoader {
  constructor(container, options) {
    this.steps = options.steps || [];
    this.currentStep = 0;
    this.container = container;
    this.render();
  }
  
  advanceTo(stepIndex) {
    this.currentStep = stepIndex;
    this.updateUI();
  }
  
  bindToUpload(formData, uploadUrl) {
    const xhr = new XMLHttpRequest();
    xhr.upload.addEventListener('progress', (e) => {
      const percent = (e.loaded / e.total) * 100;
      if (percent < 100) this.advanceTo(0);
    });
    xhr.addEventListener('load', () => {
      this.pollServerStatus(JSON.parse(xhr.response).taskId);
    });
    xhr.open('POST', uploadUrl);
    xhr.send(formData);
  }
  
  async pollServerStatus(taskId) {
    const res = await fetch(`/api/task-status/${taskId}/`);
    const data = await res.json();
    this.advanceTo(data.step);
    if (data.status !== 'completed') {
      setTimeout(() => this.pollServerStatus(taskId), 1000);
    }
  }
}
Публичный API:

JavaScript

DTF.multiStepLoader.show(taskId)    // показать overlay
DTF.multiStepLoader.hide()          // скрыть
DTF.multiStepLoader.setStep(index)  // перейти к шагу
DTF.multiStepLoader.bindToUpload(formData) // привязать к загрузке
⭐ Floating Dock — КРИТИЧЕСКИЙ (из-за конфликта)
Статус: Частично реализован, КОНФЛИКТУЕТ с FAB-кнопкой

Проблема (подтверждена ВСЕМИ агентами):
FAB-кнопка менеджера, Floating Dock и мобильная навигация — три элемента, борющиеся за одну область экрана.

Оригинал React (из effects.md):

MacOS-style dock внизу экрана
Magnification при наведении (Gaussian-like расчёт расстояния)
Tooltip с title при hover
Отдельные Mobile/Desktop версии
MotionValue для мышки
Решение конфликта:

Устройство	Решение
Desktop	Floating Dock по центру внизу с Magnification. FAB УДАЛИТЬ, перенести в Dock как элемент. Чат-виджет — правый нижний угол с z-index: 45.
Мобильные	Упрощённый Tab Bar БЕЗ Magnification. Чат — bottom: 80px (над Tab Bar).
Vanilla-подход для Magnification:

JavaScript

dock.addEventListener('mousemove', (e) => {
  const dockRect = dock.getBoundingClientRect();
  const mouseX = e.clientX - dockRect.left;
  
  icons.forEach(icon => {
    const iconRect = icon.getBoundingClientRect();
    const iconCenter = iconRect.left + iconRect.width / 2 - dockRect.left;
    const distance = Math.abs(mouseX - iconCenter);
    const scale = Math.max(1, 1.5 - distance / 200);
    icon.style.transform = `scale(${scale})`;
  });
});
Мобильная адаптация:

Отключить Magnification (hover-based, бессмыслен на тач)
Заменить на статичный ряд иконок с touch-feedback (scale animation при тапе)
CSS breakpoints:

CSS

@media (min-width: 961px) {
  .dtf-floating-dock { display: flex; }
  .mobile-dock { display: none !important; }
}
@media (max-width: 960px) {
  .dtf-floating-dock { display: none !important; }
  .mobile-dock { display: flex; }
}
Infinite Moving Cards — ВЫСОКИЙ ПРИОРИТЕТ
Статус: Частично реализован (1 использование)

Применение:

Бегущая лента логотипов клиентов/партнёров (trust-фактор)
Лента отзывов
Бегущая строка фактов: «Уже напечатано 15,000 метров пленки»
Оригинал React (из effects.md):

Массив карточек (quote, name, title)
Дублирование трека для бесшовности
CSS animation scroll — transform: translate(-50%)
Настраиваемые: direction, speed, pauseOnHover
CSS custom properties для duration и direction
Ключевая логика портирования:

CSS

@keyframes scroll {
  to { transform: translate(calc(-50% - 0.5rem)); }
}
JavaScript

// JS: клонировать .infinite-track, добавить aria-hidden="true" на клон
// Задать --animation-duration через speed prop
Speed mapping:

slow → 40s
normal → 25s
fast → 15s
SEO-решение (консенсус всех агентов):

HTML

<section data-effect="infinite-cards" data-speed="slow" data-direction="left" data-pause-on-hover="true">
  <div class="infinite-track">
    <!-- Реальный контент — индексируется -->
    <div class="infinite-item">
      <blockquote>"Відмінна якість друку!"</blockquote>
      <cite>— Олег, бренд Urbanwear</cite>
    </div>
  </div>
  <!-- JS клонирует .infinite-track с aria-hidden="true" -->
</section>

<noscript>
  <div class="partners-grid">
    <img src="logo1.webp" alt="Партнёр: Бренд X" />
  </div>
</noscript>
Производительность:

Анимация только через transform: translate3d() (GPU-ускорение)
IntersectionObserver: пауза при выходе из viewport
will-change: transform на контейнере
Placeholders And Vanish Input — ВЫСОКИЙ ПРИОРИТЕТ
Статус: Реализован частично, не соответствует бизнес-требованиям (CODEX)

Оригинал React (из effects.md):

Массив placeholder'ов, циклически сменяются
При submit — текст "исчезает" (Canvas-анимация частиц)
Кнопка submit меняет стиль
Рекомендация: УПРОЩЁННАЯ Vanilla-версия
Canvas-анимация частиц — 90% визуального эффекта можно получить через CSS:

CSS

/* Vanish через CSS вместо Canvas */
.vanish-exit {
  transform: scale(0.8);
  opacity: 0;
  filter: blur(4px);
  transition: all 0.3s ease-out;
}
Применение для DTF:

JavaScript

const placeholders = [
  "Пошук за артикулом...",
  "Футболки бавовна 100%...",
  "DTF плівка 60 см...",
  "UV-наклейки на замовлення...",
  "Худі з вашим принтом..."
];
SEO-нюансы (Gemini 3):

Placeholder — НЕ контент для индексации
CLS-риск: анимация может менять высоту → фиксированная высота контейнера + min-height
aria-label="Пошук по сайту" — статичный
Интервал смены: не менее 3-4 секунд
prefers-reduced-motion: статичный placeholder
Tooltip Card — ВЫСОКИЙ ПРИОРИТЕТ
Статус: Не реализован

Почему важно: Начинающие клиенты не понимают терминологию (DPI, CMYK, Gang Sheet, bleed, hot peel, underbase).

Оригинал React (из effects.md):

При hover показывает popup рядом с курсором
Popup следует за мышью
Автопозиционирование (не выходит за viewport)
Touch-поддержка (toggle по клику)
Spring-анимация высоты
Vanilla-реализация:

Tooltip-контейнер создаётся один раз, перемещается к нужному элементу
Позиция через el.style.left/top
Анимация через CSS transition: opacity 0.3s, transform 0.3s
Touch-detection через window.matchMedia('(hover: none)')
HTML-контракт:

HTML

<span data-effect="tooltip-card"
      data-tooltip-title="DPI (точок на дюйм)"
      data-tooltip-text="Мінімум 300 DPI для якісного друку"
      data-tooltip-image="/static/img/dpi-example.webp">
  <strong>300 DPI</strong>
</span>
Flip Words — СРЕДНИЙ ПРИОРИТЕТ
Статус: Не реализован

Оригинал React (из effects.md):

Массив слов циклически сменяется
Анимация: слово уезжает вверх + blur, новое появляется снизу
Настраиваемая длительность
Применение: «Ми друкуємо на [футболках | худі | кепках | сумках]»

SEO-решение (критическое):

HTML

<h2>
  Ми друкуємо на 
  <span data-effect="flip-words" 
        data-words='["футболках","худі","кепках","сумках"]'
        data-duration="3000">
    футболках, худі, кепках, сумках  <!-- SEO: все слова -->
  </span>
</h2>
JS при init: считывает data-words, заменяет innerText на анимированную версию. Для prefers-reduced-motion — оставляет статичный список.

CSS:

CSS

@keyframes flip-word-exit {
  to { transform: translateY(-100%); opacity: 0; filter: blur(4px); }
}
@keyframes flip-word-enter {
  from { transform: translateY(50%); opacity: 0; filter: blur(4px); }
  to { transform: translateY(0); opacity: 1; filter: blur(0); }
}
Text Generate Effect — СРЕДНИЙ ПРИОРИТЕТ
Статус: Не реализован

Оригинал React (из effects.md):

Текст разбивается на слова
Каждое слово появляется последовательно (opacity: 0 → 1, blur → clear)
SEO-ПРОБЛЕМА (критическая, выявлена Gemini 3):
Googlebot может НЕ увидеть финальный текст, если JS не выполняется.

Решение:

HTML

<!-- Сервер рендерит полный текст -->
<p data-effect="text-generate" data-delay="30" data-once="true">
  DTF-друк преміум якості — від макету до готового виробу за 24 години
</p>
<!-- JS берёт innerText, визуально прячет и анимирует. Но DOM изначально содержит полный текст! -->
Encrypted Text — СРЕДНИЙ ПРИОРИТЕТ
Статус: Реализован (3 использования)

Оригинал React (из effects.md):

Текст как случайные символы → постепенно «расшифровывается» слева направо
Настраиваемые: charset, revealDelayMs, flipDelayMs
Применение: Заголовки, отображение стоимости (wow-эффект при расчёте цены)

Действие: Проверить что исходный текст в HTML для SEO. Добавить prefers-reduced-motion → показать текст сразу.

Images Badge — ВЫСОКИЙ ПРИОРИТЕТ
Статус: Не реализован

Оригинал React (из effects.md):

"Папка" с иконками изображений
При hover иконки разлетаются веером
Почти полностью CSS (transforms на hover)
DTF-применение:

На загруженном файле в конструкторе
Как бейдж "новий", "топ" на кейсах в галерее
Статус файла: "завантажено", "перевіряється", "готово"
HTML-контракт:

HTML

<div data-effect="images-badge"
     data-text="Завантажено 3 файли"
     data-images='["/media/thumb1.webp","/media/thumb2.webp","/media/thumb3.webp"]'>
</div>
Stateful Button — ВЫСОКИЙ ПРИОРИТЕТ
Статус: Реализован, нужно расширить

Действие: Применить ко ВСЕМ формам:

Форма заказа → "Надіслати" → ⏳ "Надсилаємо..." → ✅ "Надіслано!"
Форма контакта → аналогично
Кнопка копирования → "Копіювати" → ✅ "Скопійовано!"
Loaders (5 вариантов) — СРЕДНИЙ ПРИОРИТЕТ
Из effects.md: Simple, Shimmer, Compact, SVG, Glitch — все чистый CSS.

Применение: Во время загрузки файлов, AJAX-запросов, переходов.

Tracing Beam — НИЗКИЙ ПРИОРИТЕТ
Статус: Реализован (3 использования)

Из effects.md: SVG линия сбоку от контента, рисуется по мере скролла.

Применение: Блог/документация, длинные страницы (FAQ, требования к макетам).

Dotted Glow, BG Beams, Sparkles — ДЕКОРАТИВНЫЕ
Статус: Реализованы (4×, 4×, 1× соответственно)

Рекомендации:

Использовать умеренно: 1-2 на страницу максимум
IntersectionObserver для паузы вне viewport
prefers-reduced-motion: fallback на статичный градиент
Canvas-эффекты (Dotted Glow) — отключать на слабых устройствах
Cover — НИЗКИЙ ПРИОРИТЕТ (отложено)
Из effects.md: Оборачивает текст, добавляет лучи (beams) и "space effect". При hover — "warp speed".

Применение (будущее): Hero-секция на главной.

Sidebar — НИЗКИЙ ПРИОРИТЕТ (отложено)
Из effects.md: Expandable sidebar: collapsed → expanded при hover. Отдельная мобильная версия.

Применение (будущее): Кабинет пользователя, конструктор (шаги).

Animated Tooltip — НИЗКИЙ ПРИОРИТЕТ (отложено)
Из effects.md: Ряд аватаров, tooltip с именем при hover.

Применение (будущее): «Ваш макет перевірив: Олександр»

7. SEO, ПРОИЗВОДИТЕЛЬНОСТЬ И CORE WEB VITALS
7.1. Целевые метрики (консенсус всех агентов)
Метрика	Целевое значение	Как обеспечить
LCP	< 2.5 сек	Lazy-load для не-hero изображений; priority для hero; WebP
CLS	< 0.1	Фиксированные размеры для анимированных контейнеров; min-height на секции
INP	< 200 мс	Vanilla JS + requestAnimationFrame; нет тяжёлых React-гидраций
FCP	< 1.8 сек	Критический CSS инлайн; отложенная загрузка не-критического JS
Total JS Size (gzip)	< 150 KB	Модульная загрузка эффектов; отказ от framer-motion
FPS при анимациях	60 fps	Только transform/opacity; will-change; IntersectionObserver
7.2. SEO-чеклист для анимированных компонентов
text

✅ Весь текстовый контент присутствует в HTML ДО выполнения JS
✅ Анимированный текст (Flip Words, Text Generate) — в DOM изначально
✅ Infinite Cards: дубликаты помечены aria-hidden="true"
✅ Infinite Cards: полный контент дублирован в <noscript>
✅ Все изображения имеют alt-тексты
✅ Structured data (JSON-LD) для отзывов, FAQ, продуктов
✅ Canonical URLs на каждой странице
✅ Все ресурсы хостятся локально (без CDN-зависимостей)
✅ Шрифты хостятся локально (CODEX)
✅ Meta description и title — статические, не зависят от JS
7.3. Стратегия загрузки ресурсов
HTML

<!-- base.html -->
<head>
  <!-- Критический CSS инлайн -->
  <style>/* core layout + above-the-fold styles */</style>
  
  <!-- Основной CSS — блокирующий, но минимальный -->
  <link rel="stylesheet" href="/static/dtf/css/dtf.min.css">
  
  <!-- CSS эффектов — отложенный -->
  <link rel="stylesheet" href="/static/dtf/css/effects.min.css" media="print" onload="this.media='all'">
</head>

<body>
  <!-- Контент страницы -->
  
  <!-- JS в конце body -->
  <script src="/static/dtf/js/core.js" defer></script>
  
  <!-- Модули эффектов загружаются core.js по необходимости -->
</body>
8. ПСИХОЛОГИЯ ДИЗАЙНА И UX-СТРАТЕГИЯ
8.1. Два типа пользователей
Аудитория А — «Новички»:

Не знают что такое DPI, CMYK, bleed
Боятся сделать что-то неправильно
Нуждаются в помощи менеджера
Хотят скинуть файл и получить результат
Аудитория Б — «Профессионалы»:

Знают все термины
Хотят быстрый self-service
Проверить макет и заказать за 2 минуты
Раздражаются от «лишних объяснений»
8.2. UX-стратегия: адаптивный интерфейс
НЕ два отдельных интерфейса, а один с адаптивной сложностью:

text

[Загрузка файла]
    │
    ├── 🟢 Файл проходит все проверки → Быстрый путь
    │   └── «Все чудово! Ваш файл: 300 DPI, CMYK, 0.8 м². Вартість: 450 грн. [Замовити]»
    │
    └── 🟡 Файл имеет проблемы → Путь помощи
        ├── «⚠️ Роздільність 72 DPI — рекомендуємо 300 DPI»
        ├── «ℹ️ Що таке DPI?» [Tooltip Card]
        ├── «📞 Потрібна допомога? [Звʼязатися з менеджером]»
        └── «🔧 Ми можемо виправити це за вас (+100 грн)»
8.3. Как эффекты поддерживают UX-стратегию
Эффект	Для новичков	Для профессионалов
Multi-Step Loader	«Ми перевіряємо ваш файл...» — снижает тревогу	Индикатор прогресса — подтверждение что система работает
Tooltip Card	Объяснение терминов	Быстрый справочник
Compare	«Ось різниця в якості!»	Демонстрация клиентам
Vanish Input	Подсказки что можно заказать	Быстрый поиск по артикулу
Stateful Button	«Надіслано ✅» — уверенность	Мгновенный feedback
8.4. Психологические принципы в эффектах
Эффект Зейгарник (Zeigarnik Effect): Multi-Step Loader «ви на кроці 3 з 5» — пользователь хочет дойти до конца
Социальное доказательство (Social Proof): Infinite Moving Cards + «Уже надруковано: 15,247 метрів»
Эффект IKEA: Конструктор, где пользователь «собирает» заказ → повышает воспринимаемую ценность
Управление ожиданиями: Compare «экран vs печать» предупреждает о разнице ДО заказа → меньше возвратов
Микро-вознаграждения: Sparkle при успешной загрузке, Stateful Button → зелёная галочка
9. ИНТЕГРАЦИЯ В DJANGO: ФАЙЛОВАЯ СТРУКТУРА
9.1. Структура файлов проекта
text

twocomms/dtf/
├── static/dtf/
│   ├── css/
│   │   ├── dtf.css                    # Основные стили
│   │   ├── effects/
│   │   │   ├── compare.css
│   │   │   ├── multi-step-loader.css
│   │   │   ├── infinite-cards.css
│   │   │   ├── floating-dock.css
│   │   │   ├── vanish-input.css
│   │   │   ├── tooltip-card.css
│   │   │   ├── text-generate.css
│   │   │   ├── flip-words.css
│   │   │   ├── sparkles.css
│   │   │   ├── bg-beams.css
│   │   │   ├── tracing-beam.css
│   │   │   ├── stateful-button.css
│   │   │   ├── encrypted-text.css
│   │   │   └── images-badge.css
│   │   └── effects.bundle.css         # Объединённый для продакшн
│   │
│   ├── js/
│   │   ├── core.js                    # Реестр эффектов + автоинициализация
│   │   ├── _utils.js                  # Утилиты (cn, throttle, debounce, observer)
│   │   ├── components/
│   │   │   ├── effect.compare.js
│   │   │   ├── effect.multi-step-loader.js
│   │   │   ├── effect.infinite-cards.js
│   │   │   ├── effect.floating-dock.js
│   │   │   ├── effect.vanish-input.js
│   │   │   ├── effect.tooltip-card.js
│   │   │   ├── effect.text-generate.js
│   │   │   ├── effect.flip-words.js
│   │   │   ├── effect.sparkles.js
│   │   │   ├── effect.bg-beams.js
│   │   │   ├── effect.tracing-beam.js
│   │   │   ├── effect.stateful-button.js
│   │   │   ├── effect.encrypted-text.js
│   │   │   └── effect.images-badge.js
│   │   └── dtf.js                     # Бизнес-логика (ОЧИСТИТЬ от legacy!)
│   │
│   └── img/
│       ├── compare/                   # Изображения для Compare
│       ├── partners/                  # Логотипы партнёров
│       └── tooltips/                  # Миниатюры для Tooltip Card
│
├── templates/dtf/
│   ├── base.html
│   ├── includes/
│   │   ├── _compare.html
│   │   ├── _infinite-cards.html
│   │   ├── _floating-dock.html
│   │   ├── _multi-step-loader.html
│   │   └── _tooltip.html
│   ├── home.html
│   ├── order.html
│   ├── constructor.html
│   ├── gallery.html
│   ├── blog/
│   │   ├── list.html
│   │   └── detail.html
│   └── requirements.html
│
└── views.py / urls.py / models.py
9.2. core.js — сердце системы эффектов
JavaScript

// core.js — Реестр эффектов для Django DTF
(function() {
  'use strict';
  
  const DTFEffects = {
    _registry: {},
    _initialized: new WeakSet(),
    
    register(name, initFn) {
      this._registry[name] = initFn;
    },
    
    initAll(root = document) {
      const elements = root.querySelectorAll('[data-effect]');
      elements.forEach(el => {
        if (this._initialized.has(el)) return; // Идемпотентность
        
        const effectName = el.dataset.effect;
        const initFn = this._registry[effectName];
        
        if (initFn) {
          const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
          
          const heavyEffects = ['bg-beams', 'sparkles', 'dotted-glow', 'infinite-cards'];
          
          if (heavyEffects.includes(effectName)) {
            this._lazyInit(el, initFn, prefersReduced);
          } else {
            initFn(el, { prefersReduced });
          }
          
          this._initialized.add(el);
        }
      });
    },
    
    _lazyInit(el, initFn, prefersReduced) {
      const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            initFn(el, { prefersReduced });
            observer.unobserve(el);
          }
        });
      }, { rootMargin: '200px' });
      observer.observe(el);
    }
  };
  
  document.addEventListener('DOMContentLoaded', () => DTFEffects.initAll());
  document.addEventListener('htmx:afterSwap', (e) => DTFEffects.initAll(e.target));
  
  window.DTFEffects = DTFEffects;
})();
9.3. Z-Index стандарт
CSS

:root {
  /* Content layers */
  --z-base: 1;
  --z-dropdown: 10;
  --z-sticky: 20;
  --z-header: 30;
  
  /* Navigation */
  --z-dock: 40;
  --z-chat-widget: 45;
  
  /* Overlays */
  --z-modal-backdrop: 50;
  --z-modal: 55;
  --z-toast: 60;
  --z-tooltip: 70;
  
  /* Critical overlays */
  --z-loader-overlay: 100;
  --z-loader-close-btn: 120;
}
9.4. Обязательный рефакторинг (из CODEX)
Что удалить из dtf.js:

initCompare() — перенесено в components/effect.compare.js
initTracingBeam() — перенесено в components/effect.tracing-beam.js
Любые другие legacy-функции инициализации эффектов
Почему: Дублирование создаёт рассинхрон — одна версия обновляется, другая (legacy) — нет. Единый источник истины — components/.

10. КОНСОЛИДИРОВАННЫЙ ТОП ИДЕЙ ИЗ ВСЕХ АГЕНТОВ
10.1. Обязательные (консенсус + бизнес-требования)
#	Идея	Компонент	Где	Приоритет	Источник
1	Многоступенчатый загрузчик при загрузке файла	Multi-Step Loader	Форма заказа / Конструктор	🔴 Критический	Все агенты
2	Слайдер сравнения «макет vs печать»	Compare	Главная, Галерея	🔴 Критический	Все агенты
3	Автопроверка макета (DPI, цветовой профиль, размер)	Multi-Step Loader + бэкенд	Конструктор	🔴 Критический	Бизнес-требование
4	Бесконечная карусель партнёров/отзывов	Infinite Moving Cards	Главная, Футер	🟡 Высокий	Все агенты
5	Исправление конфликта FAB/Dock	Floating Dock	Глобально	🔴 Критический	Все агенты
6	Поисковое поле с анимированными подсказками	Vanish Input	Главная, Навигация	🟡 Высокий	Claude, CODEX, Gemini 3
7	Тултипы с объяснением терминов	Tooltip Card	Требования, FAQ, Конструктор	🟡 Высокий	Claude, CODEX
8	Кнопки с состоянием (отправка → успех)	Stateful Button	Все формы	🟡 Высокий	Claude, CODEX
9	Удаление legacy-дублей из dtf.js	Рефакторинг	Глобально	🔴 Критический	CODEX
10	Flip Words «Друкуємо на [X]»	Flip Words	Главная (Hero)	🟢 Средний	Claude, CODEX
10.2. Рекомендуемые (сильные идеи)
#	Идея	Компонент	Откуда	Обоснование
11	Бегущая строка «Надруковано X метрів»	Infinite Cards + API	Gemini 1.5	Social proof в реальном времени
12	Preflight-чеклист (серия проверок с галочками)	Custom	CODEX, Gemini 3	Прозрачность процесса
13	Encrypted Text для стоимости	Encrypted Text	Claude	Wow-эффект при расчёте цены
14	Sparkle при успешной загрузке	Sparkles	Claude, Gemini 1.5	Микро-вознаграждение
15	Tracing Beam в блоге	Tracing Beam	Claude, CODEX	Прогресс чтения
16	Compare «DPI: 72 vs 300»	Compare	Gemini 3	Обучение клиента
17	Images Badge на загруженных файлах	Images Badge	effects.md	Визуальный статус
18	Text Generate для ключевых заголовков	Text Generate	effects.md	Wow-эффект появления
19	Калькулятор стоимости с анимацией	Text Generate + логика	Бизнес-требование	Расчёт метража
20	Badge статуса на файле (проверяется/ок/ошибка)	Custom CSS	CODEX	Обратная связь
10.3. Идеи «на вырост» (долгосрочные)
#	Идея	Источник	Когда
21	Odometer-эффект для цены	Antigravity	Sprint 4
22	BlurHash для ленивой загрузки изображений	Antigravity	Sprint 3
23	Shared Element Transition в галерее	Antigravity	Sprint 4
24	Border Beam на CTA-кнопках	Antigravity	Sprint 2
25	Ripple-эффект на кнопках	Antigravity	Sprint 2
26	Branded loader (логотип заполняется «чернилами»)	Antigravity	Sprint 2
27	Skeleton screens вместо спиннеров	Antigravity	Sprint 3
28	Пасхалка Konami Code → промокод	Gemini 1.5 + Antigravity	Sprint 4
29	Haptic feedback на мобильных	Gemini 1.5	После MVP
30	Микро-звуки интерфейса	Gemini 1.5	После тестирования
31	Realtime-очередь заказов	Gemini 1.5	При масштабировании
32	EyeDropper API для выбора цвета	Gemini 1.5	В конструкторе v2
33	3D-превью худи с принтом	Three.js (Gemini 1.5 / Antigravity)	Долгосрочно — киллер-фича
34	Web Components (миграция)	Gemini 1.5	Если проект значительно вырастет
11. ДОРОЖНАЯ КАРТА ВНЕДРЕНИЯ
Sprint 1 — «Фундамент» (Неделя 1-2)
Цель: Убрать критические проблемы, добавить обязательные элементы

#	Задача	Файлы	Дней
1	Удалить FAB, интегрировать менеджера в Dock	base.html, dtf.css	1
2	Multi-Step Loader (с привязкой к реальному процессу)	новый: effect.multi-step-loader.js/css, _multi-step-loader.html	3-5
3	Compare dual-mode + touch-action	effect.compare.js	2
4	Vanish Input: clear + cycling placeholders	effect.vanish-input.js	1-2
5	Infinite Cards SEO-safe	effect.infinite-cards.js	1-2
6	Рефакторинг dtf.js (удалить legacy)	dtf.js	1
Результат Sprint 1: Рабочий процесс загрузки → проверка → результат. Основные UX-проблемы решены.

Итого: 9-13 дней

Sprint 2 — «Wow-эффект» (Неделя 3-4)
Цель: Визуальная привлекательность и социальное доказательство

#	Задача	Файлы	Дней
7	Tooltip Card	новый	2
8	Flip Words	новый	0.5
9	Images Badge	новый	1
10	Text Generate Effect	новый	0.5
11	Stateful Button расширение	существующий	1
12	Sparkle при успешной загрузке	существующий	0.5
13	Encrypted Text для стоимости	существующий	0.5
Результат Sprint 2: Сайт вызывает «wow» при первом посещении. Trust-факторы на месте.

Итого: 6 дней

Sprint 3 — «Оптимизация и стабилизация» (Неделя 5-6)
Цель: SEO, производительность, edge-cases

#	Задача	Дней
14	Lighthouse аудит + оптимизация (CLS, LCP, INP → зелёная зона)	2
15	Мобильное тестирование (iOS Safari, Android Chrome, медленный интернет)	2
16	<noscript> fallback для всех анимаций	1
17	prefers-reduced-motion для всех эффектов	1
18	A/B флаги для тяжёлых эффектов (быстрое отключение)	1
19	JSON-LD разметка (отзывы, FAQ, продукты)	1
20	BlurHash для изображений	1
Итого: 9 дней

Sprint 4 — «Расширение» (Неделя 7-8, опционально)
#	Задача	Дней
21	Tracing Beam оптимизация	1
22	Compare «72 DPI vs 300 DPI»	1
23	Пасхалка Konami Code	0.5
24	Калькулятор стоимости с анимацией	3
25	Realtime-бегущая строка «надруковано X метрів»	2
26	Odometer-эффект для цены	1
27	Border Beam / Ripple на кнопках	1
12. ТОЧНЫЕ СПЕЦИФИКАЦИИ ЗАДАЧ ДЛЯ CODEX
Этот раздел — готовый тех.задание для coding-агента.

Sprint 1: Задачи
ЗАДАЧА 1: Исправление конфликта FAB/Dock
Файлы для изменения:

twocomms/dtf/templates/dtf/base.html
twocomms/dtf/static/dtf/css/dtf.css
twocomms/dtf/static/dtf/js/components/effect.floating-dock.js
Что сделать:

Найти div#dtf-fab (~строки 255-260 в base.html) → УДАЛИТЬ
Элемент "Менеджер" перенести внутрь Floating Dock как пункт
CSS: один floating-элемент на breakpoint (см. код выше)
Z-index стратегия (см. раздел 9.3)
ЗАДАЧА 2: Multi-Step Loader
Создать файлы:

effect.multi-step-loader.js
