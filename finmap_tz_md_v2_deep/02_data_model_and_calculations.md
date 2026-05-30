# 02. Модель данных и финансовая логика

Этот файл — основа проекта. Все разделы должны работать на единой модели данных. Нельзя делать отдельные “таблички” для платежей, календаря и отчетов, которые не связаны между собой.

## 1. Основные сущности

### 1.1 Company
Поля: `id`, `name`, `logo_url`, `base_currency`, `created_at`, `updated_at`, `is_demo`, `settings`.

Настройки: формат дат, часовой пояс, основная валюта, правила округления, ПДВ/НДС, список валют, плановые платежи, интеграции, права пользователей.

### 1.2 User
Поля: `id`, `email`, `name`, `avatar_url`, `role`, `position`, `company_id`, `permissions`, `status`, `last_login_at`.

Роли: `owner`, `admin`, `finance_manager`, `accountant`, `viewer`, `custom`.

### 1.3 Account
Поля: `id`, `company_id`, `name`, `type`, `currency`, `initial_balance`, `current_balance`, `is_active`, `is_archived`, `integration_id`, `sort_order`.

Типы: bank, cash, card, wallet, marketplace, warehouse, employee_money, other.

### 1.4 CurrencyRate
Поля: `currency_from`, `currency_to`, `rate`, `date`, `source`. Используется для общего остатка, переводов между валютами и отчетов.

### 1.5 Transaction
Единая сущность операции.

Типы:
- `income`;
- `expense`;
- `transfer`.

Поля: `id`, `company_id`, `type`, `status`, `amount`, `currency`, `amount_base`, `account_id`, `to_account_id`, `date_actual`, `date_agreement`, `category_id`, `counterparty_id`, `project_id`, `comment`, `created_by`, `source`, `external_id`, `is_recurring`, `recurrence_rule_id`, `parent_transaction_id`, `is_split`, `split_group_id`, `attachment_ids`.

Статусы:
- `actual` — влияет на фактический баланс;
- `planned` — участвует в прогнозе, но не влияет на фактический баланс;
- `draft` — черновик;
- `cancelled` — отменено.

### 1.6 Category
Поля: `id`, `company_id`, `name`, `type`, `parent_id`, `sort_order`, `is_system`, `is_active`.

Категории бывают income/expense/both и могут быть вложенными.

### 1.7 Counterparty
Поля: `id`, `company_id`, `name`, `type`, `group`, `edrpou`, `iban`, `country`, `address`, `contacts`.

Используется в платежах, дебиторке, кредиторке, инвойсах, фильтрах и автоправилах.

### 1.8 Project
Поля: `id`, `company_id`, `name`, `status`, `sort_order`.

Примеры: `PromUA`, `Інстаграм сторінка`, `Розетка`, `Наш онлайн-магазин`, `Без проекта`.

### 1.9 Tag
Поля: `id`, `company_id`, `name`, `color_optional`. Один платеж может иметь несколько тегов.

### 1.10 Invoice
Поля: `id`, `company_id`, `number`, `status`, `currency`, `issue_date`, `due_date`, реквизиты поставщика и плательщика, `subtotal`, `tax_amount`, `discount_amount`, `delivery_amount`, `total_amount`, `notes`, `linked_counterparty_id`, `linked_project_id`.

Позиции: `invoice_items` с названием, количеством, ценой, суммой, ПДВ/НДС.

### 1.11 IntegrationConnection
Поля: `provider`, `status`, `provider_account_id`, `account_id`, `credentials_ref`, `sync_from`, `last_sync_at`, `error_message`.

Провайдеры: PrivatBank Business, monobank, NovaPay, TOB monobank, ПУМБ, Credit Dnipro, Укргазбанк, Payoneer, Wise, TRON, Fondy, Western Bid, Checkbox, Poster, Вчасно.Каса, Hutko, ручные импорты.

### 1.12 AutomationRule
Поля: `name`, `transaction_type`, `is_enabled`, `priority`, `conditions`, `actions`, `apply_to_existing`.

### 1.13 FinancialMetric
Поля: `name`, `formula`, `income_categories`, `expense_categories`, `period`, `display_order`.

## 2. Базовые расчеты

### 2.1 Фактический баланс счета
`current_balance = initial_balance + actual_income - actual_expense + transfers_in - transfers_out`

Плановые платежи не входят в `current_balance`.

### 2.2 Остаток всех счетов
`total_actual_balance_base = sum(convert(account.current_balance, account.currency, company.base_currency, today_rate))`

Отображается в левой панели как `Всього на рахунках`.

### 2.3 Плановые платежи
`planned_income_period = sum(planned income amount_base in selected period)`

`planned_expense_period = sum(planned expense amount_base in selected period)`

Расходы показываются отрицательными.

### 2.4 Баланс с учетом будущих платежей
`forecast_balance = total_actual_balance_base + planned_income_period + planned_expense_period`

### 2.5 Остаток по дням в календаре
`balance_end_of_day = balance_start_period + sum(actual transactions up to day) + sum(planned transactions up to day)`

Для будущих дат это прогноз.

## 3. Доходы, расходы и переводы

### 3.1 Доход
Доход увеличивает счет, попадает в P&L как доход и в Cash Flow как поступление. Если `planned`, не меняет фактический баланс.

### 3.2 Расход
Расход уменьшает счет, попадает в P&L как расход и в Cash Flow как списание. Если `planned`, не меняет фактический баланс.

### 3.3 Перевод
Перевод уменьшает счет-источник и увеличивает счет-получатель. Не должен попадать в доходы/расходы P&L. При разных валютах сохранять `exchange_rate`, `from_amount`, `to_amount`.

## 4. Даты

У платежа две даты:
- `date_agreement` — дата договоренности/документа;
- `date_actual` — фактическая дата движения денег.

Cash Flow и баланс используют фактическую дату. Дебиторка/кредиторка могут использовать дату договоренности и плановую дату оплаты.

## 5. Повторяющиеся платежи

Варианты: не повторять, ежедневно, еженедельно, ежемесячно, ежегодно, кастомно. Хранить в `RecurrenceRule`: frequency, interval, by_day, by_month_day, start_date, end_date, count.

## 6. Разделение платежа

Один платеж можно разделить на несколько частей. Сумма дочерних частей должна равняться исходной. Исходный платеж становится `split_parent`, а в расчетах участвуют дочерние части.

## 7. Замена платежа на перевод

Действие `Змінити в переказ` превращает доход/расход в перевод. Старое влияние на P&L отменяется, балансы пересчитываются.

## 8. Дебиторка и кредиторка

Дебиторка = неоплаченные ожидаемые поступления: плановые доходы, неоплаченные инвойсы, частично оплаченные инвойсы, доходы без фактической оплаты.

Кредиторка = неоплаченные ожидаемые списания: плановые расходы, обязательства, закупки/счета поставщиков, кредиты, зарплаты и т.д.

## 9. Cash Flow и P&L

Cash Flow: движение денег по счетам. Включает поступления, списания, чистый денежный поток. Переводы по умолчанию исключать из операционного cash flow.

P&L: прибыльность бизнеса. `profit = income - expenses`. Переводы, стартовые балансы и технические корректировки не включать.

## 10. План/Факт

Хранить `BudgetPlan`: период, категория, проект, плановый доход, плановый расход. Отчет показывает план, факт, отклонение и процент выполнения.

## 11. Аудит

Логировать создание, редактирование, удаление, импорт, изменения счетов, интеграции, автоправила и пользователей. Сущность `AuditLog`: user, action, entity_type, entity_id, before, after, created_at.
