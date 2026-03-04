# Test and Acceptance Matrix

## 1. Цель
Подтвердить, что спецификация реализована корректно, устойчива к абузу и соответствует бизнес-правилам.

## 2. Test layers
1. Unit tests (формулы, валидаторы, trust/gate logic).
2. Integration tests (API, model interactions, dedupe flow, alerts jobs).
3. E2E tests (manager/admin UI сценарии).
4. Ops tests (scheduler, idempotency, fallback for DTF bridge).

## 3. Score formula tests
1. Gate cap applied при 0 paid conversions.
2. Gate cap stricter при 3+ day streak without conversion.
3. Trust coefficient повышает/снижает итог при одинаковом base.
4. ROI влияет только на admin score в заданной доле.
5. ELO weekly delta корректен для разных K factors.

## 4. Workflow validation tests
1. `not_interested` without reason -> validation error.
2. `not_interested` with `other` without detail -> validation error.
3. `sent_email` without cp link -> validation error.
4. `no_answer` creates follow-up chain up to attempt 3.
5. Duplicate phone/email path returns duplicate context.

## 5. Alerts tests
1. Manager receives post-report summary immediately.
2. Manager receives 10:00 digest only if report exists.
3. Admin always receives 10:00 digest.
4. No-report manager appears in admin digest with risk flag.
5. Duplicate alert prevention works by dedupe key.

## 6. Advice tests
1. Advice includes evidence block.
2. Advice marks inference for probabilistic statements.
3. Dismiss/ack does not remove source metrics.

## 7. DTF bridge tests
1. Read-only overview returns without write permissions.
2. DTF stats do not affect brand score.
3. Bridge fallback works when DTF source unavailable.
4. No cross-DB FK violations.

## 8. Role access tests
1. Manager cannot access admin-only breakdown.
2. Admin sees full incident and ROI layers.
3. DTF tab visibility respects role matrix.

## 9. Acceptance criteria
Система считается принятой, если:
1. Все P0/P1 тесты green.
2. Score outputs объяснимы через breakdown.
3. Anti-abuse сценарии не дают набрать высокий score без конверсии.
4. Alerts не дублируются и соответствуют no-report policy.
5. DTF bridge стабилен в read-only режиме.

## 10. Regression focus
1. Existing KPD/advice UI не ломаются при переходе.
2. Existing follow-up logic не теряет исторические записи.
3. CP email flows остаются совместимыми с новыми требованиями привязки.
