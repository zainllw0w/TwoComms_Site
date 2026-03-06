# UI, UX and Management Console

## 1. Принцип

Интерфейс management subdomain не должен быть “красивой статистикой”.
Он должен:
- показывать следующее лучшее действие,
- удерживать внимание на деньгах, клиентах и рисках,
- уменьшать трение,
- делать систему объяснимой,
- не превращать работу в токсичную игру.

## 2. Manager console

### 2.1 Верхний ряд
- `MOSAIC score today`
- `week KPI progress`
- `portfolio health`
- `current earnings`
- `callbacks due today`

### 2.2 Главный центральный блок
`Today Action Stack`

Порядок:
1. просроченные callback,
2. клиенты в `Risk/Rescue`,
3. warm leads without next action,
4. duplicate resolutions,
5. calls to review after QA.

### 2.3 Portfolio block
Берём идею `Tamagotchi`, но убираем клоунаду.

Вместо дешёвой геймификации делаем:
- живые карточки клиентов,
- цвет здоровья,
- маркер упущенных денег,
- trigger “лучший следующий шаг”.

### 2.4 Salary simulator
Идею сохраняем.

Менеджер может увидеть:
- если вернуть 2 риск-клиента,
- если получить 1 новый first order,
- если закрыть 1 repeat на такую-то сумму,
- как изменится итог месяца.

Это одна из самых сильных идей Gemini и её обязательно нужно внедрить.

### 2.5 Heatmap and Golden Hour
На одной странице:
- monthly heatmap,
- personal top hours,
- 7-day trend,
- reason-quality trend,
- callback SLA trend.

## 3. Admin console

### 3.1 Верхний ряд
- team score snapshot,
- no-report count,
- QA risk count,
- duplicate queue,
- payroll risk count,
- portfolio churn risk.

### 3.2 Control center
Нужны 5 колонок:
- `Coaching Needed`
- `QA Reviews`
- `Duplicate/Ownership Reviews`
- `KPI Breach`
- `Rescue/Reassign Candidates`

### 3.3 Team analytics
Отдельные вкладки:
- team heatmap,
- source mix performance,
- conversion funnel,
- portfolio health by manager,
- payback and ROI,
- telephony quality.

## 4. QA / Supervisor console

Отдельный режим, а не просто модалка у админа.

Нужны:
- live queue,
- recording player,
- scorecard panel,
- calibration mode,
- coaching notes,
- disagreement flag,
- outcome mismatch flag.

## 5. Что из Gemini берём, но ослабляем

### Берём
- `Tamagotchi/portfolio health`,
- `salary simulator`,
- `golden hour`,
- `no-touch report`,
- `shadow rival`.

### Не берём в сыром виде
- `Shark Pool`,
- `Doomsday Screen`,
- публичное унижение,
- агрессивные тексты про выживание и слабых.

## 6. No-touch report

Это сильная практическая идея.

В конце дня менеджер не должен писать сочинение.
Система сама собирает draft:
- звонки,
- verified progress,
- новые подключения,
- repeat reactivation,
- риски на завтра,
- краткий self-comment.

Менеджер:
- подтверждает,
- дописывает 1-2 строчки,
- отправляет.

Это поднимет report compliance сильнее, чем любые угрозы.

## 7. Shadow rival

Идею оставляем только в мягкой форме:
- без публичного shame,
- без токсичного текста,
- только локальное сравнение рядом с личным прогрессом.

Формулировка должна быть:
- “ещё 2 качественных действия и вы подниметесь на 1 позицию”,
а не
- “обгони Игоря, иначе ты слабый”.

## 8. Дизайн-язык

Нужна эстетика `операционный центр`, а не просто таблица.

Основные принципы:
- высокий signal density,
- крупные actionable cards,
- спокойная цветовая система,
- минимальное количество декоративного шума,
- сильный hover/explainability слой,
- один primary CTA на блок.

## 9. Что нельзя терять в UI

- explainability score,
- clear next actions,
- portfolio visibility,
- supervisor visibility,
- separation of manager/admin/private financial details,
- mobile-usable worklists для менеджера,
- desktop-optimized admin and QA views.
