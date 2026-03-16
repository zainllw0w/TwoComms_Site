# 04. Dedupe, follow-up, reminder engine и anti-abuse hardening

## 1. Что в пакете уже очень хорошо
- консервативная философия merge;
- `append-first`, а не silent create;
- import dry-run;
- rollback window;
- ownership review и audit trail;
- soft anti-abuse semantics: action не пропадает, но может потерять score-credit;
- `MAX_FOLLOWUPS_PER_DAY` защищает от ложной дисциплинарной жестокости.

Это уже значительно лучше типового CRM-хаоса.

## 2. Где остаётся главная практическая слабость
Главный незакрытый technical gap — **грязные B2B identity fields**:
- кириллица/латиница;
- укр/рус варианты;
- юридические суффиксы (`ФОП`, `ТОВ`, `ИП`, `ООО`, `LLC`);
- branch/store naming noise;
- shared phones / switchboards;
- cross-owner duplicates.

Без отдельного normalization layer dedupe будет либо слишком мягкой, либо слишком агрессивной.

## 3. Что я рекомендую добавить в identity layer

### 3.1 Multi-step normalization pipeline
До `SequenceMatcher` нужен нормализатор:
1. Unicode normalize
2. lowercase
3. strip punctuation
4. collapse whitespace
5. transliteration to canonical comparable form
6. remove legal entity tokens
7. split/store root tokens

Пример tokens blacklist:
- `фоп`
- `іп`
- `ип`
- `тов`
- `ооо`
- `llc`
- `магазин`
- `shop`

Важно: это не должно уничтожать meaningful part of name. Поэтому лучше не удалять всё подряд, а хранить:
- `normalized_name_display`
- `normalized_name_match_key`

### 3.2 Shared-phone registry
Exact phone auto-block сильный, но не безусловный.
Нужен список или flag:
- `is_shared_phone`
- `phone_group_id`
- `shared_phone_reason`

Если номер уже связан с несколькими branch-like карточками, новый exact phone должен идти не в auto-block, а в review.

### 3.3 Cross-owner background duplicate scan
UI can stay owner-friendly.
Но nightly/admin diagnostic должен видеть потенциальные дубль-кластеры across owners.
Иначе ownership gaming и дубли между менеджерами будут проходить мимо.

## 4. Как я бы усилил dedupe formula безопасно
Я не рекомендую делать auto-merge сложнее.
Я рекомендую сделать **candidate scoring** умнее, а final actions оставить консервативными.

### 4.1 Candidate score
```python
candidate_score = (
    0.45 * name_match_score
    + 0.35 * phone_match_score
    + 0.10 * owner_match_score
    + 0.10 * source_link_score
)
```

Где:
- `phone_match_score = 1.0` для exact phone, `0.7` для reliable last7+country normalization, `0.0` otherwise
- `name_match_score` = hybrid of normalized token similarity and sequence similarity
- `owner_match_score` = soft helper, not primary identity truth
- `source_link_score` = external id / URL / source key when available

Это не значит, что thresholds надо сразу менять. Это значит, что нужно считать richer score до decision zone.

### 4.2 Final actions оставить conservative
- `AUTO_BLOCK` только при exact strong identity
- `REVIEW` для ambiguous but plausible cases
- `SUGGESTION` для soft warning

То есть умнее делаем **поиск**, а не наказание.

## 5. Batch import: что ещё стоит усилить

### 5.1 Import burst grace
После массового импорта или reassignment follow-up engine не должен моментально превращать всё в MISSED debt.

Рекомендация:
- старые imported due items получают `grace_window_hours = 24..48`
- до конца grace-window они видны как `imported backlog`, а не как personal negligence

### 5.2 Duplicate debt after import
Если import preview показал `REVIEW` duplicates, но запись всё равно создана, нужен:
- `pending_duplicate_review = true`
- due date for review
- DQ impact only after grace window expires

## 6. Follow-up layer: что ещё улучшить

### 6.1 Reminder fatigue budget
Сейчас low-noise direction правильный, но нужен более явный contract:
- если у менеджера > `N` reminders за `2` часа,
- система сворачивает их в digest,
- critical only items остаются отдельными.

### 6.2 Quiet hours / timezone awareness
Нужны:
- `manager_timezone`
- `quiet_hours`
- `digest_preference`

Иначе Telegram / bot / push могут стать раздражающим шумом.

### 6.3 Callback cycling detection
Нужна явная эвристика:
```python
if same_client_reschedules_7d >= 3 and new_verified_evidence == 0:
    flag = 'CALLBACK_CYCLING_REVIEW'
```

Это admin alert, не auto-penalty.

### 6.4 Batch logging detection лучше считать не только по share, но и по пустоте смысла
Более безопасная логика:
- `batch_logging_share >= 0.80`
- `meaningful_progress == 0`
- `n_entries >= 10`
- repeated pattern on multiple days

Только тогда это достойно trust-impact candidate.

### 6.5 Same reason share лучше заменить на entropy + concentration pair
Вместо одной грубой доли лучше хранить:
- `top_reason_share`
- `reason_entropy`

Тогда система меньше будет ошибаться на честных повторяющихся паттернах базы.

## 7. Anti-abuse: что важно не испортить
Главный принцип должен остаться таким:
- low sample -> alert only
- repeated critical pattern + sufficient N -> review
- только после review -> bounded production consequence

Любая попытка превратить heuristic в мгновенный штраф ухудшит пакет.

## 8. Per-action rate limits вместо generic default
`max_per_hour = 20` как generic default — слишком абстрактно.
Нужен реестр action budgets:
- reminder send
- ownership claim
- duplicate resolution
- webhook retry
- manual bulk updates

Тогда rate limiting будет точнее и объяснимее.

## 9. Наиболее вероятные баги без этих улучшений

### Bug 1 — transliteration duplicates silently pass
Особенно на украинско-русско-латинском смешении.

### Bug 2 — shared switchboard number auto-blocks a real new branch
Это типичный B2B false positive.

### Bug 3 — imported backlog выглядит как персональный missed follow-up
Хотя это фактически технический burst.

### Bug 4 — callback cycling остаётся invisible
Потому что current ladder не ловит reschedule-loops как отдельную категорию.

## 10. Что менять в каких файлах
- `04_ANTI_DUPLICATION_AND_FOLLOWUP_ENGINE.md` — normalization, shared-phone, burst grace, entropy semantics
- `12_CALIBRATION_DEFAULTS_AND_PRESETS.md` — per-action rate limits, reminder fatigue constants
- `11_PRODUCT_BACKLOG_FOR_MANAGEMENT_SUBDOMAIN.md` — new services / models
- models: `normalized_name_match_key`, shared-phone flags, duplicate review debt, reminder preferences
- command layer: duplicate scan, reminder digesting, backlog grace handling

## 11. Приоритет внедрения
1. normalization pipeline
2. shared-phone policy
3. import burst grace
4. callback cycling / batch logging diagnostics
5. per-action rate limits
6. cross-owner background scan
