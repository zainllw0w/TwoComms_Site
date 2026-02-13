# O1 Master Consolidated Audit & Implementation Guide

Дата: 2026-02-09  
Проект: `TwoComms / dtf.twocomms.shop`  
Назначение: единый подробный документ, объединяющий и очищающий от противоречий все отчеты в `Ideas/Audit/o1`.

---

## 1. Какие файлы объединены

Этот документ консолидирует:

- `Ideas/Audit/o1/1.md`
- `Ideas/Audit/o1/EFFECTS_IMPLEMENTATION_REPORT_2025-02-09.md`
- `Ideas/Audit/o1/MASTER_IMPLEMENTATION_PLAN.md`
- `Ideas/Audit/o1/implementation_strategy_v2.md`
- `Ideas/Audit/o1/O1_DEEP_TECH_FACTCHECK_BLUEPRINT_2026-02-09.md`

Статус старых документов после консолидации:

- использовать как исторический контекст: `1.md`, `EFFECTS_IMPLEMENTATION_REPORT_2025-02-09.md`, `MASTER_IMPLEMENTATION_PLAN.md`, `implementation_strategy_v2.md`
- использовать как актуальную базу для следующего ИИ и coding-итерации: **этот файл**

---

## 2. Короткий итог (главное без воды)

1. Проект уже рабочий и не находится на нулевой стадии, но слой эффектов и часть UX-потоков несогласованы.
2. `Compare`, `Vanish`, `Infinite Cards`, `Floating Dock`, `Multi-step loader` нужно довести до production-уровня, а не просто “добавить”.
3. Для текущего production-контура Celery/Redis **не operational**; поэтому критичные пользовательские проверки делаются в sync-архитектуре.
4. Главный путь: **Sync-first + честный preflight UX + feature-flag rollout + cleanup legacy**.
5. Для следующего Opus-цикла нужен не общий креатив, а точные спецификации и верификация гипотез на фактах.

---

## 3. Что в отчетах совпадает, а что конфликтует

## 3.1 Что подтверждено всеми отчетами и кодом

- нужен единый lifecycle эффектов
- нужен cleanup дублей и legacy частей
- текущий `multi-step-loader` выглядит fake
- `compare` и `infinite-cards` недореализованы
- конфликт правого нижнего угла (FAB + dock + mobile dock)
- SEO-safe правила для движущихся карточек обязательны

## 3.2 Где есть расхождения

| Тема | В части отчетов | По фактам проекта | Финальное решение |
|---|---|---|---|
| Celery/Redis | “можно/нужно разворачивать прямо сейчас” | В production broker DNS не резолвится, worker не найден | Не блокировать UX на Celery, идти sync-first |
| Huey | “ставим как основной путь” | Возможен как переходный, но тоже требует живого worker процесса | Рассматривать как опцию B, не как базовый путь |
| “все async невозможен” | слишком категорично | Невозможен не async вообще, а текущий контур с данным infra | Формулировать как infra-ограничение текущей среды |
| Feature flags отсутствуют | встречается в ряде файлов | Flags уже есть (`DTF_FEATURE_FLAGS`, context) | Расширить/нормализовать, не создавать с нуля |
| Error boundary отсутствует | встречается в старых формулировках | В `core.js` есть `try/catch` init-level | Доработать fallback UX, не дублировать |

---

## 4. Фактическое состояние проекта (код + production)

## 4.1 Frontend/Effect layer

- Базовый реестр эффектов и HTMX hooks присутствует в `twocomms/dtf/static/dtf/js/components/core.js`.
- В `base.html` одновременно есть `#dtf-fab`, `[data-floating-dock]` и `.mobile-dock`.
- В `dtf.js` остались legacy-функции (`initCompare`, `initTracingBeam`), что создает риск рассинхронизации со слоем `effect.*`.

## 4.2 Статус must-have эффектов

| Эффект | Статус | Комментарий |
|---|---|---|
| Compare | Частично | Есть drag/pointer/range, нет полной parity с референсом (autoplay/hover/keyboard model). |
| Multi-step loader | Fake | Шаги переключаются fixed таймерами; реальная пошаговая модель не отражается. |
| Vanish input | Минимум | Pulse/shake на invalid; нет dissolve+clear и циклических placeholder’ов. |
| Infinite cards | Минимум | CSS-скролл + JS заглушка; нет SEO-safe clone protocol и pause/focus behavior. |
| Floating dock | Частично | Базовый компонент есть, но нет mac-like magnification и единой навигационной модели. |
| Sidebar constructor | Частично | Левый `aside` есть как layout, но не как отдельный эффектный интерактивный toolbar-компонент. |

## 4.3 Preflight backend

- В `twocomms/dtf/preflight/engine.py` уже реализованы ключевые проверки (magic bytes, размер, DPI, alpha/margins, color mode, tiny-detail risk, PDF checks).
- В `constructor` preflight реально исполняется sync через форму.
- В `order` preflight-блок визуально похож на реальный терминал, но не привязан к полноценному real-check output как в constructor.

## 4.4 Production-инфра факты (SSH)

- `DEBUG=False`
- `CELERY_BROKER_URL` задан
- `REDIS_PING` в production: ошибка DNS (`Name or service not known`)
- celery/huey/redis процессы: не найдены
- cron: активен

Следствие: в текущей среде надежный worker-driven UX строить нельзя как основной путь.

---

## 5. Объединенная техническая стратегия

## 5.1 Архитектурный принцип

**Primary path:** `Sync-first` + `progressive enhancement` + `feature flags`.  
**Secondary path:** optional async после инфраструктурной готовности.

## 5.2 Почему это правильно для текущей фазы

- снижает зависимость от неработающего broker/worker контура
- дает быстрый результат в UX и конверсии
- сохраняет существующий Django SSR + HTMX + Vanilla JS стек
- позволяет переносить визуальные референсы из `Effects.MD` без тяжелой миграции на React runtime

## 5.3 Что можно взять из новых файлов как полезное

- из `EFFECTS_IMPLEMENTATION_REPORT_2025-02-09.md`:
  - tiered animation budget
  - идея Motion Mini как легкого слоя для spring-анимаций (опционально)
  - phased rollout и контроль performance/a11y
- из `MASTER_IMPLEMENTATION_PLAN.md`:
  - good framing “wow vs stability”
  - фокус на sync preflight для пользовательского пути
- из `implementation_strategy_v2.md`:
  - аккуратные Vanilla/CSS паттерны для compare/cards/vanish/dock

## 5.4 Что брать с оговорками

- “полная миграция с Celery на Huey как обязательный шаг”
- “fake delay ради ощущения длительной проверки”

Финальная позиция:

- **не фейковая проверка**, а честный процесс с поэтапной визуализацией реальных результатов
- Huey только как опциональный этап, не как hard prerequisite

---

## 6. Unified spec по обязательным эффектам

Ниже единая спецификация “как делать правильно” после объединения всех документов.

## 6.1 Compare (До/После, визуально как в референсе)

Цель:

- поведение близко к Aceternity reference
- режимы `drag`, `hover` (desktop), `autoplay`
- автоматическая остановка autoplay при любом user interaction
- mobile fallback без hover

Обязательные требования:

- `data-compare-mode="drag|hover|autoplay"`
- `data-autoplay="true|false"`
- reduced-motion отключает autoplay
- keyboard support и ARIA slider semantics
- без layout shift

Файлы интеграции:

- `twocomms/dtf/static/dtf/js/components/effect.compare.js`
- `twocomms/dtf/static/dtf/css/components/effect.compare.css`
- `twocomms/dtf/templates/dtf/index.html`
- `twocomms/dtf/templates/dtf/gallery.html`
- `twocomms/dtf/templates/dtf/effects_lab.html`

## 6.2 Multi-step loader + реальный preflight

Цель:

- убрать fixed fake-step таймеры
- отображать реальные проверки файла
- дать дружелюбный PASS/WARN/FAIL с actionable guidance

Обязательные шаги в UI:

1. Файл принят
2. Формат и сигнатура
3. DPI и физические размеры
4. Прозрачность/границы
5. Риск тонких линий/деталей
6. Итог и действия

Критично:

- если backend готов быстрее, UI показывает завершение шагов честно, без симуляции “несуществующей проверки”
- `order` и `constructor` должны прийти к одному формату preflight output

Файлы интеграции:

- `twocomms/dtf/static/dtf/js/components/multi-step-loader.js`
- `twocomms/dtf/templates/dtf/order.html`
- `twocomms/dtf/templates/dtf/constructor_app.html`
- `twocomms/dtf/preflight/engine.py`
- `twocomms/dtf/urls.py` и/или `twocomms/dtf/views.py` (при выделении отдельного preflight API endpoint)

## 6.3 Vanish Input

Цель:

- при invalid input поле не просто краснеет, а очищается через controlled vanish effect
- placeholder циклически подсказывает формат ввода

Обязательные требования:

- onInvalid: shake + dissolve + clear
- onValid: обычное поведение
- mobile облегченный вариант без тяжелого canvas
- a11y: не ломать screen reader/keyboard flow

Файлы интеграции:

- `twocomms/dtf/static/dtf/js/components/vanish-input.js`
- `twocomms/dtf/static/dtf/css/components/vanish-input.css`

## 6.4 Floating Dock + нижняя навигация + constructor sidebar

Цель:

- единый navigation contract вместо 3 конкурирующих элементов
- desktop dock (с эффектом масштаба), mobile dock (без hover-magnification)
- constructor sidebar как отдельный контекстный инструмент

Обязательные требования:

- удалить конфликт: FAB + отдельный mobile dock + floating dock
- оставить один главный нижний navigation pattern
- в constructor слева отдельный инструментальный тулбар
- “upload badge / image badge” в контексте конструктора

Файлы интеграции:

- `twocomms/dtf/templates/dtf/base.html`
- `twocomms/dtf/static/dtf/js/components/floating-dock.js`
- `twocomms/dtf/static/dtf/css/components/floating-dock.css`
- `twocomms/dtf/templates/dtf/constructor_app.html`

## 6.5 Infinite Moving Cards для блога (SEO-safe)

Цель:

- на главной движущийся блок с blog/knowledge карточками
- индексируемый основной контент + декоративный клон

Обязательные требования:

- source cards = реальные статьи блога
- cloned track: `aria-hidden="true"`, `inert`, `role="presentation"`
- pause on hover/focus
- reduced-motion fallback в статический/scroll режим

Файлы интеграции:

- `twocomms/dtf/templates/dtf/index.html`
- `twocomms/dtf/static/dtf/js/components/effect.infinite-cards.js`
- `twocomms/dtf/static/dtf/css/components/effect.infinite-cards.css`

## 6.6 Speed/Tremble text effect

Цель:

- микро-эффект “скорости” для ключевых сообщений (например, “відправка день в день”)

Требования:

- краткая длительность
- только на акцентных элементах
- reduced-motion disable
- текст остается читаемым в SSR и без JS

---

## 7. Preflight спецификация после объединения

## 7.1 Что уже есть и надо переиспользовать

- `PF_MAGIC_*`
- `PF_DPI_*`
- `PF_MARGIN_*`
- `PF_NO_ALPHA/PF_EMPTY_ALPHA`
- `PF_COLOR_*`
- `PF_TINY_TEXT_*`
- PDF checks

## 7.2 Что добавить как бизнес-обязательное

- отдельное правило по ширине/формату “60 см”
- явный rule по thin lines (не только косвенный heuristic)
- warning по белому непрозрачному фону, если это риск для ожидаемого результата
- унифицированный mapping `code -> human label -> user action`

## 7.3 Важный технический долг

В ряде UI-мест ожидаются поля типа `label`, но backend checks ориентированы на `code/message`. Нужно централизованное нормализующее преобразование перед рендером.

---

## 8. Celery ("селлари")/Redis/Huey — финальная позиция

## 8.1 Что не делать прямо сейчас

- не строить критичный пользовательский flow на Celery, пока broker/worker контур фактически не стабилен
- не “рисовать async”, которого нет в runtime

## 8.2 Что делать сейчас

Вариант A (основной):

- sync preflight
- cron для некритичных фоновых задач
- UI честно отражает real checks

## 8.3 Что делать позже (если инфра готова)

Вариант B:

- managed Redis + реальный worker process (VPS/контейнер/process manager)
- перенос тяжелых задач в async

Вариант C:

- Huey/DB-backed queue как transitional вариант, если есть гарантированный worker lifecycle

---

## 9. SEO, accessibility и performance policy (единая)

1. SSR-first контент обязателен для всех текстовых блоков.
2. Декоративные дубли всегда скрываются из semantic/accessibility слоя.
3. Не использовать анимации, вызывающие layout shift.
4. Для motion-sensitive пользователей все интенсивные эффекты отключаются.
5. Animation budget вводится формально:
   - CSS-only: без жесткого лимита
   - JS-light: ограниченно
   - JS-medium/heavy: строго лимитировано во viewport

---

## 10. Единый roadmap внедрения (консолидированный)

## 10.1 Wave 0 (подготовка)

- инвентаризация дублей `effect.*` и не-prefixed файлов
- решение по единому namespace и слоям подключения
- фикс конфликта нижнего правого UI

## 10.2 Wave 1 (core must-have)

- Compare parity
- Real multi-step preflight rendering
- Vanish clear behavior
- Infinite blog cards SEO-safe

## 10.3 Wave 2 (constructor UX)

- интерактивный sidebar/toolbar в constructor
- dock-context для конструктора
- image badge + upload motion

## 10.4 Wave 3 (polish + validation)

- speed text effect
- feature-flag rollout контроль
- a11y/perf/SEO regression checks

---

## 11. Что передавать следующему ИИ (Opus 4.6)

Следующий агент должен получить:

1. этот consolidated файл
2. вопросник по бизнес/UX моделированию
3. список тех.неопределенностей для интернет-ресерча
4. четкий критерий успешности для каждого эффекта

Ключевые вопросы для Opus:

- какие preflight copy и структуры снижают тревожность и drop-off
- насколько moving blog cards улучшают engagement vs static bento
- где autoplay реально повышает trust, а где раздражает
- какие пороги latency допустимы для sync preflight до перехода к async

---

## 12. Готовый prompt (короткая версия для запуска следующей итерации)

```text
Проанализируй приложенный consolidated tech-audit по проекту TwoComms DTF.
Считай фактом: текущий стек Django SSR + HTMX + Vanilla JS, частично реализованный effect-layer, и нестабильный текущий Celery/Redis контур в production.

Твоя задача:
1) проверить жизнеспособность объединенной стратегии Sync-first для preflight и обязательных wow-эффектов;
2) дать улучшенный implementation brief для coding-агента;
3) предложить лучшие UX/SEO/performance решения для Compare, Multi-step preflight UI, Infinite blog cards, Vanish input, Floating dock/sidebar;
4) сформировать четкий список того, что надо исследовать в интернете дополнительно, с приоритетами.

Не предлагай полную миграцию на React/Vue как обязательное условие.
Сохраняй совместимость с существующим Django SSR контуром.
```

---

## 13. Финальный вывод

После объединения всех файлов в `o1` итоговая картина такая:

- ценность всех документов высокая, но по отдельности они частично дублируются и местами противоречат друг другу;
- технически корректная база сейчас: **fact-check + sync-first preflight + постепенная доводка must-have эффектов + feature-flag rollout**;
- этот файл заменяет разрозненные версии как единый вход для следующего аналитического и coding цикла.
