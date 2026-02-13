# Prompt For Next Codex Agent — DTF Effects Implementation (2026-02-09)

Ты следующий coding-агент Codex. Твоя задача: реализовать обязательные эффекты и устранить техдолг в DTF-контуре проекта.

## 0) Главная цель
Сделать на `dtf.twocomms.shop` production-уровень эффектов (визуально близко к референсам из `Effects.MD`), без миграции на React runtime, на текущем Django SSR + HTMX + Vanilla JS.

## 1) Обязательные файлы к прочтению перед стартом
1. `Ideas/Audit/o2/O2_IMPLEMENTATION_CONTEXT_DTF_EFFECTS_2026-02-09.md`
2. `twocomms/Promt/Effects.MD`
3. `twocomms/dtf/templates/dtf/base.html`
4. `twocomms/dtf/templates/dtf/index.html`
5. `twocomms/dtf/templates/dtf/order.html`
6. `twocomms/dtf/templates/dtf/constructor_app.html`
7. `twocomms/dtf/static/dtf/js/components/core.js`
8. `twocomms/dtf/static/dtf/js/components/effect.compare.js`
9. `twocomms/dtf/static/dtf/js/components/effect.infinite-cards.js`
10. `twocomms/dtf/static/dtf/js/components/multi-step-loader.js`
11. `twocomms/dtf/static/dtf/js/components/vanish-input.js`
12. `twocomms/dtf/static/dtf/js/components/floating-dock.js`
13. `twocomms/dtf/preflight/engine.py`
14. `twocomms/dtf/views.py`
15. `twocomms/dtf/forms.py`
16. `specs/dtf-codex/QA.md`
17. `specs/dtf-codex/DEPLOY.md`

## 2) Необсуждаемые ограничения
1. Менять только DTF-сайт (`twocomms/dtf/*`) и связанные DTF-спеки.
2. Не менять основной сайт `twocomms.shop`.
3. Не внедрять React runtime/Next.js migration.
4. Не делать fake progress в multi-step loader.
5. Не ломать SSR/SEO/a11y.
6. Не удалять и не откатывать чужие несвязанные изменения.

## 3) Обязательный MCP-процесс
1. Используй Sequential Thinking MCP на каждом крупном этапе: анализ, дизайн решения, проверка рисков, верификация результата.
2. Используй Context7 MCP в местах, где нужна точная справка по API/паттернам миграции поведения из React в Vanilla.
3. Если Context7 в рантайме недоступен:
- явно зафиксируй это в рабочем логе;
- продолжай на основе локального кода и официальной документации.

## 4) Что обязательно реализовать

### A) Floating Dock + constructor local dock + image badge
- Закрыть конфликт FAB vs floating dock vs mobile dock (единый контракт видимости).
- В конструкторе сделать локальный action-dock (загрузка/замена/очистка/проверка).
- Добавить image badge для состояния файла в конструкторе.
- На desktop добавить аккуратную hover magnification-анимацию иконок dock.

Ключевые файлы:
- `twocomms/dtf/templates/dtf/base.html`
- `twocomms/dtf/templates/dtf/constructor_app.html`
- `twocomms/dtf/static/dtf/js/components/floating-dock.js`
- `twocomms/dtf/static/dtf/css/components/floating-dock.css`
- при необходимости новый модуль badge (`effect.images-badge.js` + CSS)

### B) Multi-step loader с реальными preflight-шагами
Покажи шаги:
1. формат/сигнатура
2. DPI
3. физические размеры и проверка 60 см
4. прозрачность/границы
5. риск тонких линий
6. итог + рекомендации

Требования:
- sync-first честный UX (без выдуманных задержек).
- одинаковый формат отображения в `order` и `constructor`.
- если FAIL, корректно выделить этап и остановить цепочку.

Ключевые файлы:
- `twocomms/dtf/static/dtf/js/components/multi-step-loader.js`
- `twocomms/dtf/static/dtf/css/components/multi-step-loader.css`
- `twocomms/dtf/templates/dtf/order.html`
- `twocomms/dtf/templates/dtf/constructor_app.html`
- `twocomms/dtf/preflight/engine.py`
- `twocomms/dtf/views.py`

### C) Infinite Moving Cards (SEO-safe)
- Сделать реально рабочий infinite cards модуль.
- SSR-контент должен быть индексируемым.
- Клоны должны быть декоративными (`aria-hidden`, `inert`, без активных ссылок).
- Pause on hover/focus.
- Mobile/reduced-motion fallback.

Ключевые файлы:
- `twocomms/dtf/templates/dtf/index.html` (блок blog/knowledge preview)
- `twocomms/dtf/static/dtf/js/components/effect.infinite-cards.js`
- `twocomms/dtf/static/dtf/css/components/effect.infinite-cards.css`

### D) Placeholders + Vanish Input
- Invalid input => shake + vanish + clear.
- Реализовать cycling placeholders.
- Останавливать cycling при focus/typing.
- Не ломать native validation UX и фокус.

Ключевые файлы:
- `twocomms/dtf/static/dtf/js/components/vanish-input.js`
- `twocomms/dtf/static/dtf/css/components/vanish-input.css`
- `twocomms/dtf/templates/dtf/order.html`
- `twocomms/dtf/templates/dtf/constructor_app.html`
- `twocomms/dtf/templates/dtf/status.html`

### E) Compare parity (before/after)
- Добавить режимы drag + hover + autoplay.
- Autoplay останавливается при любом user interaction.
- Keyboard + ARIA slider semantics.
- Mobile fallback.

Ключевые файлы:
- `twocomms/dtf/static/dtf/js/components/effect.compare.js`
- `twocomms/dtf/static/dtf/css/components/effect.compare.css`
- `twocomms/dtf/templates/dtf/index.html`
- `twocomms/dtf/templates/dtf/gallery.html`
- `twocomms/dtf/templates/dtf/effects_lab.html`

### F) Speed/Tremble text для сообщения скорости
- Точечная анимация для copy про быструю отправку “день в день”.
- One-shot или on-hover, без постоянного раздражающего цикла.
- `prefers-reduced-motion` обязательно.

Ключевые файлы:
- `twocomms/dtf/templates/dtf/index.html`
- новый CSS/JS модуль speed-text (по необходимости)
- подключение в `twocomms/dtf/templates/dtf/base.html`

## 5) Дополнительно (если успеваешь без риска)
1. Odometer-like анимация цены в order-калькуляторе.
2. Tooltip-card для preflight терминов.
3. Text-generate effect для финальной рекомендации preflight.

## 6) Техдолг до/во время внедрения
1. Убери конфликтную навигацию и определи единые breakpoints поведения dock/FAB/mobile.
2. Нормализуй preflight output contract между backend и шаблонами.
3. Удали/рефактори legacy-инициализаторы эффектов в `dtf.js`, чтобы не было двусмысленности.

## 7) Стандарт качества кода
1. Каждый новый effect-модуль регистрируется через `DTF.registerEffect`.
2. Никакой двойной инициализации.
3. Cleanup listeners/timers/RAF обязателен.
4. Все тексты через i18n, без hardcode в одном языке.
5. Новые классы/атрибуты должны быть семантически понятными и стабильными.

## 8) Обязательная проверка перед сдачей
Локально:
- `python3 -m compileall -q twocomms/dtf`
- `python3 twocomms/manage.py test dtf --settings=test_settings`

Smoke:
- `/`
- `/order/`
- `/constructor/app/`
- `/blog/`
- `/effects-lab/`

Проверить вручную:
- compare все режимы;
- loader реальные шаги;
- vanish очистка и placeholders;
- infinite cards SEO-safe behavior;
- отсутствие конфликтов dock/fab/mobile;
- mobile breakpoints 320/375/768.

## 9) Деплой (когда код готов)
Используй SSH-команду:
```bash
sshpass -p 'trs5m4t1' ssh -o StrictHostKeyChecking=no qlknpodo@195.191.24.169 "bash -lc 'source /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.13/bin/activate && cd /home/qlknpodo/TWC/TwoComms_Site/twocomms && git pull'"
```

И runbook из:
- `specs/dtf-codex/DEPLOY.md`

## 10) Формат твоего финального отчета
В конце работы покажи:
1. Что конкретно реализовано (по пунктам A-F).
2. Список измененных файлов.
3. Что было сложно/рискованно и как решено.
4. Результаты тестов/проверок (команды + итог).
5. Что осталось как follow-up.

Работай end-to-end, без остановки на полпути. Если есть блокер, опиши его и предложи рабочий fallback, но не прекращай прогресс по остальным пунктам.
