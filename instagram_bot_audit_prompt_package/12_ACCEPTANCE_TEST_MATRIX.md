# Минимальная матрица приёмочных тестов

| ID | Сценарий | Ключевой результат |
|---|---|---|
| T01 | Новый Instagram-вопрос | Один корректный ответ |
| T02 | UA/RU/EN и смена языка | Язык и контекст сохраняются |
| T03 | Ответ на рекламу | Ad context сохранён |
| T04 | Выбор/смена товара и размера | Entities/state корректны |
| T05 | Генерация и expiry payment link | Ссылка безопасна, статус точен |
| T06 | Успешная оплата | Один заказ и один ответ |
| T07 | Duplicate payment webhook | Нет дубля заказа/сообщения |
| T08 | Pixel+CAPI | Один event_id и дедупликация |
| T09 | Неуспешная оплата | Состояние не paid |
| T10 | Manager takeover | Бот молчит |
| T11 | Bot pause | Бот молчит |
| T12 | Follow-up payment link | Один раз в допустимое время |
| T13 | Ответ до timer | Timer отменён/пересчитан |
| T14 | Отказ | Sales follow-up прекращён |
| T15 | «Подумаю» | Корректный delayed follow-up |
| T16 | «Дорого» | Сначала отработка, не скидка |
| T17 | Sales discount 10% | Только по eligibility |
| T18 | ТТН создана | Локализованное сообщение |
| T19 | Duplicate Nova Poshta event | Нет дубля |
| T20 | Заказ получен | UGC flow один раз |
| T21 | Promo за отметку | Не повторяется |
| T22 | Exchange | Purchase сохраняется |
| T23 | Full refund | Отдельный service lifecycle |
| T24 | Complaint | Suppression + escalation |
| T25 | Repeat order | Новый order context |
| T26 | Personal owner message | Не запускает sales funnel |
| T27 | Collaboration | Правильная классификация |
| T28 | Reaction only | Не выдумывает intent |
| T29 | Provider rate limit | Безопасный key fallback |
| T30 | Все ключи недоступны | Degradation/manager escalation |
| T31 | Worker restart | Jobs/state не теряются |
| T32 | UI order dropdown | Выбор существующего заказа |
| T33 | UI funnel branches | Exchange/refund/repeat видны |
| T34 | UI follow-up timer | Время и причина понятны |
| T35 | Date filters | Точные границы timezone |
| T36 | Dashboard reconciliation | Совпадает с raw events |
| T37 | Out-of-order webhook | State не откатывается неверно |
| T38 | Multiple open orders | Контексты не смешиваются |
| T39 | Forwarded payment link | Заказ связан правильно |
| T40 | Rollback drill | Предыдущая версия восстановлена |

Для каждого сценария определить unit/integration/contract/E2E/manual покрытие, fixtures, preconditions, expected events и evidence.
