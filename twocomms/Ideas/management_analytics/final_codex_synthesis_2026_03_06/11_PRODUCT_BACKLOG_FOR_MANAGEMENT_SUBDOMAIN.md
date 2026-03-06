# Product Backlog for Management Subdomain

## 1. Зачем нужен этот файл

Документы `01..10` фиксируют решения.
Этот файл переводит их в список модулей, которые реально нужно построить.

## 2. Core modules

### Module A: Score and Analytics Core
Содержит:
- `ManagerDailyScoreSnapshot`,
- `AdminDailyScoreSnapshot`,
- `PortfolioHealthSnapshot`,
- `SeasonalLadderSnapshot`,
- explainability payload,
- heatmap payload.

Готово, когда:
- score считается в shadow mode,
- объясняется по осям,
- корректно работает на исторических данных.

### Module B: Duplicate and Identity Core
Содержит:
- `ClientIdentityKey`,
- duplicate resolver,
- merge/append workflow,
- ownership conflict handling.

Готово, когда:
- exact duplicate ловится до сохранения,
- likely duplicate идёт в review,
- create-anyway логируется и ограничивается.

### Module C: Follow-Up and Reminder Engine
Содержит:
- callback ladder,
- stale shop cadence,
- no-report logic,
- digest jobs,
- action queues.

Готово, когда:
- reminder flow не спамит,
- manager получает понятные next actions,
- admin видит risk queues.

### Module D: Payroll and KPI Core
Содержит:
- daily soft KPI,
- weekly hard KPI,
- monthly compliance check,
- payroll preview,
- accelerator logic,
- penalty governance.

Готово, когда:
- менеджер видит расчёт,
- админ видит hold/freeze/risk,
- формула не зависит от ручных Excel-подсчётов.

### Module E: Portfolio Management
Содержит:
- client health states,
- orphan risk,
- rescue list,
- reassign eligible logic,
- repeat activation prompts.

Готово, когда:
- старые клиенты перестают теряться,
- повторные продажи имеют управленческий интерфейс, а не только комиссию.

### Module F: Telephony and QA Core
Содержит:
- telephony provider bridge,
- call events,
- recordings,
- QA reviews,
- calibration,
- supervisor actions.

Готово, когда:
- звонок связывается с CRM,
- админ может слушать и оценивать,
- QA влияет на coaching и trust.

### Module G: Manager Console
Содержит:
- Today Action Stack,
- salary simulator,
- portfolio health block,
- heatmap,
- golden hour,
- no-touch report.

Готово, когда:
- менеджер с домашней страницы понимает, что делать сейчас, не открывая 10 страниц.

### Module H: Admin and QA Console
Содержит:
- action center,
- duplicate queue,
- KPI breach queue,
- payroll risk,
- QA lab,
- team analytics.

Готово, когда:
- админ управляет командой через очереди действий, а не через поиск по страницам.

### Module I: DTF Read-Only Bridge
Содержит:
- отдельные summary cards,
- read-only health metrics,
- status integration,
- drilldown without metric mixing.

Готово, когда:
- DTF виден,
- но не ломает wholesale management logic.

## 3. API and service backlog

Нужны сервисы:
- duplicate check service,
- score calculation service,
- portfolio health service,
- reminder scheduler service,
- telephony ingest service,
- QA scoring service,
- payroll preview service.

Нужны API:
- duplicate preview,
- interaction append,
- callback resolve/reschedule,
- score explain,
- portfolio action,
- QA review save,
- payroll preview,
- admin queue endpoints.

## 4. UI backlog

Нужны экраны:
- manager home v2,
- duplicate modal,
- callback drawer,
- portfolio board,
- salary simulator modal,
- admin action center,
- QA recording review screen,
- team heatmap screen,
- payroll screen,
- DTF read-only dashboard.

## 5. Dependency order

Порядок зависит не от красоты, а от базового data integrity:
1. Identity and duplicate core.
2. Follow-up and reminders.
3. Score snapshots in shadow mode.
4. Manager/admin consoles.
5. Payroll activation.
6. Telephony and QA.
7. Advanced coaching and AI assist.
8. DTF read-only extension.

## 6. Что является ошибкой внедрения

Считать ошибкой, если команда попытается:
- начать с красивого UI без duplicate and callback core,
- включить penalties до shadow validation,
- включить AI coaching до нормальной verified data,
- склеить DTF в общий score,
- заменить review queues простыми пушами.
