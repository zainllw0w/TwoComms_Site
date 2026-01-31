# ADR 0004 — i18n Strategy (UA/RU)

## Status
Accepted

## Context
Нужны UA/RU версии интерфейса DTF. В проекте уже используется Django i18n в моделях.

## Decision
- Включить Django i18n для DTF страниц через `{% trans %}`.
- UA как default, RU — через `locale/ru`.
- Переключение языка по query param/cookie.

## Consequences
- Требуется поддержка перевода `.po/.mo`.
- Не влияет на основную функциональность сайта при отсутствии перевода.
