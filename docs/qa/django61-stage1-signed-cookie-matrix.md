# Stage 1: Django 6.1 signed-cookie compatibility matrix

Дата проверки: 2026-08-17.

Область: общие session/messages cookies и все project-owned custom signing
paths вне DTF. DTF-код, URL, данные и production не изменялись.

## Решение

- Project setting `SIGNED_COOKIE_LEGACY_SALT_FALLBACK` намеренно
  отсутствует; runtime использует Django 6.1 default `False`.
- Global legacy fallback не включается: в текущем non-DTF коде нет вызовов
  `HttpResponse.set_signed_cookie()` или `HttpRequest.get_signed_cookie()`.
- Salt, payload format, serializer, compression и max age существующих токенов
  не менялись.

## Executable matrix

| Путь | Django 6.1 salt change | Доказанное поведение |
|---|---|---|
| `set_signed_cookie()` / `get_signed_cookie()` | Affected | Новый v2 cookie принимается; cookie с legacy salt `cookie_name + salt` отклоняется при fallback `False`. В project-owned non-DTF коде call sites отсутствуют. |
| Session `cached_db` | Unaffected | Browser cookie содержит opaque server-side session key. Тест удаляет cache entry и восстанавливает cart из DB при запрещенном `_unsign_cookie()`. |
| Messages `FallbackStorage` -> `CookieStorage` | Unaffected | Message cookie использует прямой `get_cookie_signer(salt="django.contrib.messages")`, а не HTTP-cookie derivation. Реальный encode/decode проходит при запрещенном `_unsign_cookie()`. |
| Custom signing formats | Unaffected | Все используют `signing.dumps()` / `loads()`, `Signer` или `TimestampSigner` с собственным salt. Девять форматов проходят roundtrip при запрещенном `_unsign_cookie()`. |

## Project-owned custom formats

| Формат | Salt | API и расположение |
|---|---|---|
| OAuth state fallback cookie | `twocomms.social-auth-state.v1` | `signing.dumps/loads`; `twocomms/twocomms/middleware.py` |
| Commercial-offer click | `cp.click` | `signing.dumps/loads`; `twocomms/management/views.py`, `twocomms/management/email_templates/twocomms_cp.py` |
| Legacy management bot bind | `management.bot.bind` | `Signer`; `twocomms/management/views.py` |
| Manual Instagram order context | `storefront.manual-order.ig-client` | `signing.dumps/loads`; `twocomms/management/bot_views.py`, `twocomms/storefront/views/manual_orders.py` |
| Instagram checkout grant | `twocomms.instagram-checkout.grant.v1` | `signing.dumps/loads`; `twocomms/storefront/views/ig_checkout.py` |
| QR promo cookie payload | `twc.qr.promo` | `signing.dumps/loads`; `twocomms/storefront/views/qr.py` |
| Nova Poshta city choice | `orders.nova_poshta.city_choice` | `signing.dumps/loads`; `twocomms/orders/nova_poshta_checkout.py` |
| Nova Poshta warehouse choice | `orders.nova_poshta.warehouse_choice` | `signing.dumps/loads`; `twocomms/orders/nova_poshta_checkout.py` |
| Telegram order action | `orders.telegram-action-link` | `TimestampSigner`; `twocomms/orders/telegram_status_links.py` |

AST inventory фиксирует все 20 constructor/load/dump call sites и падает при
добавлении нового формата или переходе project code на HTTP signed-cookie API
без обновления matrix.

## RED/GREEN

- RED: `5/6` matrix tests прошли; contract упал, потому что
  `SIGNED_COOKIE_LEGACY_SALT_FALLBACK` был явно объявлен в project settings.
- GREEN после удаления project override: setting отсутствует в
  `twocomms.settings`, Django runtime default равен `False`, `6/6` tests passed.

Focused test:

```bash
"$TWC_PYTHON" manage.py test \
  storefront.tests.test_django61_signed_cookie_contract \
  --settings=test_settings_no_network_non_dtf --verbosity=2
```

Финальный локальный acceptance:

- `23/23` focused matrix и существующих consumer tests прошли;
- `manage.py check --database=default` не нашел проблем;
- non-DTF `makemigrations --check --dry-run` вернул `No changes detected`;
- compile и `git diff --check` прошли.

Источники: Django 6.1 release notes, `django.core.signing._unsign_cookie()`,
`django.contrib.messages.storage.cookie.CookieStorage` и
`django.contrib.sessions.backends.cached_db.SessionStore` установленного
Django 6.1; документация дополнительно сверена через Context7 `/django/django`.
