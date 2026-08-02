# Архитектура, код, API-ключи и технический долг

## Причинно-следственная модель

Восстанови: кто принимает Instagram webhook; как определяется user/conversation; где ownership `bot/manager/paused`; как строится AI context; кто выбирает API-ключ; кто сохраняет/отправляет ответ; какие события меняют funnel; как заказ связывается с Instagram; откуда payment/Nova Poshta events; как строится статистика; как UI интерпретирует данные.

## Карточка компонента

| Поле | Содержание |
|---|---|
| Component ID | стабильный ID |
| Назначение | бизнес-функция |
| Entry points | routes/handlers/jobs |
| Inputs/outputs | данные и события |
| State owner | БД/кэш/файл/внешняя система |
| Dependencies | внутренние/внешние |
| Failure modes | типовые отказы |
| Observability | logs/metrics/traces |
| Tests | существующие/отсутствующие |
| Findings | связанные IDs |

## Хардкод

Ищи числа и названия ключей, таймеры, тексты, language mappings, funnel/status IDs, Meta/Nova Poshta events, labels, URL, discount, manager IDs, retries, timezone, score thresholds, ad IDs и CSS magic numbers. Для каждого реши: константа, конфигурация, feature flag, DB rule, template или допустимый literal.

## Шесть ключей и резерв

Восстанови state machine ключа: `key_id`, provider/model, status, in-flight, quota, last success/failure, cooldown, failure category, cost, priority и health. Проверь atomic lease, освобождение при exception, backoff+jitter, circuit breaker, retry budget, отсутствие двойного ответа, восстановление после restart, fairness, cost monitoring, manual disable и безопасную manager fallback.

## Технический долг

Ищи код, который запускается без потребителя результата; считает бессмысленные события; polling вместо events; создаёт неиспользуемые файлы; дублирует state; хранит derived state без reconciliation; делает дорогой AI-анализ на простое событие; продолжает работу после manager takeover; не отменяет timers; скрывает ошибки fallback-ответом.

Для каждого debt: симптом, первопричина, ущерб, риск изменения, рекомендация и тест.
