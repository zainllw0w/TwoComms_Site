# DTF Bridge V1 (Read-Only)

## 1. Цель
Дать менеджеру единое рабочее окно без переключения между субдоменами, при этом сохранить архитектурную изоляцию DTF и Brand-статистики.

## 2. Scope v1
Только read-only:
1. DTF overview metrics.
2. Списки DTF leads/orders/samples/builder sessions.
3. Deep links в DTF для детального управления.

Out of scope v1:
1. CRUD DTF сущностей из management.
2. Изменение DTF статусов из management.
3. Смешивание DTF и Brand score.

## 3. Архитектурные ограничения
1. DTF может быть в отдельной БД через router.
2. Cross-DB FK между management и dtf не создаются.
3. Агрегация строится в service layer и при недоступности DTF возвращает degradable response.

## 4. Data contract (read)

### 4.1 Overview
- New leads today.
- Orders active.
- Awaiting payment.
- Paid today.
- Avg response time.

### 4.2 Lists
- Recent leads.
- Recent orders.
- Samples queue.
- Builder submitted queue.

## 5. Access model
- Role `brand_only`: DTF tab hidden.
- Role `brand_dtf`/`all`: DTF tab visible.
- Role `dtf_only`: DTF tab primary, brand cards optional/minimal.

## 6. UI behavior
1. DTF tab содержит badge "read-only v1".
2. Для действий write показывается кнопка "Open in DTF".
3. Ошибка чтения DTF не ломает management dashboard.

## 7. Fallback strategy
Если DTF data source недоступен:
1. Показать last successful snapshot timestamp.
2. Показать ограниченный offline summary.
3. Писать тех-алерт админу.

## 8. Monitoring
1. Bridge request latency p95.
2. Error rate.
3. Snapshot freshness.
4. Permission mismatch incidents.

## 9. Acceptance
1. DTF метрики не попадают в brand score.
2. Нет cross-db relation ошибок.
3. У менеджера доступна единая навигация и deep links.
