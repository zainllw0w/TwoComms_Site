# Anti-Duplication and Follow-Up Engine

## 1. Цель

У проекта уже есть:
- phone normalization,
- `ClientFollowUp`,
- `ReminderSent`,
- `ManagementLead`,
- `ShopPhone`,
- `CommercialOfferEmailLog`.

Но нет единого identity layer, который удерживает:
- exact duplicates,
- likely duplicates,
- cross-manager conflicts,
- batch import collisions,
- merge/rollback rules,
- priority order inside Action Stack.

## 2. Identity model

### 2.1 Базовые сущности
- `ClientIdentityKey`
- `ClientInteractionAttempt`
- `DuplicateReview`
- `OwnershipTransferLog`
- `FollowUpEscalationLog`

### 2.2 Identity keys
Храним ключи типов:
- phone,
- email,
- shop_name_normalized,
- google_place_id,
- messenger_handle,
- telephony_external_party_id.

## 3. Duplicate levels

### 3.1 Exact
Совпадает:
- normalized phone,
- или email,
- или telephony external party id,
- или `google_place_id`.

### 3.2 Likely
Совпадает composite similarity:
- shop name,
- city,
- partial phone,
- owner/contact name,
- site or Instagram,
- historical telephony overlap.

### 3.3 Suggestion
Сходство заметное, но не достаточное для auto-review priority.

### 3.4 Conflict
Есть ownership conflict или business contradiction.

## 4. Fuzzy matching algorithm

Вот этого действительно не хватало в первой версии пакета.

### 4.1 Preferred algorithm
Если БД = PostgreSQL, используем composite scoring:

`similarity = 0.40 * shop_name_similarity + 0.30 * phone_similarity + 0.20 * city_match + 0.10 * owner_similarity`

### 4.2 Thresholds
- `>= 0.95` = exact / auto-block
- `>= 0.70` = likely / review queue
- `>= 0.50` = suggestion / show in UI
- `< 0.50` = ignore

### 4.3 Fallback
Если `pg_trgm` или fuzzy DB tooling недоступны:
- используем normalized exact keys,
- prefix/substring phone checks,
- normalized shop name matching на стороне app service,
- manual review for borderline cases.

## 5. Create-or-append flow

Перед созданием клиента система обязана:
1. Проверить exact.
2. Проверить likely.
3. Показать модалку.
4. Дать действия:
- `open existing`,
- `append interaction`,
- `request ownership review`,
- `create branch with reason`.

`create branch with reason`:
- логируется,
- снижает trust при злоупотреблении,
- идёт в review queue,
- не даёт full new-contact credit.

## 6. Merge strategy

Теперь фиксирую merge policy, которой не хватало.

### 6.1 Rules
- primary = `most recent active canonical record`,
- secondary = `merged duplicate`,
- interactions = union to primary,
- follow-ups = consolidate, оставляем не более `1` активного follow-up на один смысловой next step,
- invoices and commercial records remap to primary,
- ownership history сохраняется,
- audit event обязателен.

### 6.2 Rollback
Merge rollback допускается в окно `72 часа`, пока не возникло необратимых downstream действий.

## 7. Batch import dedupe

### 7.1 Pipeline
1. Parse import file.
2. Remove internal batch duplicates.
3. Cross-check against DB.
4. Show preview:
- new,
- likely duplicates,
- exact duplicates,
- conflict rows.
5. Import only approved clean subset.

### 7.2 Why it matters
Если этот слой не сделать, batch import будет мгновенно ломать всю identity-модель.

## 8. Duplicate scoring rules

- exact duplicate = no new-contact credit,
- append interaction = process/follow-up credit only,
- branch override = anomaly signal,
- repeated override = trust reduction,
- merge-confirmed fraud case = admin-reviewed penalty.

## 9. Follow-up ladder

### 9.1 Для клиента
1. `scheduled`
2. `T-15m reminder`
3. `due`
4. `overdue + 2h`
5. `end-of-day breach`
6. `day-2 escalation`
7. `day-3 admin review`

### 9.2 Для магазина
1. `healthy cadence`
2. `watch`
3. `risk`
4. `rescue`
5. `reassign eligible`

## 10. Smart Action Stack prioritization

Opus прав: эскалация времени без приоритета по ценности недостаточна.

### 10.1 Priority score
`priority = 0.35 * pipeline_value + 0.30 * portfolio_urgency + 0.20 * response_probability + 0.15 * overdue_urgency`

Это нужно для сортировки `Today Action Stack`.

### 10.2 Why
Клиент на `200k` с высоким шансом ответа и уже тёплой историей должен идти выше, чем слабый холодный хвост только потому, что он старее на пару часов.

## 11. Reminder design

### 11.1 Channels
- in-app,
- Telegram,
- admin digest,
- QA queue,
- optional mobile push later.

### 11.2 Dedupe key
`{channel}:{target}:{event_type}:{time_bucket}`

### 11.3 Low-noise principle
- похожие напоминания агрегируются,
- high value tasks поднимаются выше,
- admin sees summary, not spam,
- action buttons are inline.

## 12. Technical rules

### 12.1 DB layer
- `UniqueConstraint` на exact identity keys,
- partial constraints where needed,
- indexes for phone/date/status lookups,
- JSON snapshots only for breakdowns,
- all overrides go to audit log.

### 12.2 Celery layer
- one active beat,
- overlap-sensitive jobs under lock,
- idempotent reminder jobs,
- rerun must not duplicate notifications.

## 13. Data migration note

Identity engine без migration plan бессмысленен.

План backfill и cleanup вынесен в:
- `07_IMPLEMENTATION_ROADMAP.md`

Cross-cutting audit and safety rules вынесены в:
- `13_CROSS_SYSTEM_GUARDRAILS.md`
