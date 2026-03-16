# Trust and Anti-Abuse Specification

## 1. Проблема
Сейчас значительная часть данных self-reported. Без записи разговоров нельзя считать все действия равнозначно достоверными.

## 2. Trust tiers
- Tier 1 (Hard verified): paid invoices, paid orders, approved revenue.
- Tier 2 (System verified): CP email logs, due follow-up completion, timestamped actions.
- Tier 3 (Self-reported structured): notes, messenger outreach, call outcomes without recording.
- Tier 4 (Weak signal): passive activity and low-context actions.

## 3. Базовый принцип
Tier 1 и Tier 2 задают backbone score.
Tier 3 и Tier 4 влияют ограниченно и только через trust-normalized weighting.

## 4. Threat model (manager-side abuse)
1. Массовое выставление "не интересно" без причин.
2. Фиктивные "отправил КП" без фактического отправленного письма.
3. Закрытие no-answer без обязательных попыток.
4. Искусственный "спринт" активностей за короткий интервал.
5. Копипаст причины отказа для bulk закрытия базы.
6. Отсутствие daily report для сокрытия дисциплинарных провалов.

## 5. Countermeasures

### 5.1 Mandatory validations
1. `not_interested` требует reason code.
2. reason `other` требует detail text min length.
3. `sent_email` требует CP-link на конкретный лог.
4. `no_answer` требует цепочку попыток, иначе статус неполный.

### 5.2 Trust penalties
1. Missing reason ratio > threshold -> trust down.
2. Callback overdue ratio > threshold -> trust down.
3. Unverified channel overuse -> trust down.
4. Anomaly velocity flags -> trust down.

### 5.3 Gate synergy
Даже если trust высокий, без paid conversion действует hard gate.

## 6. Trust coefficient detail
`trust_coeff in [0.55, 1.05]`

### 6.1 Input definitions
- `verified_ratio = verified_events / total_events`
- `reason_quality = valid_reason_events / not_interested_events`
- `anomaly_penalty` строится из:
- concentration index,
- repeated-reason pattern,
- no-report streak,
- callback breach streak.

### 6.2 Trust alert levels
- `>= 0.95`: healthy.
- `0.85..0.94`: caution.
- `0.70..0.84`: risk.
- `< 0.70`: critical.

## 7. Incidents and disciplinary events

### 7.1 Почему только admin-verified
Дисциплинарные инциденты влияют на карьерные решения и зарплатные последствия, значит они не могут формироваться автоматически без проверки.

### 7.2 Incident categories
- Client complaint.
- Rude communication.
- Fraud attempt.
- Process manipulation.

### 7.3 Incident severity
- S1 (minor).
- S2 (material).
- S3 (critical).

### 7.4 Score influence
- В manager daily score: мягкий effect через trust/disciplined trend.
- В admin daily score: дополнительный explicit penalty layer.

## 8. Anti-abuse policy for no-answer
1. Attempt 1: create follow-up.
2. Attempt 2: create follow-up + warning.
3. Attempt 3: eligible close with limited credit.
4. Пропуск назначенного callback -> escalating penalty and trust reduction.

## 9. Data integrity rules
1. Нельзя изменять verified события без audit trail.
2. Любой manual override требует reason + actor + timestamp.
3. Dismiss/ack советов не должен удалять исходные сигналы.

## 10. Auditability
Система обязана хранить:
- сырые события,
- нормализованные признаки trust,
- итог trust calculation snapshot на день.

Это позволит объяснить менеджеру и администратору, почему score изменился.
