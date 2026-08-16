# Stage 1: Django 6.1 MAILERS и полный email call graph

Дата проверки: 2026-08-16.

Область проверки: все production-вызовы Django email API вне DTF. DTF-код,
URL, команды, тесты и данные не затрагивались.

## Итоговый контракт

- `MAILERS` содержит три явных alias: `default`, `transactional`, `reports`.
- Все три alias пока используют одинаковые backend и SMTP options. Это сохраняет
  текущую доставку и одновременно позволяет позже развести credentials, timeout
  или backend без изменения call sites.
- `default` оставлен для неявных framework-путей Django, например встроенных
  email-механизмов authentication. В собственном production-коде неявных
  отправок больше нет.
- Клиентские, checkout, receipt, restock и CRM-письма используют
  `using="transactional"`.
- UTM-отчёт использует `using="reports"`.
- Deprecated kwargs `fail_silently`, `auth_user`, `auth_password` и
  `connection` в найденном call graph отсутствуют.
- Celery, outbox, новые retry-механизмы и изменение синхронности в этот slice не
  входят.

## Call graph и политика ошибок

| Call site | Alias | Существующая exception policy, сохранённая после перехода | Проверка |
|---|---|---|---|
| `management.views.commercial_offer_email` | `transactional` | SMTP exception перехватывается; создаётся `CommercialOfferEmailLog` со статусом `FAILED`; страница получает пользовательскую ошибку; исключение наружу не поднимается. | AST-контракт `EmailCallGraphContractTests`; HTTP-категория проверена SMTP-failure тестом `SendTestTests.test_send_test_reports_smtp_failure_without_creating_log`. |
| `management.views.commercial_offer_email_resend_api` | `transactional` | SMTP exception перехватывается; создаётся новая log-запись `FAILED`; JSON возвращает `sent=false` и текст ошибки; автоматического retry нет. | AST-контракт полного call graph. |
| `management.views.commercial_offer_email_send_api` | `transactional` | SMTP exception перехватывается; создаётся log-запись `FAILED`; JSON возвращает `sent=false`; автоматического retry нет. | AST-контракт полного call graph. |
| `management.views.commercial_offer_email_send_test_api` | `transactional` | SMTP exception превращается в HTTP 500 с `error=send_failed`; тестовая отправка не создаёт log-запись. | `SendTestTests.test_send_test_reports_smtp_failure_without_creating_log`. |
| `orders.email_receipt.send_order_receipt_email` | `transactional` | SMTP exception логируется; в `payment_payload` сохраняются `receipt_email_status=failed` и ошибка; функция возвращает `(False, error)`. Durable claim `sending` продолжает защищать от слепого дубля при неизвестном результате. | `PostPaymentRecoveryTests.test_receipt_smtp_failure_marks_failed_and_uses_transactional_mailer` и существующий marker regression test. |
| `orders.management.commands.recover_checkouts.Command.handle` | `transactional` | Ошибка пишется в `stderr`; `recovery_sent_at` остаётся пустым; команда продолжает остальные записи, поэтому следующий cron может повторить попытку. | `RecoverCheckoutsEmailPolicyTests.test_smtp_failure_is_reported_and_capture_remains_retryable`. |
| `storefront.services.restock._send_email` через `process_restock_notifications` | `transactional` | Ошибка поднимается в существующий delivery pipeline; подписка получает `FAILED`, `last_error`, счётчик попыток и `next_attempt_at` с текущим exponential retry. | `RestockDeliveryTests.test_email_smtp_failure_is_retained_for_cron_retry`. |
| `storefront.management.commands.send_utm_report.Command.handle` | `reports` | Ошибка логируется с traceback и превращается в `CommandError`; команда завершается ненулевым статусом, чтобы cron/оператор видел сбой. | `SendUtmReportEmailPolicyTests.test_smtp_failure_is_logged_and_raised_as_command_error`. |

Итого: восемь собственных non-DTF call sites, семь `transactional` и один
`reports`. Инвентаризация выполняется AST-тестом по production Python-файлам и
падает при появлении новой неописанной точки отправки.

## Конфигурационные проверки

- No-network профиль создаёт `default`, `transactional` и `reports` на locmem
  backend и проходит обычные checks с tag `mail` без отправки сообщений.
- Production-like SMTP contract строится непосредственно из проектного
  `twocomms.settings`: host, port, TLS, SSL и timeout применяются к каждому alias.
- Deployment checks с tag `mail` не содержат `mail.E001` для SMTP-конфигурации.
  Django проверяет этим кодом только `default`, поэтому тест дополнительно
  создаёт backend каждого alias и сверяет его options.
- `.env.example` явно задаёт пару `EMAIL_PORT=587`, `EMAIL_USE_TLS=True` и
  `EMAIL_USE_SSL=False`; одновременное TLS/SSL не подразумевается.

## Источники Django 6.1

- Named mailers и `MAILERS`: <https://docs.djangoproject.com/en/6.1/ref/settings/#mailers>
- Миграция со старых `EMAIL_*`: <https://docs.djangoproject.com/en/6.1/howto/mailers-migration/>
- `using=` и email API: <https://docs.djangoproject.com/en/6.1/topics/email/>

Документация перепроверена через Context7 (`/django/django`) перед реализацией.
