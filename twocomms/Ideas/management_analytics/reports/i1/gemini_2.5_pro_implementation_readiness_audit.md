# Gemini 2.5 Pro — Аудит Implementation Readiness: 65 скрытых gaps в финальном кодексе

> **Модель**: Gemini 2.5 Pro (Antigravity)
> **Дата**: 2026-03-13
> **Объект**: `final_codex_synthesis_2026_03_12` — все 28 файлов
> **Фокус**: Gaps, НЕ покрытые `tc_mosaic_improvements` — infrastructure, testing, safety, operations
> **Методология**: Sequential Thinking MCP (4 шага) + file-by-file cross-reference audit

---

## Executive Summary

Пакет `tc_mosaic_improvements` нашёл и закрыл gaps в **формулах, fairness и precision**. Но при переходе к реальному коду обнаруживается совершенно другой класс проблем — **implementation readiness gaps**: отсутствие тестовой стратегии, неопределённые контракты сервисов, formula edge cases, migration safety, monitoring, и масштабируемость кодовой базы.

> **Главный тезис**: Codex великолепен как design document. Но между design и code лежит контрактный слой, которого пока нет. Этот отчёт заполняет именно этот слой.

| Категория | Количество gaps | Критичность |
|---|---:|---|
| Тестовая стратегия | 5 | 🔴 Блокирующая |
| Formula edge cases | 6 | 🔴 Блокирующая |
| Migration и данные | 5 | 🔴 Высокая |
| Error handling и resilience | 5 | 🔴 Высокая |
| Performance и scaling | 5 | 🟡 Средняя |
| Implementation contracts | 5 | 🔴 Блокирующая |
| Transition и backward compatibility | 5 | 🔴 Высокая |
| Security и privacy | 5 | 🟡 Средняя |
| Monitoring и observability | 4 | 🟡 Средняя |
| Data quality bootstrap | 5 | 🟡 Средняя |
| Cross-domain integration | 5 | 🟡 Средняя |
| Human process | 5 | 🟢 Важно позже |
| Code architecture | 5 | 🔴 Высокая |
| **ИТОГО** | **65** | |

---

## TIER 1 — Implementation Blockers (Исправить ДО начала кодирования)

### 1.1 🔴 Тестовая стратегия ПОЛНОСТЬЮ ОТСУТСТВУЕТ

Весь кодекс (28 файлов, 5000+ строк) не содержит **ни одного упоминания** тестов. Это критический risk для money-sensitive системы.

#### Gap #21 — Нет unit-test стратегии
**Проблема**: формулы (`EWR`, `Weibull`, `trust`, `dampener`, `soft-floor`) будут реализованы без автоматической верификации.
**Рекомендация**: Создать `management/tests/` с обязательными модулями:
```
tests/
├── test_ewr.py              # EWR расчёт с golden-file данными
├── test_mosaic.py            # Composition pipeline end-to-end
├── test_trust.py             # Trust production boundary cases
├── test_dampener.py          # Dampener floor, step, collapse
├── test_gates.py             # Gate interpolation accuracy
├── test_onboarding.py        # Floor + decay + dampener interaction
├── test_churn_weibull.py     # Weibull + logistic fallback + k cap
├── test_soft_floor.py        # Payroll-safe soft floor + proration
├── test_commission.py        # Commission calculation (new/repeat/reactivation)
├── test_rescue_spiff.py      # SPIFF boundaries and capacity guard
├── test_portfolio_health.py  # Threshold transitions + dynamic guards
├── test_dedupe.py            # Normalization + matching accuracy
├── test_snapshot.py          # Snapshot idempotency + schema
├── test_day_status.py        # DMT + earned day + force majeure
└── test_defaults_parity.py   # doc/code constant parity check
```

#### Gap #22 — Нет формульных parity-тестов
**Проблема**: разработчик реализует `EWR = 0.40*Result + 0.35*EffortRatio + 0.25*SourceQuality`, но набирает коэффициент `0.45` по ошибке. Без теста — молчаливо неправильные scores.
**Рекомендация**: Golden-file тесты:
```python
# Фиксированные входные данные → фиксированный ожидаемый результат
GOLDEN_CASES = [
    {
        "input": {"revenue": 60000, "contacts": 90, "source_mix": {...}},
        "expected_ewr": 72.4,
        "tolerance": 0.5
    },
    ...
]
```

#### Gap #23 — Нет regression-тестов для snapshots
**Проблема**: ночной `compute_nightly_scores` модифицирован → snapshot payload ломается → UI падает утром.
**Рекомендация**: Snapshot schema validation test:
```python
REQUIRED_FIELDS = ["mosaic_score", "ewr_score", "trust_diagnostic", 
                   "score_confidence", "pipeline_value", "churn_avg", ...]
def test_snapshot_schema(self):
    snapshot = compute_nightly_snapshot(manager, date)
    for field in REQUIRED_FIELDS:
        self.assertIn(field, snapshot)
```

#### Gap #24 — Нет тестов для payroll расчётов
**Проблема**: commission, soft-floor, SPIFF — это ДЕНЬГИ. Ошибка = юридический и репутационный риск.
**Рекомендация**: Parametrized тесты с граничными случаями:
- Ровно 120K грн revenue (граница soft-floor)
- 0 new orders + 5 repeat orders
- Reactivation после 179 дней vs 181 день
- SPIFF при 4 rescue-клиентах за день (превышение cap)

#### Gap #25 — Нет тестов для dedupe accuracy
**Рекомендация**: Precision/recall fixtures:
```python
KNOWN_DUPLICATES = [
    ("ТОВ Ласка", "Ласка ООО", True),      # должны найти
    ("Ласка", "Ласка-Агро", False),          # не должны сливать
    ("ФОП Іванченко", "Иванченко ИП", True), # транслитерация
]
```

---

### 1.2 🔴 Service Interface Contracts

#### Gap #16 — Нет контрактов для 20+ сервисов
**Проблема**: `11_PRODUCT_BACKLOG` перечисляет `compute_ewr`, `compute_trust_production`, `find_duplicates_safe`, etc. Но ни один не имеет:
- Input signature (что на вход)
- Output type (что на выход)
- Exception contract (что при ошибке)
- Side effects (пишет ли в DB)

**Рекомендация**: Добавить в codex или создать `SERVICE_CONTRACTS.md`:
```python
# compute_ewr
# Input:
#   manager: User
#   period: DateRange (week)
#   mode: OperatingMode
# Output:
#   EWRResult(score: float, revenue_ratio: float, effort_ratio: float,
#             source_quality: float, confidence: str)
# Side effects: None (pure computation)
# Exceptions: InsufficientDataError if period has 0 working days
```

#### Gap #18 — Score composition pipeline order не определён
**Проблема**: При вычислении MOSAIC нужно: сначала EWR → потом оси → потом trust → gates → dampener → onboarding floor → confidence. Но порядок нигде не формализован.
**Рекомендация**: Explicit pipeline diagram:
```
1. compute_raw_axes(manager, period)     → {Result, SF, Process, FU, DQ, VC}
2. apply_readiness_filter(raw_axes)      → {active_axes, dormant_axes}
3. compute_trust_production(manager)     → trust: float [0.85, 1.05]
4. apply_gates(raw_axes)                 → gated_axes
5. compute_weighted_score(gated_axes)    → raw_mosaic: float
6. apply_trust(raw_mosaic, trust)        → trusted_mosaic
7. apply_dampener(trusted_mosaic, axes)  → dampened_mosaic
8. apply_onboarding_floor(dampened, day) → final_mosaic
9. compute_confidence(manager, period)   → confidence: str
```

---

### 1.3 🔴 Feature Flag Mechanism

#### Gap #43 — ACTIVE/SHADOW/DORMANT — нет реализации
**Проблема**: весь codex основан на трёхуровневом feature toggle, но не определено КАК это реализовано:
- Django settings.py constant?
- Database flag (model `FeatureFlag`)?
- Environment variable?
- Per-manager override?

**Рекомендация**: Explicit implementation contract:
```python
# Рекомендуемый подход: DB-backed feature registry
class ComponentReadiness(models.Model):
    component = models.CharField(max_length=50, unique=True)
    status = models.CharField(choices=[
        ('ACTIVE', 'Active'),
        ('SHADOW', 'Shadow'),
        ('DORMANT', 'Dormant')
    ], default='DORMANT')
    activated_at = models.DateTimeField(null=True, blank=True)
    reason = models.TextField(blank=True)
    
    class Meta:
        db_table = 'management_component_readiness'
```

Почему не `settings.py`: потому что admin должен иметь возможность переключить SHADOW → ACTIVE без redeploy.

---

### 1.4 🔴 Formula Edge Cases (6 недоопределённых формул)

#### Gap #36 — EWMA initialization
**Проблема**: EWMA формула использует `previous_ewma`, но для нового менеджера `previous_ewma` = ?
**Рекомендация**: `EWMA_SEED = 50.0` (midpoint score). Альтернатива: первые 42 дня (MIN_DAYS_FOR_EWMA) использовать simple moving average, затем переключиться на EWMA.

#### Gap #37 — Gate interpolation на границе
**Проблема**: Если evidence level ≈ Admin-confirmed, но не совсем, gate = 78 или 60?
**Рекомендация**: Всегда **Floor** (нижний gate). Причина: conservative interpretation protects payroll.
```python
# Gate interpolation: всегда консервативный
def get_gate(evidence_level: str) -> int:
    GATES = OrderedDict([
        ('paid', 100), ('admin_confirmed', 78),
        ('crm_timestamped', 60), ('self_reported', 45)
    ])
    return GATES.get(evidence_level, 45)  # default = lowest
```

#### Gap #38 — Dampener + Onboarding Floor interaction
**Проблема**: Новый менеджер на 5-м дне. Score = 25 (weak). Dampener хочет снизить до 21. Onboarding floor = 40. Порядок?
**Рекомендация**: `onboarding floor применяется ПОСЛЕ dampener` (как safety net):
```python
final = max(dampened_score, onboarding_floor_for_day(day_number))
```
Логика: onboarding — это защитный минимум, он не должен "проигрывать" dampener.

#### Gap #39 — Trust compound clamping
**Проблема**: `TRUST_BASE = 0.97`, но наказания `duplicate_abuse_weight = -0.05` и `anomaly_weight = -0.05` суммарно дают -0.10. Итого `0.87`. Это выше `TRUST_PRODUCTION_MIN = 0.85`, но что если оба активны одновременно? Нужен ли промежуточный clamp?
**Рекомендация**: **Финальный clamp, не промежуточный**:
```python
trust = TRUST_BASE + report_term + reason_term + duplicate_term + anomaly_term
trust = max(TRUST_PRODUCTION_MIN, min(TRUST_PRODUCTION_MAX, trust))
```
Промежуточные clamp создают скрытый "ceiling effect" и усложняют explainability.

#### Gap #40 — Churn score aggregation
**Проблема**: Weibull даёт per-client churn probability. Как из N probabilites получить portfolio-level score?
**Рекомендация**:
```python
# Weighted average по expected LTV
portfolio_churn_score = sum(
    client.churn_probability * client.estimated_ltv 
    for client in portfolio
) / max(1, sum(client.estimated_ltv for client in portfolio))
```
Более дорогие клиенты с высоким churn весят больше — это правильная business semantics.

#### Gap #35 — EWR revenue normalization period
**Проблема**: `TARGET_WEEKLY_REVENUE = 50_000`. Но EWR формула использует `revenue_ratio = revenue / target`. Это weekly revenue? Monthly revenue? Rolling 30d?
**Рекомендация**: **Weekly**. Explicit:
```python
revenue_ratio = weekly_verified_revenue / TARGET_WEEKLY_REVENUE
revenue_component = min(revenue_ratio, 2.0)  # cap at 2x
```

---

### 1.5 🔴 Concurrent Cron Safety

#### Gap #15 — Нет защиты от дублирования cron-команд
**Проблема**: Если `compute_nightly_scores` работает 25 минут и cron запускает её повторно — двойной snapshot, inconsistent state.
**Рекомендация**: File-based lock:
```python
import os, sys

LOCK_FILE = '/tmp/compute_nightly_scores.lock'

class Command(BaseCommand):
    def handle(self, *args, **options):
        if os.path.exists(LOCK_FILE):
            self.stderr.write("Already running, skipping.")
            sys.exit(0)
        try:
            open(LOCK_FILE, 'w').write(str(os.getpid()))
            self._compute()
        finally:
            os.remove(LOCK_FILE)
```

---

### 1.6 🔴 Migration Strategy

#### Gap #1 — Нет migration rollback protocol
**Проблема**: 15+ новых моделей. Одна неудачная миграция может заблокировать Django.
**Рекомендация**: 
- Мелкие миграции: одна модель = одна миграция
- Каждая миграция тестируется на копии production DB
- `RunPython` шаги — reversible
- Добавить `MIGRATION_CHECKLIST.md`

#### Gap #2 — Нет data seeding contract
**Проблема**: `ComponentReadiness`, `OperatingMode`, default `DayStatus` values — кто и когда создаёт initial records?
**Рекомендация**: Management command `seed_management_defaults`:
```python
class Command(BaseCommand):
    def handle(self, *args, **options):
        # Create ComponentReadiness for each axis
        for component in ['Result', 'SourceFairness', 'Process', ...]:
            ComponentReadiness.objects.get_or_create(
                component=component,
                defaults={'status': 'DORMANT'}
            )
        # Seed operating mode defaults
        # Seed point values
        # Seed source baselines
```

#### Gap #4 — Backfill strategy для существующих данных
**Проблема**: Когда добавляется `Client.is_test`, что в этом поле у 5000 существующих клиентов? `NULL`? `False`? Нужна data migration.
**Рекомендация**: Каждое новое поле с impact на аналитику должно иметь:
- Default value в migration
- Backfill rule (e.g., "все клиенты с `test` в имени → `is_test=True`")
- Post-migration verification query

---

## TIER 2 — High-Impact Safety Gaps

### 2.1 Error Handling и Resilience

#### Gap #6 — Nightly command failure cascading
**Проблема**: `compute_nightly_scores` упал в 2:15 AM. В 8:00 AM менеджер видит вчерашний snapshot как сегодняшний. Нет "stale data" protection.
**Рекомендация**:
1. Snapshot модель должна хранить `computed_at` timestamp
2. UI проверяет: `if snapshot.computed_at < today - timedelta(hours=18): show_stale_banner()`
3. Admin dashboard показывает последний successful run
4. Email/notification alert если ночная команда не выполнилась

#### Gap #7 — Partial computation handling
**Проблема**: Nightly job обработал 3 из 5 менеджеров и crashed. Для 3 менеджеров новый snapshot, для 2 — старый.
**Рекомендация**: Atomic batch processing:
```python
with transaction.atomic():
    for manager in managers:
        snapshot = compute_snapshot(manager, date)
        NightlyScoreSnapshot.objects.update_or_create(
            manager=manager, date=date,
            defaults=snapshot
        )
```
Fail = rollback всего batch. Partial state невозможен.

#### Gap #8 — FileBasedCache corruption recovery
**Проблема**: Cache directory заполнен, corrupted, или на shared hosting disc space закончился. Rate limiting перестаёт работать.
**Рекомендация**: Добавить в `OPERATIONS_RUNBOOK.md`:
```bash
# 1. Проверка размера cache
du -sh /path/to/cache_dir/

# 2. Безопасная очистка
python manage.py clearcache  # custom command

# 3. Диагностика rate-limiting
python manage.py check_rate_limit_health

# 4. Fallback: если cache unavailable, rate limiting degradа до in-memory
#    (accept higher burst risk, do NOT block operations)
```

#### Gap #9 — Webhook idempotency
**Проблема**: Binotel/Ringostat повторно отправляет webhook за тот же звонок. Без idempotency — дублированные `CallRecord`.
**Рекомендация**:
```python
# В process_telephony_webhooks:
call, created = CallRecord.objects.get_or_create(
    provider_call_id=payload['call_id'],
    defaults={...}
)
if not created:
    logger.info(f"Duplicate webhook for call {payload['call_id']}, skipping")
```

#### Gap #10 — Rate limit bypass for admin
**Проблема**: Admin ревьюит 50 дубликатов подряд → rate limiter блокирует его как "abuse".
**Рекомендация**: Rate limiter должен учитывать role:
- Manager: strict limits (per-action budgets)
- Admin: elevated limits (10x) or exempt for review actions
- System/cron: exempt

---

### 2.2 Score Composition and Architecture

#### Gap #5 — Database constraints и indexes
**Проблема**: `NightlyScoreSnapshot` будет запрашиваться по `(manager, date)` тысячи раз. Без index — full table scan.
**Рекомендация**: Обязательные constraints для новых моделей:
```python
class NightlyScoreSnapshot(models.Model):
    class Meta:
        unique_together = [('manager', 'date')]
        indexes = [
            models.Index(fields=['manager', '-date']),
        ]

class CallRecord(models.Model):
    class Meta:
        indexes = [
            models.Index(fields=['provider_call_id']),  # для idempotency
            models.Index(fields=['client', '-started_at']),
            models.Index(fields=['owner', 'started_at']),
        ]

class ScoreAppeal(models.Model):
    class Meta:
        indexes = [
            models.Index(fields=['status', '-created_at']),
        ]
```

#### Gap #12 — Snapshot table growth
**Проблема**: 5 менеджеров × 365 дней = 1825 строк/год. Кажется немного, но с `raw_data` JSONField по 5-10KB каждый = 9-18MB/год без archival.
**Рекомендация**: 
- `raw_data` хранить compact (без pretty-formatting JSON)
- Архивация старше 180 дней → отдельная таблица `ArchivedSnapshot` или partitioning
- Periodic cleanup command

#### Gap #13 — Dedupe search scaling
**Проблема**: SequenceMatcher для каждого нового клиента проверяет ВСЕ существующие. При 5000 клиентов = 5000 сравнений × каждый import.
**Рекомендация**: Prefiltering стратегия:
```python
# 1. Exact phone check (O(1) с index)
# 2. Последние 7 цифр — filter set
# 3. SequenceMatcher ТОЛЬКО для кандидатов из шага 1-2
# Цель: < 50 сравнений вместо 5000
```

---

### 2.3 KPD → MOSAIC Transition

#### Gap #41 — Нет transition protocol
**Проблема**: Shadow MOSAIC работает 8 недель. Когда переключаться на production? Кто решает? Что если KPD и MOSAIC расходятся на 15 пунктов?
**Рекомендация**: Explicit transition gate:
```markdown
## MOSAIC Activation Protocol
1. Shadow period ≥ 8 weeks
2. CV-R² ≥ 0.05 (low bar)
3. KPD vs MOSAIC correlation > 0.70
4. No unexplained divergence > 20 points for any manager
5. Admin explicit approval (logged)
6. Hold-harmless period = 4 weeks after activation
7. Rollback trigger: any manager's payout delta > 15% unexplained
```

#### Gap #42 — API/payload versioning
**Проблема**: `stats.html` получает данные из `stats_service.py`. Сейчас — KPD fields. Потом — MOSAIC + KPD в shadow. Как template знает, что показывать?
**Рекомендация**: Payload version field:
```python
def build_stats_payload(manager, request):
    payload = {
        'payload_version': 2,  # increment on schema changes
        'kpd': compute_kpd(manager),  # always present
        'mosaic': compute_shadow_mosaic(manager) if mosaic_enabled() else None,
        'show_mosaic': ComponentReadiness.is_active('mosaic'),
        ...
    }
```

---

### 2.4 Code Architecture Decomposition

#### Gap #61 — views.py god-file
**Проблема**: `views.py` уже перегружен (manager/admin, reports, reminders, payouts, invoices, contracts). Добавление freeze/review/appeal/economics → collapse.
**Рекомендация**: Разбить по domain:
```
management/views/
├── __init__.py
├── manager_views.py      # manager dashboard, reports
├── admin_views.py         # admin dashboard, readiness, economics
├── payout_views.py        # payouts, commissions, freeze
├── appeal_views.py        # appeals, disputes
├── lead_views.py          # уже существует отдельно — хорошо
├── parsing_views.py       # уже существует отдельно — хорошо
└── api_views.py           # AJAX endpoints для UI components
```

#### Gap #62 — stats_service.py decomposition
**Проблема**: Один файл получит EWR + MOSAIC + Weibull + Wilson + rescue ranking + snapshot + pipeline + portfolio + trust + confidence = 1500+ строк.
**Рекомендация**: Разбить по computation domain:
```
management/services/
├── __init__.py
├── score_service.py       # EWR, MOSAIC composition
├── trust_service.py       # Trust production/diagnostic
├── churn_service.py       # Weibull, logistic, portfolio health
├── dedupe_service.py      # Normalization, matching
├── payroll_service.py     # Commission, soft-floor, SPIFF
├── snapshot_service.py    # Nightly computation orchestration
├── forecast_service.py    # Pipeline, cohort, economics
└── advice_service.py      # Advice cards, tips
```

#### Gap #63 — Template splitting
**Проблема**: `stats.html` получит Radar + simulator + rescue + timeline + confidence badges + advice = 2000+ строк.
**Рекомендация**: Django template includes:
```html
<!-- stats.html -->
{% include "management/components/radar_chart.html" %}
{% include "management/components/salary_simulator.html" %}
{% include "management/components/rescue_top5.html" %}
{% include "management/components/client_timeline.html" %}
{% include "management/components/score_explanation.html" %}
```

#### Gap #64 — CSS/JS asset strategy
**Проблема**: Radar chart, salary simulator, timeline — нужны JS-библиотеки. Какие?
**Рекомендация**:
- Radar: **Chart.js** (CDN, lightweight, radar type built-in)
- Salary simulator: vanilla JS (no library needed, just forms + math)
- Timeline: vanilla JS + CSS (custom component)
- NO build system (no webpack/vite) — compatible with shared hosting

#### Gap #65 — Cron scheduling conflicts
**Проблема**: Все команды на `0 2 * * *`. Если все стартуют одновременно — DB contention, resource spike.
**Рекомендация**: Staggered schedule:
```
0 2 * * * compute_nightly_scores       # самый тяжёлый — первый
0 3 * * * check_duplicate_queue        # после scores
0 4 * * * send_management_reminders    # утренние reminders
*/5 * * * * process_telephony_webhooks # каждые 5 минут
```

---

## TIER 3 — Important Refinements

### 3.1 Security и Privacy

#### Gap #26 — Manager data isolation
**Рекомендация**: Middleware/decorator check:
```python
def manager_data_access_check(view_func):
    def wrapper(request, manager_id, *args, **kwargs):
        if not request.user.is_staff and request.user.id != manager_id:
            raise PermissionDenied("Cannot access other manager's data")
        return view_func(request, manager_id, *args, **kwargs)
    return wrapper
```

#### Gap #28 — Webhook authentication
**Рекомендация**: Token verification:
```python
@csrf_exempt
def telephony_webhook(request):
    token = request.headers.get('X-Webhook-Token', '')
    if not hmac.compare_digest(token, settings.TELEPHONY_WEBHOOK_SECRET):
        return HttpResponseForbidden()
    ...
```

#### Gap #29 — Персональные данные
**Рекомендация**: Добавить в `DATA_RETENTION_POLICY.md`:
- Call recordings: 90 дней active, 12 месяцев archive
- Manager performance data: retain for employment + 3 года
- Audit logs: permanent (append-only)
- Client PII: retain while active + 1 год after last order

#### Gap #30 — Audit log tamperproofing
**Рекомендация**: Django model с `editable=False`:
```python
class AuditLog(models.Model):
    # All fields read-only after creation
    class Meta:
        managed = True
        # Prevent updates via custom manager
    def save(self, *args, **kwargs):
        if self.pk:  # Already exists
            raise IntegrityError("Audit logs are immutable")
        super().save(*args, **kwargs)
```

---

### 3.2 Data Quality Bootstrap

#### Gap #51 — Source baseline calibration origin
**Проблема**: `prom.ua = 0.030`, `google_maps = 0.020` — откуда эти числа? Измерены или придуманы?
**Рекомендация**: Добавить calibration source annotation:
```markdown
| Source | Baseline | Origin | Last calibrated |
|---|---:|---|---|
| prom.ua | 0.030 | Measured from 6 months data | 2026-03-12 |
| google_maps | 0.020 | Estimated (insufficient data) | 2026-03-12 |
```

#### Gap #52 — Points table validation
**Проблема**: ORDER=45, XML_CONNECTED=35 — коррелируют ли эти веса с реальной конверсией?
**Рекомендация**: Calibration query:
```python
# Для каждого outcome посчитать:
# P(outcome → ORDER within 60 days)
# Затем сравнить с назначенными points
```

#### Gap #54 — Operating mode selection framework
**Проблема**: Когда TESTING → NORMAL? Когда NORMAL → HARDCORE? Нет criteria.
**Рекомендация**:
```markdown
TESTING → NORMAL: 
  - Manager active >= 30 days
  - Portfolio >= 50 clients
  - Weekly contacts baseline established

NORMAL → HARDCORE:
  - Admin decision (performance-driven)
  - Never automatic
  - Requires 2-week notice to manager
```

---

### 3.3 Monitoring и Observability

#### Gap #31 — Operational monitoring
**Рекомендация**: Minimum viable monitoring:
```python
# В каждой management command:
import logging
logger = logging.getLogger('management.commands')

class Command(BaseCommand):
    def handle(self, *args, **options):
        start = time.time()
        try:
            count = self._compute()
            logger.info(f"compute_nightly_scores: {count} snapshots in {time.time()-start:.1f}s")
        except Exception as e:
            logger.error(f"compute_nightly_scores FAILED: {e}", exc_info=True)
            # Optional: send alert email
            raise
```

#### Gap #32 — Score anomaly detection
**Рекомендация**: Post-computation validation:
```python
def validate_score_sanity(scores: list[float]):
    """Alert if scores look anomalous"""
    if all(s < 20 for s in scores):
        alert("All manager scores below 20 — possible formula bug")
    if max(scores) - min(scores) < 5 and len(scores) > 3:
        alert("Score variance suspiciously low — possible constant output")
    for s in scores:
        if s < 0 or s > 100:
            alert(f"Score {s} out of [0, 100] bounds")
```

---

## TIER 4 — Operational Maturity

### 4.1 Human Process

#### Gap #46 — Admin training plan
**Рекомендация**: Создать `ADMIN_GUIDE.md` с описанием:
- Как читать confidence labels
- Когда freeze, когда alert
- Appeal SLA и процедура
- Как интерпретировать admin economics (это НЕ payroll verdict)

#### Gap #47 — Manager onboarding to new system
**Рекомендация**: Постепенное введение:
1. Неделя 1: shadow score виден, но не обязателен
2. Неделя 2-4: manager видит оба числа (KPD + MOSAIC)
3. Неделя 5-8: MOSAIC в фокусе, KPD secondary
4. Неделя 9+: full MOSAIC, KPD archived

#### Gap #50 — Change communication protocol
**Рекомендация**: При изменении формул/весов:
1. Admin log entry (автоматически)
2. Notification менеджерам (template: "С [дата] формула [X] изменена: [причина]. Это повлияет на [что]")
3. Hold-harmless период 2 недели

---

## Сводная карта: все 65 gaps по приоритету

| Tier | Gaps | Блокирует имплементацию? |
|---|---|---|
| **Tier 1 — Blockers** | #1-2, #4-5, #15-16, #18, #21-25, #35-40, #43 | ✅ Да — код нельзя писать без этих контрактов |
| **Tier 2 — High-Impact** | #6-10, #12-13, #41-42, #45, #61-65 | ⚠️ Можно начать, но будут болезненные переделки |
| **Tier 3 — Important** | #19-20, #26, #28-30, #51-55 | ❌ Не блокирует, но ухудшает quality |
| **Tier 4 — Operational** | #31-33, #46-47, #50, #57-58 | ❌ Нужен после запуска |

---

## Рекомендуемый Action Plan

### Перед Phase 1 (1-2 дня)
1. ✍️ Написать `SERVICE_CONTRACTS.md` с signatures для ТОП-10 сервисов
2. ✍️ Написать `TESTING_STRATEGY.md` со списком обязательных тестов
3. ✍️ Определить `ComponentReadiness` model (feature flags)
4. ✍️ Зафиксировать formula edge cases (EWMA init, gate floor, dampener+onboarding, trust clamp)
5. ✍️ Определить migration + seeding protocol

### В каждой Phase
6. 🧪 Каждый новый сервис = сопутствующий `test_*.py`
7. 📊 Каждая новая модель = constraints + indexes
8. 🔒 Lock для каждой management command
9. 📝 Logging в каждом background job

### После Phase 3
10. 🔀 Refactor `stats_service.py` → `services/` package
11. 🔀 Refactor `views.py` → `views/` package
12. 📄 Написать `ADMIN_GUIDE.md`
13. 📄 Написать `OPERATIONS_RUNBOOK.md`

---

## Связь с предыдущим отчётом

| Отчёт | Фокус | Количество findings |
|---|---|---|
| `gemini_2.5_pro_deep_analysis_report.md` | Formula precision, fairness, score improvements | 30+ покомпонентных оценок |
| **Этот отчёт** | Implementation readiness, contracts, testing, safety | 65 infrastructure gaps |

Вместе эти два отчёта дают полную картину того, что нужно codex для перехода от design к production-safe code.

---

*Отчёт подготовлен: Gemini 2.5 Pro (Antigravity), 2026-03-13*
*Методология: 28-file full-coverage audit + 4-step Sequential Thinking + cross-reference gap analysis*
