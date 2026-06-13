# Кредиторка/дебиторка: точное погашение, карты контрагента, таймлайн планов

**Goal:** Сделать молекулярно-точное погашение обязательств (привязка реального
платежа к обязательству и периоду), стабильную приблизительную оценку, карты
контрагента с распознаванием, редизайн карточки контрагента и понятный таймлайн
плановых платежей.

**Architecture:** Зеркалим рабочий паттерн consignment.register_payment для общих
обязательств (recurring + onetime). Новые модели `ObligationSettlement` и
`CounterpartyCard`. Новый сервис `services/payables.py`. Жёсткий инвариант:
фактическое погашение НЕ меняет `RecurrenceRule.template_amount`. Единая модалка
погашения с режимами «привязать существующий платёж / новый платёж». Таймлайн
планов: просрочено → этот месяц → будущие по месяцам, внутри по дате.

**Tech Stack:** Django 4, sqlite(local)/MySQL(prod), vanilla JS, finance.css.

**Запуск тестов:** `SECRET_KEY=test_local_secret python manage.py test finance.<module>`
из `/Users/zainllw0w/TwoComms/site/twocomms`.

---

## Инварианты (нельзя нарушать)

1. **Стабильность оценки.** Погашение/проведение/синк/привязка НЕ трогают
   `template_amount` и не меняют суммы других плановых экземпляров. Оценка
   меняется только явным «Редагувати план».
2. **Нет двойного расхода.** Режим «привязать существующий платёж» НЕ создаёт
   новую транзакцию — использует существующую фактическую; баланс не меняется.
3. **Распознавание карт по last4 — слабое.** Не привязывать молча; переспрашивать.
4. **Полное погашение периода recurring** → advance next_occurrence + materialize
   следующего; частичное — остаток остаётся плановым.

---

## Task 1: Модель ObligationSettlement + CounterpartyCard + поля контрагента

**Files:**
- Modify: `finance/models_core.py` (CounterpartyCard рядом с Counterparty)
- Modify: `finance/models_txn.py` (ObligationSettlement рядом с Transaction)
- Modify: `finance/models.py` (ре-экспорт)
- Create: `finance/migrations/0018_obligation_settlement_cards.py`
- Modify: `finance/admin.py` (регистрация)

**CounterpartyCard** (models_core.py):
```python
class CounterpartyCard(models.Model):
    """Картка/рахунок контрагента (куди ми переказуємо). Реквізит контрагента,
    НЕ наш рахунок. Дозволяє авто-розпізнавання контрагента за переказом."""
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='counterparty_cards')
    counterparty = models.ForeignKey(Counterparty, on_delete=models.CASCADE, related_name='cards')
    pan_mask = models.CharField(max_length=32, blank=True, default='')   # '537541******1234'
    last4 = models.CharField(max_length=4, blank=True, default='', db_index=True)
    bank = models.CharField(max_length=64, blank=True, default='')
    iban = models.CharField(max_length=64, blank=True, default='', db_index=True)
    label = models.CharField(max_length=128, blank=True, default='')
    is_primary = models.BooleanField(default=False)
    last_used_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Картка контрагента'
        verbose_name_plural = 'Картки контрагентів'
        ordering = ['-is_primary', '-last_used_at', 'id']

    def __str__(self):
        return self.label or self.pan_mask or self.iban or f'card#{self.pk}'

    @property
    def display(self):
        tail = self.last4 or (self.pan_mask[-4:] if self.pan_mask else '')
        parts = [p for p in [self.bank, f'•••• {tail}' if tail else ''] if p]
        return ' · '.join(parts) or (self.iban or 'картка')
```

**ObligationSettlement** (models_txn.py, после Transaction):
```python
class ObligationSettlement(models.Model):
    """Зв'язок «реальний платіж → погашене зобов'язання за період».

    Молекулярна точність: кожна гривня погашення прив'язана до конкретної
    фактичної транзакції (з її рахунком/датою) і до конкретного зобов'язання
    та періоду. Дозволяє кілька доплат на одне зобов'язання.
    """
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='obligation_settlements')
    # Фактичний платіж, що погашає (income для дебіторки, expense для кредиторки).
    payment = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name='settlements')
    # Зобов'язання: повторюване правило АБО конкретна планова транзакція (onetime).
    rule = models.ForeignKey(RecurrenceRule, on_delete=models.SET_NULL, blank=True, null=True, related_name='settlements')
    planned_txn = models.ForeignKey(Transaction, on_delete=models.SET_NULL, blank=True, null=True, related_name='planned_settlements')
    period_key = models.CharField(max_length=16, blank=True, default='')  # 'YYYY-MM' періоду
    period_label = models.CharField(max_length=64, blank=True, default='')
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    currency = models.CharField(max_length=3, default='UAH')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Погашення зобов\'язання'
        verbose_name_plural = 'Погашення зобов\'язань'
        ordering = ['-created_at']
```

Поля контрагента уже есть (iban/edrpou/group/address/contacts) — менять модель не
нужно, только форму (Task 6).

**Steps:**
- [ ] Добавить классы в models_core.py / models_txn.py.
- [ ] Ре-экспорт в models.py (`CounterpartyCard`, `ObligationSettlement`).
- [ ] `makemigrations finance` → 0018.
- [ ] Зарегистрировать в admin.py.
- [ ] `migrate`; убедиться, что система загружается: `manage.py check`.
- [ ] Commit: `feat(finance): models ObligationSettlement + CounterpartyCard`.

---

## Task 2: services/cards.py — распознавание/upsert карт контрагента

**Files:**
- Create: `finance/services/cards.py`
- Create test: `finance/tests_cards.py`

**API:**
```python
def extract_card_hint(txn) -> dict:
    """Витягує реквізити отримувача з платежу: {pan_mask,last4,bank,iban,counter_name}."""

def match_counterparty_by_payment(company, txn) -> dict:
    """Повертає {'strong': cp|None, 'candidates': [cp,...], 'reason': str}.
    strong — IBAN або повна маска збіглися; candidates — лише last4 (перепитати)."""

def upsert_card(counterparty, *, pan_mask='', last4='', bank='', iban='', label='', make_primary=False, when=None) -> CounterpartyCard:
    """Створює/оновлює картку контрагента (дедуп за iban або повною маскою; за
    одним last4 НЕ дедупимо — це різні картки)."""

def cards_for(counterparty) -> list[dict]:
    """Список карток для UI (display, bank, last4, is_primary, last_used)."""
```

**Tests (tests_cards.py):** извлечение маски из comment/external_data; strong-match
по iban; weak-match по last4 даёт candidates, не strong; upsert дедуп по iban;
два контрагента с одинаковым last4 → match вернёт двух кандидатов.

- [ ] Написать тесты (RED) → запустить → реализовать → GREEN → commit.

---

## Task 3: Фикс инварианта оценки (баг Виктора 13000→17000)

**Files:**
- Modify: `finance/views/payments.py` (`transaction_update_api`, ~302-320)
- Modify: `finance/services/payloads.py` (parse_recurrence_payload — добавить флаг)
- Test: `finance/tests_recurring.py` (новый тест)

**Проблема:** при редактировании повторяемой операции вызывается
`update_plan(rule, amount=txn.amount, ...)` → шаблон перезаписывается фактической.

**Фикс:** в `transaction_update_api` НЕ передавать `amount` в `update_plan`
автоматически из `txn.amount`. Передавать сумму в план только если в payload явно
присутствует ключ `plan_amount` (новое поле модалки «Редагувати план»). Без него —
график обновляем, сумму шаблона не трогаем.

```python
if recurrence:
    if txn.recurrence_rule_id:
        plan_amount = data.get('plan_amount')
        recurring_service.update_plan(
            txn.recurrence_rule, user=request.user,
            amount=(payload_service._decimal(plan_amount, 'plan_amount') if plan_amount not in (None,'') else None),
            amount_is_estimated=recurrence['amount_is_estimated'],
            title=(recurrence['title'] or None),
            frequency=recurrence['frequency'], interval=recurrence['interval'],
            end_mode=recurrence['end_mode'], end_date=recurrence['end_date'],
            count=recurrence['count'],
        )
    else:
        recurring_service.create_rule_from_transaction(txn, user=request.user, **recurrence)
```

**Test:** создать recurring 13000 (income), провести/отредактировать экземпляр с
суммой 17000 без plan_amount → `rule.template_amount == 13000`, следующий
материализованный экземпляр == 13000.

- [ ] Тест RED → фикс → GREEN → прогнать tests_recurring + tests_transactions → commit.

---

## Task 4: services/payables.py — ядро погашения обязательств

**Files:**
- Create: `finance/services/payables.py`
- Create test: `finance/tests_payables.py`

**Модель работы (зеркало consignment):**
```python
@db_transaction.atomic
def settle_obligation(*, user, planned_txn, mode, amount=None, payment_txn=None,
                      account=None, date=None, counterparty=None,
                      full_period=True, remember_card=False, card_hint=None):
    """Гасить обязательство (planned_txn — найближчий екземпляр).
    mode='new_payment': створити новий actual {expense|income} на amount з account,
        counterparty; прив'язати settlement; закрити/зменшити плановий; advance якщо full_period.
    mode='pick_txn': використати наявний actual payment_txn; amount<=payment.amount;
        НЕ створювати дубль; прив'язати settlement; закрити/зменшити; advance якщо full_period.
    template_amount НЕ чіпаємо НІКОЛИ.
    """
```

**Вспомогательные:**
```python
def _apply_to_planned(planned_txn, amount, *, user, full_period):
    """full_period=True: для recurring — провести/скасувати поточний плановий і
       advance rule (next_occurrence + materialize); для onetime — provести як actual
       (тільки якщо mode=new_payment) або скасувати (mode=pick_txn).
       full_period=False (частково): зменшити суму планового на amount (залишок лишається);
       якщо вийшло <=0 — закрити період."""

def payable_candidates(company, counterparty, *, ttype) -> list:
    """Actual-транзакції потрібного типу без settlement, пріоритет:
       рахунок прив'язаний до контрагента > збіг по картці контрагента (iban/маска) >
       без прив'язки. Підтягуємо суму/рахунок/дату/маску."""

def reverse_link_candidates(company, payment_txn) -> list:
    """Для свіжого actual-платежу — відкриті зобов'язання того ж контрагента
       (за counterparty або розпізнаною карткою), сортування за датою/схожістю суми."""

def attach_payment_to_obligation(*, user, payment_txn, planned_txn, full_period=True):
    """Обратный поток: прив'язати наявний платіж до зобов'язання (= settle pick_txn)."""
```

**Ключевая логика advance recurring (full_period):** использовать существующий
`recurring_service`: выставить next_occurrence через `calculate_next_occurrence`
от даты периода, `materialize(rule)`. Текущий плановый экземпляр:
- mode=new_payment → плановый отменяем (cancel), факт = новый платёж.
- mode=pick_txn → плановый отменяем (cancel), факт = существующий payment_txn.
Никогда не превращаем плановый в actual в pick_txn (иначе двойной расход).

**Tests (tests_payables.py) — все вариации:**
1. pick_txn полное: баланс НЕ меняется (используется существующий), settlement
   создан, плановый cancelled, recurring advance (next_occurrence +1 период),
   template_amount неизменен.
2. new_payment полное: создан 1 actual expense, баланс −amount, settlement, advance.
3. estimated частично (план ≈2500, платёж 1400, full_period=False): остаток 1100
   остаётся плановым, template_amount == 2500 (стабильно), нет advance.
4. estimated полное (план ≈2500, платёж 1400, full_period=True): период закрыт,
   advance, template_amount == 2500, следующий экземпляр == 2500 (НЕ 1400).
5. переплата (план 2500, платёж 3000, full_period): не уходим в минус, settlement
   на 3000, advance.
6. payable_candidates приоритет: счёт контрагента выше «без привязки».
7. дебиторка симметрично (income, Виктор 13000, вернул 17000 pick_txn full):
   template_amount == 13000.
8. attach_payment_to_obligation (обратный поток) = pick_txn эффект.
9. remember_card=True с iban → upsert CounterpartyCard.
10. идемпотентность: повторная привязка того же payment не задваивает settlement.

- [ ] Тесты RED → реализовать → GREEN → commit.

---

## Task 5: API + единая модалка погашения (replace debt_settle + settle)

**Files:**
- Modify: `finance/views/payments.py` (новые API)
- Modify: `finance/views/analytics.py` (`debt_settle_api` → проксировать на новый)
- Modify: `finance/urls.py` (новые маршруты)
- Modify: `finance/templates/finance/partials/settle_modal.html` (редизайн)
- Modify: `finance/static`/theme `js/finance-planned.js` (логика режимов)
- Modify: `twocomms_django_theme/static/css/finance.css` (стили модалки)

**Новые API:**
```
GET  api/obligations/<txn_id>/settle-context/   → {counterparty, cards, accounts, candidates, per_amount, estimated, ttype}
POST api/obligations/<txn_id>/settle/           → settle_obligation(mode, amount, payment_txn_id, account_id, full_period, remember_card)
GET  api/payments/<txn_id>/reverse-candidates/  → reverse_link_candidates
POST api/payments/<txn_id>/attach-obligation/   → attach_payment_to_obligation
```

**Модалка (settle_modal.html):**
- Шапка: title + контрагент (авто) + ≈/точно сумма.
- Segmented control: «Прив'язати наявний платіж» | «Зафіксувати новий платіж».
  - Existing: список карточек кандидатов (дата, сумма, счёт/банк, маска) → выбор подтягивает сумму/счёт/дату.
  - New: счёт списания (карты/счета контрагента сверху), фактическая сумма, дата.
- Для estimated/частичного: radio «Повністю — закрити період» | «Частково — лишилось X».
- Чекбокс «Запам'ятати картку за контрагентом» (если есть card_hint).
- Кнопки Підтвердити/Скасувати, alert, состояния загрузки.

**JS:** загрузка settle-context при открытии; рендер кандидатов; пересчёт остатка;
submit на новый endpoint. Mobile bottom-sheet класс.

**Tests:** API settle-context отдаёт кандидатов и карты; POST settle pick_txn без
двойного расхода (через client); debt_settle_api старый путь по-прежнему даёт 200
(совместимость, проксирование на новую логику с дефолтами).

- [ ] Реализовать → тесты вьюх (tests_planned доп.) → GREEN → commit.

---

## Task 6: Обратный поток (после P2P-перевода)

**Files:**
- Modify: `twocomms_django_theme/static/js/finance-transactions.js` (после создания expense)
- Reuse: reverse-candidates / attach-obligation API (Task 5)
- Modify: `finance.css` (мини-промпт)

**Логика:** после успешного создания/просмотра actual expense (или income) с
контрагентом → запросить reverse-candidates; если есть открытые обязательства →
показать мини-промпт «Цей переказ у рахунок: <Зобов'язання> (≈сума)? [Так, погасити
період] [Ні, окремий платіж]». При слабом распознавании карты сперва «Це <CP>?».
«Так» → attach-obligation (full_period=True) → recurring перепрыгивает месяц.

- [ ] Реализовать → ручной/JS-smoke + браузерная проверка позже → commit.

---

## Task 7: Редизайн карточки контрагента + карты + реквизиты

**Files:**
- Modify: `finance/services/counterparty.py` (`counterparty_detail`: свернуть планы
  через obligations, добавить cards, settlements-метки)
- Modify: `finance/views/counterparties.py`
- Modify: `finance/templates/finance/counterparties/detail.html`
- Modify: counterparty modal (форма реквизитов iban/edrpou/group/address/контакты)
- Modify: `finance.css`
- Modify: `finance-counterparties.js` (CRUD карт)
- New API: cards CRUD (`api/counterparties/<id>/cards/...`)

**Изменения counterparty_detail:**
- `obligations`: вызвать `obligations.planned_obligations` отфильтровать по cp →
  карточки «дата · сумма · ≈/точно · лишилось», вместо стены плановых строк.
- `transactions`: только actual (планы убрать из общего списка) + пометка
  «у рахунок: <obligation> <period>» по ObligationSettlement.
- `cards`: cards_for(cp) — полоски как платежи.

**Tests:** counterparty_detail отдаёт obligations (свёрнутые), cards, actual-only
история; settlement-метка присутствует.

- [ ] Реализовать → tests_counterparties доп. → GREEN → commit.

---

## Task 8: Таймлайн плановых (просрочено → этот месяц → будущие)

**Files:**
- Modify: `finance/services/obligations.py` (+ `planned_timeline(company)`)
- Modify: `finance/views/planned.py` (передать timeline)
- Modify: `finance/templates/finance/planned.html` (секции-сегменты)
- Create: `finance/templates/finance/partials/timeline_section.html`
- Modify: `finance/templates/finance/payments.html` (нижний блок → таймлайн компактный)
- Modify: `finance.css` (стили сегментов, sticky-заголовки)

**`planned_timeline(company)`** → reuse planned_obligations, затем сегментация по
`next_due`:
```
segments = [
  {'key':'overdue','label':'Прострочено','items':[...по дате возр.]},
  {'key':'this_month','label':'Цей місяць','items':[...по дате]},
  # будущие — по месяцам:
  {'key':'2026-07','label':'Липень 2026','items':[...]}, ...
]
```
items — те же свёрнутые обязательства; доходы и расходы вместе, цветовая пометка по
`g.type`. Месяцы — украинские (reuse `_uk_month_year` из reports.py или _MONTHS_UK).

**Tests (tests_planned доп.):** overdue попадает в overdue; платёж этого месяца — в
this_month; следующего — в свой месяц; сортировка внутри по дате возр.; доход
будущего месяца и расход этого — в разных сегментах (кейс Виктор vs MyWest/налоги).

- [ ] Тест RED → реализовать → GREEN → commit.

---

## Task 9: Полный прогон тестов + статистика

- [ ] `python manage.py test finance` — все тесты (ожидаем 0 новых провалов).
- [ ] Зафиксировать число тестов до/после, перечислить новые тест-модули.
- [ ] Проверить `manage.py check` и отсутствие missing-migrations.
- [ ] Commit финальных правок.

---

## Task 10: Правка реальных данных Влада Мама + деплой

- [ ] git push ветки/main по правилам.
- [ ] Деплой по чек-листу workflow.md: git pull → migrate (есть 0018) →
      collectstatic (менялись CSS/JS) → НЕ compress (finance вне {% compress %},
      проверить) → touch restart.
- [ ] На сервере через Django shell (одна SSH-сессия): найти неверно проведённую
      кредиторку Влада Мама (2500), отменить неверное проведение / вернуть план,
      найти реальный перевод ~1700 и привязать через
      `payables.attach_payment_to_obligation(full_period=True)`. Проверить, что
      обязательство показывает ≈ исходную сумму, а 1700 помечен «у рахунок».
- [ ] sanity-curl `/`, `/planned/`, `/counterparties/<id>/` → 200/302.
- [ ] Обновить `.kiro/fin-upgrade-plan.md` (новая сессия — итог).

---

## Self-review покрытия спеки
- Связь платёж↔обязательство → Task 1,4. Стабильность оценки → Task 3,4.
- Карты контрагента + распознавание/дубли → Task 1,2,5,7. Реквизиты cp → Task 7.
- Единая модалка/режимы/мобайл → Task 5. Обратный поток + advance месяца → Task 6,4.
- Редизайн карточки контрагента (планы-карточки, не минусы) → Task 7.
- Таймлайн плановых по месяцам/датам → Task 8. Влада Мама данные → Task 10.
- Тесты по всем вариациям → Task 4,8 + Task 9 статистика.
