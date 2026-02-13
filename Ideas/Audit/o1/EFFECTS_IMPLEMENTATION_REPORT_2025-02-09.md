# COMPREHENSIVE EFFECTS & ARCHITECTURE TECHNICAL REPORT
## dtf.twocomms.shop — Detailed Implementation Plan for Deep Research Review

**Дата:** 2025-02-09  
**Подготовлено:** AI Agent (Antigravity Codex)  
**Цель:** Детальный технический документ для глубокого исследования другим ИИ

---

## 1. EXECUTIVE SUMMARY

### 1.1 Контекст проекта
- **Архитектура:** Django 5.x + HTMX + Vanilla JS
- **Хостинг:** cPanel Shared Hosting (ограничения по демонам, памяти, процессам)
- **Текущее состояние:** 16+ эффектов из Effects.MD запланировано, частично реализовано
- **Аудитория:** 60% новички (B2C), 40% профессионалы (B2B)

### 1.2 Ключевые проблемы (из Opus 4.6 Audit)
1. **Redis/Celery неработоспособны** на shared hosting — нужны альтернативы
2. **Multi-Step Loader использует fake таймеры** (setTimeout 260ms) — подрывает доверие
3. **Effect lifecycle хаос** — дубликаты файлов, отсутствие cleanup
4. **Критические эффекты отсутствуют или частичны:** Compare (нет autoplay/hover), Infinite Cards (stub), Vanish Input (минимальный)

### 1.3 Обязательные эффекты (требования владельца)
1. ✅ **Compare (До/После)** — autoplay + drag + hover, точно как в Aceternity UI
2. ✅ **Infinite Moving Cards** — для блога, не для отзывов; SEO-safe
3. ✅ **Multi-Step Loader** — реальная проверка документа (DPI, прозрачность, тонкие линии, края)
4. ✅ **Vanish Input с растворением текста** — при ошибке валидации
5. ✅ **Floating Dock (нижнее меню)** — macOS magnification эффект
6. ✅ **Левый тулбар (Sidebar)** — для конструктора заказов
7. ✅ **Images Badge** — анимация при загрузке файла в конструкторе
8. ✅ **Cover эффект (скорость)** — "дрожание от скорости" для текста "день в день"

---

## 2. ТЕКУЩЕЕ СОСТОЯНИЕ КОДОВОЙ БАЗЫ

### 2.1 Структура JS эффектов
```
twocomms/dtf/static/dtf/js/components/
├── core.js                    # 147 строк — DTF.registerEffect, HTMX hooks, cleanup
├── _utils.js                  # Утилиты
├── effect.compare.js          # 75 строк — только drag mode, НЕТ hover/autoplay
├── effect.infinite-cards.js   # 18 строк — STUB, только добавляет класс
├── multi-step-loader.js       # 42 строки — FAKE таймеры 260/520ms
├── floating-dock.js           # 51 строка — базовый, НЕТ magnification
├── vanish-input.js            # 33 строки — минимальный, только CSS класс
├── effect.encrypted-text.js   # реализован
├── effect.stateful-button.js  # реализован
├── sparkles.js                # реализован (базовый)
├── bg-beams.js                # ДУБЛИКАТ с effect.bg-beams.js
├── dotted-glow.js             # ДУБЛИКАТ с effect.dotted-glow.js
└── motion.js                  # обёртка для motion library
```

### 2.2 Анализ core.js (Effect Lifecycle)
**ХОРОШО:**
- ✅ `DTF.registerEffect(name, selector, initFn)` — единая точка регистрации
- ✅ `prefersReducedMotion()` — учёт a11y
- ✅ HTMX интеграция: `htmx:afterSwap` → reinit, `htmx:beforeCleanupElement` → cleanup
- ✅ `_dtfCleanup` массив на элементах для cleanup функций

**ПРОБЛЕМЫ:**
- ❌ Нет tiered budget (легкие/средние/тяжёлые анимации)
- ❌ Нет feature flags
- ❌ Нет error boundary (try/catch есть, но нет fallback UI)

### 2.3 Критический анализ компонентов

#### effect.compare.js
| Функция | Реализовано | Нужно |
|---------|-------------|-------|
| Drag mode | ✅ Да (PointerEvents) | ✅ Готово |
| Hover mode | ❌ Нет | Desktop only, mouse position → slider |
| Autoplay | ❌ Нет | 20%↔80% oscillation, IntersectionObserver |
| Keyboard a11y | ❌ Нет | Arrow keys, Tab focus |
| Touch mobile | ✅ Частично | Нет tap-to-toggle |
| ARIA | ❌ Нет | role="slider", aria-valuenow |

#### effect.infinite-cards.js
**ТЕКУЩИЙ КОД (18 строк) — ПОЛНЫЙ STUB:**
```javascript
function initInfiniteCards(node, ctx) {
  if (!node) return null;
  if (ctx && ctx.reducedMotion) {
    node.classList.add('infinite-cards-static');
    return null;
  }
  node.classList.add('infinite-cards-ready');
  return null;  // ← НИЧЕГО не делает
}
```

**НУЖНО РЕАЛИЗОВАТЬ:**
- CSS animation: `transform: translateX(calc(-50% - gap))`
- JS клонирование контента для бесшовности
- `aria-hidden="true"` + `inert` на клонах для SEO
- Pause on hover
- Configurable speed: slow (60s), normal (30s), fast (15s)

#### multi-step-loader.js
**КРИТИЧЕСКАЯ ПРОБЛЕМА — FAKE ТАЙМЕРЫ:**
```javascript
input.addEventListener('change', () => {
  if (input.files && input.files.length) {
    setStep(host, 2);
    window.setTimeout(() => setStep(host, 3), 260);  // ← FAKE!
    window.setTimeout(() => setStep(host, 4), 520);  // ← FAKE!
  }
});
```

**Пользователь видит:** "Проверяю DPI..." через 260ms, "Готово" через 520ms.
**Реальность:** Никакой проверки нет. Доверие подорвано.

---

## 3. АЛЬТЕРНАТИВЫ REDIS/CELERY (КРИТИЧНО)

### 3.1 Почему Redis/Celery нереалистичны на Shared Hosting
- cPanel убивает long-running processes при OOM
- Нет доступа к systemd/supervisor для worker демонов
- SSH есть, но nohup workers нестабильны после logout
- Memory limits: ~512MB-1GB на весь аккаунт

### 3.2 Альтернатива #1: Синхронный Preflight (РЕКОМЕНДУЕТСЯ)
**Описание:** Вся проверка файла происходит в одном HTTP запросе

**Реализация:**
```python
# views.py
@require_POST
def preflight_check(request):
    file = request.FILES.get('document')
    if not file:
        return JsonResponse({'error': 'No file'}, status=400)
    
    results = []
    # 1. Проверка формата (magic bytes)
    results.append(check_format(file))
    # 2. Проверка DPI
    results.append(check_dpi(file))
    # 3. Проверка прозрачности
    results.append(check_transparency(file))
    # 4. Проверка тонких линий
    results.append(check_thin_lines(file))
    # 5. Проверка выхода за края
    results.append(check_bleed(file))
    
    return JsonResponse({'results': results})
```

**Время выполнения:** <2-3 сек для файлов до 50MB
**UX:** Spinner + "Анализируем ваш файл..." → inline результаты

### 3.3 Альтернатива #2: Huey с SQLite Broker
**Описание:** Легковесная task queue без Redis

```python
# settings.py
HUEY = {
    'huey_class': 'huey.SqliteHuey',
    'filename': '/home/qlknpodo/TWC/huey.db',
    'immediate': False,  # async mode
}
```

**Проблема:** Требует постоянного worker процесса. На cPanel — нестабильно.

### 3.4 Альтернатива #3: HTMX Polling
**Описание:** Фоновый cron запускает проверки, JS poll статус

```html
<div hx-get="/api/preflight/status/{{ task_id }}/"
     hx-trigger="every 2s"
     hx-swap="innerHTML">
  Проверяем ваш файл...
</div>
```

**Проблема:** Требует cron job каждую минуту, задержка до 60 сек между шагами.

### 3.5 РЕКОМЕНДАЦИЯ: Синхронный Preflight
Для файлов до 50MB синхронная проверка работает за 2-3 секунды.
Это индустриальный стандарт (Printful, Printify, SPOD).
Не требует дополнительной инфраструктуры.

---

## 4. РЕАЛИЗАЦИЯ ОБЯЗАТЕЛЬНЫХ ЭФФЕКТОВ

### 4.1 Compare Slider (До/После)

#### 4.1.1 Технические требования
| Режим | Desktop | Mobile |
|-------|---------|--------|
| Autoplay | ✅ По умолчанию (IntersectionObserver) | ✅ По умолчанию |
| Hover | ✅ Mouse position → slider | ❌ Невозможно |
| Drag | ✅ PointerEvents | ✅ PointerEvents |
| Tap toggle | ❌ Не нужно | ✅ Альтернатива drag |
| Keyboard | ✅ Arrow keys ±5% | ✅ Arrow keys ±5% |

#### 4.1.2 Autoplay логика
```javascript
// Oscillation: 20% → 80% → 20% за 3 секунды
const autoplay = {
  duration: 3000,
  minPercent: 20,
  maxPercent: 80,
  pauseAtEdges: 1000,
  
  start(element) {
    if (this.prefersReducedMotion()) return;
    this.observer = new IntersectionObserver((entries) => {
      if (entries[0].isIntersecting) this.animate(element);
      else this.stop();
    });
    this.observer.observe(element);
  },
  
  animate(element) {
    // requestAnimationFrame loop с easing
    // При любом user interaction → this.stop()
  }
};
```

#### 4.1.3 ARIA доступность
```html
<div data-effect="compare"
     role="slider"
     aria-valuenow="50"
     aria-valuemin="0"
     aria-valuemax="100"
     aria-label="Сравнение качества до и после"
     tabindex="0">
```

#### 4.1.4 CSS для hover mode (чистый CSS где возможно)
```css
@media (hover: hover) and (pointer: fine) {
  [data-effect~="compare"][data-mode="hover"]:hover {
    --compare-position: var(--mouse-x-percent, 50%);
  }
}
```

### 4.2 Infinite Moving Cards (для Блога)

#### 4.2.1 Назначение
Вместо отзывов (которые могут быть фейковыми) — реальные статьи блога:
- "Как правильно ухаживать за принтами"
- "Как подготовить файл для DTF печати"
- "Разница между DTF и DTG"

#### 4.2.2 SEO-Safe реализация
```html
<!-- Оригинальный контент (индексируется) -->
<div class="infinite-cards-track" data-infinite-cards>
  <article class="card">
    <h3>Как подготовить файл для DTF</h3>
    <p>...</p>
    <a href="/blog/prepare-dtf-file/">Читать →</a>
  </article>
  <!-- ... больше карточек -->
</div>

<!-- JS создаёт клон (НЕ индексируется) -->
<div class="infinite-cards-track is-clone" aria-hidden="true" inert>
  <!-- Клонированный контент -->
</div>
```

#### 4.2.3 CSS анимация
```css
@keyframes infinite-scroll {
  from { transform: translateX(0); }
  to { transform: translateX(calc(-50% - var(--gap))); }
}

.infinite-cards-track {
  display: flex;
  gap: var(--gap, 24px);
  animation: infinite-scroll var(--duration, 30s) linear infinite;
}

.infinite-cards-track:hover,
.infinite-cards-track:focus-within {
  animation-play-state: paused;
}

@media (prefers-reduced-motion: reduce) {
  .infinite-cards-track {
    animation: none;
    overflow-x: auto;
  }
}
```

#### 4.2.4 JS реализация
```javascript
function initInfiniteCards(node, ctx) {
  if (!node) return null;
  
  // Reduced motion → статичный горизонтальный scroll
  if (ctx && ctx.reducedMotion) {
    node.style.overflowX = 'auto';
    node.style.animation = 'none';
    return null;
  }
  
  // Клонирование для бесшовности
  const clone = node.cloneNode(true);
  clone.setAttribute('aria-hidden', 'true');
  clone.setAttribute('inert', '');
  clone.classList.add('is-clone');
  node.parentElement.appendChild(clone);
  
  // Pause on hover
  const pauseHandler = () => node.style.animationPlayState = 'paused';
  const resumeHandler = () => node.style.animationPlayState = 'running';
  
  node.addEventListener('mouseenter', pauseHandler);
  node.addEventListener('mouseleave', resumeHandler);
  clone.addEventListener('mouseenter', pauseHandler);
  clone.addEventListener('mouseleave', resumeHandler);
  
  // Cleanup
  return function cleanup() {
    clone.remove();
    node.removeEventListener('mouseenter', pauseHandler);
    node.removeEventListener('mouseleave', resumeHandler);
  };
}
```

### 4.3 Multi-Step Loader (РЕАЛЬНАЯ ПРОВЕРКА)

#### 4.3.1 Шаги проверки документа
1. **Загрузка файла** — файл получен сервером
2. **Проверка формата** — magic bytes (PNG/TIFF/PDF)
3. **Анализ DPI** — минимум 150, рекомендуется 300
4. **Прозрачность** — есть ли альфа-канал
5. **Тонкие линии** — предупреждение если <0.5pt
6. **Выход за края** — bleed margins check
7. **Результат** — PASS/WARN/FAIL

#### 4.3.2 Backend (Django)
```python
# preflight/checks.py
from PIL import Image
import io

def check_dpi(file):
    img = Image.open(file)
    dpi = img.info.get('dpi', (72, 72))
    x_dpi = dpi[0] if isinstance(dpi, tuple) else dpi
    
    if x_dpi >= 300:
        return {'step': 'dpi', 'status': 'PASS', 
                'message': f'Разрешение отличное: {x_dpi} DPI'}
    elif x_dpi >= 150:
        return {'step': 'dpi', 'status': 'WARN',
                'message': f'Разрешение {x_dpi} DPI — ниже рекомендуемых 300 DPI'}
    else:
        return {'step': 'dpi', 'status': 'FAIL',
                'message': f'Разрешение {x_dpi} DPI слишком низкое'}

def check_transparency(file):
    img = Image.open(file)
    has_alpha = img.mode in ('RGBA', 'LA') or \
                (img.mode == 'P' and 'transparency' in img.info)
    
    if has_alpha:
        return {'step': 'transparency', 'status': 'PASS',
                'message': 'Прозрачный фон обнаружен ✓'}
    return {'step': 'transparency', 'status': 'INFO',
            'message': 'Файл без прозрачности — весь фон будет напечатан'}

def check_thin_lines(file):
    # Требует анализа контуров через OpenCV или PIL
    # Упрощённая версия: проверка на наличие штрихов <0.5pt
    return {'step': 'thin_lines', 'status': 'PASS',
            'message': 'Все линии достаточной толщины'}
```

#### 4.3.3 Frontend (HTMX + Vanilla JS)
```html
<form hx-post="/api/preflight/check/"
      hx-target="#preflight-results"
      hx-indicator="#preflight-spinner"
      enctype="multipart/form-data">
  
  <input type="file" name="document" accept=".png,.tiff,.pdf">
  <button type="submit">Проверить документ</button>
  
  <div id="preflight-spinner" class="htmx-indicator">
    <div class="spinner"></div>
    <span>Анализируем ваш файл...</span>
  </div>
  
  <div id="preflight-results"></div>
</form>
```

#### 4.3.4 Результат (inline, не modal)
```django
{% for check in results %}
<div class="preflight-check is-{{ check.status|lower }}">
  <span class="check-icon">
    {% if check.status == 'PASS' %}✓{% elif check.status == 'WARN' %}⚠{% else %}✗{% endif %}
  </span>
  <span class="check-message">{{ check.message }}</span>
  {% if check.status == 'FAIL' %}
    <a href="/blog/how-to-prepare-file/">Как подготовить файл →</a>
  {% endif %}
</div>
{% endfor %}
```

### 4.4 Vanish Input (Растворяющийся текст)

#### 4.4.1 Сценарий использования
1. Пользователь вводит email в поле
2. Нажимает "Отправить"
3. Email невалидный (нет @, недопустимые символы)
4. Поле подсвечивается красным
5. **Текст растворяется** particle эффектом
6. Поле очищается
7. Появляется сообщение об ошибке

#### 4.4.2 CSS эффект растворения
```css
@keyframes vanish-char {
  0% {
    opacity: 1;
    transform: translateY(0) scale(1);
    filter: blur(0);
  }
  50% {
    opacity: 0.5;
    transform: translateY(-10px) scale(0.8);
    filter: blur(2px);
  }
  100% {
    opacity: 0;
    transform: translateY(-20px) scale(0.3);
    filter: blur(5px);
  }
}

.vanish-input.is-vanishing::before {
  content: attr(data-vanish-text);
  position: absolute;
  animation: vanish-char 0.4s ease-out forwards;
}
```

#### 4.4.3 JS реализация
```javascript
function initVanishInput(node) {
  if (!node) return null;
  
  const form = node.closest('form');
  if (!form) return null;
  
  const handleInvalid = (e) => {
    e.preventDefault();
    
    const currentValue = node.value;
    if (!currentValue) return;
    
    // Сохраняем текст для анимации
    node.dataset.vanishText = currentValue;
    node.classList.add('is-vanishing');
    
    // Shake effect
    node.classList.add('is-shake');
    setTimeout(() => node.classList.remove('is-shake'), 300);
    
    // Очистка после анимации
    setTimeout(() => {
      node.value = '';
      node.classList.remove('is-vanishing');
      delete node.dataset.vanishText;
    }, 400);
    
    // Focus back
    node.focus();
  };
  
  node.addEventListener('invalid', handleInvalid);
  
  return function cleanup() {
    node.removeEventListener('invalid', handleInvalid);
  };
}
```

#### 4.4.4 Particle вариант (опционально)
Для particle эффекта требуется Canvas:
```javascript
function createVanishParticles(text, rect) {
  const canvas = document.createElement('canvas');
  // ... рендер символов как частиц
  // ... анимация разлёта
  // Motion Mini: animate(particles, { y: -50, opacity: 0 }, { type: spring })
}
```

**Рекомендация:** Начать с CSS-only vanish (blur + scale), particle добавить позже.

### 4.5 Floating Dock (Нижнее меню)

#### 4.5.1 macOS Magnification эффект
При приближении курсора к иконке — иконка увеличивается.
Соседние иконки также увеличиваются, но меньше (falloff).

#### 4.5.2 Физика magnification
```javascript
function calculateMagnification(cursorX, itemX, itemWidth) {
  const distance = Math.abs(cursorX - (itemX + itemWidth / 2));
  const maxDistance = 100; // радиус влияния
  const maxScale = 1.5; // максимальное увеличение
  
  if (distance > maxDistance) return 1;
  
  // Gaussian falloff
  const factor = 1 - (distance / maxDistance);
  return 1 + (maxScale - 1) * Math.pow(factor, 2);
}
```

#### 4.5.3 Motion Mini интеграция
```javascript
import { animate } from 'https://cdn.jsdelivr.net/npm/motion@11.13.5/mini/+esm';
import { spring } from 'https://cdn.jsdelivr.net/npm/motion@11.13.5/+esm';

function animateItem(element, scale) {
  animate(element, 
    { transform: `scale(${scale})` },
    { type: spring, stiffness: 400, damping: 25 }
  );
}
```

#### 4.5.4 HTML структура
```html
<nav data-effect="floating-dock" class="floating-dock">
  <a href="/" class="dock-item" aria-label="Главная">
    <svg><!-- home icon --></svg>
  </a>
  <a href="/catalog/" class="dock-item" aria-label="Каталог">
    <svg><!-- catalog icon --></svg>
  </a>
  <a href="/price/" class="dock-item" aria-label="Цены">
    <svg><!-- calculator icon --></svg>
  </a>
  <a href="/order/constructor/" class="dock-item is-primary" aria-label="Заказать">
    <svg><!-- upload icon --></svg>
  </a>
  <a href="/cabinet/" class="dock-item" aria-label="Кабинет">
    <svg><!-- user icon --></svg>
  </a>
</nav>
```

#### 4.5.5 Mobile layout (без magnification)
```css
@media (max-width: 768px) {
  .floating-dock {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    display: flex;
    justify-content: space-around;
    background: var(--dock-bg);
    padding: var(--dock-padding);
  }
  
  .dock-item {
    transform: none !important; /* Отключить magnification */
  }
}
```

### 4.6 Sidebar (Левый тулбар для конструктора)

#### 4.6.1 Назначение
В конструкторе заказов слева располагается тулбар:
- Загрузка файла (Images Badge)
- Выбор размера
- Выбор количества
- Опции (зеркалирование, белая подложка)
- Preview

#### 4.6.2 Реализация
Использовать Aceternity Sidebar pattern:
- Desktop: expand on hover (60px → 240px)
- Mobile: slide-in drawer
- Анимация: CSS transition 200ms ease

```css
.sidebar {
  width: var(--sidebar-collapsed, 60px);
  transition: width 0.2s ease;
}

.sidebar:hover,
.sidebar:focus-within,
.sidebar.is-open {
  width: var(--sidebar-expanded, 240px);
}
```

### 4.7 Images Badge (для конструктора)

#### 4.7.1 Описание
При наведении на зону загрузки — папка "раскрывается" показывая превью загруженных файлов.

#### 4.7.2 Реализация (CSS-only где возможно)
```css
.images-badge {
  position: relative;
}

.images-badge-images {
  position: absolute;
  display: flex;
  gap: 4px;
  transform: translateY(0) scale(0.8);
  opacity: 0;
  transition: all 0.3s ease;
}

.images-badge:hover .images-badge-images {
  transform: translateY(-35px) scale(1);
  opacity: 1;
}

.images-badge-images img:nth-child(1) { 
  transform: rotate(-15deg) translateX(-20px); 
}
.images-badge-images img:nth-child(2) { 
  transform: rotate(0deg); 
}
.images-badge-images img:nth-child(3) { 
  transform: rotate(15deg) translateX(20px); 
}
```

### 4.8 Cover (Эффект скорости/дрожания)

#### 4.8.1 Назначение
Текст "Отправка день в день" при наведении "дрожит от скорости".

#### 4.8.2 CSS реализация
```css
@keyframes speed-shake {
  0%, 100% { transform: translateX(0); }
  10% { transform: translateX(-1px) rotate(-0.5deg); }
  20% { transform: translateX(1px) rotate(0.5deg); }
  30% { transform: translateX(-1px) rotate(-0.5deg); }
  40% { transform: translateX(1px); }
  50% { transform: translateX(-1px); }
  60% { transform: translateX(1px) rotate(0.5deg); }
  70% { transform: translateX(-1px) rotate(-0.5deg); }
  80% { transform: translateX(1px); }
  90% { transform: translateX(-1px) rotate(0.5deg); }
}

[data-effect="cover"]:hover {
  animation: speed-shake 0.3s ease-in-out;
}
```

#### 4.8.3 Усиление: blur + motion smear
```css
[data-effect="cover"]:hover {
  animation: speed-shake 0.3s ease-in-out;
  text-shadow: 
    2px 0 0 rgba(0,0,0,0.1),
    -2px 0 0 rgba(0,0,0,0.1);
  filter: blur(0.3px);
}
```

---

## 5. MOTION MINI — ЗАМЕНА REACT DEPENDENCIES

### 5.1 Почему Motion Mini
- **Размер:** 2.3KB gzip (vs Framer Motion 40KB+)
- **Zero dependencies:** Чистый JS
- **CDN ready:** Работает через import из jsdelivr
- **Spring physics:** Тот же алгоритм что в Framer Motion
- **No React:** Работает с любым DOM элементом

### 5.2 Подключение
```html
<script type="module">
  import { animate } from 'https://cdn.jsdelivr.net/npm/motion@11.13.5/mini/+esm';
  import { spring } from 'https://cdn.jsdelivr.net/npm/motion@11.13.5/+esm';
  
  // Экспорт в глобальный scope для других скриптов
  window.DTF = window.DTF || {};
  window.DTF.motion = { animate, spring };
</script>
```

### 5.3 Примеры использования
```javascript
// Magnification эффект
DTF.motion.animate(element, 
  { transform: 'scale(1.5)' },
  { type: DTF.motion.spring, stiffness: 300, damping: 20 }
);

// Fade in при scroll
DTF.motion.animate('.hero-title', 
  { opacity: [0, 1], transform: ['translateY(20px)', 'translateY(0)'] },
  { duration: 0.6 }
);

// Stagger эффект для списков
const items = document.querySelectorAll('.card');
items.forEach((item, i) => {
  DTF.motion.animate(item,
    { opacity: [0, 1], transform: ['translateY(20px)', 'translateY(0)'] },
    { delay: i * 0.1 }
  );
});
```

---

## 6. TIERED ANIMATION BUDGET

### 6.1 Категории анимаций
| Tier | Тип | Лимит | Влияние на производительность |
|------|-----|-------|------------------------------|
| CSS-only | transform, opacity, clip-path | ∞ | Минимальное (GPU) |
| JS-light | IntersectionObserver + class toggle | Max 8 | Низкое |
| JS-medium | requestAnimationFrame loops | Max 3 viewport | Среднее |
| JS-heavy | Canvas, WebGL, DOM manipulation | Max 1 | Высокое |

### 6.2 Распределение эффектов
| Эффект | Tier | Одновременно |
|--------|------|--------------|
| Compare (autoplay) | JS-medium | 1-2 |
| Infinite Cards | CSS-only | 1 |
| Floating Dock magnification | JS-light | 1 |
| Vanish Input | CSS-only | ∞ |
| Encrypted Text | JS-light | 3-5 |
| BG Beams | CSS-only | 1 |
| Sparkles | CSS-only | 2 |

### 6.3 Enforcement код
```javascript
const DTF = window.DTF || {};
DTF.animationBudget = { light: 0, medium: 0, heavy: 0 };
const limits = { light: 8, medium: 3, heavy: 1 };

DTF.registerEffect = function(name, selector, initFn, tier = 'light') {
  // ... existing code ...
  
  if (DTF.animationBudget[tier] >= limits[tier]) {
    console.warn(`[DTF] Animation budget exceeded for ${tier}: ${name} skipped`);
    return; // Не инициализировать
  }
  
  DTF.animationBudget[tier]++;
  // ... rest of init
};
```

---

## 7. FEATURE FLAGS

### 7.1 Django Settings
```python
# settings.py
DTF_FEATURES = {
    # Стабильные
    'effect_encrypted_text': True,
    'effect_stateful_button': True,
    
    # В разработке
    'effect_compare_autoplay': False,
    'effect_compare_hover': False,
    'effect_infinite_cards': False,
    'effect_vanish_input_full': False,
    'effect_floating_dock_magnification': False,
    
    # Deprecated
    'legacy_compare_in_dtf_js': True,  # → мигрировать
    'fab_button': True,  # → заменить на dock
}
```

### 7.2 Template usage
```django
{% if features.effect_compare_autoplay %}
<div data-effect="compare" data-autoplay="true">
{% else %}
<div data-effect="compare">
{% endif %}
```

### 7.3 Context processor
```python
# context_processors.py
from django.conf import settings

def dtf_features(request):
    return {'features': getattr(settings, 'DTF_FEATURES', {})}
```

---

## 8. ПЛАН ВНЕДРЕНИЯ (12 НЕДЕЛЬ)

### Фаза 1: Stabilization (Недели 1-4)
| Неделя | Задачи |
|--------|--------|
| 1 | Удалить дубликаты (bg-beams.js vs effect.bg-beams.js), unified lifecycle |
| 2 | Error boundary для всех эффектов, prefers-reduced-motion везде |
| 3 | Compare: добавить hover mode + keyboard a11y |
| 4 | Compare: добавить autoplay с IntersectionObserver |

### Фаза 2: Core Effects (Недели 5-8)
| Неделя | Задачи |
|--------|--------|
| 5 | Infinite Cards: полная реализация, SEO-safe |
| 6 | Multi-Step Loader: SYNC preflight (удалить fake таймеры) |
| 7 | Vanish Input: полная реализация с particle эффектом |
| 8 | Floating Dock: magnification эффект |

### Фаза 3: Polish (Недели 9-12)
| Неделя | Задачи |
|--------|--------|
| 9 | Sidebar для конструктора, Images Badge |
| 10 | Cover (speed shake), мелкие polish эффекты |
| 11 | Performance audit (Lighthouse), a11y audit |
| 12 | QA, bug fixes, documentation |

---

## 9. ВЕРИФИКАЦИЯ

### 9.1 Автоматические тесты
- Lighthouse CI: Performance ≥70, Accessibility ≥90
- Playwright: E2E тесты для Compare, Infinite Cards
- Unit tests: preflight/checks.py

### 9.2 Ручное тестирование
- [ ] Compare работает на touch devices
- [ ] Infinite Cards не вызывают Layout Shift
- [ ] Vanish Input очищает поле при ошибке
- [ ] Floating Dock скрывается при скролле к footer
- [ ] Все эффекты отключаются при reduced-motion

### 9.3 Браузерная совместимость
- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+
- iOS Safari 14+
- Samsung Internet 14+

---

## 10. РИСКИ И MITIGATION

| Риск | Вероятность | Impact | Mitigation |
|------|-------------|--------|------------|
| Motion Mini не поддерживает нужный эффект | Средняя | Средний | Fallback на CSS-only |
| Preflight sync слишком долгий (>5 сек) | Низкая | Высокий | Показать progress bar, оптимизировать PIL |
| Magnification jank на mid-range devices | Средняя | Средний | Throttle mousemove, use CSS transform |
| SEO penalty от Infinite Cards | Низкая | Высокий | aria-hidden + inert на клонах |
| HTMX re-init ломает эффекты | Средняя | Высокий | cleanup система в core.js |

---

## 11. ВОПРОСЫ ДЛЯ ГЛУБОКОГО ИССЛЕДОВАНИЯ

1. **Motion Mini compatibility:** Проверить поддержку spring physics на всех целевых браузерах
2. **PIL performance:** Бенчмарк check_dpi() для файлов 10MB, 25MB, 50MB
3. **Infinite Cards SEO:** Проверить через Google Search Console после деплоя
4. **WCAG compliance:** Полный a11y аудит Compare и Infinite Cards
5. **Shared hosting limits:** Максимальный размер файла для sync preflight

---

## 12. ЗАКЛЮЧЕНИЕ

Проект требует систематической работы по:
1. **Стабилизации** существующего effect lifecycle
2. **Замене fake async** на реальный sync preflight
3. **Реализации** обязательных эффектов с учётом a11y и SEO
4. **Интеграции** Motion Mini для spring анимаций
5. **Внедрении** tiered budget для контроля производительности

**Ключевой инсайт:** Большинство "React-only" эффектов из Aceternity UI могут быть реализованы на Vanilla JS + CSS с минимальной помощью Motion Mini (2.3KB). Это сохраняет преимущества Django SSR и HTMX архитектуры.

**Рекомендация:** Следовать Сценарию B (Balanced) — стабилизация + 3-4 WOW эффекта. Не пытаться реализовать все 16 эффектов сразу.

---

*Документ подготовлен для глубокого исследования другим ИИ агентом. Ожидается анализ жизнеспособности предложенных решений и рекомендации по улучшению.*
