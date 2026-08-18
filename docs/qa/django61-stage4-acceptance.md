# Django 6.1: приемка Stage 4

Дата: 2026-08-18. Область: основной storefront, non-DTF. DTF не
проверялся и не изменялся.

## Выпущенный runtime

- Проверенный production SHA CSP hotfix: `f94f324cf34eabd21c48786d4d76cde79e696dc4`.
- `GET https://twocomms.shop/` вернул `200`.
- В live HTML главной: 10 корректных `<script nonce="...">`, 0 слитных
  `<scriptnonce="...">`; заголовок CSP остался `Content-Security-Policy-Report-Only`.

## Browser acceptance

Проверка выполнена через production Chrome с accessibility snapshot и DOM
evaluation, без отправки заказа и без изменения production данных.

| Поверхность | Факт |
| --- | --- |
| Каталог | Реальная ссылка категории `/catalog/tshirts/` открылась; карточки товаров и ссылки PDP присутствуют. |
| Desktop PDP | `/product/futbolka-pravyl-nemaie/`, viewport `1280px`: заголовок и галерея отрисованы, `script[nonce] = 14`, `scriptnonce = 0`, сырого JS в видимом тексте нет, `scrollWidth = clientWidth = 1280`. |
| Desktop cart/checkout | Для размера `M` запрос `POST /cart/add/` вернул `200`, `ok=true`, `count=1`; `GET /cart/mini/` вернул `200` и строку товара; `/cart/` открылся с `200` и ссылкой checkout. Заказ и платёж не отправлялись. |
| Mobile PDP | Тот же PDP при `390x844`: `scrollWidth = clientWidth = 390`, сырого JS в видимом тексте нет. |
| Mobile mini-cart | Кнопка «Відкрити міні-корзину» открывает `mobile-mini-cart` (`aria-hidden=false`); empty state отображается, горизонтального overflow нет. |
| Console | Fatal console/page errors не обнаружены. Остались только информационные сообщения и предупреждение Clarity о настройках проекта. |
| Analytics/network | Meta `fbevents.js`, TikTok pixel/events, Google Tag Manager/gtag и Clarity загружены с `200`; GA collect получил `204`; CSP reports получили `204`. |

Desktop-сценарий `PDP -> add-to-cart -> mini-cart -> cart/checkout page`
подтверждён без создания production order. Mobile-сценарий пока не закрыт:
после прокрутки sticky-кнопка добавления стала видимой, но её нажатие не
отправило запрос `/cart/add/`, а mini-cart остался пустым. Это пользовательский
дефект mobile add-to-cart, поэтому считать mobile checkout проверенным нельзя.

В том же desktop-прогоне `GET /cart/items/` один раз вернул `500` с
`OperationalError(2006)` на read-only `Product.in_bulk()`. Локальный commit
`6fed63c9e269b019a0b919f0351519ec2d25e67f` применяет существующий
однократный MySQL reconnect только к GET/HEAD этого endpoint. Focused gate из
8 cart tests прошёл, но этот commit ещё не интегрирован, не задеплоен и не
подтверждён live-повтором, поэтому production-исправление здесь не заявляется.

Инструмент screenshot в текущем browser profile не вернул файл даже при
абсолютном пути; acceptance основан на сохраненных live URL, snapshot и DOM
метриках выше.

## Stage 4 observability baseline

Read-only команда `measure_stage4_baseline --samples 9` на том же runtime:

- file cache: p50 `0.143 ms`, p95 `0.407 ms`; inventory `3265` файлов/inodes,
  `70,788,611` bytes; TTL `300`, max entries `8000`;
- concurrent `cache.add`: `2/2` winners, контракт `distributed_lock_safe=false`;
- temporary tables delta `1`, disk temporary tables delta `0`;
- aborted clients/connects delta `0/0`;
- file descriptors `5/1024` (`0.488%`);
- cache proof: cold miss -> warm hit, old-key reads `0`;
- PBKDF2 `1,500,000`: encode `536.72 ms`, verify `688.658 ms`, verify=true,
  current rehash=false, legacy rehash=true;
- MariaDB probe read-only, schema `twocomms.django61.stage4.v1`.

Первичный источник baseline: `docs/qa/django61-stage4-observability.md`.
MariaDB warning/constraint contracts: `docs/qa/django61-stage4-base004-db002.md`.
CSRF contract inventory: `docs/qa/django61-stage4-sec-003.md`.

Focused code gate (Django 6.1, без полного suite):

```text
SECRET_KEY=stage4-test-secret DEBUG=True \
  <runtime-python> twocomms/manage.py test \
  storefront.tests.test_django61_csp --settings=twocomms.settings
Ran 3 tests in 0.034s
OK
```

Профиль `test_settings_no_network_non_dtf` намеренно не используется для
этого модуля: он отключает DTF CSP и потому не может доказать сохранение
legacy DTF-заголовка.

## Решение по выходу

Шесть observability/auth пунктов и два независимых exit-gate отмечены в
implementation plan. CSP browser proof закрывает desktop/mobile PDP, загрузку
analytics и desktop cart/checkout-page flow. Общий CSP/checkout gate оставлен
открытым: mobile sticky add-to-cart не отправил запрос, а локальный retry для
найденного `/cart/items/` 500 ещё требует интеграции, deploy и одного live
повтора.
