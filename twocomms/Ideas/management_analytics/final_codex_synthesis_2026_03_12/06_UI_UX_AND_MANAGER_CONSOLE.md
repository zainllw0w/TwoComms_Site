# UI, UX and Management Console

## 1. Роль этого файла
Этот документ задаёт не "общий вкус", а точную UI/UX архитектуру management-поддомена:
- что остаётся из текущего интерфейса;
- какие новые блоки становятся обязательными;
- что видит менеджер;
- что видит админ;
- как объяснять score и дисциплину без punitive copy.

## 2. Главный UX-принцип
Management UI должен быть:
- action-first;
- recovery-first;
- role-separated;
- explainable;
- mobile-usable;
- совместимым с постепенным rollout.

Любая surface, которая сообщает о слабом результате, должна:
- объяснять причину;
- показывать зону восстановления;
- не превращать экран в панель наказания.

## 3. Что сохраняем из current UI
Текущий UI уже имеет сильную базу:
- `stats.html` с hero-блоком и spiral-visualization;
- KPI cards;
- advice list;
- follow-up section;
- admin list / admin user views;
- payout/admin surfaces.

Финальное правило:
- не ломать existing information architecture ради полной перерисовки;
- усиливать текущий интерфейс новыми модулями;
- старый spiral chart не удалять сразу, а использовать как текущий score-view рядом с новым аналитическим слоем.

## 4. Manager console

### 4.1 Верхний слой
Верх страницы менеджера должен содержать:
- period selector;
- текущий owner / persona context;
- concise KPI summary;
- primary CTA к action surfaces, а не только к просмотру цифр.

### 4.2 Hero zone
Hero-блок менеджера должен объединять:
- current KPD / shadow MOSAIC status;
- Radar preview;
- короткое explainability summary;
- delta к прошлому периоду;
- главный recovery hint.

### 4.3 Today Action Stack
Обязательный рабочий блок:
- overdue follow-ups;
- сегодня критичные клиенты;
- rescue top-5;
- pending next steps;
- текущие blockers.

Менеджер должен видеть именно порядок действий, а не просто историю проблем.

### 4.4 Portfolio block
Отдельный блок портфеля обязан показывать:
- `Healthy / Watch / Risk / Rescue`;
- snoozed clients;
- reactivation queue;
- orphan / rescue review candidates;
- ожидаемый объём внимания по портфелю.

### 4.5 Salary simulator
`Salary Simulator` становится обязательным manager surface:
- new commission;
- repeat commission;
- soft-floor effect;
- what-if scenarios;
- payout expectations.

### 4.6 Golden Hour и micro-feedback
Допустимы и желательны:
- heat / best hour hints;
- micro-feedback stream;
- small wins;
- progress-to-target cues.

Но:
- без humiliating gamification;
- без ощущения, что менеджер живёт в игре, а не в рабочей системе.

## 5. Radar Chart

### 5.1 Зачем он нужен
Radar нужен как компактный visual summary того, из чего складывается performance profile менеджера.

### 5.2 Оси
Нормативные оси:
- `Result`
- `Volume`
- `Discipline`
- `Efficiency`
- `Pipeline`
- `Communication`

Важно: Radar — explanatory surface, а не payroll truth сама по себе.

### 5.3 Режимы
- single manager profile;
- current vs previous period;
- admin overlay нескольких менеджеров.

### 5.4 Интеграция с текущим UI
Radar добавляется как новый блок рядом или сразу под текущим hero / spiral zone.

Спираль:
- остаётся текущим activity/KPD summary.

Radar:
- показывает более структурированный профиль по измерениям.

Обе поверхности могут сосуществовать в переходном периоде.

## 6. Advice surfaces

### 6.1 Recovery-first copy
Запрещённая семантика:
- "штраф";
- "провал";
- "ти знову просів";
- скрытая угроза без actionable path.

Нормативная семантика:
- "потребує уваги";
- "є простір для зростання";
- "варто переглянути пріоритети";
- "наступний крок".

### 6.2 Advice structure
Каждый advice card должен содержать:
- заголовок;
- суть;
- evidence;
- CTA;
- dismiss behavior.

### 6.3 Shadow labels
Если совет или score построен на shadow-layer, UI обязан пометить это явно.

## 7. Admin console

### 7.1 Главная задача
Admin console — это control center, а не просто таблица по менеджерам.

### 7.2 Обязательные admin блоки
- team / manager selector;
- KPI and payout overview;
- shadow MOSAIC and current KPD side by side;
- portfolio risk map;
- duplicate review queue;
- follow-up overload alerts;
- payout and accrual controls;
- force majeure / freeze / review actions.

### 7.3 Admin economics panel
Отдельный admin-only блок должен показывать:
- score-to-money relationship;
- accrual decomposition;
- repeat/new mix;
- recovery cost;
- payback / contribution views.

### 7.4 Review surfaces
Админ должен иметь отдельные surfaces для:
- duplicate disputes;
- Red Card / freeze;
- payout adjustments;
- appeals;
- snooze approvals;
- readiness status по компонентам.

## 8. Supervisor / QA console

### 8.1 Когда появляется
Supervisor/QA блок активируется после telephony rollout.

### 8.2 Что он должен уметь
- очереди звонков на review;
- rubric results;
- coaching notes;
- calibration states;
- trend views по качеству разговора.

До telephony maturity этот слой остаётся dormant или hidden.

## 9. Progressive disclosure
Не все пользователи должны видеть всю сложность сразу.

Финальная логика:
- manager видит только нужный слой действий;
- admin видит deeper analytics;
- advanced diagnostic blocks раскрываются по запросу;
- shadow/internal uncertainty не masquerades as certainty.

## 10. Mobile-first требования
- основные CTA и action queues должны нормально работать на телефоне;
- manager не должен быть привязан к desktop only для follow-up discipline;
- charts допустимы, но не должны ломать основной сценарий;
- critical buttons не должны прятаться за hover-only interactions.

## 11. Accessibility и reliability
- сильный контраст на статусных состояниях;
- текстовые подписи рядом с цветом;
- понятные loading / stale / shadow labels;
- no reliance on color only;
- ясное отображение active vs shadow vs dormant components.

## 12. States and visibility
Каждый новый блок должен иметь явное состояние:
- `ACTIVE`
- `SHADOW`
- `DORMANT`
- `FROZEN`

Пример:
- Radar может быть `SHADOW`;
- telephony widgets — `DORMANT` до rollout;
- payout item under review — `FROZEN`.

## 13. What must never be lost
- manager должен видеть, что делать дальше;
- admin должен видеть, где система ещё не готова;
- пользователь не должен путать shadow-number с payroll truth;
- интерфейс не должен превращаться в эмоционально токсичную панель.

## 14. Приземление в текущий код

### 14.1 Основные файлы
- `management/templates/management/stats.html`
- `management/templates/management/admin.html`
- `management/templates/management/base.html`
- `twocomms_django_theme/static/js/management-activity.js`
- future chart-specific JS/CSS assets

### 14.2 Что нужно будет добавить
- Radar block;
- shadow MOSAIC decomposition;
- salary simulator surfaces;
- rescue top-5 block;
- readiness badges;
- admin review / freeze / snooze widgets.

### 14.3 Что нельзя делать
- нельзя удалять текущие рабочие KPI/advice surfaces до замены;
- нельзя показывать punitive copy как default;
- нельзя делать ключевые workflows desktop-only.
