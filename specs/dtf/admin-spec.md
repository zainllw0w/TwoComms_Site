# DTF Subdomain — Admin Spec

## Django Admin
### DtfOrder
- list_display: order_number, name, phone, status, meters_total, price_total, created_at
- list_filter: status, created_at
- search: order_number, name, phone
- actions:
  - Одобрить макет → status = AwaitingPayment
  - Запросить правки → status = NeedFix + reason
  - Отправить ссылку на оплату → status = AwaitingPayment + Telegram
  - Отправлено (ТТН) → status = Shipped + tracking_number

### DtfLead
- list_display: lead_number, name, phone, lead_type, status, created_at
- list_filter: status, lead_type
- search: lead_number, name, phone

### DtfWork
- list_display: title, category, is_active, sort_order
- list_filter: category, is_active

## Acceptance Criteria
- [ ] Админка позволяет фильтровать, искать и быстро менять статусы.
- [ ] Admin actions инициируют Telegram события.
- [ ] Галерея управляется через Django Admin.
