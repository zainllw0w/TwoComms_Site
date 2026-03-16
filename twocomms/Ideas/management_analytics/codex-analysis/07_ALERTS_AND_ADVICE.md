# Alerts and Advice System Spec

## 1. Каналы
- In-app notification center.
- Telegram manager/admin channels.

## 2. Ключевые события
1. Daily report submitted.
2. Daily report missing.
3. Callback overdue.
4. Trust drop below threshold.
5. Conversion drought streak.
6. Advice generation cycle complete.

## 3. Расписание

### 3.1 Manager
1. Сразу после отправки отчета: day review + советы.
2. В 10:00 local: digest только если отчет за целевой день существует.

### 3.2 Admin
1. В 10:00 local: сводка по всем менеджерам всегда.
2. Для менеджеров без отчета: `no-report` flag с уровнем риска.
3. Critical alerts: callback breach, trust critical, anomaly spike.

## 4. No-report policy
Если отчет отсутствует:
- manager 10:00 digest не отправляется,
- admin получает флаг:
- manager id,
- day,
- active signals,
- risk tier,
- suggested action.

## 5. Advice engine requirements
1. Advice всегда содержит evidence block.
2. Advice помечается как assumption/inference, если основан на вероятностных признаках.
3. Advice имеет severity (`good`, `neutral`, `bad`, `critical`).
4. Advice можно dismiss/ack, но исходные сигналы не удаляются.

## 6. Critical alert templates

### 6.1 Callback overdue
"Просрочений передзвін: {count}. Ризик втрати конверсії."

### 6.2 Trust drop
"Рівень довіри впав до {trust}. Потрібна перевірка якості обробки."

### 6.3 No-report
"Менеджер {name} не подав звіт за {date}. Оцініть дисципліну та pipeline ризики."

## 7. Scheduling architecture

### 7.1 Celery requirements
1. Один active beat scheduler.
2. Overlap-sensitive задачи выполняются под lock.
3. Идемпотентность отправки (dedupe keys).

### 7.2 Suggested jobs
- `daily_score_finalize` (00:05).
- `manager_digest_10am` (10:00).
- `admin_digest_10am` (10:00).
- `callback_overdue_scan` (каждые 30 минут).
- `trust_anomaly_scan` (каждый час).

## 8. Dedupe keys
Каждое сообщение должно иметь стабильный key:
`{channel}:{user_or_group}:{event_type}:{date_or_ts_bucket}`

## 9. Escalation ladder
1. Warning.
2. Urgent.
3. Critical.
4. Admin mandatory review.

## 10. Acceptance conditions
1. Повторный запуск джобы не дублирует уведомления.
2. Manager 10:00 без отчета не получает digest.
3. Admin 10:00 видит no-report флаги.
4. Critical события приходят не позже SLO (15 мин).
