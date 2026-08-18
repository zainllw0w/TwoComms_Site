# Django 6.1 Stage 7: querystring pagination

Дата: 2026-08-18
Scope: `DJ6-TPL-002`
Release candidate: `76f878cbb`

В `warehouse/history.html` ручная сборка ссылок пагинации заменена на
Django 6.1 `{% querystring page=... %}`. Поэтому сохраняются повторяющиеся
параметры фильтра, текущий query string не дублирует `page`, а значения
кодируются стандартным template tag.

Проверено тестами `warehouse.tests.test_django61_querystring_pagination` и
`warehouse.tests.test_django61_pagination_ordering`: `5/5 OK`. Покрыты пустой
query, повторяющиеся параметры, замена page и HTML/URL escaping.

DTF, production settings, migrations и database schema не менялись.
