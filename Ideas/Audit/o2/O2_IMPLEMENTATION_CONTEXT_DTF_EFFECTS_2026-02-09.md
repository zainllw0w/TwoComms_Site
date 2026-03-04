# O2 Implementation Context — DTF Effects Integration (2026-02-09)

## 1) Цель документа
Подготовить максимально практичный контекст для следующего coding-агента, который будет внедрять обязательные UI/UX-эффекты на `dtf.twocomms.shop` в текущем стеке Django SSR + HTMX + Vanilla JS.

Этот документ фиксирует:
- текущий факт по коду и инфраструктуре;
- решения по архитектуре (что делаем и что НЕ делаем);
- обязательные фичи от владельца проекта;
- приоритеты, риски, последовательность внедрения;
- проверочный и деплойный протокол.

## 2) Жесткий scope
- Работать только в DTF-контуре (`twocomms/dtf/*`).
- Основной сайт `twocomms.shop` не менять.
- Не переводить проект на React runtime/Next.js ради эффектов.
- Эффекты из `twocomms/Promt/Effects.MD` использовать как поведенческие референсы, а не как drop-in код.

## 3) Источники, которые уже проанализированы
- `Ideas/Audit/o2/Объединённая спецификация эффектов для проекта dtf.twocomms.shop.pdf`
- `Ideas/Audit/o2/Техническая спецификация эффектов для сайта.pdf`
- `Ideas/Audit/o1/O1_MASTER_CONSOLIDATED_AUDIT_IMPLEMENTATION_2026-02-09.md`
- `Ideas/Audit/o1/O1_DEEP_TECH_FACTCHECK_BLUEPRINT_2026-02-09.md`
- `Ideas/Audit/FINAL_TECH_AUDIT_FOR_OPUS_4_6_2026-02-09.md`
- `Ideas/Audit/MASTER_TECH_AUDIT_2026-02-09.md`
- `Ideas/Audit/CONSOLIDATED_EFFECTS_GAP_ANALYSIS.md`
- `Ideas/Antigravity_Report.md`
- `Ideas/Gemini_1.5_Pro.md`
- `Ideas/CODEX_Report.md`
- `twocomms/Promt/Effects.MD`
- `specs/dtf-codex/CHECKLIST.md`
- `specs/dtf-codex/QA.md`
- `specs/dtf-codex/DEPLOY.md`

Технические извлечения из PDF доступны в:
- `tmp/pdfs/Объединённая спецификация эффектов для проекта dtf.twocomms.shop.txt`
- `tmp/pdfs/Техническая спецификация эффектов для сайта.txt`

## 4) Canonical решения (принять как базу)
1. Стек реализации: Django SSR + HTMX + Vanilla JS (текущий production-стек).
2. React/Next.js migration не выполняем в рамках этой задачи.
3. Multi-step loader не строим как Celery-driven realtime, пока infra не готова; делаем sync-first честный UX.
4. Все эффекты проектируются как progressive enhancement: без JS контент и ключевые сценарии остаются рабочими.
5. Для SEO-критичных секций (особенно moving cards) SSR-контент обязателен; клоны только декоративные (`aria-hidden`, `inert`).
6. Навигация: убрать конфликт FAB vs floating dock vs mobile dock через единый контракт видимости.

## 5) Фактическое состояние кода (на момент 2026-02-09)

### 5.1 Основные точки интеграции
- Реестр эффектов и lifecycle: `twocomms/dtf/static/dtf/js/components/core.js`
- Глобальный init и бизнес-логика: `twocomms/dtf/static/dtf/js/dtf.js`
- Базовое подключение CSS/JS: `twocomms/dtf/templates/dtf/base.html`

### 5.2 Must-effect статус
- Compare:
  - JS: `twocomms/dtf/static/dtf/js/components/effect.compare.js` (есть drag/range)
  - CSS: `twocomms/dtf/static/dtf/css/components/effect.compare.css` (почти пустой)
  - Пробелы: autoplay/hover/keyboard/a11y parity.
- Multi-step loader:
  - JS: `twocomms/dtf/static/dtf/js/components/multi-step-loader.js` (fixed таймеры 260/520ms)
  - CSS: `twocomms/dtf/static/dtf/css/components/multi-step-loader.css`
  - Пробелы: нет backend-driven шагов и честного результата.
- Vanish input:
  - JS: `twocomms/dtf/static/dtf/js/components/vanish-input.js` (shake class toggle)
  - CSS: `twocomms/dtf/static/dtf/css/components/vanish-input.css`
  - Пробелы: нет vanish-clear и placeholder cycling.
- Floating dock:
  - JS: `twocomms/dtf/static/dtf/js/components/floating-dock.js`
  - CSS: `twocomms/dtf/static/dtf/css/components/floating-dock.css`
  - Пробелы: нет mac-like magnification, конфликтует с FAB/mobile-dock контрактом.
- Infinite moving cards:
  - JS: `twocomms/dtf/static/dtf/js/components/effect.infinite-cards.js` (stub)
  - CSS: `twocomms/dtf/static/dtf/css/components/effect.infinite-cards.css` (базовый marquee)
  - Пробелы: clone protocol, accessibility, SEO-safe дубликаты, pause/focus behavior.

### 5.3 Текущие конфликтные зоны
- В `twocomms/dtf/templates/dtf/base.html` одновременно существуют:
  - `#dtf-fab`
  - `nav[data-floating-dock]`
  - `nav.mobile-dock`
- Это подтвержденный UX-конфликт правого нижнего угла.

### 5.4 Preflight backend (что уже есть)
- Логика: `twocomms/dtf/preflight/engine.py`
- Проверяет: magic bytes/ext, size, DPI, alpha/margins, color mode, tiny-detail risk, PDF page/media box.
- Constructor flow реально использует `analyze_upload` через форму в `twocomms/dtf/forms.py`.
- Разрыв: визуальный вывод в `constructor_app.html` ожидает `item.label`, а engine возвращает `code/status/message`.

### 5.5 Infra-факт
- Celery/Redis в production не operational (по последним аудитам и SSH-фактчеку).
- Текущая реалистичная тактика: sync-first.

## 6) Обязательные требования владельца (переведены в техзадачи)

### 6.1 Constructor dashboard + file management через floating dock
Реализация:
- В `constructor_app` добавить контекстный мини-dock действий (загрузка, очистка, превью, submit).
- В dock-элемент загрузки добавить image badge (количество/статус файла).
- На desktop добавить hover-анимацию magnification для иконок dock.

Файлы:
- `twocomms/dtf/templates/dtf/constructor_app.html`
- `twocomms/dtf/static/dtf/js/components/floating-dock.js`
- `twocomms/dtf/static/dtf/css/components/floating-dock.css`
- при необходимости: новый `effect.images-badge.js` + CSS

### 6.2 Multi-step loader с реальными шагами preflight
Нужно явно показать шаги:
1. тип/сигнатура файла
2. DPI
3. ширина/габариты и правило 60 см
4. выход за границы/поля/прозрачность
5. тонкие линии/мелкие детали
6. итог PASS/WARN/FAIL + действия

Файлы:
- `twocomms/dtf/static/dtf/js/components/multi-step-loader.js`
- `twocomms/dtf/static/dtf/css/components/multi-step-loader.css`
- `twocomms/dtf/templates/dtf/order.html`
- `twocomms/dtf/templates/dtf/constructor_app.html`
- `twocomms/dtf/preflight/engine.py`
- `twocomms/dtf/views.py` (API/JSON format при необходимости)

### 6.3 Infinite moving cards в блоке блога с SEO-safe индексацией
- Основной список карточек SSR.
- Клон трека только декоративный (`aria-hidden`, `inert`, без активных ссылок).
- Pause on hover/focus.
- Mobile/reduced-motion fallback.

Файлы:
- `twocomms/dtf/templates/dtf/index.html` (добавить/расширить блог-ленту)
- возможно `twocomms/dtf/templates/dtf/blog.html` для secondary placement
- `twocomms/dtf/static/dtf/js/components/effect.infinite-cards.js`
- `twocomms/dtf/static/dtf/css/components/effect.infinite-cards.css`

### 6.4 Invalid input: Placeholders + Vanish + clear
- При invalid: shake + vanish + очистка поля.
- Плейсхолдеры цикличны, но останавливаются на focus/typing.
- Не ломать native a11y и фокус.

Файлы:
- `twocomms/dtf/static/dtf/js/components/vanish-input.js`
- `twocomms/dtf/static/dtf/css/components/vanish-input.css`
- шаблоны с критичными полями (`order.html`, `constructor_app.html`, `status.html`, `sample.html`)

### 6.5 Speed/Tremble text для сообщения “быстро / день в день”
- Точечно, короткая анимация, без постоянного цикла.
- Активировать on hover или one-shot on reveal.
- Обязательно `prefers-reduced-motion` fallback.

Файлы:
- `twocomms/dtf/templates/dtf/index.html`
- `twocomms/dtf/static/dtf/css/components/effect.speed-text.css` (новый)
- `twocomms/dtf/static/dtf/js/components/effect.speed-text.js` (опционально, если нужен trigger)
- подключение в `twocomms/dtf/templates/dtf/base.html`

### 6.6 Before/After (compare) в “идентичном” визуальном стиле
- Сделать parity с референсом из `Effects.MD` по UX-логике:
  - drag
  - hover (desktop)
  - autoplay с остановкой на interaction
- Держать mobile fallback и keyboard ARIA semantics.

Файлы:
- `twocomms/dtf/static/dtf/js/components/effect.compare.js`
- `twocomms/dtf/static/dtf/css/components/effect.compare.css`
- `twocomms/dtf/templates/dtf/index.html`
- `twocomms/dtf/templates/dtf/gallery.html`
- `twocomms/dtf/templates/dtf/effects_lab.html`

## 7) Дополнительные top-идеи из аудитов (рекомендуется внедрить после must)
1. Odometer-like анимация цены при изменении параметров в order-калькуляторе.
2. Tooltip-card для сложных терминов preflight (DPI, safe margin, tiny lines).
3. Text-generate для финального preflight summary (attention-first copy).
4. Lazy reveal “до/после” кейсов, привязанный к viewport (чтобы не грузить сразу всё).
5. Более явный trust-блок в constructor: “что проверено” + “что делает менеджер вручную”.

## 8) Техдолг, который закрыть ПЕРЕД внедрением wow-фич
1. Устранить конфликт FAB/dock/mobile-dock контрактом видимости.
2. Нормализовать output contract preflight между backend и шаблонами (`label` vs `code/message`).
3. Вычистить legacy мертвые инициализаторы в `dtf.js` (как минимум Compare/Tracing-beam legacy-блоки).
4. Для всех новых эффектов: один модуль = один четкий selector + cleanup function.

## 9) Контракты реализации (минимальный стандарт)

### 9.1 Общий контракт effect-модуля
- Инициализация через `DTF.registerEffect(...)`.
- Идемпотентность через `core.js` lifecycle.
- Возврат cleanup function при наличии listeners/RAF/timers.
- Уважение `reducedMotion` и coarse pointer.

### 9.2 Infinite cards contract
- `data-effect="infinite-cards"`
- `data-direction="left|right"`
- `data-speed="slow|normal|fast"`
- `data-pause-on-hover="true|false"`
- Клон всегда `aria-hidden="true" inert role="presentation"`.

### 9.3 Compare contract
- `data-effect="compare"`
- `data-compare-mode="drag|hover|autoplay"`
- `data-autoplay="true|false"`
- ARIA slider + keyboard control.

### 9.4 Vanish contract
- `data-effect="vanish-input"`
- `data-vanish-input`
- `data-placeholders='[...]'`
- `data-cycle-duration="3000"`

## 10) Алгоритм внедрения (рекомендованная последовательность)
1. Baseline:
- сделать snapshot текущего поведения на `/`, `/order/`, `/constructor/app/`, `/blog/`, `/effects-lab/`.
2. Pre-cleanup:
- закрыть FAB/dock конфликт, выровнять preflight output contract.
3. Core must:
- Multi-step loader (реальные шаги), Compare parity, Vanish v2, Infinite cards SEO-safe.
4. Constructor UX:
- context dock + image badge + animation polish.
5. Marketing micro:
- speed/tremble text, optional text-generate summary.
6. QA + perf:
- функциональный smoke, accessibility checks, lighthouse delta.
7. Deploy DTF-only.

## 11) Риск-реестр
- Риск: перегрузка main thread из-за анимаций.
  - Mitigation: CSS transform/opacity, RAF throttling, reduced motion fallback.
- Риск: SEO дубли на infinite cards.
  - Mitigation: strict clone protocol (`aria-hidden`, `inert`, no links).
- Риск: неверный UX ожиданий в preflight loader.
  - Mitigation: показывать только реальные статусы, не fake delay.
- Риск: конфликт контекстного dock и глобальной навигации.
  - Mitigation: четкие роли: global dock = page navigation, constructor dock = local actions.
- Риск: breakage на mobile.
  - Mitigation: mobile-specific behavior map + manual QA at 320/375/768.

## 12) QA/Definition of Done

### 12.1 Functional DoD
- Compare: drag/hover/autoplay работают и останавливаются на user interaction.
- Loader: отображает реальные preflight шаги и корректный PASS/WARN/FAIL.
- Vanish: invalid очищает поле с эффектом, placeholders цикличны и не мешают вводу.
- Infinite cards: визуально бесконечная лента + SEO-safe clone protocol.
- Dock: нет перекрытия FAB/mobile-dock конфликтов.

### 12.2 Non-functional DoD
- Без JS: контент и критические пути доступны.
- A11y: keyboard/focus/aria-live не ломаются.
- Perf: без заметного роста CLS, без тяжелых фризов при взаимодействии.
- i18n: новый текст проходит через локализацию.

### 12.3 Проверки
Локально:
- `python3 -m compileall -q twocomms/dtf`
- `python3 twocomms/manage.py test dtf --settings=test_settings`

Серверно (минимум):
- `curl -i https://dtf.twocomms.shop/`
- `curl -i https://dtf.twocomms.shop/order/`
- `curl -i https://dtf.twocomms.shop/constructor/app/`
- `curl -i https://dtf.twocomms.shop/blog/`
- `curl -i https://dtf.twocomms.shop/robots.txt`
- `curl -i https://dtf.twocomms.shop/sitemap.xml`

## 13) Deploy protocol (DTF)
Базовый SSH-вход:
```bash
sshpass -p '${TWC_SSH_PASS}' ssh -o StrictHostKeyChecking=no qlknpodo@195.191.24.169 "bash -lc 'source /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.13/bin/activate && cd /home/qlknpodo/TWC/TwoComms_Site/twocomms && git pull'"
```

Рекомендуемый deploy-run (см. `specs/dtf-codex/DEPLOY.md`):
- `python manage.py check`
- `python manage.py migrate --noinput`
- `python manage.py collectstatic --noinput`
- `touch tmp/restart.txt`

## 14) Context retention checklist для следующего агента
Перед кодингом агент должен:
1. Прочитать этот файл полностью.
2. Прочитать `Ideas/Audit/o2/O2_PROMPT_FOR_NEXT_CODEX_IMPLEMENTATION_2026-02-09.md`.
3. Сверить текущие версии:
- `twocomms/dtf/templates/dtf/base.html`
- `twocomms/dtf/static/dtf/js/components/*.js`
- `twocomms/dtf/static/dtf/css/components/*.css`
- `twocomms/dtf/preflight/engine.py`
- `twocomms/dtf/views.py`
- `twocomms/dtf/forms.py`
4. Зафиксировать, что изменения ограничены DTF-путями.
5. Вести короткий worklog по фазам (что сделано, что осталось, какие риски).

## 15) Примечание по MCP
В следующем цикле обязательно использовать:
- Sequential Thinking MCP как основной процесс декомпозиции/проверки решений.
- Context7 MCP для точечных справок по API/паттернам.

Если Context7 недоступен в рантайме агента, fallback:
- локальный код проекта + официальная документация API браузера/библиотек.
