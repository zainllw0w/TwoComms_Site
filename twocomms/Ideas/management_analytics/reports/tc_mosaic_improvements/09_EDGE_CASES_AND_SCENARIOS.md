# 09. Edge-cases и сценарное моделирование

## Как читать этот файл
Для каждого сценария я показываю:
- как текущий пакет уже пытается его закрыть;
- где остаётся риск ложной интерпретации;
- какое безопасное улучшение я предлагаю.

---

## Сценарий 1. У менеджера обычные выходные суббота/воскресенье
**Current package:** выходные не должны ломать DMT и daily punitive checks.

**Остаточный риск:** weekly KPI и rolling windows могут неявно реагировать на календарные паузы.

**Улучшение:** rolling signals считать по working observations; weekly targets считать по working-factor.

---

## Сценарий 2. Менеджер ушёл в отпуск на неделю
**Current package:** `VACATION` / `EXCUSED` day-status защищает daily judgement.

**Остаточный риск:** weekly target и repeat soft-floor без proration всё ещё могут оказаться unfair.

**Улучшение:** prorated weekly KPI + reintegration buffer после возвращения.

---

## Сценарий 3. Менеджер заболел в середине недели
**Current package:** `SICK` neutralizes punitive day checks.

**Остаточный риск:** неполная неделя выглядит как weak pace week.

**Улучшение:** capacity-aware proration and week-level normalization.

---

## Сценарий 4. Полдня ушло на внутреннее обучение / созвон / работу с документами
**Current package:** explicit partial-capacity semantics нет.

**Риск:** система либо штрафует как полный день, либо менеджеры/админы прячут это в `EXCUSED`.

**Улучшение:** `capacity_factor` + optional day subtype `TRAINING / INTERNAL / FIELD`.

---

## Сценарий 5. Новый менеджер на 10-й день работы
**Current package:** onboarding floor full protection active.

**Остаточный риск:** UI может не объяснить, что score partially protected.

**Улучшение:** показывать protected score explicitly + decay timeline.

---

## Сценарий 6. Новый менеджер на 20-й день
**Current package:** onboarding floor должен уже затухать.

**Остаточный риск:** разработчик может ошибиться в decay semantics.

**Улучшение:** snapshot stores onboarding phase and remaining protection.

---

## Сценарий 7. Один менеджер фактически ведёт почти весь портфель
**Current package:** single-manager mode suppresses comparative authority.

**Остаточный риск:** SourceFairness or peer benchmark могут всё равно неявно выглядеть comparative.

**Улучшение:** no manager-facing peer compare below safer threshold; source fairness stays bounded and low-sample neutral.

---

## Сценарий 8. Телефония временно падает на 6 часов
**Current package:** telephony before maturity cannot punish; tech failure exists as status.

**Остаточный риск:** после rollout provider outage может выглядеть как missed meaningful calls.

**Улучшение:** `TelephonyHealthSnapshot` -> outage flag -> disable telephony-based punitive logic for window.

---

## Сценарий 9. Пакет импортирует пачку старых лидов с просроченными due dates
**Current package:** overload logic already exists.

**Остаточный риск:** imported historical due items instantly become personal missed backlog.

**Улучшение:** import burst grace window + separate `imported backlog` label.

---

## Сценарий 10. Один телефон общий для нескольких точек/филиалов
**Current package:** exact phone currently tends toward auto-block.

**Остаточный риск:** false positive dedupe on shared switchboard.

**Улучшение:** shared-phone registry and review-first override for flagged numbers.

---

## Сценарий 11. Клиент давно не заказывал, но у него запланирован seasonal gap
**Current package:** `expected_next_order` and planned gap already reduce churn.

**Остаточный риск:** field may be too implicit and under-explained.

**Улучшение:** explicit planned-gap reason, until-date, approver, confidence.

---

## Сценарий 12. Клиент только что вошёл в rescue top-5, но manager already overloaded
**Current package:** `max 3/day` and DQ grace already exist.

**Остаточный риск:** top-5 still may feel like extra punishment queue.

**Улучшение:** action stack split into `must do today` and `best opportunities`; rescue actionability tie-breaker.

---

## Сценарий 13. Менеджер активно логирует сотни касаний в конце дня
**Current package:** DQ red flags mention batch logging, anti-abuse is review-first.

**Остаточный риск:** share-based heuristic alone may false-flag honest backlog days.

**Улучшение:** require repeated pattern + low meaningful progress + minimum volume before escalation.

---

## Сценарий 14. Один и тот же reason массово повторяется по честно плохой базе
**Current package:** report integrity / reason quality exist.

**Остаточный риск:** crude same_reason_share over-penalizes homogeneous segments.

**Улучшение:** entropy + concentration pair instead of single top-share threshold.

---

## Сценарий 15. Менеджер на долгом пустом grind-е без verified progress
**Current package:** EWR still gives effort credit; trust/dampener/process/follow-up should compensate.

**Остаточный риск:** Result can remain too neutral for too long.

**Улучшение:** test EWR-v2 in shadow where effort term softly depends on rolling verified progress ratio.

---

## Сценарий 16. Один счастливый order резко улучшает картину на маленьком sample
**Current package:** `Wilson` is back as admin-only conservative diagnostic.

**Остаточный риск:** manager/admin may still visually over-trust lucky period.

**Улучшение:** score confidence + Wilson + sample sufficiency badges on admin surfaces.

---

## Сценарий 17. Менеджер спорит по payout item и freeze status неясен
**Current package:** appeals and freeze/review surfaces exist.

**Остаточный риск:** without SLA and explicit freeze reason UI, dispute becomes anxious chaos.

**Улучшение:** payout dispute SLA, freeze reason line, evidence-first appeal drawer.

---

## Сценарий 18. После обновления формулы старые и новые snapshots сравниваются как будто это одно и то же
**Current package:** formula governance exists, but no fully explicit snapshot version contract.

**Остаточный риск:** historical comparisons become semantically dirty.

**Улучшение:** `formula_version`, `defaults_version`, `snapshot_schema_version` in every snapshot.

---

## Сценарий 19. Команда однажды не запустилась ночью, но менеджер утром видит цифры как будто всё ок
**Current package:** cron health is conceptually required.

**Остаточный риск:** no visible stale data policy -> false certainty.

**Улучшение:** stale banner + admin health widget + snapshot freshness field.

---

## Сценарий 20. QA rubric меняется спустя месяц и historical comparisons ломаются
**Current package:** QA reliability thresholds already exist.

**Остаточный риск:** no rubric versioning.

**Улучшение:** store rubric_version and calibration_cycle_id in every review.

---

## Сценарий 21. Manager sees peer benchmark in a 3-person team
**Current package:** comparative overlay hidden at `N < 3`.

**Остаточный риск:** 3-4 person benchmark is still de facto guessable.

**Улучшение:** manager-facing peer benchmark only from safer threshold (e.g. `N >= 5`) or banded representation.

---

## Сценарий 22. Force majeure day overlaps with already verified payouts
**Current package:** verified payouts are not destroyed by force majeure.

**Остаточный риск:** admin/operator may still over-freeze unrelated items.

**Улучшение:** event scope field: score-only / DMT-only / payout-automation-freeze / full-day protection.

---

## Сценарий 23. Менеджер вернулся после долгого отпуска и в первый день выглядит провалившимся
**Current package:** onboarding doesn’t cover this, leave statuses cover only absence.

**Остаточный риск:** no reintegration mode.

**Улучшение:** 2+3 day reintegration capacity curve.

---

## Сценарий 24. Руководитель пытается использовать admin-only analytics как прямой payroll verdict
**Current package:** package warns against this.

**Остаточный риск:** confidence label without routing semantics is still weak protection.

**Улучшение:** LOW = observe only, MEDIUM = coaching, HIGH = escalation-eligible.

---

## Сценарий 25. DTF bridge accidentally pollutes wholesale truth
**Current package:** non-mixing principle already exists.

**Остаточный риск:** UI convenience can gradually erode boundary.

**Улучшение:** separate nav/tab, separate adapter, explicit “not part of wholesale score/payroll”.

## Общий вывод по edge-cases
Пакет уже закрыл большинство “больших” рисков.
Остаточные проблемы почти все выглядят как **precision / semantics / operationalization risks**, а не как architectural failures.

Это хорошая новость: систему надо не ломать и строить заново, а аккуратно довести до состояния, где:
- данные интерпретируются в контексте доступности и confidence;
- edge-case не превращается в ложную punitive logic;
- admin видит не только цифру, но и пригодность этой цифры для решения.
