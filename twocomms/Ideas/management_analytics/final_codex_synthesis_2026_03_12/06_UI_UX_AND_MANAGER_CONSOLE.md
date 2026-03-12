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

### 4.3.1 Rescue Top-5
`rescue top-5` не должен быть произвольным списком тревоги. Нормативная сортировка:
- по `Expected LTV Loss`, а не по голому overdue;
- с объяснением, почему клиент оказался в top-5;
- не более `5` карточек одновременно, чтобы не превращать экран в "лес умирающих деревьев".

Рабочая формула:
`Expected LTV Loss = avg_order_value × expected_orders_per_year × P(churn_weibull)`

`P(churn_weibull)` обязан:
- использовать logistic fallback при `<5` заказах;
- уважать `expected_next_order` / planned gap;
- не маскироваться под generic "risk score" без объяснения модели.

Если точный LTV ещё недоступен, допускается fallback через `pipeline_value + churn_risk`, но UI обязан пометить это как interim logic.

Виджет также обязан показывать:
- potential scaled `SPIFF` за verified rescue (`500-2000 грн`);
- cap на новый rescue-load: не более `3` rescue-клиентов/day из pool без admin override;
- `DQ grace` / report-integrity предупреждение, если менеджера нельзя безопасно перегружать rescue-задачами в этот день.

### 4.4 Portfolio block
Отдельный блок портфеля обязан показывать:
- `Healthy / Watch / Risk / Rescue`;
- snoozed clients;
- reactivation queue;
- orphan / rescue review candidates;
- ожидаемый объём внимания по портфелю.

### 4.4.1 Client communication timeline
Карточка клиента должна иметь единый `communication timeline`, чтобы следующий touch не требовал ручного восстановления истории по нескольким экранам.

Минимальный состав timeline:
- calls;
- email / КП;
- CRM notes;
- follow-ups and reschedules;
- invoices / orders;
- ownership changes;
- QA / dispute flags where relevant.

### 4.5 Salary simulator
`Salary Simulator` становится обязательным manager surface:
- new commission;
- repeat commission;
- reactivation commission;
- soft-floor effect;
- what-if scenarios;
- payout expectations.

В shadow mode simulator должен уметь показывать `hold harmless` delta:
- если новая система дала бы больше текущей, разница видна как bonus delta;
- если новая система дала бы меньше, менеджер в shadow period не должен воспринимать это как уже совершившийся штраф.

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
- `SourceFairness`
- `Process`
- `FollowUp`
- `DataQuality`
- `VerifiedCommunication`

Важно: Radar — explanatory surface, а не payroll truth сама по себе.

Если команде позже понадобится отдельный coaching-profile Radar с осями вроде `Volume / Efficiency / Pipeline`, он должен существовать как отдельный виджет, а не подменять authoritative MOSAIC Radar.

### 5.3 Режимы
- single manager profile;
- current vs previous period;
- admin overlay нескольких менеджеров.

При `N < 3` managers:
- manager-facing Radar показывает только self profile + previous period;
- comparative overlay скрывается, чтобы не деанонимизировать коллегу и не создавать ложную "командную норму" на сверхмалой выборке.

### 5.4 Интеграция с текущим UI
Radar добавляется как новый блок рядом или сразу под текущим hero / spiral zone.

Спираль:
- остаётся текущим activity/KPD summary.

### 5.5 Explainable waterfall
Каждая score-sensitive цифра должна быть кликабельной и раскрываться в waterfall / decomposition view.

Минимум:
- base score / payout before modifiers;
- влияние trust, gate, dampener и portfolio/rescue logic;
- short text explanation для каждого шага;
- отдельная shadow label, если расчёт ещё не production-final.

Radar:
- показывает более структурированный профиль по измерениям.

Обе поверхности могут сосуществовать в переходном периоде.

### 5.6 Correctability / appeal affordance
Explainability без correctability остаётся половиной решения.

Manager-facing правило:
- рядом с score-sensitive decline, payout-sensitive adjustment или QA-sensitive review должен быть явный `Appeal / Оспорить`;
- appeal CTA не показывается для purely informative cards без consequence layer;
- лимит по scoring appeals живёт через weekly guard, но valid appeal возвращает слот обратно.

Admin-facing правило:
- appeal должен открывать evidence-first review drawer, а не свободный текстовый хаос;
- результат фиксируется как `confirm / adjust / reject`;
- appeal history остаётся видимой в audit trail и не исчезает после resolution.

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
- payback / contribution views;
- forecast scenarios;
- score confidence label (`LOW / MEDIUM / HIGH`) для решений.

### 7.4 Review surfaces
Админ должен иметь отдельные surfaces для:
- duplicate disputes;
- Red Card / freeze;
- payout adjustments;
- appeals;
- snooze approvals;
- readiness status по компонентам.
- force-majeure trigger с reason и affected window;
- saved filters / queue presets / contextual evidence drawer для high-volume review work.

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

### 10.1 Обязательные mobile requirements
- bottom navigation или другой equally stable thumb-friendly shell;
- one-thumb primary actions for callback / reschedule / complete;
- compact action stack without hover dependency;
- fast add/log flow;
- push-ready notification surface;
- critical buttons must stay visible without desktop-only affordances.

### 10.2 What must work first-class on mobile
- Today Action Stack;
- callback handling;
- quick call logging;
- rescue actions;
- no-touch report confirm;
- earnings snapshot.

### 10.3 General rule
- manager не должен быть привязан к desktop only для follow-up discipline;
- charts допустимы, но не должны ломать основной сценарий;
- PWA можно рассматривать как enhancement later phase, но mobile-first worklist обязателен сразу.

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
- client communication timeline payload and UI;
- readiness badges;
- admin review / freeze / snooze widgets;
- confidence labels and hold-harmless messaging in shadow mode.

### 14.3 Что нельзя делать
- нельзя удалять текущие рабочие KPI/advice surfaces до замены;
- нельзя показывать punitive copy как default;
- нельзя делать ключевые workflows desktop-only.
