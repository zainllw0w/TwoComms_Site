# ADR 0002 — File Storage & Validation

## Status
Accepted

## Context
DTF-заказы требуют загрузки PDF/PNG (ганг-лист) или нескольких файлов для помощи. Нужно безопасное хранение и базовая проверка типов/размера.

## Decision
- Использовать FileField/ImageField с upload_to `dtf/orders/` и `dtf/leads/`.
- Валидация типов в формах (PDF/PNG для готового, иные — предупреждение/перевод в help).
- Ограничить размер файла на уровне формы.

## Consequences
- Безопасное хранение в MEDIA_ROOT.
- Нет сложной конвертации форматов в MVP.
