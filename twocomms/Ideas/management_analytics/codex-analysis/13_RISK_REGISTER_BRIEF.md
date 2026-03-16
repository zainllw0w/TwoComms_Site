# Risk Register Brief

## 1. Product risks
1. Score complexity может быть непонятной без explainability.
2. Слишком жесткие penalties могут демотивировать новых менеджеров.

## 2. Data integrity risks
1. Self-reported actions remain partially unverifiable.
2. Duplicate records могут искажать conversion и trust.

## 3. Operational risks
1. Missed scheduler jobs -> delay alerts.
2. Duplicate scheduler instances -> double notifications.

## 4. Architecture risks
1. DTF source недоступен -> bridge data gaps.
2. Multi-DB inconsistencies при ошибочной попытке cross-relations.

## 5. Abuse risks
1. Mass closure with low-quality reasons.
2. Fake messenger outreach.
3. Callback bypass behavior.

## 6. Mitigations summary
1. Hard gate + trust coefficient.
2. Mandatory validations and dedupe checks.
3. Single beat + lock + dedupe alert keys.
4. Admin-verified incident workflow.
5. DTF read-only v1 with fallback snapshot.
