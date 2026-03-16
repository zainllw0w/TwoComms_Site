# 06. UI/UX: manager/admin surfaces, explainability и fairness-perception

## 1. Что current package делает очень правильно
- action-first manager console;
- recovery-first copy;
- separate admin control center;
- Radar + waterfall coexist in transition;
- appeal affordance уже встроен;
- mobile-first requirements зафиксированы;
- shadow/dormant/frozen states названы явно.

Это очень сильная база. Улучшать нужно точечно, не перерисовывая всё.

## 2. Главный UX risk
Чем система точнее, тем больше риск, что пользователь воспримет её как opaque.
Поэтому я считаю главным направлением UI-усиления не “ещё один график”, а:
- показывать **уверенность** и **свежесть** числа;
- объяснять **что изменилось именно сегодня**;
- визуально отделять **minimum / target / shadow / frozen**.

## 3. Что я бы добавил в manager console

### 3.1 `Почему изменилось сегодня`
Отдельный мини-блок рядом с hero:
- `+4` за follow-up recovery
- `-3` за missed due window
- `+2` за verified commercial progress
- `shadow only` for explanatory changes

Это уменьшает ощущение “число само прыгнуло”.

### 3.2 `Snapshot freshness` banner
Если последний snapshot старше safe-window:
- показывать banner `данные не обновлялись X часов`
- не прятать экран,
- но блокировать иллюзию текущей точности

Для payout-adjacent shadow cards при stale snapshot лучше показывать `stale / awaiting refresh`.

### 3.3 Confidence badges на ключевых поверхностях
Не только в admin.
В manager UI тоже полезно показывать:
- `HIGH confidence`
- `MEDIUM confidence`
- `LOW confidence`

Но не везде, а в наиболее спорных местах:
- rescue top-5
- salary simulator shadow layer
- portfolio-risk transitions

### 3.4 Distinction между `minimum day` и `target pace`
Это очень важно.
Иначе менеджер увидит “earned day = да” и может решить, что pace тоже healthy.

UI should show:
- `день закрыт минимально`;
- `идёте в целевом темпе`;
- `нужен recovery`.

### 3.5 Advice cooldown / anti-spam
Правило `max 3 cards` хорошее, но этого мало.
Нужно ещё:
- `cooldown_hours`
- `dismiss_ttl`
- `reappear_only_if_state_changed`

Иначе одни и те же advice cards быстро перестанут читаться.

## 4. Benchmarking: где я бы был осторожнее пакета
Пакет уже скрывает comparative overlays при `N < 3`, и это правильно.
Но для truly anonymous benchmark я бы был ещё консервативнее:
- `N < 5` -> no peer benchmark in manager view
- `N = 3-4` -> only self vs previous period
- peer benchmark разрешать лишь через aggregated team band or admin layer

Это safer для tiny team и снижает риск полу-прозрачной деанонимизации.

## 5. Radar: как сделать его ещё честнее

### 5.1 Axis confidence ring
Если axis low-sample or dormant-adjacent:
- контур оси dashed;
- badge `low data`;
- comparison suppressed.

### 5.2 Change arrows per axis
Чтобы Radar не был просто красивой картинкой, добавить:
- small `↑ / ↓ / →` per axis vs previous period

### 5.3 `Why this axis is low` drawer
По клику не только decomposition, но и:
- 2-3 root causes
- 1 next action

## 6. Rescue UI: что улучшить без усложнения

### 6.1 Разделить `deadline risk` и `value risk`
В top-5 карточке полезно отдельно показывать:
- `value at risk`
- `time urgency`

Тогда менеджер понимает, почему карточка высокая в списке.

### 6.2 Confidence + planned gap display
Если клиент пока в planned gap или churn-confidence low:
- показать это прямо в карточке,
- иначе top-5 выглядит слишком категорично.

### 6.3 Action stack split
Today Action Stack лучше делить на:
- `обязательные сегодня`
- `лучшие возможности дня`

Это уменьшает cognitive overload.

## 7. Salary simulator: что улучшить
- показывать confidence band, а не только single number;
- для shadow-mode отображать `current truth / shadow candidate / delta`;
- отдельно показывать `why delta happened`;
- freeze items отображать с explicit status line.

## 8. Mobile-first: что бы я усилил дополнительно
- offline-safe draft for quick notes / report confirm;
- sticky quick-action footer only on action screens, not everywhere;
- one-tap callback result templates;
- compact state chips (`ACTIVE / SHADOW / FROZEN / STALE`).

## 9. Admin UX: где есть потенциал роста

### 9.1 `Formula / snapshot / jobs health` widget
В admin стоит добавить верхний системный блок:
- current formula version
- snapshot freshness
- last successful nightly job
- stale risk
- active incidents

### 9.2 Queue presets
Пакет уже намекает на saved filters. Я бы сделал обязательными presets:
- duplicate review
- payout freeze
- low confidence managers
- overloaded follow-up
- telephony mismatch
- appeals awaiting SLA breach

### 9.3 Evidence-first compare drawer
Для admin compare нескольких managers полезно видеть не только цифры, но и:
- data volume
- verified coverage
- stale flags
- concentration risk

## 10. Наиболее вероятные UX bugs без этих улучшений

### Bug 1 — число честное, но выглядит произвольным
Из-за отсутствия “why changed today” layer.

### Bug 2 — shadow number visually looks final
Если не показывать freshness/confidence/state clearly enough.

### Bug 3 — manager optimizes to minimum day
Если UI не разводит minimum vs target.

### Bug 4 — anonymous benchmark де-факто раскрывает коллегу
Если в tiny team peer compare включить слишком рано.

## 11. Что менять в каких файлах
- `06_UI_UX_AND_MANAGER_CONSOLE.md` — freshness/confidence, advice cooldown, benchmark threshold
- `03_PAYROLL_KPI_AND_PORTFOLIO.md` — minimum vs target pace copy
- `15_ADMIN_ECONOMICS_AND_EARNED_DAY.md` — admin health and confidence widgets
- `11_PRODUCT_BACKLOG_FOR_MANAGEMENT_SUBDOMAIN.md` — new UI blocks and payload builders
- `stats.html`, `admin.html`, `base.html`, JS/CSS assets

## 12. Приоритет внедрения
1. snapshot freshness / state badges
2. why-changed-today block
3. minimum vs target pace distinction
4. advice cooldown
5. queue presets and admin health widget
6. benchmark hardening
