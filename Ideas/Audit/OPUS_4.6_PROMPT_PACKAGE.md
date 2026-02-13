# OPUS 4.6 ANALYSIS PROMPT — DTF Project Deep Dive

---

## ⚠️ ВАЖНО: КОНТЕКСТ ДЛЯ AI

**Ты получаешь этот документ как единственный источник информации о проекте.**  
У тебя НЕТ доступа к файлам проекта. Весь контекст содержится ниже.

---

## ЧАСТЬ A: О ПРОЕКТЕ

### A.1 Общее описание

**Название:** dtf.twocomms.shop  
**Тип:** B2B/B2C поддомен для DTF-печати (Direct-to-Film)  
**Основной бизнес:** Печать на одежде по технологии DTF  
**Монетизация:** Продажа услуг печати, готовых принтов, sample kit

**Технический стек:**
- Backend: Django 5.x (Python 3.13)
- Frontend: Vanilla JavaScript (без React/Vue)
- Стилизация: Custom CSS + CSS variables
- Интерактивность: HTMX для partial page updates
- База данных: MySQL (production)
- Очереди: Celery (настроен, но НЕ РАБОТАЕТ на production!)
- Хостинг: cPanel shared hosting

**Архитектура frontend:**
```
Django SSR → HTML → HTMX partial updates
                  ↓
            JS Effect Layer (vanilla)
                  ↓
            CSS Animations/Transitions
```

### A.2 Существующие страницы

| Страница | URL | Назначение |
|----------|-----|------------|
| Главная | `/` | Landing с hero, features, testimonials |
| Каталог | `/catalog/` | Готовые принты для покупки |
| Цены | `/price/` | Калькулятор цен, тарифная сетка |
| Конструктор | `/order/constructor/app/` | Upload + preflight + заказ |
| Галерея | `/gallery/` | Примеры работ до/после |
| Блог | `/blog/` | Статьи, requirements, FAQ |
| Кабинет | `/cabinet/` | Личный кабинет клиента |
| Sample Kit | `/order/sample/` | Заказ тестового набора |

### A.3 Целевая аудитория

**Сегмент 1: Новички (60%)**
- Первый раз заказывают DTF-печать
- Не понимают технические требования (DPI, CMYK, margins)
- Нуждаются в reassurance и guidance
- Боятся ошибиться и потерять деньги

**Сегмент 2: Профессионалы (40%)**
- Регулярно заказывают печать
- Знают технические требования
- Ценят скорость и контроль
- Раздражаются от избыточных пояснений

### A.4 Ключевые бизнес-метрики (цели)

- Conversion rate landing → order: 3-5%
- File upload success rate: >80%
- Preflight pass rate: >70%
- Sample kit → full order conversion: 25%
- Repeat order rate: 40%

---

## ЧАСТЬ B: ТЕКУЩЕЕ СОСТОЯНИЕ ЭФФЕКТОВ

### B.1 Что такое "эффект" в проекте

Эффект = JavaScript-компонент для визуальной интерактивности.

**Архитектура:**
```javascript
// Регистрация эффекта
DTF.registerEffect('effect-name', '[selector]', initFunction);

// Lifecycle
- init: при загрузке страницы
- reinit: после htmx:afterSwap
- cleanup: при htmx:beforeCleanupElement
```

### B.2 Список всех эффектов и их статус

#### ✅ ГОТОВЫЕ К PRODUCTION

| Эффект | Строк кода | Что делает | Качество |
|--------|------------|------------|----------|
| **Encrypted Text** | 76 JS | Scramble-анимация текста при появлении | 85% |
| **Stateful Button** | 131 JS | Кнопка с состояниями loading/success/error | 90% |
| **Flip Words** | в dtf.js | Смена слов с анимацией | 70% |

---

#### ⚠️ РАБОТАЮТ, НО ТРЕБУЮТ ДОРАБОТКИ

| Эффект | Строк | Что есть | Чего нет | Приоритет |
|--------|-------|----------|----------|-----------|
| **Compare** | 75 JS | Базовый slider до/после | Autoplay, hover mode, 3D | Высокий |
| **Tracing Beam** | 48 JS | Progress bar при скролле | SVG beam path | Низкий |
| **Pointer Highlight** | 29 JS | Hover class toggle | Cursor-following glow | Низкий |

---

#### ❌ ТРЕБУЮТ ПОЛНОЙ ПЕРЕДЕЛКИ

| Эффект | Проблема | Что показывает сейчас | Что должно быть |
|--------|----------|----------------------|-----------------|
| **Infinite Cards** | 18 строк-пустышка | Ничего (только добавляет CSS class) | Бесконечный горизонтальный scroll карточек с отзывами |
| **Vanish Input** | 33 строки-минимум | Shake на invalid | Cycling placeholders + particle vanish + auto-clear |
| **Multi-Step Loader** | 42 строки + BLOCKER | Fake таймеры без backend | Modal с реальным прогрессом preflight |
| **Floating Dock** | 51 строка | Статичная навигация | macOS-style magnification при hover |
| **Sparkles** | 37 строк | 4 статичные точки | Случайно генерируемые искры |
| **BG Beams** | 35 строк | Только toggle class | Анимированные световые лучи |
| **Dotted Glow** | 33 строки | Только toggle class | Анимированная сетка точек с glow |

---

#### ❌ НЕ РЕАЛИЗОВАНЫ (из Effects.MD референса)

| Эффект | Потенциальное применение | Сложность |
|--------|-------------------------|-----------|
| Tooltip Card | Пояснения терминов, подсказки | Средняя |
| Images Badge | File manager, галерея загрузок | Средняя |
| Cover | Hero секции | Высокая |
| Animated Tooltip | Hover-подсказки | Низкая |
| Sidebar | Кабинет, навигация | Высокая |
| Text Generate | Trust-блоки, storytelling | Средняя |

---

### B.3 Детальный анализ критичных эффектов

#### COMPARE (Slider До/После)

**Где используется:** 6 мест (gallery, index, quality)

**Текущий код (упрощенно):**
```javascript
// effect.compare.js — 75 строк
pointer.addEventListener('pointermove', (e) => {
  const pct = (e.clientX - rect.left) / rect.width * 100;
  media.style.setProperty('--compare', `${pct}%`);
});
```

**Что умеет:**
- Drag слайдер мышью/touch
- Показывает два изображения

**Чего не умеет:**
- ❌ Autoplay (автоматическое движение)
- ❌ Hover mode (движение за курсором без клика)
- ❌ 3D perspective эффект
- ❌ Остановка autoplay при взаимодействии
- ❌ Keyboard accessibility

**Бизнес-ценность:**
- Критично для демонстрации качества (72 DPI vs 300 DPI, screen vs print)
- Один из главных trust-building элементов

---

#### INFINITE CARDS (Карусель отзывов)

**Где используется:** 1 место (testimonials на главной)

**Текущий код:**
```javascript
// effect.infinite-cards.js — 18 строк
// ПУСТЫШКА!
node.classList.add('infinite-cards-ready');
return null; // Ничего не делает!
```

**CSS анимация существует, но JS не дублирует контент для бесшовности:**
```css
@keyframes dtfInfiniteCards {
  from { transform: translateX(0); }
  to { transform: translateX(-50%); }
}
```

**Что должно быть:**
- Бесконечный горизонтальный scroll
- SEO: первый track = реальный контент, клон = aria-hidden
- Пауза при hover
- Настройка: direction (left/right), speed (slow/normal/fast)

---

#### MULTI-STEP LOADER (Прогресс Preflight)

**Где используется:** 2 места (constructor, order upload)

**КРИТИЧЕСКИЙ БЛОКЕР:**
> Celery/Redis на production НЕ РАБОТАЕТ!
> Broker DNS error: "Name or service not known"
> Worker процессы не найдены

**Текущий код (FAKE!):**
```javascript
// multi-step-loader.js — 42 строки
input.addEventListener('change', () => {
  setStep(host, 2);
  setTimeout(() => setStep(host, 3), 260);  // FAKE!
  setTimeout(() => setStep(host, 4), 520);  // FAKE!
});
```

**Что должно быть:**
1. Modal overlay на весь экран
2. Реальные шаги preflight: Upload → DPI check → Colors → Size → Preview
3. Polling backend для статуса
4. Обработка ошибок

**Варианты решения:**
1. **A) Починить Celery/Redis** → real async polling
2. **B) Synchronous preflight** → честный single-request flow
3. **C) Fake но честный** → показывать что это "оценка", не реальные шаги

---

#### VANISH INPUT (Поле ввода с эффектом)

**Где используется:** 3 места (email forms, search)

**Текущий код:**
```javascript
// vanish-input.js — 33 строки
field.classList.add('is-vanish');
setTimeout(() => field.classList.remove('is-vanish'), 420);
```

**Что умеет:** Shake при invalid

**Чего не умеет:**
- ❌ Cycling placeholders (меняющиеся подсказки)
- ❌ Очистка поля после vanish
- ❌ Particle effect (текст "разлетается")

---

### B.4 UX Конфликт: FAB / Dock / Mobile Dock

**Проблема:** В правом нижнем углу одновременно присутствуют 3 элемента:

```html
<!-- base.html содержит все три! -->
<button id="dtf-fab">Quick Action</button>
<nav data-floating-dock>Desktop Nav</nav>
<nav class="mobile-dock">Mobile Nav</nav>
```

**Результат:** Перекрытие, z-index войны, плохой UX

**Нужно решить:**
- Единый контракт: что показывать на каком breakpoint
- Один source of truth для z-index
- Убрать дублирование функционала

---

## ЧАСТЬ C: PREFLIGHT ENGINE (Backend)

### C.1 Что проверяет Preflight

**Файл:** `twocomms/dtf/preflight/engine.py`

| Проверка | Что делает | Результат |
|----------|------------|-----------|
| Magic bytes | Проверяет реальный тип файла | PASS/FAIL |
| Extension | Сравнивает с допустимыми | PASS/FAIL |
| File size | Проверяет max size | PASS/WARN/FAIL |
| DPI | Извлекает и проверяет (min 150) | PASS/WARN/FAIL |
| Alpha channel | Определяет прозрачность | INFO |
| Margins | Проверяет отступы для bleed | WARN |
| Color mode | RGB/CMYK/Grayscale | INFO/WARN |
| PDF pages | Single page requirement | PASS/FAIL |
| PDF media box | Размеры страницы | INFO |

### C.2 Проблема UX при ошибках

**Текущее поведение:**
- FAIL = красное сообщение
- WARN = желтое предупреждение

**Проблема:**
- Пользователи паникуют при WARN
- Не понятно как исправить
- Нет "что дальше" guidance

**Нужно:**
- Copy-framework для снижения тревожности
- Конкретные инструкции по исправлению
- Опция "продолжить несмотря на" для некритичных WARN

---

## ЧАСТЬ D: ИДЕИ ИЗ ДРУГИХ АГЕНТОВ

### D.1 Из CODEX Report (100 идей)

**Топ-10 практичных:**
1. Унифицировать effect lifecycle (register → init → reinit → cleanup)
2. Добавить feature flags для эффектов
3. Создать performance budget (max 3 анимации одновременно)
4. Внедрить prefers-reduced-motion везде
5. SEO-safe infinite scroll
6. Lazy loading для тяжелых эффектов
7. A/B тестирование для Compare autoplay
8. Error boundary для JS эффектов
9. Component contracts documentation
10. Visual regression testing

### D.2 Из Claude-4-Sonnet (100 идей)

**Топ-10 креативных:**
1. 3D hoodie visualizer с физикой ткани
2. AR preview на телефоне
3. AI color palette suggestions
4. Gang sheet optimizer (Tetris-like)
5. Real-time collaboration для дизайнеров
6. Price calculator с drag-and-drop
7. Before/after slider с timeline
8. Sound design для interactions
9. Haptic feedback на mobile
10. Dark mode с proper color tokens

### D.3 Из Antigravity Report (100 идей)

**Фокус на WOW-эффекты:**
1. Parallax hero sections
2. Liquid animations
3. Magnetic buttons
4. Text reveal on scroll
5. SVG morphing
6. Particle systems
7. Gradient animations
8. Blur transitions
9. Stagger animations
10. Spring physics

### D.4 Из Gemini 1.5 Pro

**Фокус на Psychology/Performance:**
1. Cognitive load reduction
2. Progressive disclosure
3. Skeleton loading states
4. Optimistic UI updates
5. Error recovery patterns
6. Micro-copy optimization
7. Trust signals placement
8. Social proof integration
9. Scarcity/urgency (ethical)
10. Personalization based on behavior

---

## ЧАСТЬ E: ИНФРАСТРУКТУРНЫЕ ОГРАНИЧЕНИЯ

### E.1 Celery/Redis Проблема

**Статус на production (проверено по SSH):**
```bash
$ ping broker.redis.url
# Name or service not known

$ ps aux | grep celery
# Нет worker процессов
```

**Влияние:**
- Multi-Step Loader с реальным polling НЕВОЗМОЖЕН
- Background tasks не работают
- Emails через Celery не отправляются

**Варианты решения:**
1. Настроить Redis на cPanel (сложно, shared hosting)
2. Использовать SQLite-based job queue (huey)
3. Перейти на VPS/cloud
4. Принять sync-only архитектуру

### E.2 Shared Hosting Ограничения

- Нет root доступа
- Лимиты на процессы
- Нет произвольных портов
- Ограниченный crontab
- Memory limits

### E.3 Техдолг

**Legacy в dtf.js:**
```javascript
// Эти функции определены но не вызываются!
function initCompare() { ... }  // ← legacy
function initTracingBeam() { ... }  // ← legacy
```

**Дублирующие файлы:**
- `bg-beams.js` И `effect.bg-beams.js`
- `sparkles.js` И потенциально дубль

---

## ЧАСТЬ F: ЧТО НУЖНО ОТ ТЕБЯ (OPUS 4.6)

### F.1 Твоя роль

**Ты — Senior Research + Business + UX Analyst**

Твоя задача НЕ писать код, а:
1. Проанализировать идеи
2. Дать экспертную оценку
3. Предложить приоритизацию
4. Исследовать лучшие практики в индустрии
5. Ответить на открытые вопросы

### F.2 Что нужно выдать

#### БЛОК 1: Verification Matrix

Таблица: "Идея/Claim → Подтверждено/Оспорено → Почему → Что делать"

Проверь:
- Правильность приоритетов из D.1-D.4
- Реалистичность технических решений
- Бизнес-ценность предложений

#### БЛОК 2: Market/UX Research

С источниками из интернета:
- Как DTF/print-on-demand сервисы показывают preflight?
- Best practices для before/after comparisons?
- Motion patterns для e-commerce конверсии?
- SEO для JS-heavy animations?

#### БЛОК 3: Behavioral Model

Для двух аудиторий (новички 60% / профи 40%):
- Как должен отличаться UX?
- Какие effects для кого?
- Adaptive complexity recommendations?

#### БЛОК 4: Forecast & Scenarios

90-дневные сценарии:
- **A) Conservative:** только стабилизация
- **B) Balanced:** стабилизация + 3 wow-фичи
- **C) Aggressive:** полный effect rollout

Для каждого: плюсы, риски, метрики контроля

#### БЛОК 5: Pre-Codex Technical Prep

Что подготовить перед кодингом:
- JSON contracts для компонентов
- Content strings (UA/RU/EN)
- Event schemas
- Acceptance criteria
- Feature flag map

#### БЛОК 6: Final Recommendations

- Top-10 действий в порядке приоритета
- What NOT to do (антипаттерны)
- Quick wins vs long-term investments

---

### F.3 Конкретные вопросы

1. **Compare autoplay:** Включать по умолчанию или по hover?
2. **Infinite cards speed:** slow/normal/fast — какой оптимален для trust?
3. **Preflight WARN:** Как уменьшить тревожность без скрытия проблем?
4. **FAB vs Dock:** Оставить одно или унифицировать?
5. **3D effects:** Стоят ли performance trade-off?
6. **Haptics/Sound:** Для DTF B2B/B2C уместно?
7. **Multi-Step Loader:** Fake честный или ждать infra fix?
8. **Dark mode:** Приоритет для DTF аудитории?
9. **Motion limits:** Сколько анимаций на страницу максимум?
10. **Mobile-first:** Какие effects обязательны на mobile?

---

### F.4 Ограничения для ответов

⛔ **НЕ предлагать:**
- React/Next.js/Vue миграцию
- Web Components как core
- Полную смену стека
- Решения требующие VPS без обоснования

✅ **Учитывать:**
- cPanel shared hosting
- Vanilla JS + HTMX архитектура
- Качество > сложность
- Бизнес-метрики важнее "красоты"

---

## ЧАСТЬ G: ВНЕШНИЕ РЕФЕРЕНСЫ

### Технические

- HTMX Events: https://htmx.org/events/
- Core Web Vitals: https://web.dev/articles/vitals
- JS SEO: https://developers.google.com/search/docs/crawling-indexing/javascript/javascript-seo-basics
- CSS touch-action: https://developer.mozilla.org/en-US/docs/Web/CSS/touch-action

### Индустриальные (для research)

- Printful (DTF competitor)
- Printify (DTF competitor)
- CustomInk (print-on-demand)
- Gooten (B2B print)
- SPOD (Spreadshirt)

---

## ЧАСТЬ H: ФОРМАТ ОТВЕТА

```markdown
# OPUS 4.6 ANALYSIS REPORT

## 1. Verification Matrix
[таблица]

## 2. Market/UX Research
[с источниками]

## 3. Behavioral Model
[новички vs профи]

## 4. Forecast & Scenarios
[A/B/C сценарии]

## 5. Pre-Codex Technical Prep
[чек-листы]

## 6. Final Recommendations
[топ-10 + антипаттерны]

## 7. Answers to Specific Questions
[ответы на F.3]

## 8. Top-15 Questions for Project Owner
[уточняющие вопросы]
```

---

**КОНЕЦ ДОКУМЕНТА ДЛЯ OPUS 4.6**
