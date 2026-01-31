# ADR 0003 — Telegram Notifications

## Status
Accepted

## Context
Проект уже использует Telegram бот для уведомлений (orders.telegram_notifications).

## Decision
Использовать существующий TelegramNotifier для DTF событий, с отдельными шаблонами сообщений и логированием ошибок.

## Consequences
- Быстрое внедрение без новой интеграции.
- Зависимость от существующих TELEGRAM_* env vars.
