# ADR 0001 — Subdomain Routing for DTF

## Status
Accepted

## Context
Проект уже использует субдомен `management.twocomms.shop` через middleware `SubdomainURLRoutingMiddleware` и отдельный `urls_management.py`.

## Decision
Добавить поддержку `dtf.twocomms.shop` в том же middleware, использовать отдельный `urls_dtf.py` и отдельное Django приложение `dtf`.

## Consequences
- Изоляция маршрутов DTF от основного сайта.
- Минимальные изменения существующей архитектуры.
- Нужно расширить ALLOWED_HOSTS и CSRF_TRUSTED_ORIGINS.
