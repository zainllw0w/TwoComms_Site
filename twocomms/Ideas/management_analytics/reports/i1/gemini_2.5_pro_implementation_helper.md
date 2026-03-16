# Gemini 2.5 Pro — Комплексный помощник для создания файла имплементации

> **Модель**: Gemini 2.5 Pro (Antigravity)
> **Дата**: 2026-03-13
> **Назначение**: Максимально детальный контекстный документ для AI-агента, который будет создавать финальный файл имплементации
> **Принцип**: Всё что нужно знать, найти и не пропустить — в одном файле

---

## РАЗДЕЛ 1: ПОЛНАЯ КАРТА ФАЙЛОВ КОДОВОЙ БАЗЫ

### 1.1 management/ — Python modules

| Файл | Строки | Описание | Codex-relevance |
|---|---:|---|---|
| `models.py` | 1160 | 22 модели: Client, ManagementLead, LeadParsingJob, LeadParsingResult, Report, CommercialOfferEmailSettings, CommercialOfferEmailLog, Shop, ShopPhone, ShopShipment, ShopCommunication, ShopInventoryMovement, ManagementDailyActivity, ClientFollowUp, ManagementStatsConfig, ManagementStatsAdviceDismissal, ReminderSent, ReminderRead, ManagerCommissionAccrual, ManagerPayoutRequest, ManagementContract, ContractSequence, + rejection reason request модели | 🔴 CRITICAL — каждая модель влияет на имплементацию |
| `stats_service.py` | 1259 | KPD formula, generate_advice (8 типов), get_stats_payload, source normalization, success_weight table, full stats computation | 🔴 CRITICAL — основной файл для расширения |
| `views.py` | 5912 | God-file: home, admin_overview, admin_user_clients, payout CRUD (6 endpoints), invoice CRUD (6), contract CRUD (5), commercial offer email (8 endpoints), reports, reminders, profile, Telegram bot webhook, info | 🟡 НЕ ТРОГАТЬ — огромен, но функционирует |
| `shop_views.py` | 946 | Shop CRUD: save, detail, add_contact, set_next_contact, inventory_move, delete, shipment/contract download | 🟢 Не затрагивается внедрением |
| `stats_views.py` | 222 | stats page, stats_admin_list, stats_admin_user, advice_dismiss, activity_pulse | 🔴 РАСШИРЯТЬ — добавить MOSAIC endpoints |
| `lead_views.py` | 234 | Lead create, detail, process | 🟡 Может затрагиваться dedupe |
| `parsing_views.py` | 381 | Parser dashboard, start/step/pause/resume/stop, status, lead moderation | 🟢 Не затрагивается |
| `invoice_service.py` | 574 | Invoice generation (PDF), template rendering | 🟢 Не затрагивается |
| `parser_service.py` | 415 | Google Maps parser logic | 🟢 Не затрагивается |
| `lead_services.py` | 57 | Lead processing helper functions | 🟡 Может затрагиваться dedupe |
| `forms.py` | 247 | Django forms for management | 🟡 Может потребовать новых form |
| `constants.py` | 24 | POINTS table + TARGET_CLIENTS_DAY + TARGET_POINTS_DAY + REMINDER_WINDOW_MINUTES | 🔴 ИСПРАВИТЬ xml_connected + добавить MOSAIC constants |
| `admin.py` | 78 | Django admin: ManagementStatsConfig, ManagementDailyActivity, ClientFollowUp, ManagementStatsAdviceDismissal, ManagementLead, LeadParsingJob, LeadParsingResult | 🟡 РАСШИРИТЬ — добавить новые модели |
| `urls.py` | 85 | 75 URL patterns через 5 view modules | 🟡 РАСШИРИТЬ — добавить новые endpoints |

### 1.2 management/management/commands/

| Файл | Строки | Описание |
|---|---:|---|
| `notify_test_shops.py` | 95 | Telegram notification for test shop expiry (last 24h). Uses ReminderSent for idempotency. IMPORTANT: shows EXISTING pattern for management commands + Telegram integration |

### 1.3 management/templates/management/

| Template | Описание | Codex-relevance |
|---|---|---|
| `stats.html` | Manager stats dashboard — ОСНОВНОЙ target для MOSAIC UI | 🔴 РАСШИРЯТЬ |
| `stats_admin_list.html` | Admin stats list — target для admin readiness | 🔴 РАСШИРЯТЬ |
| `admin.html` | Admin overview page | 🟡 Может расширяться |
| `home.html` | Manager home/dashboard (clients list) | 🟡 Minor updates |
| `shops.html` | Shop management page | 🟢 Не затрагивается |
| `reports.html` | Manager reports page | 🟢 Не затрагивается |
| `invoices.html` | Invoice management | 🟢 Не затрагивается |
| `contracts.html` | Contract management | 🟢 Не затрагивается |
| `payouts.html` | Payout management | 🟡 Может расширяться для SPIFF |
| `commercial_offer_email.html` | CP email builder | 🟢 Не затрагивается |
| `parsing.html` | Parser dashboard | 🟢 Не затрагивается |
| `info.html` | Manager info/profile | 🟢 Не затрагивается |
| `login.html` | Login page | 🟢 Не затрагивается |
| `base.html` | Base template with navigation | 🟡 Может нуждаться в новых nav items |
| `emails/commercial_offer.html` | CP email template | 🟢 |
| `emails/twocomms_cp_visual.html` | CP visual email template | 🟢 |
| `partials/commercial_offer_log_row.html` | CP log row partial | 🟢 |

### 1.4 Другие файлы с management-зависимостями

| Файл | Зависимость |
|---|---|
| `orders/models.py` → `WholesaleInvoice` | `ManagerCommissionAccrual.invoice` = FK. `stats_service.py` делает try-import |
| `storefront/models.py` → `Product` | `Shop.test_product` = FK (nullable) |
| `settings.AUTH_USER_MODEL` | Все user FK в management |
| `userprofile.models` → `UserProfile` | `tg_manager_chat_id` для Telegram notifications |

---

## РАЗДЕЛ 2: ПОЛНАЯ SCHEMA МОДЕЛЕЙ (EXISTING + PROPOSED)

### 2.1 Existing: Client (models.py строки 23-79)

```python
class Client(models.Model):
    # === Identity ===
    shop_name = models.CharField(max_length=255)           # Название магазина/клиента
    phone = models.CharField(max_length=30, blank=True)     # Raw phone
    phone_normalized = models.CharField(max_length=20, db_index=True, blank=True)  # +380XXXXXXXXX
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    website = models.URLField(blank=True)
    source = models.CharField(max_length=100, blank=True)   # Откуда клиент
    
    # === CRM State ===
    call_result = models.CharField(max_length=30, choices=[...], default='')
    # Choices: order, test_batch, waiting_payment, waiting_prepayment, xml_connected,
    #          sent_email, sent_messenger, wrote_ig, thinking, other,
    #          no_answer, invalid_number, not_interested, expensive
    
    comment = models.TextField(blank=True)
    next_call_at = models.DateTimeField(null=True, blank=True)  # Follow-up date
    
    # === Scoring Override ===
    points_override = models.IntegerField(null=True, blank=True)  # ⚠️ Manual override!
    
    # === Ownership ===
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=CASCADE, related_name='managed_clients')
    
    # === Timestamps ===
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # === Phone normalization ===
    def save(self, *args, **kwargs):
        if self.phone:
            self.phone_normalized = normalize_phone(self.phone)
        super().save(*args, **kwargs)
```

**PROPOSED extensions for Client:**
```python
# НЕ добавлять is_test — тест привязан к Shop, не к Client
expected_next_order = models.DateField(null=True, blank=True)  # Portfolio health
normalized_name_hash = models.CharField(max_length=32, blank=True, db_index=True)  # Dedupe precheck
```

### 2.2 Existing: ManagementLead (models.py строки 82-184)

```python
class ManagementLead(models.Model):
    class Status(models.TextChoices):
        MODERATION = 'moderation'
        BASE = 'base'         # Approved, awaiting processing
        CONVERTED = 'converted'  # → Client created
        REJECTED = 'rejected'
    
    class NicheStatus(models.TextChoices):
        NEW = 'new'
        IN_NICHE = 'in_niche'
        OUT_OF_NICHE = 'out_of_niche'
    
    shop_name = models.CharField(max_length=255)
    phone, phone_normalized, email, website, address
    google_place_id = models.CharField(max_length=100, blank=True, db_index=True)
    
    lead_source = models.CharField(...)  # parser, manual, import
    status = models.CharField(choices=Status.choices)
    niche_status = models.CharField(choices=NicheStatus.choices)
    
    added_by = models.ForeignKey(User, related_name='added_leads')
    moderated_by = models.ForeignKey(User, related_name='moderated_leads', null=True)
    processed_by = models.ForeignKey(User, related_name='processed_leads', null=True)
    converted_client = models.ForeignKey('Client', null=True)
    parser_job = models.ForeignKey('LeadParsingJob', null=True)
    
    # Indexes: mgmt_lead_status_dt, mgmt_lead_phone_norm
```

### 2.3 Existing: Shop (models.py строки 617-687)

```python
class Shop(models.Model):
    class ShopType(models.TextChoices):
        TEST = 'test'
        FULL = 'full'
    
    name = models.CharField(max_length=255)
    shop_type = models.CharField(choices=ShopType.choices)
    description = models.TextField(blank=True)
    location = models.TextField(blank=True)        # Адрес
    website = models.URLField(blank=True)
    instagram = models.URLField(blank=True)
    
    # Test management
    test_product = models.ForeignKey('storefront.Product', null=True)
    test_connected_at = models.DateField(null=True)
    test_period_days = models.PositiveIntegerField(default=14)
    
    # Scheduling
    next_contact_at = models.DateTimeField(null=True)
    
    # Ownership (DUAL!)
    created_by = models.ForeignKey(User, related_name='created_shops')
    managed_by = models.ForeignKey(User, related_name='managed_shops', null=True)
    
    # Indexes: mgmt_shop_type_dt, mgmt_shop_managed_by, mgmt_shop_next_contact
```

### 2.4 Existing: ManagerCommissionAccrual (models.py строки 959-993)

```python
class ManagerCommissionAccrual(models.Model):
    owner = models.ForeignKey(User)
    invoice = models.OneToOneField('orders.WholesaleInvoice')
    base_amount = models.DecimalField()       # Invoice total
    percent = models.DecimalField()           # Commission %
    amount = models.DecimalField()            # Actual commission
    frozen_until = models.DateTimeField(db_index=True)  # ⚠️ FREEZE ALREADY EXISTS
    created_at = models.DateTimeField()
```

### 2.5 Existing: ManagementStatsConfig (models.py строки 941-956)

```python
class ManagementStatsConfig(models.Model):
    """Singleton (pk=1). JSON fields for weights and thresholds."""
    kpd_weights = models.JSONField(default=dict, blank=True)     # KPD formula weights
    advice_thresholds = models.JSONField(default=dict, blank=True)  # Advice trigger thresholds
    updated_at = models.DateTimeField(auto_now=True)
```

**PROPOSED extensions:**
```python
mosaic_weights = models.JSONField(default=dict, blank=True)      # MOSAIC axis weights
defaults_version = models.CharField(max_length=20, default='1.0')  # For audit
formula_version = models.CharField(max_length=20, default='1.0')   # For snapshot linking
```

### 2.6 PROPOSED: New Models (6 required)

```python
# 1. ComponentReadiness — Feature flags for ACTIVE/SHADOW/DORMANT
class ComponentReadiness(models.Model):
    component = models.CharField(max_length=50, unique=True)
    status = models.CharField(choices=[('ACTIVE','Active'),('SHADOW','Shadow'),('DORMANT','Dormant')], default='DORMANT')
    activated_at = models.DateTimeField(null=True, blank=True)
    reason = models.TextField(blank=True)
    class Meta:
        db_table = 'management_component_readiness'

# 2. NightlyScoreSnapshot — Idempotent per (manager, date)
class NightlyScoreSnapshot(models.Model):
    manager = models.ForeignKey(User, on_delete=CASCADE)
    snapshot_date = models.DateField()
    mosaic_score = models.FloatField(null=True)
    ewr_score = models.FloatField(null=True)
    trust_production = models.FloatField(null=True)
    axes_breakdown = models.JSONField(default=dict)  # {Result: 72, SF: 45, ...}
    raw_data = models.JSONField(default=dict)         # Full computation trace
    score_confidence = models.CharField(max_length=10, default='LOW')
    formula_version = models.CharField(max_length=20, blank=True)
    defaults_version = models.CharField(max_length=20, blank=True)
    computed_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        unique_together = [('manager', 'snapshot_date')]
        indexes = [models.Index(fields=['manager', '-snapshot_date'])]

# 3. CommandRunLog — Observability for management commands
class CommandRunLog(models.Model):
    command_name = models.CharField(max_length=100)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True)
    status = models.CharField(choices=[('running','Running'),('done','Done'),('failed','Failed')])
    rows_processed = models.IntegerField(default=0)
    warnings_count = models.IntegerField(default=0)
    error_message = models.TextField(blank=True)
    class Meta:
        indexes = [models.Index(fields=['command_name', '-started_at'])]

# 4. ScoreAppeal — Appeal workflow
class ScoreAppeal(models.Model):
    manager = models.ForeignKey(User, on_delete=CASCADE)
    appeal_type = models.CharField(choices=[('score','Score'),('payout','Payout'),('freeze','Freeze')])
    status = models.CharField(choices=[('pending','Pending'),('accepted','Accepted'),('rejected','Rejected')])
    reason = models.TextField()
    resolution = models.TextField(blank=True)
    resolved_by = models.ForeignKey(User, null=True, related_name='resolved_appeals')
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True)
    class Meta:
        indexes = [models.Index(fields=['status', '-created_at'])]

# 5. ManagerDayStatus — Day ledger (earned day / force majeure / sick)
class ManagerDayStatus(models.Model):
    manager = models.ForeignKey(User, on_delete=CASCADE)
    date = models.DateField()
    status = models.CharField(choices=[
        ('working','Working'), ('weekend','Weekend'), ('sick','Sick'),
        ('vacation','Vacation'), ('force_majeure','ForceMajeure'),
        ('tech_failure','TechFailure')
    ], default='working')
    capacity_factor = models.FloatField(default=1.0)  # 0.0-1.0
    reason = models.TextField(blank=True)
    class Meta:
        unique_together = [('manager', 'date')]

# 6. CallRecord — Telephony (Phase 3, DORMANT initially)
class CallRecord(models.Model):
    client = models.ForeignKey('Client', on_delete=CASCADE, related_name='call_records')
    owner = models.ForeignKey(User, on_delete=CASCADE)
    source = models.CharField(max_length=20, default='manual')
    started_at = models.DateTimeField()
    duration_seconds = models.PositiveIntegerField(default=0)
    direction = models.CharField(max_length=10, choices=[('in','Incoming'),('out','Outgoing')])
    outcome = models.CharField(max_length=64, blank=True)
    recording_url = models.URLField(blank=True)
    provider_call_id = models.CharField(max_length=120, blank=True, db_index=True)
    raw_payload = models.JSONField(default=dict, blank=True)
    class Meta:
        indexes = [
            models.Index(fields=['client', '-started_at']),
            models.Index(fields=['owner', 'started_at']),
        ]
```

---

## РАЗДЕЛ 3: ФОРМУЛЫ — ТОЧНЫЕ СПЕЦИФИКАЦИИ

### 3.1 Текущая KPD формула (stats_service.py строки 182-251)

```python
def compute_kpd(metrics: dict, config: dict) -> dict:
    cfg = config.get("kpd") or {}
    
    # Effort: active time + points
    active_norm = float(cfg.get("active_norm_minutes", 240))  # 4 hours
    points_norm = float(cfg.get("points_norm", 180))
    max_effort = float(cfg.get("max_effort", 2.2))
    
    active_minutes = float(metrics.get("active_seconds", 0)) / 60.0
    effort_active = 0.0 if active_minutes <= 0 else min(1.0, (active_minutes / max(1.0, active_norm)) ** 0.6)
    
    pts = float(metrics.get("points", 0))
    effort_points = 0.0 if pts <= 0 else min(1.2, (pts / max(1.0, points_norm)) ** 0.55) * 1.2
    effort = min(max_effort, effort_active + effort_points)
    
    # Quality: success_weighted with Laplace smoothing
    sw = float(metrics.get("success_weighted", 0))
    cnt = float(metrics.get("processed", 0))
    quality = min(1.6, ((sw + 1.0) / (cnt + 5.0)) * 2.0) if cnt > 0 else 0.0
    
    # Ops: CP + shops + invoices (each capped at 0.4)
    cp = float(metrics.get("cp_email_sent", 0))
    shops = float(metrics.get("shops_created", 0))
    inv = float(metrics.get("invoices_created", 0))
    ops = min(0.4, cp / 5.0 * 0.4) + min(0.4, shops / 2.0 * 0.4) + min(0.4, inv / 2.0 * 0.4)
    ops = min(1.2, ops)
    
    # Penalty: missed followups + late reports + missing reports + plan missing
    fu_total = float(metrics.get("followups_total", 0))
    fu_missed = float(metrics.get("followups_missed", 0))
    missed_rate = fu_missed / max(1.0, fu_total) if fu_total > 0 else 0.0
    
    rep_req = int(metrics.get("report_days_required", 0))
    rep_late = int(metrics.get("report_days_late", 0))
    rep_miss = int(metrics.get("report_days_missing", 0))
    late_rate = rep_late / max(1, rep_req) if rep_req > 0 else 0.0
    miss_rate = rep_miss / max(1, rep_req) if rep_req > 0 else 0.0
    
    plan_miss = float(metrics.get("followup_plan_missing", 0))
    plan_pen = min(0.15, plan_miss / 20.0 * 0.15)
    
    penalty = min(0.6, missed_rate * 0.8 + late_rate * 0.25 + miss_rate * 0.5 + plan_pen)
    
    # Final
    raw = (effort + quality + ops) * (1.0 - penalty)
    value = round(max(0.0, raw), 2)
    
    return {
        "value": value,
        "effort": round(effort, 3),
        "quality": round(quality, 3),
        "ops": round(ops, 3),
        "penalty": round(penalty, 3),
        "grade": _kpd_grade(value),
    }
```

### 3.2 Success Weight Table (stats_service.py строки 553-561)

```python
EXISTING_SUCCESS_WEIGHTS = {
    'order': 1.0,
    'test_batch': 0.8,
    'waiting_payment': 0.6,
    'waiting_prepayment': 0.5,
    'xml_connected': 0.4,
    # all others: 0.0
}
```

### 3.3 Points Table (constants.py) — FULL с drift annotation

```python
POINTS = {
    "order": 45,              # codex: 45 ✅
    "test_batch": 25,          # codex: 25 ✅
    "waiting_payment": 20,     # codex: 20 ✅
    "waiting_prepayment": 18,  # codex: 18 ✅
    "xml_connected": 15,       # codex: 35 🔴 DRIFT! Difference: -57%
    "sent_email": 15,          # codex: 15 ✅
    "sent_messenger": 15,      # codex: 15 ✅
    "wrote_ig": 15,            # codex: 15 ✅
    "thinking": 10,            # codex: 10 ✅
    "other": 8,                # codex: 8 ✅
    "no_answer": 5,            # codex: 5 ✅
    "invalid_number": 5,       # codex: 5 ✅
    "not_interested": 5,       # codex: 5 ✅
    "expensive": 5,            # codex: 5 ✅
}

LEAD_ADD_POINTS = 2            # Points for adding a lead
LEAD_BASE_PROCESSING_PENALTY = 2  # Penalty for base-processing
TARGET_CLIENTS_DAY = 20        # Daily target clients
TARGET_POINTS_DAY = 100        # Daily target points
REMINDER_WINDOW_MINUTES = 15   # Follow-up reminder window
```

### 3.4 KPD Config Defaults (stats_service.py строки 130-169)

```python
DEFAULT_KPD_CONFIG = {
    "active_norm_minutes": 240,  # 4 hours
    "points_norm": 180,
    "max_effort": 2.2,
}

DEFAULT_ADVICE_CONFIG = {
    "min_n_sources": 15,          # Min clients from source to analyze
    "min_n_strong": 20,           # Min clients for strong recommendation
    "missed_followups_warn_pct": 8.0,   # Warning at 8% missed
    "missed_followups_alert_pct": 15.0,  # Alert at 15% missed
    "report_deadline_hour": 19,   # Reports due by 19:00
    "report_late_grace_minutes": 60,  # 60 min grace period
    "stale_shop_days": 14,        # Shop stale after 14 days
}
```

### 3.5 MOSAIC Formula (from codex 02_MOSAIC_SCORE_SYSTEM.md)

```python
# EWR = Earned Weighted Revenue (codex §2.1-2.2)
EWR_WEIGHTS = {
    "revenue_ratio": 0.40,
    "effort_ratio": 0.35,
    "source_quality": 0.25,
}
TARGET_WEEKLY_REVENUE = 50_000  # UAH

# MOSAIC Axes (codex §2.3)
MOSAIC_WEIGHTS = {
    "Result": 0.40,
    "SourceFairness": 0.15,
    "Process": 0.15,
    "FollowUp": 0.15,
    "DataQuality": 0.10,
    "VerifiedCommunication": 0.05,
}

# Trust Production (codex §2.5)
TRUST_BASE = 0.97
TRUST_PRODUCTION_MIN = 0.85
TRUST_PRODUCTION_MAX = 1.05
TRUST_COMPONENTS = {
    "report_penalty": -0.02,           # per missing report
    "reason_code_missing": -0.005,     # per missing reason
    "duplicate_abuse": -0.05,          # if flagged
    "anomaly_evidence": -0.05,         # if anomaly detected
    "report_bonus": +0.01,             # per on-time report
    "clean_record_bonus": +0.03,       # no violations
}

# Gates (codex §2.6)
EVIDENCE_GATES = {
    "paid": 100,
    "admin_confirmed": 78,
    "crm_timestamped": 60,
    "self_reported": 45,
}

# Dampener (codex §2.6)
DAMPENER_ALPHA = 0.3  # EWMA smoothing factor
MIN_DAYS_FOR_EWMA = 42
EWMA_SEED = 50.0  # Initial value for new managers

# Onboarding Floor (codex §2.6)
ONBOARDING_FLOOR_DAY_1 = 55
ONBOARDING_FLOOR_DECAY_RATE = 0.5  # Points per day
ONBOARDING_DURATION_DAYS = 42
```

---

## РАЗДЕЛ 4: CODEX ФАЙЛ → КОД ФАЙЛ MAPPING

| Codex файл | Key topics | Target code files | Action |
|---|---|---|---|
| `01_MASTER_SYNTHESIS` | Architecture overview, principles | ALL files | REFERENCE ONLY |
| `02_MOSAIC_SCORE_SYSTEM` | EWR, axes, trust, gates, dampener, onboarding | `services/score_service.py` (NEW), `services/trust_service.py` (NEW) | CREATE |
| `03_PAYROLL_KPI_AND_PORTFOLIO` | Commission, soft-floor, SPIFF, DMT, earned day | `services/payroll_service.py` (NEW), `models.py` (extend ManagerCommissionAccrual) | CREATE |
| `04_ANTI_DUPLICATION_AND_FOLLOWUP` | Dedupe, follow-up ladder, rate limiting | `services/dedupe_service.py` (NEW), `models.py` (extend Client) | CREATE |
| `05_IP_TELEPHONY_QA_SUPERVISOR` | CallRecord, QA, supervisor | `models.py` (add CallRecord), Phase 3+ only | DEFER |
| `06_UI_UX_AND_MANAGER_CONSOLE` | Radar, simulator, rescue, timeline | `stats.html`, `stats_views.py`, new JS/CSS | EXTEND |
| `07_IMPLEMENTATION_ROADMAP` | Phase plan, acceptance criteria | Implementation file itself | REFERENCE |
| `08_SENSITIVE_TO_CONTEXT` | Context-sensitive behaviors | Throughout codebase | REFERENCE |
| `09_RESEARCH_QUESTIONS` | Open questions | N/A | REFERENCE |
| `10_CHURN_MODEL_WEIBULL` | Weibull, logistic, portfolio | `services/churn_service.py` (NEW) | CREATE |
| `11_PRODUCT_BACKLOG` | Module list A-L | Implementation file itself | REFERENCE |
| `12_CALIBRATION_DEFAULTS` | Defaults registry, thresholds | `constants.py` (extend), `ManagementStatsConfig` (extend) | EXTEND |
| `13_CROSS_SYSTEM_GUARDRAILS` | Audit, access, formula governance | `models.py` (AuditLog), middleware | CREATE |
| `14_SCORING_EXPLAINABILITY` | Score explanation, confidence | `services/score_service.py`, stats template | CREATE |
| `15_ADMIN_ECONOMICS_AND_EARNED_DAY` | Break-even, forecast, workload | `services/forecast_service.py` (NEW) | CREATE |
| `16_ADDITIONAL_SCORING_DETAILS` | Detailed axis formulas | `services/score_service.py` | CREATE |
| `17_CALIBRATION_EVOLUTION` | A/B testing, recalibration | Config versioning | REFERENCE |
| `18_PACKAGE_CHANGELOG` | Change history | REFERENCE ONLY | — |
| `19-28` | Supplementary materials | Various | REFERENCE |

---

## РАЗДЕЛ 5: ВЕЩИ КОТОРЫЕ ЛЕГКО ПРОПУСТИТЬ (GOTCHAS)

### 5.1 🔴 КРИТИЧЕСКИЕ

1. **`points_override` на Client** — если MOSAIC не учтёт этот override, менеджеры, использующие manual overrides, получат inconsistent scores.

2. **Dual Shop FK: `created_by ≠ managed_by`** — при построении portfolio для менеджера нужно использовать `managed_by`, НЕ `created_by`. Пример: менеджер A создал магазин, потом его переназначили менеджеру B. Stats_service.py uses `created_by` (строки 801, 920) — это потенциальный баг при смене ownership!

3. **`normalize_phone()` handles ONLY +380** — если когда-либо добавятся международные клиенты, phone dedup сломается. Кодекс должен зафиксировать это ограничение.

4. **success_rate с Laplace smoothing** (строка 1100): `(sw + 1.0) / (cnt + 5.0)` — при cnt=0 результат = 0.2 (не ноль!). Это Bayesian prior, и MOSAIC EWR transition должен учитывать это поведение.

5. **WholesaleInvoice try-except** (строки 778-798) — if orders app not installed, all invoice data = 0. This SILENTLY disables revenue tracking. MOSAIC must handle this the same way.

6. **60-second cache on stats payload** (строка 1170) — `cache.set(cache_key, payload, 60)`. MOSAIC shadow computation will be cached too, so nightly snapshot vs real-time stats may show different values.

7. **`ManagementDailyActivity` tracks only focused tab time** — если менеджер переключается на другую вкладку, active_seconds перестаёт считаться. Кодекс предлагает использовать это как "diagnostic", но в KPD это PRODUCTION component.

### 5.2 🟡 ВАЖНЫЕ

8. **Existing management command `notify_test_shops.py`** — использует `ReminderSent` for idempotency и `MANAGEMENT_TG_BOT_TOKEN` env var. Новые commands ДОЛЖНЫ следовать этому pattern.

9. **`ContractSequence` model** (строки 1158-1160) — auto-incrementing sequence per year for contracts. Not relevant to MOSAIC but shows pattern for auto-numbered entities.

10. **`admin.py` registers only 6 of 22 models** — Client, Shop, Report, CommercialOffer*, ManagerCommission*, ManagerPayout*, ManagementContract — НЕ зарегистрированы. New models must be registered.

11. **`views.py` is 5912 lines** — splitting it will be a separate massive task. Do NOT attempt to split during MOSAIC implementation. Keep changes ADDITIVE only.

12. **`stats_views.py` line 5: `from .stats_service import get_stats_payload`** — extending stats_service means stats_views needs to import new functions but existing import must NOT break.

13. **Email templates** — `management/email_templates/twocomms_cp.py` is a Python file generating HTML email (not a Django template). It's separate from templates/.

14. **Telegram webhook endpoint** — `path('tg-manager/webhook/<str:token>/', views.management_bot_webhook)` already exists. New MOSAIC notifications can potentially USE this same bot, extending its handler.

15. **`advice_dismiss` sets `expires_at`** — dismissals are TEMPORARY (default 7 days in ManagementStatsAdviceDismissal). New MOSAIC tips must respect this pattern.

### 5.3 🟢 ПОЛЕЗНО ЗНАТЬ

16. **Existing indexes are well-designed** — `mgmt_lead_status_dt`, `mgmt_shop_type_dt`, `mgmt_fu_owner_dt_st`, etc. Follow same naming convention for new indexes.

17. **`related_name` convention** — uses descriptive names like `managed_clients`, `created_shops`, `managed_shops`. Follow this pattern.

18. **JSONField usage** — ManagementStatsConfig uses JSONField for flexible config. This is the pattern for any new configurable settings.

19. **`FOLLOWUP_PLAN_CALL_RESULTS`** (stats_service.py) — defines which call_results REQUIRE a follow-up plan. Currently: 'thinking', 'sent_email', 'sent_messenger', 'wrote_ig', 'waiting_payment', 'waiting_prepayment'. MOSAIC should use same list.

---

## РАЗДЕЛ 6: URL PATTERNS — ПОЛНАЯ КАРТА с endpoint signatures

### Существующие (75 endpoints, 5 view modules):

**views.py (основной, 44 endpoints):**
- Auth: `login/`, `logout/`
- Admin: `admin-panel/` (+10 sub-endpoints for users, invoices, payouts)
- Reports: `reports/`, `reports/send/`
- Reminders: `reminders/read/`, `reminders/feed/`
- Profile: `profile/update/`, `profile/bind-code/`
- Telegram: `tg-manager/webhook/<token>/`
- Invoices: 6 CRUD endpoints
- Contracts: 5 CRUD endpoints
- CP Email: 8 API endpoints
- Payouts: `payouts/`, `payouts/api/request/`
- Home: ``

**shop_views.py (9 endpoints):**
- Shops: `shops/`, save, detail, contact, next-contact, inventory, delete, shipment-download, contract-download

**stats_views.py (5 endpoints):**
- Stats: `stats/`, `stats/admin/`, `stats/admin/<user_id>/`, `stats/advice/dismiss/`, `activity/pulse/`

**lead_views.py (3 endpoints):**
- Leads: create, detail, process

**parsing_views.py (7 endpoints):**
- Parsing: dashboard, start, step, pause, resume, stop, status, lead-moderation

### Новые endpoints (минимум):

```python
# Stats extensions (add to stats_views.py)
path('stats/mosaic/shadow/', stats_views.mosaic_shadow_api, name='management_mosaic_shadow'),
path('stats/score/explain/', stats_views.score_explain_api, name='management_score_explain'),

# Appeals (add to views.py or new appeal_views.py)
path('appeals/', views.appeals, name='management_appeals'),
path('appeals/api/submit/', views.appeal_submit_api, name='management_appeal_submit'),

# Admin extensions (add to views.py)
path('admin-panel/readiness/', views.admin_readiness, name='management_admin_readiness'),
path('admin-panel/readiness/api/toggle/', views.admin_readiness_toggle_api, name='management_admin_readiness_toggle'),
path('admin-panel/economics/', views.admin_economics, name='management_admin_economics'),
path('admin-panel/freeze/', views.admin_freeze_api, name='management_admin_freeze'),
```

---

## РАЗДЕЛ 7: TELEGRAM INTEGRATION PATTERN

### Existing pattern (from `notify_test_shops.py`):

```python
# 1. Environment variables:
MANAGER_TG_BOT_TOKEN = os.environ.get("MANAGER_TG_BOT_TOKEN")
MANAGEMENT_TG_ADMIN_CHAT_ID = os.environ.get("MANAGEMENT_TG_ADMIN_CHAT_ID")

# 2. Get user's chat_id:
profile = user.userprofile
chat_id = int(getattr(profile, "tg_manager_chat_id", None) or 0) or None

# 3. Send message:
requests.post(f"https://api.telegram.org/bot{token}/sendMessage", 
              data={"chat_id": chat_id, "text": text}, timeout=8)

# 4. Track delivery with ReminderSent:
ReminderSent.objects.create(key=unique_key, chat_id=chat_id)
```

### Existing webhook handler (views.py → management_bot_webhook):
- Handles Telegram callbacks for payout/contract/invoice approval flow
- Uses `admin_tg_chat_id` + `admin_tg_message_id` stored on the model
- Pattern: model stores TG message reference → callback updates model status

---

## РАЗДЕЛ 8: РЕКОМЕНДУЕМАЯ ПОСЛЕДОВАТЕЛЬНОСТЬ ИМПЛЕМЕНТАЦИИ

### Strict dependency order:

```
Step 0: Fix xml_connected drift + add parity test
  ↓
Step 1: Add ComponentReadiness model + migration + seed
  ↓
Step 2: Add NightlyScoreSnapshot model + migration
  ↓  
Step 3: Add CommandRunLog model + migration
  ↓
Step 4: Extend ManagementStatsConfig (mosaic_weights, versions)
  ↓
Step 5: Create services/ directory with __init__.py
  ↓
Step 6: Create services/score_service.py (compute_ewr, compute_mosaic)
  ↓  
Step 7: Create services/trust_service.py (compute_trust_production)
  ↓
Step 8: compute_nightly_scores management command
  ↓
Step 9: Extend get_stats_payload() with shadow_mosaic
  ↓
Step 10: Extend stats.html with shadow MOSAIC card
  ↓
Step 11: Create services/advice_service.py (enhanced tips)
  ↓
Step 12: Radar chart component (Chart.js)
  ↓
Step 13: Admin readiness surface
  ↓
Step 14: Services/payroll_service.py (commission, soft-floor, SPIFF)
  ↓
Step 15: ManagerDayStatus model + earned-day logic
  ↓
Step 16: ScoreAppeal model + appeal workflow
  ↓
Step 17: Admin economics page
  ↓
Step 18: Services/dedupe_service.py
  ↓
Step 19: Services/churn_service.py (Weibull)
  ↓
Step 20: Portfolio health + rescue top-5
  ↓
Step 21: KPD → MOSAIC activation gate check
  ↓
Step 22: tests/ directory with all test modules
```

### What NOT to do:
- ❌ Split views.py during implementation — too risky
- ❌ Change existing KPD formula — keep as-is until MOSAIC activated
- ❌ Add CallRecord before telephony provider selected
- ❌ Create new models without admin.py registration
- ❌ Skip ComponentReadiness — it's the safety net

---

## РАЗДЕЛ 9: ENV VARIABLES И SETTINGS

### Existing env vars used by management:
```
MANAGER_TG_BOT_TOKEN          — Telegram bot for manager notifications
MANAGEMENT_TG_BOT_TOKEN       — Telegram bot for admin notifications  
MANAGEMENT_TG_ADMIN_CHAT_ID   — Admin chat ID(s), comma-separated
```

### Django settings to be aware of:
```python
CACHES = {
    'default': {
        'BACKEND': '...',  # Check actual backend (FileBasedCache vs others)
    }
}
AUTH_USER_MODEL = '...'        # The user model used throughout
TIME_ZONE = 'Europe/Kyiv'     # ⚠️ Ukrainian timezone affects all date calculations
USE_TZ = True                  # Timezone-aware datetimes
```

---

## РАЗДЕЛ 10: CROSS-REFERENCE — REPORTS FINDINGS → IMPLEMENTATION ACTIONS

### From `gemini_2.5_pro_deep_analysis_report.md`:
| Finding | Action in implementation |
|---|---|
| MOSAIC weight calibration needed | Use shadow mode to validate weights |
| EWR precision suggestions | Implement as spec'd, tune in shadow |
| Source fairness improvements | Include in SourceFairness axis |
| Churn model should use Wilson | Include Wilson as diagnostic companion |

### From `gemini_2.5_pro_implementation_readiness_audit.md` (65 gaps):
| Gap | Action |
|---|---|
| #21-25: Testing strategy | Create tests/ alongside each service |
| #16,18: Service contracts | Define input/output/side-effects per function |
| #43: Feature flags | ComponentReadiness model (Step 1) |
| #36-40: Formula edge cases | Implement EWMA seed, gate floor, dampener+onboarding order |
| #1-4: Migration rollback | Small migrations, reversible RunPython |
| #15: Cron safety | File-based lock in each management command |
| #41-42: Transition protocol | ComponentReadiness + correlation monitoring |
| #61-65: Code architecture | services/ directory (Step 5-6) |

### From `gemini_2.5_pro_code_reality_cross_audit.md` (47 gaps):
| Gap | Action |
|---|---|
| A1: Shop subsystem invisible | Document in codex, consider RetailHealth sub-axis |
| A2: ManagementDailyActivity exists | Map to Process axis or keep as KPD-only |
| A5: KPD formula undocumented | Create KPD→MOSAIC transition map |
| B1: xml_connected drift | FIX IMMEDIATELY in constants.py |
| B2: Dual scoring tables | Document both POINTS and success_weight |
| C1: Telegram integration | Extend existing pattern for MOSAIC alerts |
| C2: WholesaleInvoice dependency | Handle with try-except like existing code |
| D2: Triple attribution | Define portfolio_scope per entity type |
| E1-E2: Model/Service maps | Use maps from this document |

---

## РАЗДЕЛ 11: ТЕСТОВАЯ ИНФРАСТРУКТУРА

### Required test modules (from implementation_readiness_audit):

```
management/tests/
├── __init__.py
├── test_ewr.py              # EWR computation with golden-file data
├── test_mosaic.py            # Full MOSAIC pipeline end-to-end
├── test_trust.py             # Trust production boundary cases
├── test_dampener.py          # EWMA dampener + onboarding floor
├── test_gates.py             # Evidence gate interpolation
├── test_kpd.py               # Existing KPD formula (lock behavior)
├── test_churn_weibull.py     # Weibull + logistic fallback
├── test_soft_floor.py        # Payroll soft-floor + proration
├── test_commission.py        # Commission (new/repeat/reactivation)
├── test_rescue_spiff.py      # SPIFF boundaries + capacity guard
├── test_portfolio_health.py  # Threshold transitions
├── test_dedupe.py            # Phone + name dedup accuracy
├── test_snapshot.py          # Snapshot idempotency + schema
├── test_day_status.py        # Earned day + force majeure
├── test_defaults_parity.py   # ⚠️ doc/code constant parity check
├── test_advice.py            # Advice generation + dismissal
├── factories.py              # Test data factories (Client, Shop, etc.)
└── conftest.py               # Shared fixtures
```

### Golden-file test pattern:
```python
GOLDEN_CASES = [
    {
        "input": {"revenue": 60000, "contacts": 90, "source_mix": {"prom":40, "google":30}},
        "expected_ewr": 72.4,
        "tolerance": 0.5,
    },
    # ... more cases
]

def test_ewr_golden(self):
    for case in GOLDEN_CASES:
        result = compute_ewr(**case["input"])
        self.assertAlmostEqual(result.score, case["expected_ewr"], delta=case["tolerance"])
```

---

## РАЗДЕЛ 12: PERFORMANCE BUDGETS

| Operation | Target | Current baseline |
|---|---|---|
| `get_stats_payload()` | < 200ms | Not measured (has 60s cache) |
| `stats.html` load | < 2s | Depends on payload |
| `compute_nightly_scores` (all managers) | < 30 min | N/A (doesn't exist yet) |
| `duplicate_check` per client | < 500ms | N/A |
| Admin overview load | < 2s | Not measured |

### Query hotspots to watch:
- `stats_service.py` has multiple `.annotate()` chains — each is a separate DB query
- Shop stale query (строки 920-926) joins `Shop` + `ShopCommunication` — could be slow with many shops
- Follow-up problem list (строки 644-651) fetches individual client data — potential N+1

---

*Документ подготовлен: Gemini 2.5 Pro (Antigravity), 2026-03-13*
*Полный инвентарь: models.py (1160 строк, 22 модели), stats_service.py (1259 строк), views.py (5912 строк), shop_views.py (946), stats_views.py (222), lead_views.py (234), parsing_views.py (381), invoice_service.py (574), parser_service.py (415), forms.py (247), lead_services.py (57), constants.py (24), admin.py (78), urls.py (85), notify_test_shops.py (95), 17 templates*
