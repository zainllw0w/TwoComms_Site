# Django 6.1 MariaDB warning constraints design

Дата: 2026-08-19. Scope: только non-DTF модели и disposable MariaDB 11.4.12.

## Цель

Убрать четыре ожидаемых database-check warning не через silence/allowlist, а
через реально работающие ограничения MariaDB, сохранив текущие публичные и
внутренние write-path.

## Выбранный контракт

- `ReviewVote`: обычный unique key `(review_id, user_id)` защищает
  зарегистрированных пользователей. MariaDB разрешает несколько `NULL`,
  поэтому гостевые строки не конфликтуют с ним. Для гостей stored generated
  column возвращает `anon_key` только при `user_id IS NULL`; unique key
  `(review_id, generated_anon_key)` обеспечивает прежнюю conditional семантику.
- `ProductFitOption`: stored generated column возвращает `product_id` только
  при `is_default = TRUE`; unique key на колонке допускает любое количество
  non-default строк и не более одной default строки на товар.
- `WebPushDeviceSubscription`: Django state меняется на
  `URLField(max_length=768, unique=False)`, но migration не выполняет DDL над
  endpoint. Уже существующий production `varchar(1000)` и физический
  `UNIQUE endpoint USING HASH` сохраняются через `SeparateDatabaseAndState`.
  State-only `UniqueConstraint(endpoint)` сохраняет `Model.full_clean()`
  semantics, не возвращая field-level `mysql.W003`.
  Gate принимает физическую длину не меньше 768, требует HASH-уникальность и
  запрещает новую digest-колонку.
- Перед созданием каждого нового unique key migration выполняет fail-closed
  duplicate scan. Найденные дубли не исправляются автоматически.
- Compatibility gate перестаёт разрешать четыре warning и проверяет три
  production-like MyISAM таблицы, две generated columns, три новых unique
  indexes и сохранённый endpoint HASH index через `information_schema` и
  `SHOW CREATE TABLE`.

## Почему не альтернативы

- Silence/продление allowlist оставляет гонки и только скрывает предупреждения.
- Сокращение push endpoint до 255 символов может отвергать валидные provider
  URLs. Digest создавал бы второй источник истины и ненужный production DDL,
  тогда как существующий MyISAM HASH index уже обеспечивает уникальность.
- Application-only `save()`/`get_or_create()` проверки не защищают concurrent
  writers и bulk/SQL paths.

## Доказательство совместимости

Одноразовая MariaDB `11.4.12` с MyISAM приняла обе stored generated columns и
три новых unique-key сценария. Допустимые NULL/default строки были сохранены;
повторный registered vote, anonymous vote и default fit были отклонены новыми
indexes, а повторный endpoint - сохранённым HASH index. Все три таблицы
остались MyISAM. Production и DTF не использовались.
