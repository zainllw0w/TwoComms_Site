# DTF Subdomain — Data Models Spec

## DtfLead
**Purpose:** консультация/помощь/вопрос менеджеру.

**Fields (draft):**
- id (PK)
- lead_number (строка, уникальная)
- lead_type (help | consultation | fab)
- name, phone
- contact_channel (telegram | whatsapp | instagram | call)
- contact_handle (ник/ссылка)
- city, np_branch
- task_description (текст)
- deadline_note (строка)
- source (order_help | fab | other)
- status (new | in_progress | closed)
- manager_note (text)
- created_at, updated_at

## DtfLeadAttachment
- lead (FK)
- file (FileField)
- created_at

## DtfOrder
**Purpose:** заказ DTF печати.

**Fields (draft):**
- id (PK)
- order_number (строка, уникальная)
- order_type (ready | help)
- status (NewLead/NewOrder, CheckMockup, NeedFix, AwaitingPayment, Printing, Ready, Shipped, Closed)
- name, phone
- contact_channel, contact_handle
- city, np_branch
- comment (text)
- gang_file (FileField)
- length_m (decimal)
- copies (int)
- meters_total (decimal)
- price_per_meter (decimal)
- price_total (decimal)
- pricing_tier (string/nullable)
- requires_review (bool)
- tracking_number (string)
- manager_note (text)
- created_at, updated_at

## DtfWork
**Purpose:** галерея работ на лендинге.

**Fields (draft):**
- title
- category (macro | process | final)
- image (ImageField)
- is_active
- sort_order

## Acceptance Criteria
- [ ] Order и Lead разделены и имеют отдельные номера.
- [ ] Lead поддерживает multi-upload.
- [ ] Order хранит расчет метража и цену (snapshot).
- [ ] Work позволяет загрузку 9+ изображений через админку.
