# Anti-Duplication and Follow-Up Engine

## 1. Цель

У текущего проекта уже есть:
- нормализация телефонов,
- `phone_normalized`,
- `ClientFollowUp`,
- `ReminderSent`,
- `ManagementLead`,
- `ShopPhone`,
- `CommercialOfferEmailLog`.

Но нет единого `identity engine`, который предотвращает:
- создание дублей,
- cross-manager collisions,
- повторную продажу одного и того же клиента как нового,
- искусственное раздувание score,
- пропажу клиента между `Lead`, `Client`, `Shop`, `TelephonyCall`.

## 2. Финальная модель дублей

### 2.1 Уровни совпадения

#### Exact duplicate
Совпадают:
- `phone_normalized`,
- или email,
- или provider telephony external mapping,
- или `google_place_id`.

#### Likely duplicate
Совпадает комбинация:
- имя магазина,
- город,
- часть телефона,
- сайт/instagram,
- owner/contact name,
- телеметрия звонков.

#### Conflict duplicate
Есть спор:
- один номер, разные магазины,
- один магазин, разные номера,
- один клиент уже закреплён, но есть новые факты,
- ownership спорный.

## 3. Identity graph

Нужно добавить отдельный слой, а не надеяться только на `Client.phone_normalized`.

### 3.1 Новые сущности
- `ClientIdentityKey`
- `ClientInteractionAttempt`
- `DuplicateReview`
- `OwnershipTransferLog`
- `FollowUpEscalationLog`

### 3.2 ClientIdentityKey
Содержит тип и значение ключа:
- phone,
- email,
- shop_name_normalized,
- google_place_id,
- messenger_handle,
- telephony_external_party_id.

Это позволит:
- привязать телефонию,
- связать Shop и Client,
- находить исторические дубли,
- строить audit trail при смене владельца.

## 4. Create-or-append flow

При создании клиента система обязана:
1. Проверить `exact`.
2. Проверить `likely`.
3. Показать менеджеру модалку.
4. Дать три действия:
- `open existing`,
- `append interaction`,
- `create branch record with reason`.

`create anyway` разрешается только если:
- есть причина,
- лог пишется,
- score credit ограничен,
- duplicate review попадает админу.

## 5. Scoring rules for duplicates

- exact duplicate не может давать full credit как новый cold contact,
- appended interaction может давать только process/follow-up credit,
- override duplicate добавляет anomaly signal,
- repeated override снижает trust.

## 6. Follow-up ladder

Это финальная замена шумным blind scans.

### 6.1 Лестница для клиента
1. `scheduled`
2. `T-15m reminder`
3. `due`
4. `overdue + 2h`
5. `end-of-day breach`
6. `day-2 escalation`
7. `day-3 admin review`

### 6.2 Лестница для магазина
1. `healthy cadence`
2. `watch`
3. `risk`
4. `rescue`
5. `reassign eligible`

### 6.3 Правило тестового магазина
Для тестовой ростовки cadence плотнее:
- early reminder,
- end-of-test decision,
- follow-up plan required.

## 7. Reminder design

### 7.1 Каналы
- in-app,
- Telegram,
- admin digest,
- QA queue if telephony enabled.

### 7.2 Dedupe key
Используем ключ в стиле Codex:
`{channel}:{target}:{event_type}:{time_bucket}`

### 7.3 Низкошумный принцип
Не слать 20 похожих пушей подряд.

Система должна:
- объединять похожие просрочки,
- показывать top priority first,
- выносить summary админу,
- сохранять action buttons рядом с напоминанием.

## 8. Техническая реализация на Django

### 8.1 Что стоит сделать на уровне БД
На базе официальных возможностей Django:
- `UniqueConstraint` для точных identity keys,
- условные constraints для активных записей,
- отдельные индексы под phone/date/status lookups,
- `JSONField` для breakdown и snapshot метаданных,
- лог manual override с actor/reason/timestamp.

Это соответствует официальной модели Django constraints и partial uniqueness.

### 8.2 Celery правила
Для reminder jobs:
- один активный beat scheduler,
- overlap-sensitive jobs под lock,
- job обязана быть idempotent,
- повторный запуск не должен дублировать уведомления.

## 9. Что получает админ

Админ получает три очереди:
- `duplicate review queue`,
- `ownership review queue`,
- `callback breach queue`.

Это намного сильнее, чем просто “увидеть статистику дублей”.

## 10. Что получает менеджер

Менеджер получает:
- безопасное предупреждение о дубле до сохранения,
- быстрый выбор следующего действия,
- понятный follow-up timer,
- работу без страха, что система случайно спишет клиента или создаст хаос.
