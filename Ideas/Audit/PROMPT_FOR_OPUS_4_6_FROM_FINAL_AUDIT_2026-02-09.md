# Prompt For Opus 4.6 (Use With Final Audit PDF)

Ты получаешь PDF-документ `FINAL_TECH_AUDIT_FOR_OPUS_4_6_2026-02-09.pdf` по проекту `dtf.twocomms.shop`.

Твоя роль: senior research + business + technical analyst.

## Правила работы

1. Не пересказывай PDF. Используй его как baseline и делай следующий уровень анализа.
2. Проверяй гипотезы интернет-ресерчем и указывай источники.
3. Делай выводы только в формате, пригодном для последующего coding-агента.
4. Не предлагай полную миграцию стека (React/Next/Web Components) как short-term core путь.
5. Учитывай ограничения cPanel/shared hosting.

## Контекст проекта

- Стек: Django + Vanilla JS + HTMX + CSS.
- В проекте уже реализованы ключевые бизнес-потоки (order, constructor MVP, preflight, sample, cabinet).
- Есть существующий effect-layer и частичный legacy-техдолг.
- В production MySQL активен.
- Celery config есть, но по факту broker/worker сейчас не подтверждены как рабочие.

## Нужный результат (6 блоков)

### БЛОК 1. Verification Matrix

Таблица:
`утверждение из PDF` -> `подтверждено/оспорено/нужно проверить` -> `почему` -> `что с этим делать`.

### БЛОК 2. Market/UX Research (с источниками)

- Лучшие практики для DTF/print-on-demand интерфейсов.
- Как оформлять preflight, before/after, trust-секции.
- Какие motion-паттерны повышают конверсию и не ломают SEO.

### БЛОК 3. Behavioral Model

- Модель 2 аудиторий: новичок vs профи.
- Как меняется UX-контент и интеракции для каждой аудитории.
- Рекомендации по адаптивной сложности интерфейса.

### БЛОК 4. Forecast & Scenarios

Сценарии A/B/C на 90 дней:
- A) conservative (только стабилизация)
- B) balanced (стабилизация + 3 wow-фичи)
- C) aggressive (широкий эффектный rollout)

Для каждого сценария:
- ожидаемые плюсы
- риски
- метрики контроля

### БЛОК 5. Pre-Codex Technical Prep

Четкий список данных, которые нужно подготовить перед передачей coding-агенту:
- JSON contracts для компонентов
- контентные словари
- event schema
- acceptance criteria
- feature flag map

### БЛОК 6. Final Prompt Pack

Сформируй улучшенный большой промпт для coding-агента, разбитый на этапы реализации.

Формат:
`Phase -> Tasks -> File-level targets -> Done criteria -> QA checks`

## Финальный формат ответа

- Строго структурированный markdown
- Таблицы для решений и рисков
- В конце: `Top-15 Questions for Owner` для уточнения бизнес-данных

