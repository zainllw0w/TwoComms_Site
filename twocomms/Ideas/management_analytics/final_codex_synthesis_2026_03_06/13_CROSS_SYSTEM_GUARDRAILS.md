# Cross-System Guardrails

## 1. Зачем этот файл

После Opus-аудита стало ясно, что архитектура нуждается не только в формулах и UI, но и в едином наборе cross-cutting guardrails.

Этот файл собирает:
- audit,
- notification preferences,
- security,
- backup,
- performance,
- i18n readiness.

## 2. Central Audit Log

Все чувствительные действия должны попадать в единый audit log:
- duplicate merge,
- ownership transfer,
- score override,
- payroll decision,
- QA decision,
- commission dispute outcome,
- config preset change.

Audit event обязан содержать:
- actor,
- action,
- target,
- old value,
- new value,
- reason,
- timestamp,
- session or request identifier.

## 3. Notification preferences

Нужен отдельный user-level preference layer:
- in-app on/off,
- Telegram on/off,
- quiet hours,
- digest mode,
- language,
- escalation opt-in/opt-out where safe.

Иначе хорошая reminder architecture быстро превращается в раздражающий фон.

## 4. Security rules

Обязательные guardrails:
- authenticated API only,
- rate limiting on sensitive endpoints,
- webhook signature verification,
- validated serializers/validators,
- safe file import policy,
- audit log for admin actions,
- least privilege between manager/admin/QA roles.

## 5. Backup and disaster recovery

Нужны:
- daily DB backup,
- tested restore path,
- broker/cache recovery plan,
- pre-migration backup checkpoint,
- recovery runbook.

Без этого any large identity or payroll migration опасна.

## 6. Performance budgets

Before rollout, fix budgets:
- p95 API latency target,
- import preview runtime target,
- reminder job runtime target,
- score finalization runtime target,
- query count budget for manager home and admin center.

Особенно критично для:
- dedupe previews,
- action stack sorting,
- admin dashboards,
- telephony history queries.

## 7. i18n readiness

Нужна готовность минимум к:
- Ukrainian primary,
- Russian transitional fallback if needed by business,
- future English-safe code structure.

Принцип:
- no business-critical copy hard-coded inside logic,
- explainability and coaching text should be translatable.

## 8. What this file protects against

- “мы забыли залогировать merge”,
- “push-уведомления сыпятся ночью”,
- “все медленно после нового dedupe”,
- “после миграции нечего откатить”,
- “QA спор невозможно восстановить по истории”.
