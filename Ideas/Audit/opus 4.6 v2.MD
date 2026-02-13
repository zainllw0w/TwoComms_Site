📋 ЕДИНЫЙ КОНСОЛИДИРОВАННЫЙ ОТЧЁТ: Визуальные эффекты для dtf.twocomms.shop

Версия: FINAL | Консолидация v1 + v2

НАЗНАЧЕНИЕ ЭТОГО ДОКУМЕНТА

Для AI-агентов: Этот отчёт — единственный источник истины для всех последующих итераций анализа, сравнения и генерации промптов. Любой агент, получающий этот документ, должен опираться на него как на базу, а не пересоздавать анализ с нуля.

Для человека: Полная картина проекта, принятых решений, приоритетов и следующих шагов.

ОГЛАВЛЕНИЕ

Проект и контекст
Цепочка исследований и карта агентов
Консенсус и расхождения агентов
Принятое архитектурное решение
Контракт портирования React → Vanilla JS
Покомпонентный разбор всех эффектов
SEO, производительность, Core Web Vitals
Психология дизайна и UX-стратегия
Консолидированный ТОП идей
Дорожная карта внедрения
Риски и митигация
Точные спецификации для Codex (Sprint 1–3)
Открытые вопросы к владельцу
Промпт-заготовка для следующего этапа
1. ПРОЕКТ И КОНТЕКСТ

1.1. Что такое dtf.twocomms.shop
Субдомен основного бренда одежды twocomms.shop. Самостоятельная сервисная платформа для:

Продажи DTF-плёнки (Direct-to-Film)
Нанесения принтов на одежду
Партнёрского взаимодействия с швейными фабриками, брендами и B2B-клиентами
Ключевые функции платформы:

Конструктор заказов (загрузка макетов, drag-and-drop)
Автопроверка макетов (DPI, цветовой профиль, размер)
Калькулятор стоимости
Система оформления заказа
Галерея работ
Блог / база знаний
1.2. Технический стек
Слой	Технология
Backend	Python Django
Frontend	Vanilla JS + HTMX + CSS
Шаблоны	Django Templates
Фреймворки JS	Нет (без React/Next.js/Angular)
Интерактивность	Progressive enhancement через JavaScript
1.3. Две аудитории (критически важно для UX)
Аудитория А — «Новички»	Аудитория Б — «Профессионалы»
Знания	Не знают DPI, CMYK, bleed	Знают всё
Поведение	Боятся ошибиться, нуждаются в помощи	Хотят self-service за 2 минуты
Потребность	Объяснения + поддержка менеджера	Скорость + минимум «лишнего»
Решение: Один интерфейс с адаптивной сложностью (подробнее в разделе 8).

2. ЦЕПОЧКА ИССЛЕДОВАНИЙ И КАРТА АГЕНТОВ

2.1. Хронология
Этап	Агент	Кодовое имя	Задача
1	Claude 4 Sonnet	«Системный архитектор»	100 идей в табличном формате, план интеграции
1	CODEX (OpenAI)	«Практичный инженер»	Глубокий аудит кода, 100 идей, 3 спринта
1	Gemini 1.5 Pro	«Визионер-инноватор»	Web Components, haptics, психология UX
2	GPT-5.2 Pro	«Арбитр»	Сравнительный анализ трёх агентов
3	Gemini 3 Pro	«Технический стратег»	Aceternity UI, Next.js 15, Tailwind v4
4	Claude 4 Sonnet (2-й)	«Antigravity»	Гибрид React+Vite в Django, 100 идей по страницам
5	Claude Opus 4	«Мета-аналитик»	Мега-отчёт v1 + v2, консолидация всего
2.2. Что каждый агент сделал ЛУЧШЕ всех
Агент	Сильная сторона	Что взять
CODEX	Самый глубокий аудит существующего кода: подсчёт использований (6× compare, 4× bg-beams), размеры файлов (gzip), обнаружение legacy-дублей в dtf.js	План CODEX — основа для спринтов
Claude 4 Sonnet (1-й)	Табличный формат 100 идей с приоритетами — готовый backlog. Внимание к a11y.	Структура идей — готовый backlog
Gemini 1.5 Pro	Психологические паттерны (доверие, геймификация, wow). Бюджет производительности. Идеи: haptic, пасхалки, реалтайм-индикаторы.	Бюджет производительности + инновационные идеи на будущее
Gemini 3 Pro	Детальный разбор 5 компонентов Aceternity UI. CLS-проблемы. touch-action. «Листовые компоненты». DTF-специфика (Gang Sheets, DPI).	Технические нюансы портирования компонентов
GPT-5.2 Pro	Корректный арбитраж: CODEX — самый реалистичный, Claude — лучший справочник, Gemini — вдохновение.	Валидация общей стратегии
Antigravity	100 идей по конкретным страницам. Odometer для цены. BlurHash. Shared Element Transition.	Каталог идей по страницам + отдельные wow-фичи
2.3. Финальный рейтинг полезности
Критерий	CODEX	Claude 4 (1-й)	Gemini 1.5	Gemini 3	GPT-5.2	Antigravity
Аудит кода	⭐⭐⭐⭐⭐	⭐⭐⭐	⭐⭐	⭐⭐	⭐	⭐⭐
Практичность	⭐⭐⭐⭐⭐	⭐⭐⭐⭐	⭐⭐⭐	⭐⭐⭐⭐	⭐⭐⭐	⭐⭐⭐
Инновационность	⭐⭐⭐	⭐⭐⭐	⭐⭐⭐⭐⭐	⭐⭐⭐⭐	⭐⭐	⭐⭐⭐⭐
SEO-грамотность	⭐⭐⭐⭐	⭐⭐⭐⭐	⭐⭐⭐	⭐⭐⭐⭐⭐	⭐⭐⭐	⭐⭐⭐
Понимание DTF	⭐⭐⭐⭐⭐	⭐⭐⭐⭐	⭐⭐⭐⭐	⭐⭐⭐⭐⭐	⭐⭐⭐	⭐⭐⭐
3. КОНСЕНСУС И РАСХОЖДЕНИЯ АГЕНТОВ

3.1. Полный консенсус (все агенты согласны)
Пункт	Статус
Vanilla JS лучше React для текущего проекта	✅ Все (Gemini 1.5 предлагает Web Components, Antigravity — React+Vite, но остальные 4 — за Vanilla)
FAB-кнопка менеджера конфликтует с Floating Dock	✅ Все 6 агентов
Multi-Step Loader обязателен для загрузки файлов	✅ Все
Compare обязателен для демонстрации качества	✅ Все
Infinite Moving Cards для социального доказательства	✅ Все
SEO требует отдельного внимания при анимациях	✅ Все
Производительность — приоритет	✅ Все
Мобильная адаптация критична	✅ Все
3.2. Точки расхождения
Вопрос	Claude 4	CODEX	Gemini 1.5	Gemini 3	Antigravity	Принятое решение
Архитектура фронтенда	Vanilla JS	Vanilla JS	Web Components	Next.js 15	React+Vite	Vanilla JS + CSS
Библиотека анимаций	Vanilla	Vanilla	Motion One (~5KB)	framer-motion	framer-motion	CSS transitions + requestAnimationFrame
Haptic feedback	—	—	✅	—	—	Отложить (после MVP)
Звуковые эффекты	—	—	✅	—	—	Отложить (тестировать с пользователями)
3D-эффекты	Ограниченно	Ограниченно	Three.js	Критикует за FPS	Three.js	Долгосрочно (Sprint 4+)
3.3. Уникальные находки каждого агента
CODEX:

Количественный аудит: сколько раз каждый эффект используется (6× compare, 4× bg-beams, 3× encrypted-text, 3× tracing-beam, 1× sparkles, 1× infinite-cards)
Legacy-дубли в dtf.js: initCompare(), initTracingBeam() — дублируют модули
Размеры файлов: ~17KB gzip суммарно — есть запас по бандлу
Оценка трудоёмкости: простые 1-2 дня, средние 3-5, сложные 5-10
Claude 4 Sonnet:

Табличный формат идей → готовый backlog для Jira/Trello
Конфликт FAB с Dock — обнаружен первым
Подробные плюсы/минусы для каждого компонента
Gemini 1.5 Pro:

Группировка идей по психологическим паттернам (доверие, контроль, геймификация)
Бюджет производительности: CLS < 0.1, INP < 200ms, JS < 150KB gzip, 60fps
Идеи: пасхалка Konami Code → скидка, реалтайм-индикаторы (очередь заказов, остаток плёнки)
Motion One (~5KB) вместо framer-motion (~30KB)
Gemini 3 Pro:

CLS от текстовых эффектов — глубокий анализ проблемы
touch-action: none для решения конфликта свайпов в Compare
Архитектура «листовых компонентов» (изоляция клиентского кода)
DTF-специфика: Gang Sheets, DPI-проверка, RGB vs CMYK
Antigravity:

100 идей разбиты по конкретным страницам (Landing, Constructor, Gallery, Price, Blog, Cabinet, Cart)
Odometer-эффект для цены
BlurHash для ленивой загрузки изображений
Shared Element Transition для галереи
4. ПРИНЯТОЕ АРХИТЕКТУРНОЕ РЕШЕНИЕ

4.1. Вердикт: Django + Vanilla JS — правильный выбор
Аргументы ЗА:

Проект уже построен на Django — менять бэкенд нецелесообразно
HTMX уже используется и отлично работает с Django
Vanilla JS даёт максимальный контроль над размером бандла
Нет overhead от React runtime (~40KB min+gzip)
Компоненты Aceternity UI — это CSS-анимации + JS-логика, портируемые
SEO-friendly: Django рендерит HTML на сервере, JS — progressive enhancement
Почему НЕ React/Next.js:

Полная перестройка фронтенда — месяцы работы
Потеря преимуществ серверного рендеринга Django
Увеличение сложности деплоя (два сервера)
React hydration может конфликтовать с Django-шаблонами
Почему НЕ Web Components:

Shadow DOM усложняет отладку стилей
Требует рефакторинга ВСЕХ существующих эффектов
Минимальный выигрыш при текущем масштабе проекта
Единственное исключение: React+Vite (идея Antigravity) может быть полезна в БУДУЩЕМ для изолированного тяжёлого компонента (3D-вьювер на Three.js), который встраивается в Django-страницу как island.

4.2. Архитектурная схема
text

┌──────────────────────────────────────────────┐
│                   DJANGO                      │
│    (серверный рендеринг HTML-шаблонов)        │
│                                               │
│  base.html → подключает:                     │
│    ├── dtf.css (основные стили)               │
│    ├── effects/*.css (стили эффектов)         │
│    ├── core.js (реестр эффектов)              │
│    ├── _utils.js (cn, throttle, debounce)    │
│    └── components/effect.*.js (модули)        │
│                                               │
│  Шаблоны используют data-attributes:         │
│    <div data-effect="compare"                 │
│         data-first-image="..."                │
│         data-second-image="...">              │
│    </div>                                     │
│                                               │
│  core.js при DOMContentLoaded:               │
│    → Находит [data-effect]                   │
│    → Вызывает соответствующий init()         │
│    → Поддерживает HTMX re-init              │
│    → Lazy-load тяжёлых эффектов              │
│       через IntersectionObserver              │
└──────────────────────────────────────────────┘
4.3. Ключевые принципы
Прогрессивное улучшение: Без JS сайт показывает статический контент
Модульность: Каждый эффект = отдельный effect.{name}.js + effects/{name}.css
Идемпотентная инициализация: Повторный вызов init() не дублирует эффект
HTMX-совместимость: Re-init при htmx:afterSwap
Lazy-loading: Тяжёлые эффекты подгружаются при видимости (IntersectionObserver)
4.4. Структура файлов проекта
text

twocomms/dtf/
├── static/dtf/
│   ├── css/
│   │   ├── dtf.css                        # Основные стили
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
│   │   └── effects.bundle.css             # Объединённый для продакшн
│   │
│   ├── js/
│   │   ├── core.js                        # Реестр эффектов + авто-init
│   │   ├── _utils.js                      # Утилиты (cn, throttle, debounce, observer)
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
│   │   └── dtf.js                         # Бизнес-логика (ОЧИСТИТЬ от legacy!)
│   │
│   └── img/
│       ├── compare/                       # Пары до/после
│       ├── partners/                      # Логотипы партнёров
│       └── tooltips/                      # Миниатюры для Tooltip Card
│
├── templates/dtf/
│   ├── base.html
│   ├── includes/
│   │   ├── _compare.html
│   │   ├── _infinite-cards.html
│   │   ├── _floating-dock.html
│   │   ├── _multi-step-loader.html
│   │   ├── _tooltip.html
│   │   └── _flip-words.html
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
4.5. core.js — сердце системы
JavaScript

// core.js — Реестр эффектов для Django DTF
(function() {
  'use strict';
  
  const DTF = (window.DTF = window.DTF || {});
  const registry = {};
  const initialized = new WeakSet();
  const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const heavyEffects = ['bg-beams', 'sparkles', 'dotted-glow', 'infinite-cards'];
  
  DTF.registerEffect = function(name, selector, initFn) {
    registry[name] = { selector, initFn };
  };
  
  DTF.initAll = function(root) {
    root = root || document;
    const elements = root.querySelectorAll('[data-effect]');
    
    elements.forEach(function(el) {
      if (initialized.has(el)) return;
      
      var effectName = el.dataset.effect;
      var entry = registry[effectName];
      if (!entry) return;
      
      var ctx = { reducedMotion: prefersReduced };
      
      if (heavyEffects.indexOf(effectName) !== -1) {
        lazyInit(el, entry.initFn, ctx);
      } else {
        entry.initFn(el, ctx);
      }
      
      initialized.add(el);
    });
  };
  
  function lazyInit(el, initFn, ctx) {
    var observer = new IntersectionObserver(function(entries) {
      entries.forEach(function(entry) {
        if (entry.isIntersecting) {
          initFn(el, ctx);
          observer.unobserve(el);
        }
      });
    }, { rootMargin: '200px' });
    observer.observe(el);
  }
  
  // Инициализация
  document.addEventListener('DOMContentLoaded', function() { DTF.initAll(); });
  
  // HTMX совместимость
  document.addEventListener('htmx:afterSwap', function(e) { DTF.initAll(e.target); });
})();
4.6. Что адаптировано из отчёта Gemini 3 Pro (Next.js → Django)
Рекомендация Gemini 3 (Next.js)	Адаптация для Django
"use client" изоляция	Не нужна — Django рендерит всё на сервере
Tailwind v4 @theme	CSS Custom Properties (--color-brand-primary)
React 19 overrides	Нерелевантно
IntersectionObserver lazy-load	✅ Полностью применимо
touch-action: none для свайпов	✅ Полностью применимо
WebP для изображений	✅ Полностью применимо
aria-hidden для дубликатов	✅ Полностью применимо
Z-Index стратегия	✅ Полностью применимо
5. КОНТРАКТ ПОРТИРОВАНИЯ React → Vanilla JS

Для агентов: Этот раздел — обязательная инструкция для любого coding-агента, создающего компоненты.

5.1. Общие зависимости Aceternity UI и их замены
text

React (useState, useRef, useEffect)    →  DOM API + класс/closure
motion/react (framer-motion)           →  CSS transitions/animations + requestAnimationFrame
clsx + tailwind-merge (cn())           →  Простая функция cn() в _utils.js
@tabler/icons-react                    →  SVG иконки инлайн или sprite
5.2. Таблица соответствий React → Vanilla
React-концепция	Vanilla-аналог	Пример
useState(value)	Переменная в closure + DOM-обновление	let isVisible = false;
useRef(null)	document.querySelector() или параметр node	const el = node.querySelector('.inner');
useEffect(() => {}, [deps])	Код в теле initEffect(node)	Инициализация при вызове
AnimatePresence	CSS transition + classList.toggle	.tooltip { transition: opacity 0.3s; }
motion.div с initial/animate/exit	CSS keyframes или JS requestAnimationFrame	@keyframes fadeIn { ... }
onMouseEnter/Move/Leave	addEventListener(...)	Идентично
JSX {isVisible && <div>}	el.style.display = isVisible ? '' : 'none'	Условное отображение
className={cn("base", cond)}	el.classList.toggle('active', condition)	Динамические классы
style={{ top: pos.y }}	el.style.top = pos.y + 'px'	Инлайн стили
{children}	innerHTML или контент внутри элемента	Контент из HTML
5.3. Шаблон JS-модуля эффекта
JavaScript

// static/dtf/js/components/effect.{name}.js
(function () {
  'use strict';
  
  const DTF = (window.DTF = window.DTF || {});

  /**
   * @param {HTMLElement} node — контейнер с data-effect="{name}"
   * @param {Object} ctx — { reducedMotion: boolean }
   * @returns {Function|null} cleanup function
   */
  function init{Name}(node, ctx) {
    if (!node) return null;
    
    // 1. Reduced-motion fallback
    if (ctx && ctx.reducedMotion) {
      node.classList.add('is-static');
      return null;
    }
    
    // 2. Чтение конфигурации из data-attributes
    const config = { /* ... */ };
    
    // 3. DOM-структура (если нужно)
    
    // 4. Привязка событий
    
    // 5. Cleanup
    return function cleanup() {
      // removeEventListener, cancelAnimationFrame, etc.
    };
  }

  // Регистрация
  if (DTF.registerEffect) {
    DTF.registerEffect('{name}', '[data-effect~="{name}"]', init{Name});
  }
})();
5.4. Шаблон CSS-модуля эффекта
CSS

/* static/dtf/css/effects/{name}.css */

/* Base State — без JS */
[data-effect~="{name}"] {
  min-height: var(--effect-{name}-height, auto);
  position: relative;
  overflow: hidden;
}

/* Animated State — после init JS */
[data-effect~="{name}"].is-initialized {
  /* стили после инициализации */
}

/* Static / Reduced Motion */
[data-effect~="{name}"].is-static,
@media (prefers-reduced-motion: reduce) {
  [data-effect~="{name}"] {
    animation: none !important;
    transition: none !important;
  }
}

/* Animations */
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
6. ПОКОМПОНЕНТНЫЙ РАЗБОР ВСЕХ ЭФФЕКТОВ

6.1. Сводная матрица
Компонент	Статус	Действие	Приоритет	Сложность портирования	Sprint
Compare	✅ Реализован (6×)	Доработать: dual-mode, touch-action	🔴 Критический	🟡 Средняя	1
Multi-Step Loader	❌ Не реализован	Создать с нуля, привязать к Celery	🔴 Критический	🔴 Сложная	1
Floating Dock	⚠️ Конфликт с FAB	Исправить: удалить FAB, оставить Dock	🔴 Критический	🟡 Средняя (magnification)	1
Vanish Input	⚠️ Частично	Доработать: cycling placeholders + clear	🟡 Высокий	🟢 Простая (упрощённая версия)	1
Infinite Moving Cards	⚠️ Частично (1×)	Доработать: SEO-safe, больше контента	🟡 Высокий	🟢 Простая	1
Tooltip Card	❌ Не реализован	Создать	🟡 Высокий	🟡 Средняя	2
Flip Words	❌ Не реализован	Создать	🟢 Средний	🟢 Простая	2
Text Generate Effect	❌ Не реализован	Создать	🟢 Средний	🟢 Простая	2
Images Badge	❌ Не реализован	Создать	🟡 Высокий	🟢 Простая (CSS)	2
Stateful Button	✅ Реализован	Расширить на все формы	🟡 Высокий	🟢 Простая	2
Encrypted Text	✅ Реализован (3×)	Проверить SEO, reduced-motion	🟢 Низкий	🟢 Простая	3
Tracing Beam	✅ Реализован (3×)	Оптимизировать	🟢 Низкий	🟡 Средняя (SVG + scroll)	3
Dotted Glow	✅ Реализован (4×)	Добавить IntersectionObserver	🟢 Низкий	🟢 Простая	3
BG Beams	✅ Реализован (4×)	Оптимизировать	🟢 Низкий	🟢 Простая	3
Sparkles	✅ Реализован (1×)	Оптимизировать	🟢 Низкий	🟢 Простая	3
Sidebar	❌ Не реализован	Отложить	🟢 Низкий	🟡 Средняя	4+
Cover	❌ Не реализован	Отложить	🟢 Низкий	🟡 Средняя	4+
Animated Tooltip	❌ Не реализован	Отложить	🟢 Низкий	🟢 Простая	4+
6.2. Детальный разбор каждого компонента
🔴 Compare (Слайдер До/После) — КРИТИЧЕСКИЙ

Статус: Реализован (6 использований). Нужна доработка.

Бизнес-ценность для DTF:

«Макет на экране» vs «Отпечаток на ткани» — управление ожиданиями
72 DPI vs 300 DPI — обучение клиента
DTF vs шелкография — конкурентное преимущество
RGB на экране vs реальный цвет — снижение возвратов
Что делает оригинал (из effects.md):

Два изображения наложены, ползунок управляет clip-path/маской
Режимы: hover, drag
Autoplay с настраиваемой длительностью
Sparkles-эффект на ручке
Что доработать:

Dual-mode (идея CODEX): data-autoplay="true" → auto-sweep 2-3 цикла → freeze на ручном управлении
Touch: touch-action: pan-y на контейнере (Gemini 3) — вертикальный скролл работает, горизонтальный перехватывается Compare
Мобильные: Только drag-режим (data-slide-mode="drag" при matchMedia('(hover: none)'))
Изображения: WebP, srcset для responsive, lazy-load для второго изображения
SEO: alt-тексты на обоих изображениях. <noscript> fallback с двумя картинками рядом.

Accessibility: aria-label на ручке, role="slider", aria-valuemin/max/now.

🔴 Multi-Step Loader — КРИТИЧЕСКИЙ

Статус: Не реализован. Создать с нуля.

Почему критически важен:
Клиент загружает файл (иногда сотни MB), стандартный спиннер вызывает тревогу. Multi-Step Loader превращает ожидание в демонстрацию компетентности:

text

Этап 1: «📤 Завантаження файлу на захищений сервер...» (реальный прогресс)
Этап 2: «🔍 Перевірка роздільності (DPI)...»
Этап 3: «🎨 Аналіз колірного профілю...»
Этап 4: «📐 Розрахунок площі та вартості...»
Этап 5: «✅ Генерація превʼю для підтвердження...»
Что делает оригинал (из effects.md):

Массив loadingStates: [{text: "..."}]
Полноэкранный overlay
Текущий шаг подсвечен, предыдущие — галочка, следующие — серые
Анимация переключения (slide up)
Настраиваемые: duration, loop, value
Связь с бэкендом:

text

Фронт                       →  Django Celery Task
"Завантаження файлу"        →  xhr.upload.onprogress
"Перевірка DPI"             →  task.step = 'dpi'
"Аналіз кольорів"           →  task.step = 'colors'
"Розрахунок площі"          →  task.step = 'area'
"Генерація превʼю"          →  task.step = 'preview'
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
      this.pollServerStatus(JSON.parse(xhr.responseText).taskId);
    });
    xhr.open('POST', uploadUrl);
    xhr.send(formData);
  }
  
  async pollServerStatus(taskId) {
    const res = await fetch(`/api/task-status/${taskId}/`);
    const data = await res.json();
    this.advanceTo(data.step);
    if (data.status !== 'completed' && data.status !== 'error') {
      setTimeout(() => this.pollServerStatus(taskId), 1000);
    }
  }
}
Публичный API:

JavaScript

DTF.multiStepLoader.show(taskId)    // показать overlay
DTF.multiStepLoader.hide()          // скрыть
DTF.multiStepLoader.setStep(index)  // перейти к шагу
DTF.multiStepLoader.bindToUpload(formData)  // привязать к загрузке
HTML-контракт:

HTML

<div data-effect="multi-step-loader"
     data-steps='[
       {"text": "📤 Завантаження файлу...", "key": "upload"},
       {"text": "🔍 Перевірка DPI...", "key": "dpi"},
       {"text": "🎨 Аналіз кольорів...", "key": "colors"},
       {"text": "📐 Розрахунок площі...", "key": "area"},
       {"text": "✅ Генерація превʼю...", "key": "preview"}
     ]'
     data-poll-url="/api/task-status/"
     data-upload-url="/api/upload/"
     style="display: none;"
     aria-live="polite">
</div>
🔴 Floating Dock — КРИТИЧЕСКИЙ (конфликт)

Проблема (подтверждена ВСЕМИ 6 агентами):
FAB-кнопка менеджера, Floating Dock и мобильная навигация — три элемента в одной области экрана.

Что делает оригинал (из effects.md):

MacOS-style dock внизу экрана
Magnification при наведении (иконки увеличиваются — Gaussian-like расчёт расстояния)
Tooltip с title при hover
Отдельные Mobile/Desktop версии
framer-motion MotionValue для мыши
Решение (консолидированное):

Устройство	Решение
Desktop (≥961px)	Floating Dock по центру внизу с magnification. FAB удалить — менеджер как элемент Dock.
Mobile (<960px)	Упрощённый Tab Bar БЕЗ magnification. Touch-feedback (scale при тапе).
Vanilla JS для magnification:

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
CSS (breakpoints):

CSS

@media (min-width: 961px) {
  .dtf-floating-dock { display: flex; }
  .mobile-dock { display: none !important; }
}
@media (max-width: 960px) {
  .dtf-floating-dock { display: none !important; }
  .mobile-dock { display: flex; }
}
🟡 Vanish Input — ВЫСОКИЙ ПРИОРИТЕТ

Статус: Реализован частично, не соответствует бизнес-требованиям (CODEX).

Что делает оригинал (из effects.md):

Массив placeholder'ов, циклически сменяются
При submit — Canvas-анимация «рассыпания» текста на частицы
Кнопка submit меняет стиль
Рекомендация — упрощённая версия (90% эффекта, 10% сложности):

Placeholder cycling — через CSS animation или JS setInterval
Vanish — через CSS: transform: scale(0.8) + opacity: 0 + filter: blur(4px) ВМЕСТО Canvas
DTF-placeholders:

JavaScript

const placeholders = [
  "Пошук за артикулом...",
  "Футболки бавовна 100%...",
  "DTF плівка 60 см...",
  "UV-наклейки на замовлення...",
  "Худі з вашим принтом..."
];
SEO: Меняющийся placeholder — не контент для индексации. aria-label="Пошук по сайту" — статичный.

CLS: Фиксированная высота контейнера input + min-height.

Интервал смены: не менее 3-4 секунд (Gemini 3).

🟡 Infinite Moving Cards — ВЫСОКИЙ ПРИОРИТЕТ

Статус: Частично реализован (1×). Доработать.

Что делает оригинал (из effects.md):

Массив карточек (quote, name, title)
Дублирование трека для бесшовности
CSS animation scroll — transform: translate(-50%)
Настраиваемые: direction, speed, pauseOnHover
CSS custom properties для duration и direction
HTML-контракт (SEO-safe):

HTML

<section data-effect="infinite-cards" 
         data-speed="slow" 
         data-direction="left"
         data-pause-on-hover="true">
  <div class="infinite-track">
    <!-- Реальный контент — индексируется -->
    <div class="infinite-item">
      <blockquote>"Відмінна якість друку!"</blockquote>
      <cite>— Олег, бренд Urbanwear</cite>
    </div>
    <!-- ... -->
  </div>
  <!-- JS клонирует .infinite-track с aria-hidden="true" -->
</section>

<noscript>
  <div class="partners-grid">
    <img src="logo1.webp" alt="Партнер: Бренд X" />
    <img src="logo2.webp" alt="Партнер: Бренд Y" />
  </div>
</noscript>
Speed mapping: slow → 40s, normal → 25s, fast → 15s

Производительность:

Анимация только transform: translate3d() (GPU)
IntersectionObserver: пауза вне viewport
will-change: transform
🟡 Tooltip Card — ВЫСОКИЙ ПРИОРИТЕТ

Статус: Не реализован. Создать.

Что делает оригинал (из effects.md):

При hover — popup рядом с курсором
Popup следует за мышью
Автопозиционирование (не выходит за viewport)
Touch-поддержка (toggle по клику)
Spring-анимация высоты
DTF-применение: Термины (DPI, CMYK, Gang Sheet, bleed, hot peel, underbase)

HTML-контракт:

HTML

<span data-effect="tooltip-card"
      data-tooltip-title="DPI (точок на дюйм)"
      data-tooltip-text="Мінімум 300 DPI для якісного друку"
      data-tooltip-image="/static/img/dpi-example.webp">
  <strong>300 DPI</strong>
</span>
Поведение:

Desktop: popup при hover, следует за мышью
Mobile: popup при tap, закрывается при tap вне или через 3 секунды
Автопозиционирование
🟢 Flip Words — СРЕДНИЙ ПРИОРИТЕТ

Статус: Не реализован. Создать.

Что делает оригинал (из effects.md):

Массив слов циклически сменяется
Анимация: translateY(-100%) + blur → translateY(0) + blur(0)
Настраиваемая длительность
DTF-применение: «Ми друкуємо на [футболках | худі | кепках | сумках]»

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
JS при init: считывает data-words, заменяет innerText на анимированную версию.

CSS:

CSS

@keyframes flip-word-exit {
  to { transform: translateY(-100%); opacity: 0; filter: blur(4px); }
}
@keyframes flip-word-enter {
  from { transform: translateY(50%); opacity: 0; filter: blur(4px); }
  to { transform: translateY(0); opacity: 1; filter: blur(0); }
}
🟢 Text Generate Effect — СРЕДНИЙ ПРИОРИТЕТ

Что делает оригинал: Текст разбивается на слова, каждое появляется последовательно (opacity + blur).

SEO-решение:

HTML

<p data-effect="text-generate" data-delay="30" data-once="true">
  DTF-друк преміум якості — від макету до готового виробу за 24 години
</p>
Django рендерит полный текст. JS его визуально прячет и анимирует. Для ботов текст ВСЕГДА доступен.

🟢 Encrypted Text — РЕАЛИЗОВАН

Статус: 3 использования. Проверить SEO и reduced-motion.

Что делает: Текст как случайные символы → постепенная «расшифровка» слева направо.

SEO-решение: Исходный текст в HTML. JS прячет и анимирует. prefers-reduced-motion → показать сразу.

🟢 Images Badge — ВЫСОКИЙ ПРИОРИТЕТ

Статус: Не реализован. Создать.

Что делает оригинал: «Папка» с иконками, при hover разлетаются веером. Почти полностью CSS.

DTF-применение:

Бейдж на загруженном файле в конструкторе
Бейджи "нове", "топ" на кейсах в галерее
HTML

<div data-effect="images-badge"
     data-text="Завантажено 3 файли"
     data-images='["/media/thumb1.webp","/media/thumb2.webp","/media/thumb3.webp"]'>
</div>
🟢 Stateful Button — РЕАЛИЗОВАН, расширить

Что расширить: Применить ко ВСЕМ формам:

Форма заказа: «Надіслати» → ⏳ «Надсилаємо...» → ✅ «Надіслано!»
Кнопка копирования: «Копіювати» → ✅ «Скопійовано!»
🟢 Декоративные (BG Beams, Sparkles, Dotted Glow) — РЕАЛИЗОВАНЫ

Рекомендации:

1-2 на страницу максимум
IntersectionObserver для паузы вне viewport
prefers-reduced-motion → статичный градиент
Canvas-эффекты — отключать на слабых устройствах
🟢 Tracing Beam — РЕАЛИЗОВАН

Индикатор прогресса чтения в блоге. Лёгкий (~2KB). Не влияет на SEO.

⏸️ Отложенные (Sprint 4+)

Компонент	Зачем	Когда
Sidebar	Кабинет пользователя, конструктор	Sprint 4
Cover	Hero-секция с лучами	Sprint 4
Animated Tooltip	Команда технологов	Sprint 4
3D-вьювер (Three.js)	Превью худи с принтом	Долгосрочно
Haptic feedback	Тактильный отклик на мобильных	После MVP
Звуковые эффекты	Микро-звуки	После тестирования
7. SEO, ПРОИЗВОДИТЕЛЬНОСТЬ, CORE WEB VITALS

7.1. Целевые метрики
Метрика	Целевое значение	Как обеспечить
LCP	< 2.5 сек	Lazy-load для не-hero изображений; priority для hero; WebP
CLS	< 0.1	Фиксированные размеры для анимированных контейнеров; min-height
INP	< 200 мс	Vanilla JS + requestAnimationFrame; нет React-гидрации
FCP	< 1.8 сек	Критический CSS инлайн; отложенная загрузка не-критического JS
Total JS (gzip)	< 150 KB	Модульная загрузка; нет framer-motion
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
✅ Шрифты хостятся локально
✅ Meta description и title — статические, не зависят от JS
7.3. Стратегия загрузки ресурсов
HTML

<head>
  <!-- Критический CSS инлайн -->
  <style>/* core layout + above-the-fold */</style>
  
  <!-- Основной CSS -->
  <link rel="stylesheet" href="/static/dtf/css/dtf.min.css">
  
  <!-- CSS эффектов — отложенный -->
  <link rel="stylesheet" href="/static/dtf/css/effects.min.css" 
        media="print" onload="this.media='all'">
</head>
<body>
  <!-- Контент -->
  
  <!-- JS в конце body -->
  <script src="/static/dtf/js/core.js" defer></script>
  <!-- core.js динамически подгружает нужные модули -->
</body>
7.4. Z-Index стандарт
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
8. ПСИХОЛОГИЯ ДИЗАЙНА И UX-СТРАТЕГИЯ

8.1. Адаптивный интерфейс (не два отдельных!)
text

[Загрузка файла]
    │
    ├── 🟢 Файл проходит все проверки → БЫСТРЫЙ ПУТЬ (профессионалы)
    │   └── «Все ок! 300 DPI, CMYK, 0.8 м². Вартість: 450 грн. [Замовити]»
    │
    └── 🟡 Файл имеет проблемы → ПУТЬ ПОМОЩИ (новички)
        ├── «⚠️ Роздільність 72 DPI — рекомендуємо 300 DPI»
        ├── «ℹ️ Що таке DPI?» [Tooltip Card]
        ├── «📞 Потрібна допомога? [Зв'язатися з менеджером]»
        └── «🔧 Ми можемо виправити (+100 грн)»
8.2. Как эффекты поддерживают стратегию
Эффект	Для новичков	Для профессионалов
Multi-Step Loader	«Ми перевіряємо ваш файл...» — снижает тревогу	Подтверждение что система работает
Tooltip Card	Объяснение терминов	Быстрый справочник
Compare	«Ось різниця в якості!»	Демонстрация клиентам
Vanish Input	Подсказки что можно заказать	Быстрый поиск по артикулу
Stateful Button	«Відправлено ✅» — уверенность	Мгновенный feedback
8.3. Психологические принципы
Zeigarnik Effect (прогресс-бар): Multi-Step Loader «ви на кроці 3 з 5» — пользователь хочет дойти до конца
Social Proof: Infinite Moving Cards + бегущая строка «Вже надруковано: 15 247 метрів»
IKEA Effect: Конструктор где пользователь сам «собирает» заказ → повышает ценность
Expectation Setting: Compare «екран vs друк» предупреждает о разнице цвета ДО заказа → меньше возвратов
Micro-rewards: Sparkle при успешной загрузке, Stateful Button с галочкой
9. КОНСОЛИДИРОВАННЫЙ ТОП ИДЕЙ

9.1. Обязательные (Sprint 1-2)
#	Идея	Компонент	Где	Приоритет	Источник
1	Многоступенчатый загрузчик при загрузке файла	Multi-Step Loader	Форма заказа / Конструктор	🔴	Все агенты
2	Слайдер сравнения «макет vs друк»	Compare	Главная, Галерея	🔴	Все агенты
3	Автопроверка макета (DPI, колір, розмір)	Multi-Step Loader + бэкенд	Конструктор	🔴	Требование
4	Бесконечная карусель партнёров/отзывов	Infinite Moving Cards	Главная, Футер	🟡	Все агенты
5	Исправление конфликта FAB/Dock	Floating Dock	Глобально	🔴	Все агенты
6	Поиск с анимированными подсказками	Vanish Input	Главная, Навигация	🟡	Claude, CODEX, Gemini 3
7	Тултипы с объяснением терминов	Tooltip Card	Требования, FAQ, Конструктор	🟡	Claude, CODEX
8	Кнопки с состоянием (отправка → успех)	Stateful Button	Все формы	🟡	Claude, CODEX
9	Удаление legacy-дублей из dtf.js	Рефакторинг	Глобально	🔴	CODEX
10	Flip Words «Друкуємо на [X]»	Flip Words	Hero	🟢	Claude, CODEX
9.2. Рекомендуемые (Sprint 2-3)
#	Идея	Источник	Обоснование
11	Бегущая строка «Надруковано X метрів»	Gemini 1.5	Social proof в реальном времени
12	Preflight-чеклист (проверки с галочками)	CODEX, Gemini 3	Прозрачность процесса
13	Encrypted Text для стоимости	Claude	Wow-эффект при расчёте цены
14	Sparkle при успешной загрузке	Claude, Gemini 1.5	Микро-вознаграждение
15	Tracing Beam в блоге	Claude, CODEX	Прогресс чтения
16	Compare «72 DPI vs 300 DPI»	Gemini 3	Обучение клиента
17	Badge на загруженном файле (статус)	CODEX	Визуальная обратная связь
18	BlurHash для ленивой загрузки	Antigravity	UX при медленном соединении
19	Skeleton screens вместо спиннеров	Antigravity	Современный паттерн загрузки
20	Border Beam на CTA-кнопках	Antigravity	Привлечение внимания
9.3. Идеи «на вырост» (Sprint 4+)
#	Идея	Источник	Когда
21	Odometer-эффект для цены	Antigravity	Sprint 4
22	Shared Element Transition в галерее	Antigravity	Sprint 4
23	Пасхалка Konami Code → промокод	Gemini 1.5	Sprint 4
24	Кастомный branded loader (логотип + «чернила»)	Antigravity	Sprint 4
25	3D-превью худі з принтом (Three.js)	Gemini 1.5	Долгосрочно
26	Haptic feedback на мобільних	Gemini 1.5	После MVP
27	Мікро-звуки інтерфейсу	Gemini 1.5	После тестирования
28	Realtime-черга замовлень	Gemini 1.5	При масштабировании
29	EyeDropper API для вибору кольору	Gemini 1.5	Конструктор v2
30	Web Components (міграція)	Gemini 1.5	Если проект вырастет
10. ДОРОЖНАЯ КАРТА ВНЕДРЕНИЯ

Sprint 1 — «Фундамент» (Неделя 1-2)
#	Задача	Файлы	Дней
1	Удалить FAB, интегрировать в Dock	base.html, dtf.css	1
2	Multi-Step Loader (с привязкой к бэкенду)	новый: effect.multi-step-loader.js/css	3-5
3	Compare dual-mode + touch-action	effect.compare.js	2
4	Vanish Input: cycling placeholders + clear	effect.vanish-input.js	1-2
5	Infinite Cards SEO-safe	effect.infinite-cards.js	1-2
6	Рефакторинг dtf.js (удалить legacy-дубли)	dtf.js	1
Итого: 9-13 дней

Результат: Рабочий процесс «загрузка файла → проверка → результат». Основные UX-проблемы решены.

Sprint 2 — «Wow-эффект» (Неделя 3-4)
#	Задача	Файлы	Дней
7	Tooltip Card	новый	2
8	Flip Words	новый	0.5
9	Images Badge	новый	1
10	Text Generate Effect	новый	0.5
11	Stateful Button — расширить на все формы	существующий	1
12	Sparkle при успешной загрузке	существующий	0.5
13	Encrypted Text для стоимости	существующий	0.5
Итого: 6 дней

Результат: Сайт вызывает «wow» при первом посещении. Trust-факторы на месте.

Sprint 3 — «Оптимизация» (Неделя 5-6)
#	Задача	Дней
14	Lighthouse аудит + оптимизация (CLS, LCP, INP)	2
15	Мобильное тестирование (iOS Safari, Android Chrome)	2
16	<noscript> fallback для всех эффектов	1
17	prefers-reduced-motion для всех эффектов	1
18	A/B флаги для тяжёлых эффектов	1
19	JSON-LD разметка (отзывы, FAQ, продукты)	1
20	BlurHash для изображений	1
Итого: 9 дней

Sprint 4 — «Расширение» (Неделя 7-8, опционально)
Задача	Дней
Compare «72 DPI vs 300 DPI»	1
Tracing Beam оптимизация	0.5
Пасхалка Konami Code	0.5
Калькулятор стоимости с анимацией	3
Realtime бегущая строка «надруковано X метрів»	2
Odometer для цены	1
Skeleton screens	1
11. РИСКИ И МИТИГАЦИЯ

Риск	Вероятность	Влияние	Митигация
Перегрузка эффектами → медленная загрузка	Средняя	Высокое	Бюджет 150KB JS gzip. Lazy-loading. IntersectionObserver. A/B флаги.
CLS от анимированного текста → падение в SEO	Высокая	Высокое	Фиксированные размеры контейнеров. Lighthouse после каждого Sprint.
Конфликт свайпов на мобильных (Compare vs навигация)	Средняя	Среднее	touch-action: pan-y. Тестирование на iOS Safari.
Скрытый контент для Googlebot	Средняя	Высокое	Весь текст в HTML. <noscript> fallback. Google Search Console.
Эффекты не работают в Safari	Средняя	Среднее	Cross-browser тестирование. WebKit-prefixes.
Legacy-код ломается после рефакторинга	Средняя	Высокое	Git branches. Staging. Один файл за раз.
Визуальный шум для B2B-клиентов	Средняя	Высокое	Правило «каждый эффект = доверие». Отдельный B2B-лендинг?
Haptic/звуки раздражают	Низкая	Среднее	Opt-in. Отложить до тестирования.
Правило CODEX (чеклист перед добавлением любого эффекта):
«Любой эффект должен повышать доверие пользователя и понятность процесса, а не просто двигаться для красоты.»

text

✅ Повышает ли это доверие?
✅ Упрощает ли понимание процесса?
✅ Снижает ли тревожность?
✅ Помогает ли конверсии?

Если все ответы «нет» — эффект не нужен.
12. ТОЧНЫЕ СПЕЦИФИКАЦИИ ДЛЯ CODEX

Для агентов: Этот раздел — прямые инструкции для coding-агента. Его можно извлечь и передать как самостоятельный документ.

Sprint 1 — Задачи
ЗАДАЧА 1: Исправление конфликта FAB/Dock

Файлы:

twocomms/dtf/templates/dtf/base.html
twocomms/dtf/static/dtf/css/dtf.css
twocomms/dtf/static/dtf/js/components/effect.floating-dock.js
Действия:

Найти div#dtf-fab → УДАЛИТЬ
Элемент «Менеджер» перенести внутрь Dock как дополнительный пункт
CSS: breakpoints (desktop ≥961px → Dock с magnification; mobile <960px → Tab Bar без magnification)
Z-index стратегия (см. раздел 7.4)
ЗАДАЧА 2: Multi-Step Loader

Создать:

effect.multi-step-loader.js
effects/multi-step-loader.css
_multi-step-loader.html
HTML-контракт: (см. раздел 6.2, компонент Multi-Step Loader)

JS-API: .show(taskId), .hide(), .setStep(index), .bindToUpload(formData)

Связь с бэкендом: XHR upload → progress → fetch polling каждые 1000ms → { step, status, message }

ЗАДАЧА 3: Compare dual-mode + touch

Файл: effect.compare.js

Что добавить:

data-autoplay="true" → auto-sweep 2-3 цикла → freeze на ручном
touch-action: pan-y на контейнере
data-slide-mode="drag" на мобильных (matchMedia('(hover: none)'))
ЗАДАЧА 4: Vanish Input доработка

Файл: effect.vanish-input.js

Что добавить:

Cycling placeholders из data-placeholders='[...]'
При invalid: vanish-анимация → очистка → возврат placeholder
data-vanish-clear="true" — авто-очистка
Whitelist полей (не применять к textarea)
ЗАДАЧА 5: Infinite Moving Cards SEO-safe

Файл: effect.infinite-cards.js

Что сделать:

Первый трек — реальный контент
JS клонирует трек с aria-hidden="true" + tabindex="-1"
<noscript> fallback
Speed mapping: slow=40s, normal=25s, fast=15s
IntersectionObserver для паузы
ЗАДАЧА 6: Рефакторинг dtf.js

Файл: dtf.js

Удалить: initCompare(), initTracingBeam() и любые другие legacy-инициализаторы эффектов.

Проверить: Функции не вызываются из других мест.

Sprint 2 — Задачи
ЗАДАЧА 7: Tooltip Card (новый)

HTML-контракт, поведение (desktop/mobile), автопозиционирование — см. раздел 6.2.

ЗАДАЧА 8: Flip Words (новый)

HTML-контракт, SEO-решение, CSS-анимация — см. раздел 6.2.

ЗАДАЧА 9: Images Badge (новый)

HTML-контракт — см. раздел 6.2.

ЗАДАЧА 10: Text Generate Effect (новый)

HTML-контракт, SEO-решение — см. раздел 6.2.

ЗАДАЧА 11: Stateful Button — расширение

Применить ко ВСЕМ формам: заказ, контакт, копирование.

ЗАДАЧА 12-13: Sparkle при успехе + Encrypted Text для стоимости

Доработка существующих компонентов.

Sprint 3 — Задачи
#	Задача	Критерий готовности
14	Lighthouse аудит	LCP < 2.5s, CLS < 0.1, INP < 200ms
15	Мобильное тестирование	iOS Safari + Android Chrome + медленный интернет
16	noscript fallback	Каждый [data-effect] — текст доступен без JS
17	prefers-reduced-motion	Каждый init() → класс is-static
18	A/B флаги	Возможность быстро отключить любой эффект
19	JSON-LD	Structured data для отзывов, FAQ, продуктов
20	BlurHash	Placeholder для ленивых изображений
13. ОТКРЫТЫЕ ВОПРОСЫ К ВЛАДЕЛЬЦУ

Перед генерацией финального промпта для Codex нужно подтвердить:

Celery: Есть ли уже Celery для фоновых задач, или Multi-Step Loader будет работать с fake-delay?
Контент для Infinite Cards: Есть реальные отзывы / логотипы партнёров?
Tooltip Card контент: Список терминов DTF для тултипов — готов?
Изображения для Compare: Есть пары «до/после» (макет на экране vs печать на ткани)?
Flip Words: Какие точные слова для «Ми друкуємо на [...]»?
Локализація: Сайт на українській, російській чи обох? Тексти ефектів якою мовою?
14. ПРОМПТ-ЗАГОТОВКА ДЛЯ СЛЕДУЮЩЕГО ЭТАПА

text

=== ПРОМПТ ДЛЯ НОВОГО ЧАТА / СЛЕДУЮЩЕЙ ИТЕРАЦИИ ===

КОНТЕКСТ:
Проект dtf.twocomms.shop — платформа DTF-друку. 
Стек: Django + Vanilla JS + HTMX + CSS. Без React.

ПРЕДЫСТОРИЯ:
6 AI-агентов провели исследование визуальных эффектов 
Aceternity UI. Результат — единый консолидированный отчёт 
(прикреплённый файл), содержащий:
- Принятые архитектурные решения
- Контракт портирования React → Vanilla JS
- Покомпонентный разбор 18 эффектов
- SEO/производительность/a11y решения
- Дорожную карту на 4 спринта
- Точные спецификации для 13 задач

КЛЮЧЕВЫЕ РЕШЕНИЯ:
- Django + Vanilla JS + data-attributes + core.js
- Обязательные: Compare, Multi-Step Loader, Infinite Cards, 
  Floating Dock, Vanish Input, Tooltip Card, Stateful Button
- SEO: весь текст в HTML до JS, noscript fallback
- JS < 150KB gzip, CLS < 0.1, INP < 200ms, 60fps

ЗАДАЧА:
На основе прикреплённого отчёта, [указать конкретную задачу]:
- Генерация промпта для Codex (Sprint 1)
- Сравнение с новыми идеями
- Код конкретного компонента
- Аудит текущей реализации

Не пересоздавать анализ — использовать отчёт как базу.

=== КОНЕЦ ПРОМПТА ===