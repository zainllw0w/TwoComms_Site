# Data Model and API Contract

## 1. Цель
Фиксация сущностей, полей, индексов и API-контрактов для внедрения гибридной системы оценки и workflow контроля.

## 2. Core entities

### 2.1 ManagerDailyScore
- `date` (date, indexed)
- `manager_id` (fk/auth user, indexed)
- `result_score` (float)
- `quality_score` (float)
- `activity_score` (float)
- `pipeline_score` (float)
- `discipline_score` (float)
- `base_score` (float)
- `gate_cap` (float)
- `trust_coeff` (float)
- `roi_score` (float)
- `final_score_manager` (float)
- `final_score_admin` (float)
- `breakdown_json` (json)
- unique: `(manager_id, date)`

### 2.2 ManagerWeeklyElo
- `manager_id`
- `week_start`
- `elo_before`
- `elo_after`
- `delta`
- `source_score_week`
- unique: `(manager_id, week_start)`

### 2.3 ManagerIncident
- `manager_id`
- `date`
- `severity` (`s1`, `s2`, `s3`)
- `category` (`complaint`, `rude`, `fraud`, `manipulation`, `other`)
- `description`
- `verified_by_admin` (bool)
- `verified_by_user_id` (nullable)
- `penalty_points`
- `created_at`

### 2.4 ClientInteractionAttempt
- `client_id`
- `manager_id`
- `channel` (`phone`, `email`, `telegram`, `instagram`, `whatsapp`, `other`)
- `result`
- `scheduled_callback_at`
- `completed_at`
- `reason_code`
- `reason_text`
- `is_verified`
- `verification_type` (`hard`, `system`, `self`, `weak`)
- `created_at`

### 2.5 ClientCPLink
- `client_id`
- `cp_log_id`
- `channel_type` (`email`, `messenger`, `other`)
- `verified_flag`
- `linked_by`
- `linked_at`
- unique: `(client_id, cp_log_id)`

## 3. Indexing recommendations
1. `ManagerDailyScore(manager_id, date desc)`.
2. `ManagerIncident(manager_id, verified_by_admin, date desc)`.
3. `ClientInteractionAttempt(client_id, manager_id, created_at desc)`.
4. `ClientInteractionAttempt(manager_id, result, created_at desc)`.
5. `ClientCPLink(cp_log_id)`.

## 4. API endpoints (contract only)

### 4.1 Process client
`POST /management/api/client/process`

#### Request (example)
```json
{
  "client_id": 123,
  "result": "not_interested",
  "reason_code": "price",
  "reason_text": ""
}
```

#### Validation
1. `not_interested` -> reason required.
2. `reason_code=other` -> reason_text required.
3. `sent_email` -> cp_log_id required.
4. `callback` -> scheduled_callback_at required.

### 4.2 Stats manager
`GET /management/api/stats/manager/{id}?period=week`

### 4.3 Stats admin
`GET /management/api/stats/admin/{id}?period=week`

### 4.4 DTF overview read-only
`GET /management/api/dtf/overview?period=week`

### 4.5 Advice ack
`POST /management/api/advice/ack`

### 4.6 Alerts feed
`GET /management/api/alerts/feed`

## 5. Response shape guidelines
1. Всегда include `generated_at` и `timezone`.
2. Явно помечать `inference=true` для вероятностных советов.
3. Для score include breakdown и input counts.

## 6. Permissions
- Manager:
- own stats,
- own alerts,
- own advice ack.
- Admin:
- all manager stats,
- all incidents,
- team comparison and ROI details.

## 7. DTF integration guardrails
1. Никаких FK из management core entities на dtf entities.
2. DTF read через service adapter с timeout и graceful fallback.

## 8. Audit fields
Каждая write-операция, влияющая на score, должна логировать:
- actor,
- action,
- target,
- previous value,
- new value,
- timestamp.
