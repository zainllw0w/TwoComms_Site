# DJ6-SEC-002: строгая Base64-валидация

Дата проверки: 2026-08-17. Базовый SHA: `3c8f86ae5`.

## Инвентаризация

| Путь | Данные | Runtime-статус | Решение |
| --- | --- | --- | --- |
| `management/parser_usage.py` | `GOOGLE_SERVICE_ACCOUNT_JSON_B64` | Активный credential path для Google Monitoring | Переведён на строгий decoder. |
| `management/bot_views.py` | Meta `signed_request` signature/payload | Публичный compliance callback | Signature и JSON payload отклоняют whitespace, trailing garbage и невалидную Base64 до HMAC/JSON processing. |
| `management/views.py` | Legacy Telegram manager start wrapper | Активный compatibility path для ранее выданных deep links | Валидные padded/unpadded wrappers сохранены; garbage и surrounding whitespace больше не игнорируются. |
| `storefront/views/monobank.py` | `X-Sign` | Активный retail/dropshipper webhook path | Строгий decode выполняется до запроса публичного ключа. |
| `storefront/views/monobank.py` | Base64 PEM публичного ключа | Активный provider path | Поддержаны Base64 PEM и исходный PEM; мусор отклоняется до PEM parser. |
| `storefront/views/utils.py` | `X-Sign` | Загружаемый, но не имеющий статических callers legacy-дубликат | Hardened тем же контрактом без изменения алгоритма подписи. |
| `storefront/views.py.backup` | `X-Sign` и Base64 PEM | Модуль реально исполняется lazy loader; decoder helpers сейчас вызываются только его неэкспортируемым `monobank_webhook` | Hardened, чтобы загружаемый provider-код не сохранял permissive поведение. |
| `ManagerPersonalData.*_enc` | Fernet bytes в `BinaryField` | Активный PII persistence path | Закреплён Django 6.1 round-trip и native strict `BinaryField.to_python()`; PII exception detail удалён из warning. |

Общий `strict_b64decode()` принимает standard и URL-safe алфавиты, полностью
padded и полностью unpadded формы. Он явно добавляет только отсутствующий
padding и отклоняет частичный padding, длину `mod 4 == 1`, whitespace,
не-ASCII, посторонние символы и данные после `=`. Исключение всегда содержит
только `Invalid Base64 payload`.

Оставшийся `base64.b64decode()` в `management/views.py` декодирует константный
project-owned tracking-pixel literal при импорте модуля. Это не credential,
PII или внешний provider input и поэтому не входит в strict input boundary.

DTF-код, webhook digest/signature formats и бизнес-обработка платежей не
изменялись.

## RED / GREEN

- Baseline до изменений: прежние parser/onboarding/Monobank тесты `40/40`.
- RED: новые контракты завершились `exit 1` на unpadded и URL-safe payloads,
  permissive whitespace/`!!`, provider garbage и PII exception-detail log.
- Дополнительный decoder proof: modular public key, utils signature и loaded
  legacy signature дали ожидаемые `3/3` RED, потому что `b64decode()` принимал
  хвост `!!`.
- Review RED: valid Meta/Telegram payloads прошли, но три malformed
  варианта с trailing garbage ошибочно принимались.
- Дополнительный RED: предварительный `.strip()` скрывал surrounding
  whitespace legacy wrapper от strict decoder (`0/1`).
- GREEN: полные table-driven контракты `21/21`.
- Focused strict Base64 + существующие Meta/manager consumers: `28/28`.

## Release checks

- CPython `3.14.6`, Django `6.1`.
- `manage.py check --database=default --settings=test_settings_no_network_non_dtf`: OK.
- `manage.py makemigrations --check --dry-run --noinput --settings=test_settings_migrations_non_dtf`: `No changes detected`.
- Изменённые Python-модули и реально загружаемый `views.py.backup`: compile OK.
- `git diff --check`: OK.

В совмещённом тестовом выводе остаются прежние ожидаемые сообщения тестов,
которые намеренно имитируют `order.save()` failure, и предупреждение об
отсутствующем worktree `staticfiles/`; новых warnings от Base64-контракта нет.
