# Client Processing Flow (Mandatory)

## 1. Цель
Сделать процесс обработки лида устойчивым к ошибкам и абузу при сохранении скорости работы менеджера.

## 2. Главные правила
1. Нельзя закрыть `not_interested` без причины.
2. Нельзя подтвердить `sent_email` без выбора отправленного КП.
3. `no_answer` обрабатывается цепочкой до 3 попыток.
4. Любой duplicate перед созданием должен быть явно показан менеджеру.

## 3. Flow: create or update client
1. Ввод телефона/email.
2. Авто-проверка дедупа (phone_normalized + email).
3. Если дубль найден:
- показать owner, дату, последний результат, комментарий,
- дать кнопки: `open existing`, `append interaction`, `create anyway` (только с reason).
4. Если дубля нет: стандартное создание.

## 4. Статусы и обязательные поля

| Статус | Обязательные поля |
|---|---|
| `not_interested` | reason_code, reason_text если `other` |
| `sent_email` | cp_log_id |
| `callback` | scheduled_callback_at |
| `no_answer` | attempt increment + next follow-up |
| `order/paid` | order reference or payment proof link |

## 5. No-answer chain
1. Attempt 1 -> schedule follow-up + reminder.
2. Attempt 2 -> schedule follow-up + warning.
3. Attempt 3 -> allow close (limited score credit).
4. Missed follow-up -> mark breach and reduce trust.

## 6. CP linkage policy

### 6.1 Email channel
Обязательно выбрать отправленный CP из логов менеджера.

### 6.2 Messenger channels
Разрешено как weakly verifiable событие.
Требует:
- channel type,
- free-text reference,
- follow-up date.

## 7. Reason taxonomy
Рекомендуемый enum:
- competitor,
- no_assortment,
- price,
- not_target,
- closed_business,
- seasonal,
- no_budget,
- already_contacted,
- other (+ detail required).

## 8. Validation pseudo-rules
```python
if status == "not_interested" and not reason_code:
    reject("reason_required")

if status == "not_interested" and reason_code == "other" and len(reason_text.strip()) < 12:
    reject("reason_detail_required")

if status == "sent_email" and not cp_log_id:
    reject("cp_link_required")

if status == "callback" and not scheduled_callback_at:
    reject("callback_time_required")
```

## 9. UX requirements
1. Все обязательные ошибки показываются до сохранения.
2. Менеджер видит влияние на score (например, "без причины баллы почти не начислятся").
3. Для дублей окно должно быть быстрым и информативным, без блокировки работы.

## 10. Data recording
Каждое изменение должно фиксироваться как interaction attempt для дальнейшего trust/score анализа.
