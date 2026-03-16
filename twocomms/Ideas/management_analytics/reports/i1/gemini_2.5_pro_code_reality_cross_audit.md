# Gemini 2.5 Pro — Code ↔ Codex Cross-Reference Audit

> **Модель**: Gemini 2.5 Pro (Antigravity)
> **Дата**: 2026-03-13
> **Объект**: `final_codex_synthesis_2026_03_12` (28 файлов) vs. `management/` (реальный код: models.py, stats_service.py, constants.py, views, services)
> **Фокус**: Gaps между тем что кодекс **предполагает** и тем что **реально существует** в коде
> **Методология**: Sequential Thinking MCP + полный code review + file-by-file cross-reference
> **Предшественники**: дополняет `gemini_2.5_pro_deep_analysis_report.md` (формулы) и `gemini_2.5_pro_implementation_readiness_audit.md` (инфраструктура)

---

## Executive Summary

Предыдущие два отчёта работали "внутри кодекса": один анализировал формулы, другой — инфраструктуру для имплементации. Этот отчёт делает то, чего **не делал никто** — сравнивает кодекс с **реальным production-кодом** (`management/models.py`: 1160 строк, 22 модели; `stats_service.py`: 1259 строк; `constants.py`: 24 строки).

> **Главное открытие**: Кодекс описывает систему так, будто она начинается с нуля. Но management-подсистема **уже содержит** сложную production-инфраструктуру, которую кодекс полностью игнорирует. Это создаёт серьёзный risk: имплементация "по кодексу" может СЛОМАТЬ или ПРОДУБЛИРОВАТЬ существующую функциональность.

### Обзор findings

| Категория | Gaps | Критичность |
|---|---:|---|
| **A. Кодекс слеп к реальному коду** | 12 | 🔴 Критическая |
| **B. Внутренние противоречия кодекса** | 8 | 🔴 Блокирующая |
| **C. Пропущенные интеграции** | 10 | 🟡 Высокая |
| **D. Бизнес-логика, которую никто не нашёл** | 9 | 🟡 Высокая |
| **E. Подготовка к имплементации: контракты code↔codex** | 8 | 🔴 Критическая |
| **ИТОГО** | **47** | |

**В совокупности с предыдущими отчётами: 65 + 30+ + 47 = ~142 findings.**

---

## КАТЕГОРИЯ A: Кодекс СЛЕП к реальному коду (12 gaps)

### A1. 🔴 Shop Subsystem — 5 моделей, НЕВИДИМЫХ для кодекса (Impact: 10/10)

**Факт**: В `management/models.py` существует полностью рабочая система отслеживания розничных магазинов:

| Модель | Строки кода | Назначение |
|---|---|---|
| `Shop` | 617-687 | Магазин с типом (test/full), локацией, URL'ами, тестовым товаром, периодом теста |
| `ShopPhone` | 689-712 | Множественные номера телефонов на магазин с ролями (owner/manager/admin/other) |
| `ShopShipment` | 715-757 | Отгрузки (ТТН) с привязкой к WholesaleInvoice + суммы |
| `ShopCommunication` | 760-785 | Журнал коммуникаций с магазинами |
| `ShopInventoryMovement` | 788-832 | Движение товаров (приход/продажа/корректировка) |

**Что уже вычисляет `stats_service.py` по магазинам** (строки 800-996):
- `shops_created`, `shops_test`, `shops_full` — за период
- `stale_shops_count` + `stale_shops_list` — магазины без контакта > N дней
- `overdue_tests` + `overdue_tests_list` — просроченные тестовые периоды
- `tests_converted_total` — конверсия тест → полный магазин
- `shipments_count` + `shipments_amount` — отгрузки
- `inv_sales_qty`, `inv_receipts_qty`, `inv_adjust_count` — движение товаров
- `comms_count` — количество коммуникаций
- Advice карточки #7: stale shops, next contact due, overdue tests

**Что кодекс говорит о магазинах**: **НИЧЕГО**. Ни один из 28 файлов не упоминает Shop, ShopShipment, ShopPhone, ShopCommunication, ShopInventoryMovement. Слово "магазин" даже не используется в контексте клиентской инфраструктуры.

**Почему это критично**:
1. MOSAIC НЕ ИМЕЕТ оси для "здоровье ретейл-отношений после первой продажи"
2. KPI модель НЕ учитывает работу по удержанию магазинов
3. Portfolio health НЕ включает churn-сигналы магазинов
4. Rescue-концепция НЕ покрывает "умирающие" магазины (stale, overdue test)
5. Ownership-диспуты НЕ адресуют `created_by ≠ managed_by` для магазинов

**Рекомендация**: Добавить в кодекс раздел "Shop Lifecycle and Retention Analytics":
- MOSAIC ось или sub-axis: `RetailHealth` (stale contact rate, test conversion %, shipment frequency)
- KPI integration: тестовые конверсии → в Result или в Ops
- Portfolio layer: Shop → ShopShipment revenue attribution → ManagerCommissionAccrual

---

### A2. 🔴 ManagementDailyActivity уже СУЩЕСТВУЕТ (Impact: 8/10)

**Факт**: Модель `ManagementDailyActivity` (строки 835-864):
```python
class ManagementDailyActivity(models.Model):
    """Active time counts only when Management tab is visible + focused and user is not idle."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, ...)
    date = models.DateField(db_index=True)
    active_seconds = models.PositiveIntegerField(default=0)
    last_seen_at = models.DateTimeField(null=True, blank=True)
```

**Как используется в KPD** (stats_service.py, строки 185-193):
```python
active_minutes = float(metrics.get("active_seconds", 0)) / 60.0
effort_active = 0.0 if active_minutes <= 0 else min(1.0, (active_minutes / max(1.0, active_norm)) ** 0.6)
```
Active time — ОСНОВНОЙ компонент `effort` в KPD, который является ключевым фактором итоговой оценки.

**Что кодекс говорит**: `15_ADMIN_ECONOMICS_AND_EARNED_DAY.md §2.7`: "Если команда позже захочет добавить workload consistency / active tab time, это допустимо только как explicit admin-only metric"

**Проблема**: Кодекс считает active_seconds гипотетическим будущим функционалом, хотя это **production-critical компонент текущего scoring engine**.

**Рекомендация**: 
- Кодекс должен ЯВНО описать ManagementDailyActivity как existing component
- MOSAIC integration: решить, входит ли active_seconds в Process axis или остаётся только в KPD legacy
- Transition plan: если MOSAIC НЕ будет использовать active_seconds, менеджеры увидят резкий сдвиг при переходе

---

### A3. 🔴 CommercialOffer Email System — 50+ полей, absent from codex (Impact: 7/10)

**Факт**: Две модели (строки 352-613):
- `CommercialOfferEmailSettings` — 50+ полей: pricing mode, CTA types, gallery (neutral/edgy), branding, opt tiers, dropship settings
- `CommercialOfferEmailLog` — полный лог отправок с analytics (mode, segment, pricing, CTA, gallery items)

**Как используется в stats** (строки 769-776):
```python
cp_total = cp_qs.count()
cp_sent = cp_qs.filter(status='SENT').count()
cp_failed = cp_qs.filter(status='FAILED').count()
```
CP e-mails — компонент KPD `ops` и advice #8 (source comparison).

**Что кодекс говорит**: Ни один из 28 файлов не упоминает commercial offer, коммерческое предложение, CP email, или email marketing system.

**Рекомендация**: Добавить CP emails как VerifiedCommunication touch-point в MOSAIC Process axis. Качество CP (ratio sent/failed, mode distribution) = signal для Process качества.

---

### A4. 🔴 Contract Management System — absent from codex (Impact: 6/10)

**Факт**: `ManagementContract` (строки 1087-1160) — полный lifecycle:
- `draft → pending → approved → rejected` workflow
- Telegram admin notifications (`admin_tg_chat_id`, `admin_tg_message_id`)
- `ContractSequence` — автонумерация по годам
- `ContractRejectionReasonRequest` — запрос причины отклонения через Telegram

**Что кодекс говорит**: Ноль упоминаний контрактов с реалізаторами.

**Рекомендация**: Включить ContractStatusTransition в Process quality signal. Контракт approved = процессная зрелость менеджера.

---

### A5. 🔴 Existing KPD Formula — кодекс не знает деталей (Impact: 9/10)

**Факт**: KPD в коде (строки 182-251) — это 4-компонентная формула:

| Компонент | Диапазон | Расчёт |
|---|---|---|
| **Effort** | 0..2.2 | `effort_active` (active_seconds / norm)^0.6 + `effort_points` (points / norm)^0.55 * 1.2 |
| **Quality** | 0..1.6 | `(success_weighted + 1.0) / (processed + 5.0) * 2.0` (Laplace smoothing) |
| **Ops** | 0..1.2 | `min(0.4, cp/5*0.4) + min(0.4, shops/2*0.4) + min(0.4, invoices/2*0.4)` |
| **Penalty** | 0..0.6 | `missed_rate*0.8 + report_late*0.25 + report_missing*0.5 + followup_penalty` |
| **Final** | ≥ 0 | `(effort + quality + ops) * (1 - penalty)` |

**Что кодекс говорит**: "KPD" упоминается как "текущая шкала", которую MOSAIC заменит. Но ДЕТАЛЕЙ текущей KPD формулы — нет.

**Почему это критично для transition**:
- KPD effort использует `active_seconds` → MOSAIC не планирует использовать
- KPD quality использует `success_weighted` с Laplace smoothing → MOSAIC EWR использует другую формулу
- KPD ops включает CP emails + shops + invoices → MOSAIC не имеет эквивалента
- KPD penalty включает report discipline → MOSAIC не адресует

**Рекомендация**: Создать `KPD_TO_MOSAIC_TRANSITION_MAP.md`:
```
KPD Effort (active_time) → MOSAIC ???  (GAP: не определено)
KPD Effort (points)      → MOSAIC Result axis (partial)
KPD Quality              → MOSAIC Result axis (EWR replaces)
KPD Ops (CP + shops)     → MOSAIC Process + VerifiedComm (partial)
KPD Penalty (missed FU)  → MOSAIC FollowUp axis (replaces)
KPD Penalty (reports)    → MOSAIC DataQuality axis (partial)
```

---

### A6. 🟡 Existing Advice System — 8 типов, уже production (Impact: 6/10)

**Факт**: `generate_advice()` (строки 260-532) содержит 8 advice type:
1. Productivity trend (points/hour)
2. Follow-up discipline (missed rate)
3. Source test recommendations
4. Active time vs results (3-day window)
5. Report discipline (late/missing)
6. Follow-up planning after key stages
7. Shop health (stale/overdue/test)
8. Source quality comparison

**Что кодекс говорит**: Файл 06 UI/UX описывает "tips" как новую фичу к разработке, не зная что sophisticated advice engine уже работает.

**Рекомендация**: Кодекс должен MAP новые tips к existing advice infra. Не создавать новую систему, а расширять `generate_advice()`.

---

### A7. 🟡 ManagementStatsConfig singleton — уже существует (Impact: 6/10)

**Факт**: `ManagementStatsConfig` (строки 941-956) — singleton с `kpd_weights` и `advice_thresholds` как JSONField.

Используется в `_get_or_build_config()` (строки 130-169) с defaults:
```python
"kpd": {"active_norm_minutes": 240, "points_norm": 180, "max_effort": 2.2, ...}
"advice": {"min_n_sources": 15, "min_n_strong": 20, "missed_followups_warn_pct": 8.0, ...}
```

**Что кодекс говорит**: `12_CALIBRATION_DEFAULTS_AND_PRESETS.md` предлагает отдельный defaults registry с версионированием.

**Рекомендация**: Расширить СУЩЕСТВУЮЩИЙ ManagementStatsConfig, а не создавать новую модель:
- Добавить `mosaic_weights` JSONField
- Добавить `defaults_version` CharField
- Добавить `formula_version` CharField
- Migrations: сохранить backward compatibility с текущими kpd_weights

---

### A8. 🟡 ManagementStatsAdviceDismissal — dismissal already implemented (Impact: 5/10)

**Факт**: `ManagementStatsAdviceDismissal` (строки 917-938) — модель для скрытия советов менеджером с expiration.

**Что кодекс говорит**: UI/UX раздел предлагает "dismissable tips" как новую фичу.

**Рекомендация**: Просто MAP новые MOSAIC tips к существующему dismissal механизму. Ключ = advice `key` string.

---

### A9. 🟡 Client model fields — уже частично готовы (Impact: 5/10)

**Факт**: `Client` модель (строки 23-79) уже имеет:
- `phone_normalized` — нормализованный телефон (codex предлагает "добавить")
- `points_override` — ручной override баллов (codex не знает о нём)
- `source` — источник контакта (codex предлагает переделать)
- `call_result` — 13 choices (codex предлагает расширить)

**Рекомендация**: Не переделывать Client с нуля. Расширять incrementally через `add field` migrations.

---

### A10. 🟡 ClientFollowUp — уже полная модель (Impact: 5/10)

**Факт**: `ClientFollowUp` (строки 867-914) — 5 статусов (open, done, rescheduled, cancelled, missed), привязка к Client + Owner, метадату через JSONField.

`stats_service.py` уже считает: fu_total, fu_missed, fu_done, fu_rescheduled, fu_cancelled, fu_open, fu_overdue_open, missed_effective, missed_rate, fu_problem_list.

**Что кодекс говорит**: `04_ANTI_DUPLICATION_AND_FOLLOWUP_ENGINE.md` описывает follow-up ladder как "планируемую систему".

**Рекомендация**: FollowUp ENGINE уже работает. Кодекс должен описывать РАСШИРЕНИЯ (ladder escalation, auto-reschedule), а не базовую модель.

---

### A11. 🟡 ManagerCommissionAccrual — frozen_until уже есть (Impact: 5/10)

**Факт**: `ManagerCommissionAccrual` (строки 959-993):
```python
base_amount = models.DecimalField(...)
percent = models.DecimalField(...)
amount = models.DecimalField(...)
frozen_until = models.DateTimeField(db_index=True)
```

**Что кодекс говорит**: Файл 03 описывает commission freeze как новую концепцию.

**Рекомендация**: Freeze механизм уже реализован через `frozen_until`. MOSAIC/payroll integration должен РАСШИРИТЬ его, не заменять.

---

### A12. 🟡 ManagerPayoutRequest — workflow уже production (Impact: 5/10)

**Факт**: `ManagerPayoutRequest` (строки 996-1048) — полный payout workflow: processing → approved/rejected → paid. С Telegram integration:
```python
admin_tg_chat_id = models.BigIntegerField(null=True, blank=True)
admin_tg_message_id = models.BigIntegerField(null=True, blank=True)
```

**Рекомендация**: Новый payroll pipeline из кодекса (soft-floor, SPIFF, rescue) должен ИСПОЛЬЗОВАТЬ существующий PayoutRequest как final destination, не создавать отдельный pipeline.

---

## КАТЕГОРИЯ B: Внутренние противоречия кодекса (8 gaps)

### B1. 🔴 Points table DRIFT уже существует (Impact: 9/10)

**Факт — ПРЯМОЕ ПРОТИВОРЕЧИЕ**:

| CallResult | `constants.py` (код) | `12_CALIBRATION_DEFAULTS` (кодекс) | Δ |
|---|---:|---:|---|
| `order` | 45 | 45 | ✅ |
| `test_batch` | 25 | 25 | ✅ |
| `waiting_payment` | 20 | 20 | ✅ |
| `waiting_prepayment` | 18 | 18 | ✅ |
| **`xml_connected`** | **15** | **35** | **🔴 -57%** |
| `sent_email` | 15 | 15 | ✅ |
| `sent_messenger` | 15 | 15 | ✅ |
| `wrote_ig` | 15 | 15 | ✅ |
| `thinking` | 10 | 10 | ✅ |
| `other` | 8 | 8 | ✅ |
| `no_answer` | 5 | 5 | ✅ |
| `invalid_number` | 5 | 5 | ✅ |
| `not_interested` | 5 | 5 | ✅ |
| `expensive` | 5 | 5 | ✅ |

**`xml_connected` = 15 в production-коде, 35 в кодексе**. Это РОВНО тот баг "silent config drift", о котором tc_mosaic_improvements предупреждает в §8. Но баг уже СУЩЕСТВУЕТ.

**Рекомендация**: 
1. НЕМЕДЛЕННО определить: 15 или 35 — какое значение правильное?
2. Добавить parity test (как предложено в Gap #22 предыдущего отчёта):
```python
def test_points_match_codex():
    from management.constants import POINTS
    CODEX_POINTS = {"order": 45, "xml_connected": 35, ...}
    for key, expected in CODEX_POINTS.items():
        assert POINTS[key] == expected, f"DRIFT: {key}={POINTS[key]}, codex={expected}"
```

---

### B2. 🔴 success_weight vs points — два разных scoring (Impact: 8/10)

**Факт**: В `stats_service.py` есть **ОТДЕЛЬНАЯ** таблица весов (строки 553-561):
```python
def _success_weight_for_call_result(code: str) -> float:
    return {
        'order': 1.0,
        'test_batch': 0.8,
        'waiting_payment': 0.6,
        'waiting_prepayment': 0.5,
        'xml_connected': 0.4,
    }.get(code, 0.0)
```

Эта таблица используется для `success_weighted` → `quality` в KPD и `success_rate` в source comparison.

**Проблема**: Кодекс описывает ОДНУ таблицу points. Но в коде есть ДВЕ разные таблицы: `POINTS` (для баллов) и `_success_weight_for_call_result` (для quality/success). Они имеют РАЗНЫЕ пропорции:

| Result | Points ratio (vs order) | Success weight ratio (vs order) |
|---|---|---|
| order | 1.0 | 1.0 |
| test_batch | 0.56 | 0.8 |
| xml_connected | 0.33 (code) / 0.78 (codex) | 0.4 |

**Рекомендация**: Кодекс должен явно описать обе таблицы и их разные роли:
- `POINTS` → абсолютные баллы (рейтинг продуктивности)
- `success_weight` → относительный вес для quality index (conversion funnel position)

---

### B3. 🟡 source normalization: codex vs code (Impact: 7/10)

**Факт**: Кодекс (`04_ANTI_DUPLICATION`) предлагает SequenceMatcher для name matching. Код (`stats_service.py` строки 535-550) использует простую keyword-категоризацию:
```python
def _normalize_source(raw: str) -> tuple[str, str]:
    sl = s.lower()
    if "instagram" in sl: return "instagram", "Instagram"
    if "prom" in sl: return "prom_ua", "Prom.ua"
    if "google" in sl: return "google_maps", "Google Карти"
    if "форум" in sl: return "forums", "Сайти / форуми"
    # fallback: md5 hash bucket
    return f"custom_{digest}", s
```

**Проблема**: Кодекс предлагает сложный ML-подобный matching, но реальный код уже использует простую и работающую систему. Нужно ли менять?

**Рекомендация**: Для SOURCE normalization — текущий подход ДОСТАТОЧЕН. SequenceMatcher нужен для КЛИЕНТСКИХ имён (дедупликация), не для source categorization. Кодекс должен чётко разделить: source normalization ≠ client name dedup.

---

### B4. 🟡 phone normalization — только Украина (Impact: 6/10)

**Факт**: `normalize_phone()` (строки 8-20):
```python
def normalize_phone(raw_phone: str) -> str:
    if digits.startswith("380") and len(digits) == 12: return f"+{digits}"
    if digits.startswith("0") and len(digits) == 10: return f"+38{digits}"
    if len(digits) == 9: return f"+380{digits}"
```

Обрабатывает ТОЛЬКО украинские номера (+380). Кодекс описывает `phone_last7` matching без учёта международного формата.

**Рекомендация**: Если бизнес работает только в Украине — текущая нормализация ДОСТАТОЧНА. Но кодекс должен это явно зафиксировать как constraint: "Phone normalization assumes +380 prefix. International clients will require normalization extension."

---

### B5. 🟡 Laplace smoothing vs Wilson interval (Impact: 7/10)

**Код** использует Laplace smoothing для success rate (строка 679):
```python
"success_rate": round((sw + 1.0) / (cnt + 5.0), 3)
```

**Кодекс** (`02_MOSAIC §8`) предлагает Wilson Score Interval для diagnostic confidence.

**Проблема**: Это ДВА РАЗНЫХ underлежащих approach. Laplace = Bayesian prior. Wilson = frequentist confidence interval. Они дадут РАЗНЫЕ результаты при малых выборках.

**Рекомендация**: Кодекс должен решить:
- Laplace smoothing → для production success_rate (лёгкий, достаточный)
- Wilson interval → для diagnostic confidence badge ("high/medium/low" label)
- Они дополняют друг друга, не заменяют

---

### B6. 🟡 report discipline: code vs codex (Impact: 5/10)

**Код** считает report_days_required только для рабочих дней С активностью (строка 879):
```python
if d.weekday() < 5 and int(base.get("clients") or 0) > 0:
    report_days_required += 1
```

**Кодекс** не определяет: нужен ли report в день без обработанных клиентов? Что если менеджер работал (active_seconds > 0) но не обработал ни одного клиента?

**Рекомендация**: Текущая логика ПРАВИЛЬНАЯ (report нужен если были клиенты). Но это нужно ЗАДОКУМЕНТИРОВАТЬ в кодексе как explicit rule.

---

### B7. 🟡 cache strategy — codex proposes FileBasedCache, code uses default cache (Impact: 5/10)

**Код** использует абстрактный `cache` (Django default cache backend, строка 131):
```python
cache_key = "mgmt:stats:config:v1"
cached = cache.get(cache_key)
```

**Кодекс** (`04_ANTI_DUPLICATION §4.6`) explicitly рекомендует FileBasedCache.

**Рекомендация**: Алайнмент — проверить settings.py для CACHES['default']. Если уже FileBasedCache — нет action. Если другой backend — не менять, алайнить кодекс к реальности.

---

### B8. 🟡 Кодекс предлагает `is_test` field на Client — но Test уже на Shop (Impact: 5/10)

**Факт**: Shop.ShopType.TEST — тестовые партии привязаны к МАГАЗИНУ, не к клиенту. Кодекс предлагает `Client.is_test`, но реальная модель использует `Shop.shop_type == "test"`.

**Рекомендация**: НЕ добавлять `is_test` на Client. Оставить на Shop. Кодекс нужно исправить.

---

## КАТЕГОРИЯ C: Пропущенные интеграции (10 gaps)

### C1. 🔴 Telegram Admin Workflow — основной канал решений (Impact: 8/10)

**Факт**: Три модели используют Telegram для admin approval:
- `ManagerPayoutRequest.admin_tg_chat_id` + `admin_tg_message_id`
- `ManagementContract.admin_tg_chat_id` + `admin_tg_message_id`
- `InvoiceRejectionReasonRequest.admin_chat_id` + `prompt_message_id`
- `PayoutRejectionReasonRequest.admin_chat_id` + `prompt_message_id`
- `ContractRejectionReasonRequest.admin_chat_id` + `prompt_message_id`

**Что кодекс говорит**: Ноль упоминаний Telegram как admin workflow channel.

**Рекомендация**: Кодекс должен ЯВНО описать:
- Freeze action → Telegram notification to admin
- Appeal → Telegram prompt for resolution
- MOSAIC anomaly → Telegram alert
- Score override → Telegram audit trail

---

### C2. 🔴 WholesaleInvoice cross-module dependency (Impact: 7/10)

**Факт** (строки 778-798):
```python
try:
    from orders.models import WholesaleInvoice
except Exception:
    WholesaleInvoice = None
```

Management module ЗАВИСИТ от orders module. Invoice creation, payment status, approval — всё берётся оттуда. `ManagerCommissionAccrual.invoice` — OneToOneField к `orders.WholesaleInvoice`.

**Что кодекс говорит**: Кодекс описывает commission как если бы revenue была self-contained. Но `base_amount` в commission берётся из WholesaleInvoice.

**Рекомендация**: Добавить в кодекс секцию "Cross-Module Dependencies":
```
management → orders.WholesaleInvoice (invoice data, amounts, status)
management → storefront.Product (Shop.test_product)
management → settings.AUTH_USER_MODEL (all foreign keys)
```

---

### C3. 🟡 Revenue attribution — 3 paths, no reconciliation (Impact: 7/10)

**Три разных источника revenue**:
1. `ManagerCommissionAccrual.base_amount` — на уровне отдельного инвойса
2. `ShopShipment.invoice_total_amount` — на уровне отгрузки (может включать несколько инвойсов?)
3. `WholesaleInvoice.total_amount` — первоисточник суммы

Кодекс предполагает `attributed_revenue` как единый чистый показатель. Реальность: revenue распределена по трём моделям с потенциальными расхожениями.

**Рекомендация**: Определить single source of truth для revenue: `WholesaleInvoice.total_amount` (filtered by is_approved=True, payment_status='paid'). Все остальные — derived.

---

### C4. 🟡 Report model — слишком минималистична (Impact: 5/10)

**Факт**: `Report` модель (строки 285-304) — всего 4 поля: owner, created_at, points, processed.

Кодекс предлагает расширенные отчёты с breakdown по осям, confidence, comments. Текущая модель не поддерживает ничего из этого.

**Рекомендация**: Extend Report model с JSONField `details`:
```python
details = models.JSONField(default=dict, blank=True)
# {"mosaic_snapshot_id": ..., "axes_breakdown": {...}, "notes": "..."}
```

---

### C5. 🟡 ManagementLead pipeline — not in codex (Impact: 6/10)

**Факт**: `ManagementLead` (строки 82-184) — полная лид-модель с pipeline: moderation → base → converted/rejected. С niche_status, Google Place ID integration, parser job linkage.

Кодекс обсуждает "dedup" и "follow-up" для Client, но никогда не упоминает ManagementLead pipeline как standalone concept. А это ПРЕДШЕСТВУЮЩИЙ этап перед Client.

**Рекомендация**: Кодекс должен описать ПОЛНЫЙ client lifecycle: Lead → (moderation) → Client → (follow-up) → Shop → (retention). Сейчас описан только средний этап.

---

### C6. 🟡 LeadParsingJob — automated lead generation (Impact: 5/10)

**Факт**: `LeadParsingJob` (строки 187-234) + `LeadParsingResult` (237-282) — Google Maps parser с tracking: keywords, cities, request limits, dedup stats, error handling.

Кодекс не знает о существовании автоматизированной лідогенерації. MOSAIC SourceFairness axis should consider parser-generated vs manual leads.

**Рекомендация**: SourceFairness axis → учитывать `lead_source` (manual vs parser). Parser leads автоматически высокого объёма но потенциально низкого quality.

---

### C7. 🟡 CommercialOfferEmailLog — untapped analytics (Impact: 5/10)

Detailed per-send analytics exist: mode (LIGHT/VISUAL), segment (NEUTRAL/EDGY), pricing, CTA type. This data could feed into Process quality or VerifiedCommunication, but codex doesn't know about it.

---

### C8. 🟡 Email templates (twocomms_cp.py) — not mentioned (Impact: 4/10)

`management/email_templates/twocomms_cp.py` exists. Codex UI/UX section doesn't reference it.

---

### C9. 🟡 Existing indexes — partially address performance concerns (Impact: 4/10)

Many models already have well-designed indexes (e.g., `mgmt_lead_status_dt`, `mgmt_shop_type_dt`, `mgmt_fu_owner_dt_st`). Codex's performance concerns are partially mitigated.

---

### C10. 🟡 stats caching — 60s TTL already implemented (Impact: 4/10)

```python
cache.set(cache_key, payload, 60)  # short cache for near-realtime feel
```

Кодекс предлагает caching стратегию, но базовый caching уже работает.

---

## КАТЕГОРИЯ D: Бизнес-логика, которую НИКТО не нашёл (9 gaps)

### D1. 🔴 Test→Full Shop Conversion — KEY metric, не в MOSAIC (Impact: 8/10)

Stats_service уже считает `tests_converted_total`. Это КРИТИЧЕСКИЙ бизнес-показатель: менеджер привлёк клиента на тест-партию, тот перешёл в полный магазин. Это Revenue Validation в чистом виде.

**Рекомендация**: MOSAIC Result axis or Portfolio Health → include test_to_full_conversion_rate:
```python
conversion_rate = tests_converted / (tests_converted + tests_active + tests_overdue)
```

---

### D2. 🔴 `created_by` vs `owner` vs `managed_by` — тройная атрибуция (Impact: 8/10)

**Три разных FK pattern для "чей менеджер"**:

| Модель | FK(s) | Роль |
|---|---|---|
| `Client` | `owner` | Кто ведёт клиента |
| `Shop` | `created_by` + `managed_by` | Кто создал + кто ведёт сейчас |
| `ManagementLead` | `added_by` + `moderated_by` + `processed_by` | Тройное отслеживание |
| `Report` | `owner` | Автор отчёта |
| `ManagerCommissionAccrual` | `owner` | Получатель комиссии |
| `ShopShipment` | `created_by` | Кто создал отгрузку |
| `ShopCommunication` | `created_by` | Кто сделал коммуникацию |

**Проблема**: Кодекс говорит "портфель менеджера" и "ownership disputes" но не определяет: ЧТО именно определяет портфель? `Client.owner`? `Shop.managed_by`? Или все три?

**Рекомендация**: Определить `portfolio_scope`:
```python
# Portfolio = all entities WHERE manager is the active responsible party
portfolio = {
    "clients": Client.objects.filter(owner=manager),
    "shops": Shop.objects.filter(managed_by=manager),  # NOT created_by!
    "leads": ManagementLead.objects.filter(processed_by=manager, status='converted'),
}
```

---

### D3. 🟡 Shipment/Revenue tracking already exists (Impact: 6/10)

**Факт**: `ShopShipment.invoice_total_amount` + `ShopInventoryMovement` дают полную картину fulfillment. Кодекс описывает "revenue attribution" как будущую фичу, но данные УЖЕ ЕСТЬ.

**Рекомендация**: Использовать existing shipment data для revenue attribution вместо создания нового слоя.

---

### D4. 🟡 Stale shop = churn signal, но не в MOSAIC (Impact: 6/10)

Stats показывает `stale_shops_count`. Это ПРЯМОЙ retention/churn indicator. MOSAIC Churn Weibull — на уровне individual client, а stale shop — на уровне business relationship.

**Рекомендация**: Add `shop_health_decay` как sub-signal в Portfolio Health:
```python
shop_health = (active_shops - stale_shops) / max(1, total_shops)
```

---

### D5. 🟡 `points_override` — manual override mechanism (Impact: 5/10)

**Факт**: `Client.points_override` (строка 55) позволяет вручную задать баллы. Кодекс не знает об этом.

**Проблема**: При MOSAIC transition, если менеджер или админ использует points_override, это создаст inconsistency между MOSAIC score (рассчитанный автоматически) и overridden points (ручные).

**Рекомендация**: Определить政策: points_override → deprecated при переходе на MOSAIC? Или transform в "MOSAIC manual adjustment"?

---

### D6. 🟡 InvoiceRejectionReasonRequest — dispute workflow (Impact: 5/10)

Существующий workflow для rejection reasons через Telegram. Кодекс описывает "appeal" как новый процесс, но rejection reason request — это уже ФОРМА appeal.

**Рекомендация**: Align appeal system с existing rejection reason mechanism.

---

### D7. 🟡 `ReminderSent` + `ReminderRead` — reminder tracking (Impact: 4/10)

Модели для отслеживания отправленных/прочитанных напоминаний. Кодекс предлагает follow-up reminders но не знает о existing tracking.

---

### D8. 🟡 `LEAD_ADD_POINTS = 2`, `LEAD_BASE_PROCESSING_PENALTY = 2` (Impact: 4/10)

Constants для lead processing points. Кодекс не упоминает lead processing penalties. Это может конфликтовать с новой scoring системой.

---

### D9. 🟡 `TARGET_CLIENTS_DAY = 20`, `TARGET_POINTS_DAY = 100` (Impact: 4/10)

Existing daily targets. Кодекс prescribes `EWR TARGET_WEEKLY_REVENUE = 50_000` but doesn't address daily client/point targets that already drive UI communications.

---

## КАТЕГОРИЯ E: Подготовка к имплементации — контракты code↔codex (8 gaps)

### E1. 🔴 Model Extension Map — какие НОВЫЕ модели, какие РАСШИРЕНИЯ (Impact: 10/10)

Для имплементации КРИТИЧЕСКИ необходима карта:

| Модель | Action | Что менять |
|---|---|---|
| `Client` | **EXTEND** | Добавить: `is_test`→НЕТ (на Shop), `expected_next_order`, `normalized_name_hash` |
| `ManagementStatsConfig` | **EXTEND** | Добавить: `mosaic_weights`, `defaults_version`, `formula_version` |
| `ClientFollowUp` | **EXTEND** | Добавить: ladder_step, auto_escalation_level |
| `Report` | **EXTEND** | Добавить: `details` JSONField для MOSAIC breakdown |
| `ManagerCommissionAccrual` | **KEEP** | frozen_until уже ON — не трогать |
| `ManagerPayoutRequest` | **KEEP** | workflow уже production — не трогать |
| `NightlyScoreSnapshot` | **NEW** | Создать для MOSAIC snapshots |
| `ComponentReadiness` | **NEW** | Feature flags ACTIVE/SHADOW/DORMANT |
| `CallRecord` | **NEW** | Telephony data для QA/supervisor |
| `ScoreAppeal` | **NEW** | Appeal workflow |
| `AuditLog` | **NEW** | Immutable audit trail |
| `CommandRunLog` | **NEW** | Observability для management commands |

---

### E2. 🔴 Service Function Map — какие НОВЫЕ, какие РАСШИРЕНИЯ (Impact: 9/10)

| Функция | Файл | Action |
|---|---|---|
| `compute_kpd()` | stats_service.py:182 | **KEEP** — оставить как legacy; вызывать параллельно с MOSAIC |
| `generate_advice()` | stats_service.py:260 | **EXTEND** — добавить MOSAIC-aware tips |
| `_normalize_source()` | stats_service.py:535 | **KEEP** — достаточна для source categorization |
| `_success_weight_for_call_result()` | stats_service.py:553 | **KEEP** — используется в quality, align с codex |
| `get_stats_payload()` | stats_service.py:564 | **EXTEND** — добавить MOSAIC snapshot в response |
| `normalize_phone()` | models.py:8 | **EXTEND** — если нужна международная поддержка |
| `compute_ewr()` | — | **NEW** |
| `compute_mosaic()` | — | **NEW** |
| `compute_trust_production()` | — | **NEW** |
| `compute_churn_weibull()` | — | **NEW** |
| `find_duplicates_safe()` | — | **NEW** |
| `build_rescue_top5()` | — | **NEW** |
| `compute_score_confidence()` | — | **NEW** |

---

### E3. 🔴 UI Template Map — какие РАСШИРЯТЬ, какие СОЗДАВАТЬ (Impact: 8/10)

Нужно выяснить и задокументировать:
- Существующие templates (stats.html) → plan what to ADD
- Новые components (radar chart, simulator, rescue) → plan where to INSERT
- Mobile responsiveness → current state?

---

### E4. 🔴 Migration Order — STRICT последовательность (Impact: 8/10)

```
Phase 0 (Prep):
  0a. Fix xml_connected: 15→35 or confirm 15 is correct
  0b. Add doc-code parity test
  
Phase 1 (Foundations):
  1a. migration: ManagementStatsConfig → add mosaic_weights, defaults_version
  1b. migration: ComponentReadiness model (NEW)
  1c. migration: NightlyScoreSnapshot model (NEW)
  1d. migration: CommandRunLog model (NEW)
  1e. seed: ComponentReadiness defaults = all DORMANT
  
Phase 2 (Score Engine):
  2a. service: compute_ewr() in new services/score_service.py
  2b. service: compute_mosaic() — SHADOW only
  2c. extend: get_stats_payload() → include shadow_mosaic
  2d. management command: compute_nightly_scores → create snapshots
  
Phase 3 (Transition):
  3a. extend: generate_advice() → MOSAIC-aware tips
  3b. extend: stats.html → show shadow score
  3c. ComponentReadiness: Result → SHADOW
  3d. Monitor KPD vs MOSAIC divergence
  
Phase 4 (Activation):
  4a. ComponentReadiness: axes → ACTIVE
  4b. KPD → secondary display
  4c. Hold-harmless period
```

---

### E5. 🟡 Admin Panel Integration (Impact: 7/10)

`admin.py` needs to be studied. New models need Admin registration. ManagementStatsConfig should get mosaic_weights editing in admin.

---

### E6. 🟡 URL/View Routing (Impact: 6/10)

New API endpoints for MOSAIC data, appeal submission, score explanation. Must integrate with existing URL patterns.

---

### E7. 🟡 Telegram Bot Integration (Impact: 6/10)

New alerts (freeze, anomaly, stale snapshot) should use the existing Telegram admin pattern.

---

### E8. 🟡 Test Infrastructure Bootstrap (Impact: 6/10)

Currently `management/tests.py` exists. Need: test factories for Client, Shop, ManagerCommissionAccrual, etc., using `factory_boy` or similar.

---

## Сводная карта: связь всех трёх отчётов

| Отчёт | Фокус | Findings | Unique Value |
|---|---|---|---|
| `deep_analysis_report` | Формулы, fairness, scores | 30+ оценок | Что УЛУЧШИТЬ в формулах |
| `implementation_readiness_audit` | Infrastructure, contracts, testing | 65 gaps | Что СОЗДАТЬ для безопасной имплементации |
| **Этот отчёт** | **Code ↔ Codex alignment** | **47 gaps** | **Что СУЩЕСТВУЕТ и как НЕ СЛОМАТЬ** |

---

## Итоговая рекомендация

> **Перед началом любого кодирования**: код и кодекс должны быть СИНХРОНИЗИРОВАНЫ. Этот отчёт даёт карту расхождений. Без этой синхронизации имплементация "по кодексу" будет параллельно дублировать и ломать production-функциональность.

### TOP-5 немедленных действий:

1. 🔴 **Исправить xml_connected drift** (15 vs 35) — определить правильное значение
2. 🔴 **Добавить Shop subsystem в кодекс** — 5 моделей невидимы для design document
3. 🔴 **Создать KPD→MOSAIC transition map** — точное соответствие 4 компонентов KPD к 6 осям MOSAIC
4. 🔴 **Model Extension Map** (E1) — какие модели расширять, какие создавать, какие не трогать
5. 🔴 **Service Function Map** (E2) — какие функции расширять, какие создавать, какие не трогать

---

*Отчёт подготовлен: Gemini 2.5 Pro (Antigravity), 2026-03-13*
*Методология: Full code review (management/models.py: 1160 строк, stats_service.py: 1259 строк, constants.py: 24 строки) + all 28 codex files + Sequential Thinking MCP + code↔codex cross-reference analysis*
