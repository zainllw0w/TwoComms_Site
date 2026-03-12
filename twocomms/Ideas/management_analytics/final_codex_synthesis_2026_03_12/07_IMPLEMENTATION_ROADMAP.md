# Implementation Roadmap

## 1. Роль этого файла
Этот документ описывает не все идеи пакета, а порядок безопасного внедрения этих идей в текущий `management`.

Главная задача roadmap:
- не перепутать `authoritative design` и `safe rollout`;
- не тащить в первую фазу зависимости, которых нет на хостинге;
- не включить денежно-чувствительные формулы до shadow-validation.

## 2. Архитектурная база внедрения

### 2.1 Current stack
- `Django 5.2.11`
- shared hosting
- current `management` app with models, views, templates and commands folder

### 2.2 Нормативный execution stack
- `management commands + cron` вместо `Celery`;
- `FileBasedCache` вместо `Redis`;
- DB snapshots вместо очередей, завязанных на отдельный брокер;
- feature rollout через `ACTIVE / SHADOW / DORMANT` статусы.

## 3. Общий принцип внедрения
- сначала data foundation и guards;
- затем shadow analytics;
- затем UI-поверхности;
- только потом осторожное включение боевых последствий;
- telephony/QA выносится в отдельную ветку зрелости, а не тащится в core phase.

## 4. Phase map для одного разработчика

| Phase | Смысл | Оценка |
|---|---|---:|
| `0` | Freeze decisions и package alignment | 1-2 дня |
| `1` | Data foundation и safety fields | 3-5 дней |
| `2` | Dedupe / follow-up hardening | 4-6 дней |
| `3` | Shadow MOSAIC / EWR / snapshots | 5-7 дней |
| `4` | Manager/Admin UI surfaces | 5-7 дней |
| `5` | Payroll-safe rollout and Earned Day | 4-6 дней |
| `6` | Telephony preparation | 3-5 дней |
| `7` | Telephony + QA soft launch | 5-8 дней |
| `8` | Validation / calibration / expansion | после накопления данных |

Оценка дана для focus-mode single developer без крупных внешних blockers.

## 5. Phase 0: Freeze decisions

### 5.1 Цель
Прекратить дрейф требований и зафиксировать:
- пакет authoritative docs;
- список reference docs;
- список DORMANT assumptions;
- точный code impact map.

### 5.2 Выходы
- использовать текущую папку `final_codex_synthesis_2026_03_12` как baseline for implementation planning;
- согласовать, что `02`, `03`, `04`, `07`, `12`, `13`, `15`, `17`, `19` считаются главными при планировании.

## 6. Phase 1: Data foundation и safety fields

### 6.1 Сделать
- добавить `is_test` на `Client`;
- добавить или подготовить `DayStatus` / day-ledger layer;
- подготовить `Client Snooze`;
- подготовить `NightlyScoreSnapshot`;
- нормализовать source strategy или минимум централизовать mapping;
- заложить `expected_next_order` / portfolio-support fields where justified.

### 6.2 Code anchors
- `management/models.py`
- `management/migrations/*`
- `management/stats_service.py`

### 6.3 Acceptance
- тестовые данные больше не попадают в боевую аналитику;
- groundwork для snapshots, snooze и phase-aware day logic заложен;
- ни один из новых fields не ломает existing views.

## 7. Phase 2: Dedupe / follow-up hardening

### 7.1 Сделать
- fuzzy duplicate warnings;
- review queue / dispute-friendly flow;
- `MAX_FOLLOWUPS_PER_DAY`;
- reminder dedupe keys;
- FileBasedCache rate limiting;
- follow-up overload and overdue logic.

### 7.2 Code anchors
- `management/models.py`
- `management/views.py`
- `management/lead_views.py`
- `management/parsing_views.py`
- `management/stats_service.py`

### 7.3 Acceptance
- текущая dedupe-система больше не опирается на недоступные технологии;
- follow-up breaches считаются с учётом реальной пропускной способности;
- reminder layer остаётся low-noise.

## 8. Phase 3: Shadow MOSAIC / EWR / snapshots

### 8.1 Сделать
- реализовать `EWR`;
- собрать new axis payloads;
- ввести `Component Readiness Registry`;
- считать shadow MOSAIC рядом с текущим KPD;
- сохранять расчёты в nightly snapshots.

### 8.2 Background execution
Нужны management commands:
- `python manage.py compute_nightly_scores`
- `python manage.py send_management_reminders`
- `python manage.py check_duplicate_queue`

### 8.3 Acceptance
- текущий production UI не сломан;
- admin может сравнить current KPD и shadow MOSAIC;
- snapshots сохраняются повторяемо и объяснимо.

## 9. Phase 4: Manager/Admin UX surfaces

### 9.1 Сделать
- Radar;
- shadow MOSAIC decomposition;
- salary simulator;
- rescue top-5;
- readiness badges;
- admin review and freeze surfaces.

### 9.2 Code anchors
- `management/templates/management/stats.html`
- `management/templates/management/admin.html`
- supporting JS/CSS assets

### 9.3 Acceptance
- manager видит action-first surfaces;
- admin видит control-center surfaces;
- shadow labels понятны и не masquerade as final payroll truth.

## 10. Phase 5: Payroll-safe rollout and Earned Day

### 10.1 Сделать
- soft-floor logic для repeat commission;
- phase-aware DMT;
- Earned Day ledger;
- weekend / excused / tech failure handling;
- payout decomposition improvements.

### 10.2 Code anchors
- `management/models.py`
- `management/views.py`
- payout templates and APIs

### 10.3 Acceptance
- никаких cliff penalties;
- no telephony dependency in phase-0 payroll logic;
- explainability по выплатам доступна менеджеру и админу.

## 11. Phase 6: Telephony preparation

### 11.1 Сделать
- `CallRecord` data model;
- webhook inbox / log;
- provider integration adapter interface;
- telephony readiness badges in admin.

### 11.2 Background execution
Нужны команды вида:
- `python manage.py process_telephony_webhooks`
- `python manage.py reconcile_call_records`

### 11.3 Acceptance
- telephony can start collecting data without changing payroll rules;
- provider failures do not corrupt core management logic.

## 12. Phase 7: Telephony + QA soft launch

### 12.1 Сделать
- provider webhook activation;
- mapping call -> client;
- QA review queue;
- diagnostic trust and supervisor surfaces.

### 12.2 Ограничение
Эта фаза не должна автоматически включать telephony в payroll-critical calculations.

### 12.3 Acceptance
- data is visible and useful;
- QA is calibrated enough for coaching;
- `VerifiedCommunication` can move from `DORMANT` to `SHADOW`, and only then later to `ACTIVE`.

## 13. Phase 8: Validation and calibration

### 13.1 Когда разрешено
Только когда:
- `>=3` meaningful managers;
- `>=60` дней usable data;
- telephony and score snapshots stable enough.

### 13.2 Что разрешено в этой фазе
- validation suite;
- source baseline recalibration;
- anti-gaming activation;
- seasonality reconsideration;
- wider MOSAIC participation in production decisions.

## 14. Shadow mode правила
- минимальная длительность shadow mode: `6-8 недель` для score-sensitive логики;
- в течение shadow mode admin обязан видеть расхождения `KPD vs MOSAIC`;
- до окончания shadow mode нельзя использовать MOSAIC как единственную payroll-истину.

## 15. Rollback и freeze criteria

### 15.1 Rollback triggers
- snapshots inconsistent;
- huge unexplained divergence between KPD and shadow MOSAIC;
- payout math unclear;
- reminder storm or duplicate chaos;
- telephony ingestion corrupts main flows.

### 15.2 Что делать при rollback
- переводить новый компонент в `SHADOW` или `DORMANT`;
- сохранять данные и audit trail;
- не откатывать вслепую verified financial truth.

## 16. Success metrics по фазам
- Phase 1: test and non-test data cleanly separated.
- Phase 2: duplicate creation rate drops, reminder noise stays controlled.
- Phase 3: shadow score is reproducible and explainable.
- Phase 4: manager/admin can use new surfaces without workflow regression.
- Phase 5: payout logic remains stable and understandable.
- Phase 6-7: telephony starts adding evidence, not instability.

## 17. Приземление в текущий код

### 17.1 Основные зоны
- `management/models.py`
- `management/stats_service.py`
- `management/stats_views.py`
- `management/views.py`
- `management/urls.py`
- `management/templates/management/*.html`
- `management/management/commands/`

### 17.2 Что roadmap explicitly запрещает
- запрещает first-phase dependency на Celery/Redis;
- запрещает запускать validation раньше времени;
- запрещает включать DORMANT-компоненты как источник production punishment;
- запрещает смешивать shadow analytics и payroll truth без отдельного gate.
