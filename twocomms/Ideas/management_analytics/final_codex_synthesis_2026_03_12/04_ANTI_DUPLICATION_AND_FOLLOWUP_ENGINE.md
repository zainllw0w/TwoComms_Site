# Anti-Duplication and Follow-Up Engine

## 1. Роль этого файла
Этот документ описывает production-safe логику:
- dedupe;
- create-or-append flow;
- reminder ladder;
- follow-up SLA;
- ownership disputes;
- rate limiting и low-noise notifications.

Главный принцип: пропущенный дубль неприятен, но ложное склеивание разных клиентов опаснее.

## 2. Ground truth текущего management
На текущем коде уже существуют:
- `Client` c `phone_normalized`;
- `ClientFollowUp`;
- `ManagementLead`;
- `ReminderSent` и `ReminderRead`;
- report/follow-up surfaces в `views.py` и `stats_service.py`.

Это означает, что будущая dedupe/follow-up система должна быть эволюцией текущих сущностей, а не новой параллельной CRM.

## 3. Identity model

### 3.1 Основные сущности
- `Client` — ядро owner/lead/follow-up truth;
- `ManagementLead` — входящий сырой слой и pre-conversion зона;
- `Shop` — downstream коммерческий объект;
- `ClientFollowUp` — operational commitment layer.

### 3.2 Базовые identity keys
- `phone_normalized`
- `phone_last7`
- normalized `shop_name`
- normalized owner/full name if available
- source link / source external id when it exists

### 3.3 Что не используем как обязательный ключ
- `city`, потому что его нет в текущей модели `Client`;
- `website_url` как primary identity, потому что сейчас поле почти пустое;
- free-form notes.

## 4. Финальная dedupe-стратегия

### 4.1 Почему не pg_trgm
Current hosting не гарантирует `pg_trgm`, поэтому authoritative flow строится без database extensions.

### 4.2 Blocking strategy
Для сужения кандидатов используем:
- exact `phone_normalized`;
- `phone_last7`;
- first token normalized name;
- optional source external id.

### 4.3 Final decision zones

| Zone | Условие | Действие |
|---|---|---|
| `AUTO_BLOCK` | exact phone match | не создавать новую запись |
| `REVIEW` | `phone_last7 + name similarity >= 0.85` или `name similarity >= 0.90` | ручная проверка |
| `SUGGESTION` | `name similarity >= 0.75` | warning, но создание разрешено |
| `CLEAR` | ничего подозрительного | обычное создание |

### 4.4 Нормативная функция
```python
from difflib import SequenceMatcher

def compute_similarity(name_a: str, name_b: str) -> float:
    return SequenceMatcher(None, (name_a or "").strip().lower(), (name_b or "").strip().lower()).ratio()

def find_duplicates_safe(new_name: str, new_phone_normalized: str, candidates: list[dict]) -> list[dict]:
    phone_last7 = (new_phone_normalized or "")[-7:]
    results = []

    for item in candidates:
        existing_phone = item.get("phone_normalized") or ""
        existing_name = item.get("shop_name") or ""

        if existing_phone and new_phone_normalized and existing_phone == new_phone_normalized:
            results.append({"level": "AUTO_BLOCK", "client_id": item["id"], "reason": "exact phone"})
            continue

        similarity = compute_similarity(new_name, existing_name)
        last7_match = bool(existing_phone and phone_last7 and existing_phone[-7:] == phone_last7)

        if last7_match and similarity >= 0.85:
            results.append({"level": "REVIEW", "client_id": item["id"], "reason": "phone_last7 + name"})
        elif similarity >= 0.90:
            results.append({"level": "REVIEW", "client_id": item["id"], "reason": "very similar name"})
        elif similarity >= 0.75:
            results.append({"level": "SUGGESTION", "client_id": item["id"], "reason": "similar name"})

    return results
```

## 5. Create-or-Append Flow

### 5.1 Нормативная последовательность
1. Нормализовать телефон и имя.
2. Найти кандидатов в owner-scope.
3. Прогнать decision zones.
4. При `AUTO_BLOCK` предложить append to existing record.
5. При `REVIEW` показать admin/manager review UI.
6. При `SUGGESTION` показать мягкий warning.
7. Только после этого создавать новую запись.

### 5.2 Append важнее blind-create
Если совпадение правдоподобно, default-поведение должно двигать пользователя к append / review, а не к тихому созданию дубля.

### 5.3 Что запрещено
- silent merge без audit trail;
- auto-merge на fuzzy match alone;
- перенос ownership без review.

## 6. Ownership и race conditions

### 6.1 Основное правило
Ownership спорного клиента не должен менятьcя незаметно.

### 6.2 Safe flow
- exact conflict -> review queue;
- manual approve/reject by admin or authorized manager;
- audit log on every ownership change;
- if concurrent claim appears, existing owner signal should be surfaced immediately.

### 6.3 Future-ready lock
При будущей кодовой реализации спорных ownership transitions рекомендуется использовать `select_for_update` / transactional lock для узких критичных путей.

## 7. Follow-Up ladder

### 7.1 Основные статусы
Current status machine уже задаёт хороший фундамент:
- `OPEN`
- `DONE`
- `MISSED`
- `RESCHEDULED`
- `CANCELLED`

### 7.2 Ladder без шума
В authoritative модели напоминания и escalations не сканируют "всё подряд". Они строятся вокруг due-state и overdue-state.

Базовые уровни:
- `T-15m` reminder;
- due-now reminder;
- overdue same day;
- next-day escalation;
- accumulated-overdue escalation.

### 7.3 Физический лимит
`MAX_FOLLOWUPS_PER_DAY = 25` обязателен.

Если due tasks больше:
- лишние задачи перераспределяются;
- дисциплинарный breach считается только внутри фактической дневной пропускной способности;
- accumulated overload уходит в admin alert.

### 7.4 Нормативная функция
```python
def compute_followup_state(due_today: int, completed_today: int, total_overdue: int, *, is_working_day: bool = True) -> dict:
    if not is_working_day:
        return {"level": "EXCUSED", "effective_due": 0, "effective_missed": 0}

    max_per_day = 25
    effective_due = min(due_today, max_per_day)
    redistributed = max(0, due_today - max_per_day)
    effective_missed = max(0, effective_due - completed_today)
    missed_rate = effective_missed / max(1, effective_due)

    if total_overdue >= 10:
        level = "REASSIGN_REVIEW"
    elif total_overdue >= 5:
        level = "RISK"
    elif total_overdue >= 2:
        level = "ESCALATION"
    else:
        level = "NORMAL"

    return {
        "level": level,
        "effective_due": effective_due,
        "effective_missed": effective_missed,
        "missed_rate": missed_rate,
        "redistributed": redistributed,
    }
```

### 7.5 Нейтраль при нуле задач
Если `effective_due == 0`, follow-up дисциплина не должна автоматически проваливаться.

## 8. Reactivation, churn и snooze

### 8.1 Что входит в follow-up контур
- overdue callbacks;
- dormant clients with expected next order;
- rescue candidates;
- reactivation priority.

### 8.2 Что пока не активируем в деньги
Сложные churn-модели и сезонные корректировки остаются shadow/admin-only, пока:
- мало исторических заказов;
- мало менеджеров;
- нет достаточной валидации.

### 8.3 Client Snooze
Если клиент официально в паузе:
- follow-up timers могут быть заморожены;
- churn-risk не должен ложно взлетать;
- snooze обязателен с reason, range и review rules.

## 9. Reminders и low-noise delivery

### 9.1 Каналы
- in-app reminder feed;
- Telegram / bot integration where already exists;
- admin summary queue instead of spam.

### 9.2 Reminder dedupe
Каждое напоминание должно иметь dedupe key:
- `entity_id`
- `reminder_type`
- `target_window`

### 9.3 Не шумим
Система не должна:
- слать одно и то же напоминание каждые 15 минут бесконечно;
- эскалировать без изменения состояния;
- заваливать админа неагрегированными уведомлениями.

## 10. Rate limiting и anti-abuse

### 10.1 Нормативный стек
Rate limiting строится через `FileBasedCache`, а не через Redis.

### 10.2 Минимальная функция
```python
from django.core.cache import caches

def check_rate_limit(user_id: int, action: str, *, max_per_hour: int = 20) -> tuple[bool, str | None]:
    cache = caches["default"]
    key = f"rate:{user_id}:{action}"
    current = cache.get(key, 0)
    if current >= max_per_hour:
        return False, "hourly limit reached"
    cache.set(key, current + 1, timeout=3600)
    return True, None
```

### 10.3 Что лимитируем
- mass reminder send;
- repeated duplicate resolution actions;
- repeated ownership claim actions;
- future telephony webhook or sync retries if needed.

## 11. Reminder engine execution model
Фоновый execution layer должен быть совместим с текущим хостингом:
- `management command + cron`;
- DB-backed pending records;
- retries and errors stored explicitly;
- no assumption of Celery or Redis.

## 12. Приземление в текущий код

### 12.1 Основные файлы
- `management/models.py` — `Client`, `ClientFollowUp`, `ReminderSent`, `ReminderRead`, `ManagementLead`;
- `management/views.py` — reminder feed / mark-as-read / current follow-up sync flow;
- `management/lead_views.py` и `parsing_views.py` — будущие точки для pre-conversion dedupe warnings;
- `management/stats_service.py` — follow-up metrics and advice inputs.

### 12.2 Что нужно добавить
- fuzzy duplicate review layer;
- explicit duplicate dispute model or lightweight audit record;
- optional snooze model;
- command(s) for reminder delivery and duplicate queue checks.

### 12.3 Что нельзя делать
- нельзя auto-merge по fuzzy match;
- нельзя штрафовать за overload сверх физического лимита;
- нельзя делать dedupe-контур зависимым от технологий, которых нет на хостинге.
