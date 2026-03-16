# 🔄 Система дедупликации контактов и управление перезвонами

## Оглавление
1. [Анализ текущей системы дублей](#1-анализ-текущей-системы)
2. [Выявленные уязвимости](#2-выявленные-уязвимости)
3. [Предложение: Система дедупликации](#3-предложение-система-дедупликации)
4. [Система перезвонов и итогов](#4-система-перезвонов-и-итогов)
5. [Техническое решение](#5-техническое-решение)

---

## 1. Анализ текущей системы

### 1.1 Текущие механизмы нормализации телефонов

Модель `Client` и `ManagementLead` имеют поле `phone_normalized`, рассчитываемое в `save()`:

```python
def normalize_phone(raw_phone: str) -> str:
    digits = re.sub(r"\D+", "", raw_phone or "")
    if not digits:
        return ""
    if digits.startswith("380") and len(digits) == 12:
        return f"+{digits}"           # +380XXXXXXXXX
    if digits.startswith("0") and len(digits) == 10:
        return f"+38{digits}"         # → +380XXXXXXXXX
    if len(digits) == 9:
        return f"+380{digits}"        # → +380XXXXXXXXX
    if raw_phone and str(raw_phone).strip().startswith("+"):
        return f"+{digits}"           # Международный формат
    return digits                     # Fallback
```

**Покрытие:** Украинские номера (380), 10-значные (0XXXXXXXXX), 9-значные.

### 1.2 Где проверяются дубли сейчас

| Источник | Дубль-проверка | Как |
|----------|---------------|-----|
| Lead Parser (Google Maps) | ✅ Есть | `LeadParsingResult.status = DUPLICATE`, считается `duplicate_skipped` |
| Ручное добавление лида | ❌ Нет | Менеджер может добавить любой лид без проверки |
| Создание Client | ❌ Нет | `phone_normalized` не имеет `unique` constraint |
| Перезвон → новый Client | ❌ Нет | Повторный контакт создаёт новую запись |
| Между менеджерами | ❌ Нет | Два менеджера могут работать с одним номером |

### 1.3 Модели с `phone_normalized`

| Модель | `phone_normalized` | `db_index` | `unique` |
|--------|-------------------|------------|----------|
| `Client` | ✅ Есть | ✅ Да | ❌ **НЕТ** |
| `ManagementLead` | ✅ Есть | ✅ Да | ❌ **НЕТ** |
| `ShopPhone` | ❌ Нет | — | — |

> [!CAUTION]
> **Критический дефект**: Отсутствие `unique` constraint на `phone_normalized` в модели `Client` — основная причина дублей. Один и тот же контакт может быть добавлен неограниченное количество раз.

---

## 2. Выявленные уязвимости

### 2.1 Сценарии абуза

#### Сценарий 1: Многократное добавление одного контакта
```
Менеджер А добавляет: +380991234567 → "Не відповідає" → +5 балів
Менеджер А добавляет снова: +380991234567 → "Не відповідає" → +5 балів
... × 10 раз = +50 балів за один номер
```

#### Сценарий 2: Кросс-менеджерные дубли
```
Менеджер А обработал: +380991234567 → "Подумає" → +10 балів
Менеджер Б добавляет: +380991234567 → "Не цікавить" → +5 балів
Оба получают баллы за одного клиента, клиент получает два звонка
```

#### Сценарий 3: Перезвон как новый контакт
```
День 1: Менеджер А → +380991234567 → "Подумає" (+10), назначен перезвон
День 3: Менеджер А перезванивает → создаёт НОВОГО Client → "Замовлення" (+45)
Итого: +55 балів вместо +45 (перезвон не должен давать дополнительные баллы)
```

#### Сценарий 4: Lead Pipeline → Client дублирование
```
ManagementLead: phone=+380991234567, status="base"
Менеджер обрабатывает лид → создаёт Client с тем же номером
Но лид остаётся в базе → может быть обработан снова
```

### 2.2 Оценка масштаба проблемы

Без доступа к production БД невозможно точно оценить масштаб, но на основе архитектуры:

- **Потенциальный % дублей**: 10-30% (на основе типичных CRM)
- **Влияние на баллы**: Раздутие баллов на 5-15% (ложное увеличение КПД)
- **Влияние на клиентский опыт**: Клиент получает повторные звонки от разных менеджеров

---

## 3. Предложение: Система дедупликации

### 3.1 Трёхуровневая дедупликация

#### Уровень 1: Превентивная проверка (при добавлении)
```python
def check_duplicate_before_save(phone_normalized, current_user=None):
    """
    Проверяет дубли ДО сохранения контакта.
    Возвращает список совпадений.
    """
    matches = []
    
    # 1. Точное совпадение в Client
    client_matches = Client.objects.filter(
        phone_normalized=phone_normalized
    ).select_related('owner')
    
    for client in client_matches:
        matches.append({
            'type': 'client',
            'id': client.id,
            'shop_name': client.shop_name,
            'owner': client.owner.get_full_name(),
            'call_result': client.get_call_result_display(),
            'created_at': client.created_at,
            'is_mine': client.owner == current_user,
        })
    
    # 2. Совпадение в ManagementLead
    lead_matches = ManagementLead.objects.filter(
        phone_normalized=phone_normalized,
        status__in=['base', 'converted'],
    )
    for lead in lead_matches:
        matches.append({
            'type': 'lead',
            'id': lead.id,
            'shop_name': lead.shop_name,
            'status': lead.get_status_display(),
            'added_by': lead.added_by_display,
        })
    
    # 3. Совпадение в ShopPhone
    shop_matches = ShopPhone.objects.filter(
        phone=phone_normalized
    ).select_related('shop')
    for sp in shop_matches:
        matches.append({
            'type': 'shop',
            'id': sp.shop.id,
            'shop_name': sp.shop.name,
            'managed_by': sp.shop.managed_by.get_full_name() if sp.shop.managed_by else '—',
        })
    
    return matches
```

#### Уровень 2: Модальное окно для менеджера

При обнаружении совпадений менеджер видит модальное окно:

```
╔══════════════════════════════════════════════════╗
║  ⚠️ Знайдено дублі для +380991234567            ║
╠══════════════════════════════════════════════════╣
║                                                  ║
║  📋 Клієнт: "Магазин Сонячний" (Олена К.)       ║
║     Підсумок: Подумає (10 балів)                 ║
║     Дата: 15.02.2026                             ║
║                                                  ║
║  📋 Лід: "Sunny Shop" (парсинг)                 ║
║     Статус: У базі                               ║
║     Додано: 10.02.2026                           ║
║                                                  ║
║  Що робити?                                      ║
║                                                  ║
║  [📞 Це перезвон]  [➕ Додати як новий]  [❌ Скасувати] ║
║                                                  ║
╚══════════════════════════════════════════════════╝
```

**Варианты действий:**
1. **«Це перезвон»** — обновляет существующий Client, не начисляет баллы за добавление (только за результат перезвона)
2. **«Додати як новий»** — создаёт Client, но помечает `is_duplicate_override=True` и логирует (для аудита)
3. **«Скасувати»** — отменяет добавление

#### Уровень 3: Административный аудит

Еженедельный автоматический отчёт для админа:

```
📊 Звіт про дублі (тиждень 15.02 – 21.02)
─────────────────────────────────────────
• Нових дублів знайдено: 23
• Менеджери з найбільше дублів:
  1. Дмитро Л. — 8 дублів (34% від його контактів)
  2. Андрій С. — 6 дублів (18%)
  3. Ірина В.  — 4 дублі (9%)
  
• Кросс-менеджерних дублів: 5
  (один клієнт обдзвонений різними менеджерами)

• Рекомендація: Перевірити роботу Дмитра Л.
```

### 3.2 Миграция БД

```python
# migrations/XXXX_add_duplicate_detection.py

class Migration(migrations.Migration):
    operations = [
        # 1. Добавить soft-unique index (не блокирующий, для проверки)
        migrations.AddIndex(
            model_name='client',
            index=models.Index(
                fields=['phone_normalized', 'owner'],
                name='mgmt_client_phone_owner',
            ),
        ),
        
        # 2. Добавить поле для отметки override
        migrations.AddField(
            model_name='client',
            name='is_duplicate_override',
            field=models.BooleanField(default=False),
        ),
        
        # 3. Добавить поле для связи с оригиналом
        migrations.AddField(
            model_name='client',
            name='duplicate_of',
            field=models.ForeignKey(
                'self', null=True, blank=True,
                on_delete=models.SET_NULL,
                related_name='duplicates',
            ),
        ),
        
        # 4. Нормализация ShopPhone
        migrations.AddField(
            model_name='shopphone',
            name='phone_normalized',
            field=models.CharField(max_length=50, blank=True, db_index=True),
        ),
    ]
```

### 3.3 Алгоритм нечёткого сопоставления

Помимо точного совпадения `phone_normalized`, нужен fuzzy matching для:
- Разных форматов одного номера (с + и без)
- Ошибок при вводе (1 цифра отличается)
- Одинаковых имён магазинов с разными номерами

```python
def fuzzy_duplicate_check(phone_norm, shop_name):
    """Нечёткое сопоставление для случаев, где точное не срабатывает."""
    
    candidates = []
    
    # 1. Последние 9 цифр совпадают (разный код страны)
    last_9 = phone_norm[-9:] if len(phone_norm) >= 9 else phone_norm
    candidates += Client.objects.filter(
        phone_normalized__endswith=last_9
    ).exclude(phone_normalized=phone_norm)
    
    # 2. Совпадение по имени магазина (Levenshtein distance ≤ 3)
    from difflib import SequenceMatcher
    all_recent = Client.objects.filter(
        created_at__gte=timezone.now() - timedelta(days=90)
    ).values_list('id', 'shop_name', flat=False)
    
    for client_id, name in all_recent:
        ratio = SequenceMatcher(None, shop_name.lower(), name.lower()).ratio()
        if ratio > 0.8:  # 80% сходства
            candidates.append(client_id)
    
    return candidates
```

---

## 4. Система перезвонов и итогов

### 4.1 Текущая система (ClientFollowUp)

Текущая модель `ClientFollowUp`:
- Status: `open`, `done`, `rescheduled`, `cancelled`, `missed`
- `due_at` — когда перезвонить
- `closed_at` — когда закрыт
- `closed_by_report` — связь с отчётом

**Проблемы:**
1. Перезвон не привязан к результату (нет поля для итога перезвона)
2. Нет автоматического создания follow-up при определённых call_result
3. Нет ограничения на количество переносов
4. `missed` устанавливается вручную (должен быть автоматически)
5. Нет уведомлений в Telegram о приближающемся перезвоне

### 4.2 Предложение: Расширенная система перезвонов

#### 4.2.1 Новые поля для ClientFollowUp

```python
class ClientFollowUp(models.Model):
    # ... существующие поля ...
    
    # НОВЫЕ ПОЛЯ:
    call_result = models.CharField(
        max_length=50,
        choices=Client.CallResult.choices,
        null=True, blank=True,
        verbose_name="Итог перезвона",
    )
    call_notes = models.TextField(
        blank=True,
        verbose_name="Заметки к перезвону",
    )
    reschedule_count = models.PositiveIntegerField(
        default=0,
        verbose_name="Количество переносов",
    )
    max_reschedules = models.PositiveIntegerField(
        default=3,
        verbose_name="Максимум переносов",
    )
    reminder_sent = models.BooleanField(
        default=False,
        verbose_name="Напоминание отправлено",
    )
    source_followup = models.ForeignKey(
        'self', null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='chain',
        verbose_name="Предыдущий перезвон в цепочке",
    )
```

#### 4.2.2 Автоматическое создание перезвонов

```python
# Автоматически создавать follow-up при определённых результатах
AUTO_FOLLOWUP_RESULTS = {
    'thinking':           timedelta(days=2),   # Подумает → через 2 дня
    'sent_email':         timedelta(days=3),   # КП email → через 3 дня
    'sent_messenger':     timedelta(days=2),   # КП мессенджер → через 2 дня
    'wrote_ig':           timedelta(days=2),   # Instagram → через 2 дня
    'no_answer':          timedelta(days=1),   # Не ответил → через 1 день
    'expensive':          timedelta(days=7),   # Дорого → через 7 дней
    'waiting_payment':    timedelta(days=1),   # Ожидается оплата → через 1 день
    'waiting_prepayment': timedelta(days=1),   # Предоплата → через 1 день
}
```

#### 4.2.3 Автоматический missed

```python
# Celery task: запускать каждые 30 минут
@shared_task
def auto_mark_missed_followups():
    """Автоматически помечает просроченные перезвоны как missed."""
    now = timezone.localtime(timezone.now())
    overdue = ClientFollowUp.objects.filter(
        status='open',
        due_at__lt=now - timedelta(hours=4),  # Просрочено > 4ч
    )
    count = overdue.update(
        status='missed',
        closed_at=now,
    )
    return f"Marked {count} followups as missed"
```

#### 4.2.4 Автоматические напоминания о магазинах (каждые 4 дня)

```python
# Celery task: запускать ежедневно в 9:00
@shared_task
def generate_shop_contact_reminders():
    """Создаёт напоминания для магазинов без контакта > 4 дней."""
    threshold = timezone.now() - timedelta(days=4)
    
    stale_shops = Shop.objects.filter(
        Q(next_contact_at__isnull=True) | Q(next_contact_at__lt=timezone.now()),
    ).annotate(
        last_comm=Max('communications__contacted_at'),
    ).filter(
        Q(last_comm__lt=threshold) | Q(last_comm__isnull=True),
    )
    
    for shop in stale_shops:
        # Создаём напоминание в Telegram для менеджера
        send_telegram_reminder(
            user=shop.managed_by,
            message=f"🔔 Магазин '{shop.name}' не контактувався > 4 днів!",
        )
        # Устанавливаем next_contact_at
        shop.next_contact_at = timezone.now() + timedelta(days=4)
        shop.save(update_fields=['next_contact_at'])
```

### 4.3 Цепочка контактов (Contact Chain)

Вместо создания нового Client при перезвоне, система должна:

```
Contact Chain для +380991234567:
┌──────────────────────────────────────────┐
│ #1  01.02.2026  📞 Перший дзвінок        │
│     Результат: Подумає (+10 балів)        │
│     Менеджер: Олена К.                    │
├──────────────────────────────────────────┤
│ #2  03.02.2026  📞 Перезвон               │
│     Результат: Відправили КП (+15 балів)  │
│     Менеджер: Олена К.                    │
├──────────────────────────────────────────┤
│ #3  06.02.2026  📞 Перезвон               │
│     Результат: Замовлення! (+45 балів)    │
│     Менеджер: Олена К.                    │
├──────────────────────────────────────────┤
│ #4  08.02.2026  🏪 Магазин створено       │
│     Тип: Тестова партія                   │
│     Менеджер: Олена К.                    │
└──────────────────────────────────────────┘

Загальні бали: 10+15+45 = 70 (follow-up не дублюють)
Конверсійний час: 5 днів (від першого дзвінка до замовлення)
```

### 4.4 Баллы за перезвоны

```
Перезвон → результат улучшился: +баллы за РАЗНИЦУ
    Был "подумає" (10) → стал "замовлення" (45) → +35 балів
    
Перезвон → результат ухудшился: 0 баллов
    Был "подумає" (10) → стал "не цікавить" (5) → 0 балів
    
Перезвон → тот же результат: +2 балла (за попытку)
    Был "не відповідає" → снова "не відповідає" → +2 балів
    
Перезвон → missed: -2 балла (штраф)
```

---

## 5. Техническое решение

### 5.1 Новая модель ContactInteraction

```python
class ContactInteraction(models.Model):
    """
    Единая запись взаимодействия с контактом.
    Заменяет подход "новый Client = новый контакт".
    """
    client = models.ForeignKey(
        Client, on_delete=models.CASCADE,
        related_name='interactions',
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )
    interaction_type = models.CharField(
        max_length=20,
        choices=[
            ('first_call', 'Перший дзвінок'),
            ('followup', 'Перезвон'),
            ('shop_comm', 'Комунікація з магазином'),
            ('email', 'Email / КП'),
        ],
    )
    call_result = models.CharField(
        max_length=50,
        choices=Client.CallResult.choices,
        null=True, blank=True,
    )
    points_earned = models.IntegerField(default=0)
    notes = models.TextField(blank=True)
    followup = models.ForeignKey(
        ClientFollowUp, null=True, blank=True,
        on_delete=models.SET_NULL,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['client', '-created_at']),
            models.Index(fields=['owner', '-created_at']),
        ]
```

### 5.2 API для проверки дублей

```python
# lead_views.py — новый эндпоинт
@require_POST
@login_required
def check_duplicate_api(request):
    """
    POST /leads/api/check-duplicate/
    Body: { "phone": "+380991234567" }
    Response: { "duplicates": [...], "count": 2 }
    """
    phone = request.POST.get('phone', '')
    phone_norm = normalize_phone(phone)
    
    if not phone_norm:
        return JsonResponse({'duplicates': [], 'count': 0})
    
    duplicates = check_duplicate_before_save(phone_norm, request.user)
    return JsonResponse({
        'duplicates': duplicates,
        'count': len(duplicates),
    })
```

### 5.3 Фронтенд интеграция

```javascript
// При вводе номера телефона в форму добавления клиента
phoneInput.addEventListener('blur', async function() {
    const phone = this.value.trim();
    if (phone.length < 9) return;
    
    const response = await fetch('/leads/api/check-duplicate/', {
        method: 'POST',
        headers: { 'X-CSRFToken': csrfToken },
        body: new URLSearchParams({ phone }),
    });
    const data = await response.json();
    
    if (data.count > 0) {
        showDuplicateModal(data.duplicates);
    }
});
```

### 5.4 Скрипт очистки существующих дублей

```python
# management command: python manage.py deduplicate_clients
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = "Найти и обработать дубли контактов"
    
    def handle(self, *args, **options):
        from collections import Counter
        
        phones = Client.objects.values_list('phone_normalized', flat=True)
        counter = Counter(phones)
        duplicates = {phone: count for phone, count in counter.items() 
                      if count > 1 and phone}
        
        self.stdout.write(f"Знайдено {len(duplicates)} номерів з дублями")
        self.stdout.write(f"Загалом дублів: {sum(duplicates.values()) - len(duplicates)}")
        
        for phone, count in sorted(duplicates.items(), key=lambda x: -x[1])[:20]:
            clients = Client.objects.filter(phone_normalized=phone).order_by('created_at')
            self.stdout.write(f"\n  {phone} — {count} записів:")
            for c in clients:
                owner_name = c.owner.get_full_name() if c.owner else '—'
                self.stdout.write(
                    f"    [{c.id}] {c.shop_name} | {c.get_call_result_display()} "
                    f"| {owner_name} | {c.created_at:%Y-%m-%d}"
                )
```

---

## 6. Углублённый анализ — дополнения v2

### 6.1 Обнаружена ЧАСТИЧНАЯ дедупликация в parser_service.py

> [!NOTE]
> **Ранее упущено**: Парсер Google Maps **уже имеет** качественную систему дедупликации!

Функция `_duplicate_state()` (parser_service.py:196-214) проверяет:

```python
def _duplicate_state(phone_normalized: str, place_id: str) -> str | None:
    # 1. Ищет в ManagementLead по phone ИЛИ google_place_id (OR logic)
    query = Q()
    if phone_normalized:
        query |= Q(phone_normalized=phone_normalized)
    if place_id:
        query |= Q(google_place_id=place_id)
    
    # 2. Если найден REJECTED лид → return "rejected" (пропустить навсегда)
    if lead_qs.filter(status=ManagementLead.Status.REJECTED).exists():
        return "rejected"
    
    # 3. Если найден ЛЮБОЙ лид → return "duplicate"
    if lead_qs.exists():
        return "duplicate"
    
    # 4. КРОСС-МОДЕЛЬНАЯ ПРОВЕРКА: ищет в Client!
    if phone_normalized and Client.objects.filter(phone_normalized=phone_normalized).exists():
        return "duplicate"
    
    return None  # Добавить можно
```

**Статистика парсера (LeadParsingJob):**
- `duplicate_skipped` — кол-во пропущенных дублей
- `already_rejected_skipped` — кол-во пропущенных ранее отклонённых
- `no_phone_skipped` — без номера

**Вывод**: Дедупликация работает для **автоматического парсинга**, но **полностью отсутствует для ручного добавления** через `home()`.

### 6.2 Точные места уязвимости в коде

**home() — views.py:527-539 — НОЛЬ проверок:**
```python
# 1. Создание нового Client — БЕЗ ПРОВЕРКИ дублей
client = Client.objects.create(
    shop_name=shop_name,
    phone=phone,            # ← Может быть любой! Даже уже существующий!
    website_url=website_url,
    full_name=full_name,
    role=role,
    source=source_display,
    call_result=call_result,
    ...
    owner=request.user,     # ← Любой менеджер может добавить любой номер
)

# 2. Обновление Client — тоже без проверки:
client = Client.objects.get(id=client_id)
client.phone = phone        # ← Можно изменить phone на уже существующий!
client.save()
```

### 6.3 Follow-up система — проблема с `_close_followups_for_report`

**Баг**: При отправке дневного отчёта ВСЕ сегодняшние OPEN follow-ups помечаются как MISSED:

```python
# views.py:204-215
def _close_followups_for_report(report: Report):
    report_day = _local_date_from_dt(report.created_at)
    ClientFollowUp.objects.filter(
        owner=report.owner,
        due_date=report_day,       # ← Все за сегодня
        status=ClientFollowUp.Status.OPEN,  # ← Все открытые → MISSED
    ).update(
        status=ClientFollowUp.Status.MISSED,
        closed_at=report.created_at,
        closed_by_report=report,
    )
```

**Проблема**: Если перезвон запланирован на 17:00, a отчёт отправлен в 15:00 → перезвон будет помечен как MISSED, хотя он ещё не был due.

**Исправление**: Добавить `due_at__lt=report.created_at`:
```python
ClientFollowUp.objects.filter(
    owner=report.owner,
    due_date=report_day,
    due_at__lt=report.created_at,  # ← Только прошедшие!
    status=ClientFollowUp.Status.OPEN,
).update(...)
```

### 6.4 SQL-запрос для аудита дублей в production

```sql
-- Найти все phone_normalized с несколькими записями Client
SELECT phone_normalized, COUNT(*) as cnt,
       GROUP_CONCAT(DISTINCT owner_id) as owners,
       GROUP_CONCAT(call_result) as results
FROM management_client
WHERE phone_normalized != ''
GROUP BY phone_normalized
HAVING cnt > 1
ORDER BY cnt DESC
LIMIT 50;

-- Кросс-менеджерные дубли (один номер, разные менеджеры)
SELECT phone_normalized, COUNT(DISTINCT owner_id) as managers,
       COUNT(*) as total_records
FROM management_client
WHERE phone_normalized != ''
GROUP BY phone_normalized
HAVING managers > 1
ORDER BY managers DESC, total_records DESC;

-- Дубли между Lead и Client
SELECT ml.phone_normalized, ml.status as lead_status,
       mc.call_result, mc.owner_id
FROM management_managementlead ml
JOIN management_client mc ON ml.phone_normalized = mc.phone_normalized
WHERE ml.status IN ('base', 'moderation')
  AND ml.phone_normalized != '';
```

### 6.5 Приоритезированный план исправлений

| Приоритет | Действие | Сложность | Влияние |
|-----------|---------|-----------|---------|
| 🔴 P0 | Добавить check_duplicate в `home()` POST | Низкая | Критическое — предотвращает абуз |
| 🔴 P0 | Исправить `_close_followups_for_report` (баг) | Низкая | Высокое — неверная статистика missed |
| 🟡 P1 | Добавить unique index на `(phone_normalized, owner)` | Средняя | Высокое — DB-level защита |
| 🟡 P1 | Frontend модальное окно при дубле | Средняя | Высокое — UX для менеджера |
| 🟢 P2 | Fuzzy matching (Levenshtein) | Высокая | Среднее |
| 🟢 P2 | ContactInteraction модель | Высокая | Высокое — но большой рефакторинг |
| 🔵 P3 | Management command для очистки | Низкая | Разовое — запустить на production |
```

---

## Deep Dive v3 — Молекулярный анализ дедупликации

### Критическое открытие: Асимметричная защита

**Молекулярный анализ кода выявил 3 пути создания контактов:**

| Путь | Файл | Dedup проверка | Результат |
|------|------|----------------|-----------|
| `lead_create_api()` | lead_views.py:101-105 | ✅ Client + ManagementLead | 409 Conflict |
| `home()` POST | views.py:527-539 | ❌ Нет проверки | Дубликат создаётся |
| `parser_service._duplicate_state()` | parser_service.py | ✅ Client + ManagementLead | Помечает как дубль |

```python
# lead_views.py:101-105 — ИМЕЕТ проверку:
has_duplicate = (
    Client.objects.filter(phone_normalized=phone_normalized).exists()
    or ManagementLead.objects.filter(phone_normalized=phone_normalized).exists()
)

# views.py home() POST — НЕ ИМЕЕТ такой проверки!
# Client.objects.create(...) без проверки duplicates
```

### Исследовательские данные по дедупликации (2025)

**Лучшие практики CRM dedup (web research)**:
1. **Нормализация на входе** — стандартизация телефонов (уже есть `normalize_phone()`)
2. **Multi-field analysis** — телефон + имя + компания (не реализовано)
3. **Merge over delete** — сохранять историю при объединении (не реализовано)
4. **Алгоритмы fuzzy matching**:
   - **Levenshtein distance** — для опечаток в именах
   - **Jaro-Winkler** — эффективен для начала строк
   - **Soundex/Metaphone** — фонетическое сходство
   - **Token-based** — порядок слов не важен
5. **Master record ownership** — кто решает, какая запись основная

### Обновлённая матрица приоритетов v3

```
| Приоритет | Задача | Сложность | Влияние |
|-----------|--------|-----------|---------|
| 🔴 P0-NEW | Добавить dedup в home() POST | НИЗКАЯ | КРИТИЧЕСКОЕ — закрыть дыру |
| 🔴 P0 | Исправить _close_followups_for_report | Низкая | Высокое |
| 🟡 P1 | DB unique index (phone_normalized, owner) | Средняя | DB-level защита |
| 🟡 P1 | Frontend modal при дубле (как lead_create_api) | Средняя | UX |
| 🟡 P1-NEW | Унифицировать dedup логику в utils.py | Средняя | DRY |
| 🟢 P2 | Multi-field matching (phone + name + shop) | Высокая | Среднее |
| 🟢 P2 | Fuzzy matching (Levenshtein, threshold 85%) | Высокая | Среднее |
| 🟢 P2 | Merge UI (выбор master record) | Высокая | Среднее |
| 🔵 P3 | Management command для очистки | Низкая | Разовое |
| 🔵 P3-NEW | Регулярный аудит дублей (cron job) | Средняя | Мониторинг |
```

> [!CAUTION]
> **P0-NEW** — самый быстрый фикс: скопировать 4 строки из `lead_create_api()` в `home()` POST handler. Оценка: 15 минут работы, но закрывает критическую дыру в дедупликации.

---

## Улучшенная дедупликация (от владельца, ПРИОРИТЕТ)

> [!IMPORTANT]
> **Требование владельца**: При обнаружении дубля показать: КТО обработал, КОГДА, РЕЗУЛЬТАТ, комментарий, кол-во попыток дозвона, отправленные КП. См. детали в [07_MANAGER_WORKFLOW.md](./07_MANAGER_WORKFLOW.md#7-система-дублей-улучшенная).

### Новый workflow дедупликации:

```
1. Менеджер нажимает "Обробити" в базе лидов
2. Система проверяет phone_normalized по Client + ManagementLead
3. ЕСЛИ НАЙДЕН → показать модальное окно:
   • Имя клиента / компания
   • Кто обработал (менеджер)
   • Дата обработки
   • Результат (call_result)
   • Причина отказа (если "не интересно")
   • Комментарий менеджера
   • Количество попыток (CallAttempt)
   • Последнее КП (CommercialOfferEmailLog)
   • [Переглянути] [Скасувати] [Все одно додати]
4. ЕСЛИ НЕ НАЙДЕН → обычная обработка
```

### Дополнительно: Email дедупликация для КП
Перед отправкой КП проверить `CommercialOfferEmailLog` на тот же email за последние 30 дней. Показать кто отправлял и какой шаблон.
