# 📞 Интеграция IP-телефонии: исследование и план реализации

## Оглавление
1. [Зачем нужна IP-телефония](#1-зачем-нужна-ip-телефония)
2. [Обзор провайдеров в Украине](#2-обзор-провайдеров)
3. [Сравнительный анализ](#3-сравнительный-анализ)
4. [Технические требования](#4-технические-требования)
5. [Архитектура интеграции](#5-архитектура-интеграции)
6. [WebRTC софтфон](#6-webrtc-софтфон)
7. [Plan B: Бюджетные альтернативы](#7-бюджетные-альтернативы)
8. [Дорожная карта интеграции](#8-дорожная-карта)

---

## 1. Зачем нужна IP-телефония

### 1.1 Проблемы без IP-телефонии

| Проблема | Влияние |
|----------|---------|
| Менеджер звонит с личного телефона | Нет записи, нет контроля |
| Нельзя проверить качество звонков | Абуз системы баллов |
| Нет данных о длительности | КПД неточный |
| Нет статуса «на линии» | Не видно, работает ли менеджер |
| Клиент перезванивает — непонятно кому | Потерянные лиды |
| Нет автоматического определения результата | Ручной ввод |

### 1.2 Что даёт IP-телефония

1. **Запись всех звонков** — контроль качества
2. **Автоматический трекинг** — время, длительность, результат
3. **Click-to-call** — звонок в один клик из CRM
4. **Incoming routing** — входящие звонки на менеджера, закреплённого за клиентом
5. **Call scoring** — автоматическая оценка звонка (AI)
6. **Whisper/Barge-in** — возможность подсказывать менеджеру на линии
7. **IVR** — автоматическое голосовое меню
8. **Reports** — детальная статистика звонков
9. **Anti-fraud** — подтверждение, что звонок действительно был

### 1.3 Как это улучшает КПД

```
ТЕКУЩИЙ КПД:
  努力 (Effort) = активный_час + баллы
  ↓ Проблема: нет данных о реальных звонках

НОВЫЙ КПД с IP-телефонией:
  Effort = активный_час + баллы + РЕАЛЬНЫЕ_ЗВОНКИ
  
  call_effort = min(1.0, (total_call_minutes / 120) ^ 0.7)
  
  Это добавляет ТРЕТИЙ компонент в Effort:
  effort = min(2.5, effort_active + effort_points + call_effort * 0.5)
```

---

## 2. Обзор провайдеров в Украине

### 2.1 Binotel

| Параметр | Значение |
|----------|---------|
| Сайт | binotel.ua |
| Основан | 2011 |
| Специализация | Виртуальная АТС, CRM-интеграция |
| Запись звонков | ✅ Да |
| API | ✅ REST API |
| CRM интеграция | 40+ готовых, custom API |
| WebRTC (софтфон в браузере) | ✅ Да |
| Click-to-call | ✅ Да |
| IVR | ✅ Да |
| Цена | от 540 грн/мес за номер + 0.50 грн/мин |
| Бесплатный период | 14 дней |
| Плюсы | Надёжный, много интеграций |
| Минусы | Относительно дорогой, UI старого поколения |

#### Binotel API ключевые endpoints:
```
POST /api/2.0/stats/incoming-calls-for-period/
POST /api/2.0/stats/outgoing-calls-for-period/
POST /api/2.0/calls/make-call/
POST /api/2.0/calls/call-record-link/
Webhook: /api/2.0/callback/ — при каждом звонке
```

### 2.2 Ringostat

| Параметр | Значение |
|----------|---------|
| Сайт | ringostat.com |
| Специализация | Маркетинг-аналитика + телефония |
| Запись звонков | ✅ Да |
| API | ✅ REST API + Webhooks |
| CRM интеграция | 70+ готовых |
| WebRTC | ✅ Да (Ringostat Smart Phone) |
| Call tracking (коллтрекинг) | ✅ Лучший в Украине |
| AI скоринг звонков | ✅ Да (AI: tone, keywords) |
| Цена | от 1440 грн/мес (Starter) |
| Бесплатный период | 14 дней |
| Плюсы | Лучшая аналитика, AI, коллтрекинг |
| Минусы | Самый дорогой |

#### Ringostat API ключевые возможности:
```
GET /api/call-records — записи звонков
POST /api/calls/start — инициировать звонок
Webhook events:
  - call.start
  - call.answer
  - call.end
  - call.missed
Интеграция: автоматическое создание контакта в CRM
```

### 2.3 UniTalk

| Параметр | Значение |
|----------|---------|
| Сайт | unitalk.cloud |
| Специализация | IP-телефония + коллтрекинг |
| Запись звонков | ✅ Да |
| API | ✅ REST API |
| CRM интеграция | 40+ готовых |
| WebRTC | ✅ Да |
| Коллтрекинг | ✅ Да |
| Цена | от 470 грн/мес + минуты |
| Бесплатный период | 14 дней |
| Плюсы | Доступная цена, хороший API |
| Минусы | Менее развитая аналитика |

### 2.4 Другие провайдеры

| Провайдер | Цена (от) | API | Запись | Коммент |
|-----------|----------|-----|--------|---------|
| **Phonet** (phonet.ua) | 250 грн/мес | ✅ | ✅ | Бюджетный, базовые функции |
| **StreamTelecom** | 300 грн/мес | ✅ | ✅ | Для малого бизнеса |
| **VoIPTime** | 400 грн/мес | ✅ | ✅ | Контакт-центр |
| **A4** (a4.com.ua) | 500 грн/мес | Ограничен | ✅ | SIP-телефония |

---

## 3. Сравнительный анализ

### 3.1 Матрица сравнения

| Критерий | Вес | Binotel | Ringostat | UniTalk | Phonet |
|----------|-----|---------|-----------|---------|--------|
| Цена | 20% | 6/10 | 4/10 | 8/10 | 9/10 |
| API качество | 20% | 8/10 | 9/10 | 7/10 | 5/10 |
| Запись звонков | 15% | 9/10 | 9/10 | 8/10 | 7/10 |
| WebRTC софтфон | 15% | 8/10 | 9/10 | 7/10 | 4/10 |
| CRM интеграция | 10% | 8/10 | 9/10 | 7/10 | 5/10 |
| AI скоринг | 10% | 3/10 | 9/10 | 3/10 | 1/10 |
| Надёжность | 10% | 9/10 | 8/10 | 7/10 | 6/10 |
| **ИТОГО** | | **7.2** | **7.8** | **7.0** | **5.5** |

### 3.2 Рекомендация

> [!IMPORTANT]
> **Рекомендованный провайдер: UniTalk**
> 
> **Почему UniTalk, а не Ringostat (лидер)?**
> - UniTalk на ~70% дешевле Ringostat при аналогичном API
> - Достаточный функционал для текущей команды (3-6 менеджеров)
> - WebRTC софтфон доступен
> - Запись звонков входит в базовый пакет
> - API покрывает все необходимые интеграции
> 
> **Когда перейти на Ringostat?**
> - Когда команда вырастет до 10+ менеджеров
> - Когда понадобится AI скоринг звонков
> - Когда маркетинг-аналитика станет приоритетом

### 3.3 Бюджет (оценка для 4 менеджеров)

| Провайдер | Месячный бюджет | Включено |
|-----------|----------------|----------|
| **UniTalk** | ~2,500-3,500 грн/мес | 4 линии + запись + WebRTC |
| Binotel | ~3,500-5,000 грн/мес | 4 линии + запись + WebRTC |
| Ringostat | ~5,500-8,000 грн/мес | 4 линии + запись + AI + коллтрекинг |
| Phonet | ~1,500-2,000 грн/мес | 4 линии + запись (без WebRTC) |

---

## 4. Технические требования

### 4.1 Минимальные требования к провайдеру

1. ✅ REST API для программного управления звонками
2. ✅ Webhook для получения событий в реальном времени (call start, end, result)
3. ✅ Запись звонков с доступом по API
4. ✅ Click-to-call (инициирование звонка через API)
5. ✅ WebRTC софтфон (опционально, для звонков из браузера)
6. ✅ Идентификация менеджера по внутреннему номеру / SIP-аккаунту
7. ✅ Хранение записей минимум 30 дней

### 4.2 Архитектурные требования к нашей системе

```
Django Management App ←→ IP Telephony Provider
    ↓                           ↓
Webhook handler             REST API calls
    ↓                           ↓
- Сохранить звонок          - Инициировать звонок
- Обновить Client           - Получить запись
- Начислить баллы           - Получить статистику
- Обновить КПД              
```

---

## 5. Архитектура интеграции

### 5.1 Новые модели

```python
class TelephonyCall(models.Model):
    """Запись звонка из IP-телефонии."""
    
    class Direction(models.TextChoices):
        INCOMING = 'incoming', 'Вхідний'
        OUTGOING = 'outgoing', 'Вихідний'
    
    class Status(models.TextChoices):
        ANSWERED = 'answered', 'Відповів'
        MISSED = 'missed', 'Пропущений'
        BUSY = 'busy', 'Зайнято'
        FAILED = 'failed', 'Помилка'
    
    external_id = models.CharField(
        max_length=255, unique=True, db_index=True,
        verbose_name="ID от провайдера",
    )
    provider = models.CharField(
        max_length=30, default='unitalk',
        verbose_name="Провайдер",
    )
    
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='telephony_calls',
    )
    
    direction = models.CharField(
        max_length=10, choices=Direction.choices,
    )
    status = models.CharField(
        max_length=10, choices=Status.choices,
    )
    
    caller_number = models.CharField(max_length=50)
    callee_number = models.CharField(max_length=50)
    caller_number_normalized = models.CharField(
        max_length=50, blank=True, db_index=True,
    )
    callee_number_normalized = models.CharField(
        max_length=50, blank=True, db_index=True,
    )
    
    # Связь с Contact
    client = models.ForeignKey(
        Client, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='telephony_calls',
    )
    
    started_at = models.DateTimeField(db_index=True)
    answered_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    
    duration_seconds = models.PositiveIntegerField(default=0)
    talk_duration_seconds = models.PositiveIntegerField(default=0)
    wait_duration_seconds = models.PositiveIntegerField(default=0)
    
    recording_url = models.URLField(blank=True)
    recording_local = models.FileField(
        upload_to='telephony/recordings/',
        blank=True, null=True,
    )
    
    score = models.PositiveSmallIntegerField(
        null=True, blank=True,
        verbose_name="Оценка звонка (1-5)",
    )
    scored_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='scored_calls',
    )
    
    raw_data = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Телефонний дзвінок"
        verbose_name_plural = "Телефонні дзвінки"
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['manager', '-started_at']),
            models.Index(fields=['status', '-started_at']),
            models.Index(fields=['caller_number_normalized']),
            models.Index(fields=['callee_number_normalized']),
        ]
```

### 5.2 Webhook Handler

```python
# telephony_views.py
import hmac
import hashlib

@csrf_exempt
@require_POST
def telephony_webhook(request, provider_token):
    """
    POST /telephony/webhook/<provider_token>/
    
    Обрабатывает events от IP-телефонии:
    - call.start → создать TelephonyCall
    - call.answer → обновить времена
    - call.end → финализировать, начислить баллы
    """
    # 1. Verify token
    if provider_token != settings.TELEPHONY_WEBHOOK_TOKEN:
        return HttpResponseForbidden()
    
    # 2. Parse event
    data = json.loads(request.body)
    event_type = data.get('event')
    
    if event_type == 'call.start':
        handle_call_start(data)
    elif event_type == 'call.answer':
        handle_call_answer(data)
    elif event_type == 'call.end':
        handle_call_end(data)
    
    return JsonResponse({'ok': True})


def handle_call_end(data):
    """При завершении звонка."""
    call_id = data['call_id']
    call = TelephonyCall.objects.get(external_id=call_id)
    
    call.ended_at = parse_datetime(data['ended_at'])
    call.duration_seconds = data['duration']
    call.talk_duration_seconds = data.get('talk_duration', 0)
    call.recording_url = data.get('recording_url', '')
    call.status = 'answered' if call.talk_duration_seconds > 0 else 'missed'
    call.save()
    
    # Auto-match to Client
    phone_norm = normalize_phone(
        call.callee_number if call.direction == 'outgoing' else call.caller_number
    )
    client = Client.objects.filter(
        phone_normalized=phone_norm, owner=call.manager
    ).first()
    if client:
        call.client = client
        call.save(update_fields=['client'])
    
    # Update daily stats
    update_call_stats(call.manager, call)
```

### 5.3 Click-to-Call интеграция

```python
# telephony_service.py
import requests

def initiate_call(manager, phone_number, provider='unitalk'):
    """
    Инициирует звонок: сначала звонит менеджеру,
    затем после ответа — клиенту.
    """
    config = get_telephony_config(provider)
    
    # Определяем внутренний номер менеджера
    manager_ext = manager.profile.telephony_extension
    
    response = requests.post(
        f"{config['api_url']}/calls/make",
        headers={'Authorization': f"Bearer {config['api_key']}"},
        json={
            'from': manager_ext,
            'to': phone_number,
            'caller_id': config['company_number'],
        },
    )
    
    if response.status_code == 200:
        return response.json()['call_id']
    else:
        raise TelephonyError(response.text)
```

### 5.4 Интеграция с КПД

```python
# В stats_service.py — добавить call-based метрики

def get_call_metrics(user, day_start, day_end):
    """Метрики звонков из IP-телефонии."""
    calls = TelephonyCall.objects.filter(
        manager=user,
        started_at__gte=day_start,
        started_at__lt=day_end,
    )
    
    total_calls = calls.count()
    answered_calls = calls.filter(status='answered').count()
    total_talk_minutes = calls.aggregate(
        total=Sum('talk_duration_seconds')
    )['total'] or 0
    total_talk_minutes = total_talk_minutes / 60
    
    avg_call_duration = (
        calls.filter(status='answered').aggregate(
            avg=Avg('talk_duration_seconds')
        )['avg'] or 0
    )
    
    return {
        'total_calls': total_calls,
        'answered_calls': answered_calls,
        'answer_rate': answered_calls / max(1, total_calls),
        'total_talk_minutes': round(total_talk_minutes, 1),
        'avg_call_duration_seconds': round(avg_call_duration),
    }
```

---

## 6. WebRTC софтфон

### 6.1 Встроенный софтфон в CRM

Вместо отдельного приложения, менеджер звонит прямо из браузера:

```
╭─────────────────────────────╮
│  📞 Софтфон        [▼ пауза]│
│                              │
│  ╭──────────────────────╮   │
│  │ +380991234567        │   │
│  │ Магазин "Сонячний"   │   │
│  │                      │   │
│  │    ⏱️ 02:34          │   │
│  │    🟢 На лінії       │   │
│  │                      │   │
│  │  [🔇 Mute] [⏸️ Hold] │   │
│  │  [📞 Transfer]       │   │
│  │                      │   │
│  │  [🔴 Завершити]      │   │
│  ╰──────────────────────╯   │
│                              │
│  📝 Після дзвінка:          │
│  Результат: [▼ Оберіть   ]  │
│  Нотатка: [_____________]   │
│  Перезвон: [📅 Обрати дату] │
│                              │
│  [💾 Зберегти результат]    │
╰─────────────────────────────╯
```

### 6.2 After-Call Processing

После каждого звонка менеджер **обязан** выбрать результат:
1. Результат звонка (call_result)
2. Заметка (опционально)
3. Запланировать перезвон (опционально)

Без этого следующий звонок заблокирован (soft lock — можно пропустить через 30 сек).

### 6.3 Admin: Прослушивание звонков

```
╭─ 📞 Журнал дзвінків (Олена К.) ────────────────────╮
│                                                      │
│ 📞 14:23  Вихідний → +380991234567  ⏱ 3:45  ⭐⭐⭐⭐ │
│           "Магазин Сонячний" → Замовлення             │
│           [▶️ Прослухати] [📋 Деталі]                │
│                                                      │
│ 📞 14:15  Вихідний → +380997654321  ⏱ 1:12  ⭐⭐    │
│           "Style Store" → Не цікавить                │
│           [▶️ Прослухати] [📋 Деталі]                │
│                                                      │
│ 📞 14:08  Вихідний → +380995551234  ⏱ 0:00  —      │
│           "ФОП Петренко" → Не відповідає             │
│           [❌ Немає запису]                           │
│                                                      │
│ Середня тривалість: 2:18 │ Відповіли: 67%           │
│ Загалом сьогодні: 23 дзвінки │ 34 хв розмов          │
╰──────────────────────────────────────────────────────╯
```

---

## 7. Бюджетные альтернативы (Plan B)

Если бюджет ограничен и IP-телефония пока недоступна:

### 7.1 Telegram Call Tracking (бесплатно)

Менеджер звонит через обычный телефон, но **фиксирует** звонок в системе:
- Нажимает «Начав дзвінок» в CRM перед звонком
- Нажимает «Завершив дзвінок» после
- Система засекает длительность
- Менеджер обязательно вводит результат

**Плюсы:** Бесплатно, не требует провайдера
**Минусы:** Нет записи, можно «фейковать» звонки

### 7.2 Google Voice + Webhook (низкобюджетно)

**Не доступно в Украине напрямую**, но через VPN/SIP-шлюз:
- Google Voice → SIP trunk → CRM webhook
- Запись через сторонний сервис

### 7.3 Самодельный VoIP (open-source)

- **FreePBX** / **Asterisk** — бесплатная АТС
- Установить на VPS (150-200 грн/мес)
- SIP trunk от украинского оператора (от 100 грн/мес)
- WebRTC через **JsSIP** или **SIP.js**

**Оценочный бюджет: 500-700 грн/мес** (дешевле любого облачного провайдера)
**Минусы:** Требует технической поддержки, настройки, troubleshooting

### 7.4 Сравнение Plan B вариантов

| Вариант | Стоимость | Запись | Click-to-call | Сложность |
|---------|----------|-------|---------------|-----------|
| Telegram tracking | 0 грн | ❌ | ❌ | Низкая |
| FreePBX + SIP | ~600 грн/мес | ✅ | ✅ | Высокая |
| UniTalk (рекомендован) | ~2,500 грн/мес | ✅ | ✅ | Средняя |
| Ringostat (премиум) | ~5,500 грн/мес | ✅ | ✅ + AI | Средняя |

---

## 8. Дорожная карта интеграции

### Этап 1: Подготовка (1 неделя)
- [ ] Выбрать провайдера (рекомендация: UniTalk)
- [ ] Зарегистрировать аккаунт, получить тестовый период
- [ ] Создать модель `TelephonyCall` и миграцию
- [ ] Настроить webhook endpoint

### Этап 2: Базовая интеграция (2 недели)
- [ ] Webhook handler для call events (start, answer, end)
- [ ] Click-to-call API из CRM
- [ ] Auto-matching звонков с Client (по phone_normalized)
- [ ] Отображение звонков в профиле клиента

### Этап 3: Записи и аналитика (1-2 недели)
- [ ] Загрузка и хранение записей звонков
- [ ] Плеер для прослушивания (admin)
- [ ] Call log view (журнал звонков)
- [ ] Call metrics в статистике (total_calls, talk_minutes, answer_rate)

### Этап 4: Интеграция с КПД (1 неделя)
- [ ] Добавить call_effort в формулу КПД
- [ ] Минимальная длительность звонка для начисления баллов (>15 сек)
- [ ] Anti-fraud: сверить кол-во Client entries с реальными звонками
- [ ] Dashboard метрик звонков

### Этап 5: Продвинутые функции (2-3 недели)
- [ ] WebRTC софтфон в CRM (если провайдер поддерживает)
- [ ] After-call processing form
- [ ] Call scoring (admin оценка 1-5)
- [ ] Incoming call routing (входящие → закреплённый менеджер)
- [ ] Whisper mode (подсказки на линии)

### Этап 6: AI и автоматизация (будущее)
- [ ] Speech-to-text транскрипция
- [ ] Автоматическое определение тональности (sentiment)
- [ ] Keyword detection (ключевые слова в разговоре)
- [ ] Автоматическое определение call_result по содержимому
- [ ] AI coaching: подсказки менеджеру на основе анализа лучших звонков

---

## 9. Углублённый анализ — дополнения v2

### 9.1 Существующая инфраструктура для IP-телефонии

Из deep-dive обнаружено, что несколько компонентов **уже готовы** для интеграции:

| Компонент | Статус | Что нужно для интеграции |
|-----------|--------|-------------------------|
| Telegram bot (`_send_telegram_message()`) | ✅ Готов | Добавить call notifications |
| Webhook endpoint architecture | ✅ Есть паттерн | `telephony_webhook` по аналогии с TG webhook |
| `phone_normalized` в Client | ✅ Есть | Auto-matching по номеру |
| `phone_normalized` в ManagementLead | ✅ Есть | Кросс-matching Lead → Call |
| `ManagementDailyActivity` | ✅ Есть | Добавить `call_minutes` поле |
| `normalize_phone()` в models.py | ✅ Есть | Использовать для callee/caller normalization |
| `_load_env_tokens()` | ✅ Есть | Добавить TELEPHONY_API_KEY, TELEPHONY_WEBHOOK_TOKEN |

### 9.2 Activity Pulse как валидация звонков

Текущий activity pulse (POST каждые 30 сек) может использоваться для **кросс-валидации** звонков:

```python
# Пример: Менеджер заявляет 45 звонков за день,
# но Activity Pulse показывает только 15 минут на сайте.
# → Аномалия! Менеджер, вероятнее всего, добавляет фейковые контакты.

def validate_call_claim(user, date):
    activity = ManagementDailyActivity.objects.filter(
        user=user, date=date
    ).first()
    
    clients_added = Client.objects.filter(
        owner=user, created_at__date=date
    ).count()
    
    if activity and activity.active_seconds < 1800:  # < 30 минут
        if clients_added > 15:
            # 🚨 Аномалия: 15+ контактов за < 30 минут на сайте
            flag_suspicious_activity(user, date, 'high_clients_low_activity')
```

### 9.3 Дублирование normalize_phone — КРИТИЧНО для IP-телефонии

Обнаружено **3 места** с нормализацией телефонов:
1. `models.py` → `normalize_phone()` — в `Client.save()` и `ManagementLead.save()`
2. `forms.py` → `normalize_ua_phone()` — в `CommercialOfferEmailForm`
3. `parser_service.py` → использует `normalize_phone()` из models

> [!CAUTION]
> Перед интеграцией IP-телефонии **ОБЯЗАТЕЛЬНО** нужно:
> 1. Вынести `normalize_phone()` в `/management/utils.py`
> 2. Удалить `normalize_ua_phone()` из `forms.py`
> 3. Все 3 точки (models, forms, parser) должны использовать **один** `normalize_phone()`
> 4. `TelephonyCall` должен использовать тот же `normalize_phone()` для `caller_number_normalized` и `callee_number_normalized`

Без этого **auto-matching** звонков с клиентами будет ненадёжным.

### 9.4 Стоимостная оптимизация: что можно сделать БЕСПЛАТНО

До покупки IP-телефонии можно получить **80% ценности** за 0 грн:

| Функция | Реализация | Стоимость | % ценности |
|---------|-----------|-----------|------------|
| Manual call tracking (кнопка «Дзвоню/Завершив») | JavaScript timer + AJAX | 0 грн | 30% |
| After-call form (обязательный итог) | Modal после timer stop | 0 грн | 20% |
| Cross-validation (activity vs contacts) | Python validation | 0 грн | 15% |
| Call duration estimate | Timer в браузере | 0 грн | 10% |
| Telegram notification о пропущенных | Celery task | 0 грн | 5% |
| **ИТОГО без IP-телефонии** | | **0 грн** | **80%** |

### 9.5 Обновлённый Этап 0: «Бесплатная подготовка»

Добавить этап до покупки провайдера:

- [ ] Вынести `normalize_phone()` в `utils.py` (DRY)
- [ ] Добавить manual call tracking (timer + AJAX)
- [ ] Добавить after-call form (modal с обязательным call_result)
- [ ] Добавить `call_duration_estimated` поле в Client (или ContactInteraction)
- [ ] Cross-validation: activity pulse vs client count (anomaly detection)
- [ ] Создать модель `TelephonyCall` заранее (без данных)

Это позволит **начать собирать данные** о звонках бесплатно и **подготовить архитектуру** для полноценной интеграции.

---

## Deep Dive v3 — Молекулярный анализ телефонии

### Точки интеграции с `get_stats_payload()`

Молекулярный анализ `stats_service.py` выявил **готовую инфраструктуру** для интеграции:

```python
# get_stats_payload() уже считает:
metrics_now = {
    "processed": processed,          # Количество обработанных
    "points": int(points or 0),      # Баллы
    "active_seconds": active_seconds, # <-- СЮДА добавить call_seconds
    "followups_total": fu_total,     # Передзвоны
    "followups_missed": fu_missed,   # <-- call_missed можно добавить
    "success_weighted": ...,         # <-- call_result влияет на это
    ...
}
```

### Расширение KPD формулы для звонков

Текущая формула `compute_kpd()` может быть расширена **без ломания**:

```python
# Новый sub-компонент: Call Efficiency (0..0.4)
call_count = float(metrics.get("telephony_calls", 0) or 0)
call_avg_duration = float(metrics.get("telephony_avg_duration", 0) or 0)
call_success_rate = float(metrics.get("telephony_success_rate", 0) or 0)

call_efficiency = min(0.4,
    min(0.15, call_count / 20 * 0.15) +           # 20 звонков = макс
    min(0.1, call_avg_duration / 300 * 0.1) +      # 5 мин средний = макс
    min(0.15, call_success_rate * 0.15)             # 100% success = макс
)

# Увеличить max_ops: 1.2 → 1.6
ops = existing_ops + call_efficiency
```

### `TelephonyCall` модель → Advice engine интеграция

Новые категории советов (generate_advice):

| # | Категория | Тон | Условие |
|---|-----------|-----|---------|
| 9 | Низкая частота звонков | neutral | calls/day < 10 при processed > 15 |
| 10 | Короткие звонки | bad | avg_duration < 60s на 20+ звонках |
| 11 | Высокая конверсия звонков | good | call_success_rate > 40% |
| 12 | Много неотвеченных | neutral | no_answer_rate > 50% |

### Данные для Dashboard (уже собираемые vs новые)

| Метрика | Статус | Источник |
|---------|--------|----------|
| Количество контактов | ✅ Уже есть | clients_qs.count() |
| Время активности | ✅ Уже есть | ManagementDailyActivity |
| Количество звонков | 🆕 Нужно | TelephonyCall.count() |
| Средняя длительность | 🆕 Нужно | TelephonyCall.avg(duration) |
| Записи разговоров | 🆕 Нужно | TelephonyCall.recording_url |
| Shipments | ✅ Уже есть | ShopShipment |
| Inventory | ✅ Уже есть | ShopInventoryMovement |
| КП emails | ✅ Уже есть | CommercialOfferEmailLog |
| Накладные | ✅ Уже есть | WholesaleInvoice |
| Коммуникации | ✅ Уже есть | ShopCommunication |

> [!TIP]
> **Ключевой инсайт v3**: `get_stats_payload()` уже обрабатывает **10 типов данных** (clients, followups, reports, CP emails, invoices, shops, shipments, inventory, communications, activity). Добавить 11-й тип (telephony) — **минимальное изменение** (~20-30 строк кода).

### Обновлённая очередь интеграции

```
Phase 1: Data Collection (0 cost)
  ✅ TelephonyCall модель уже создана
  → Добавить manual call timer в home.html
  → Добавить after-call form (modal)
  → Считать TelephonyCall в get_stats_payload()

Phase 2: Call Analytics (0 cost)
  → Добавить call_efficiency в compute_kpd()
  → Добавить 4 новых advice категории
  → Dashboard: call charts (sparklines уже поддерживаются)

Phase 3: VoIP Integration (~$50-100/мес)
  → API интеграция с Binotel/Ringostat
  → Автозаполнение TelephonyCall
  → Click-to-call из home.html
  → Автоматическая запись

Phase 4: AI Analysis (~$20-50/мес)
  → Speech-to-text для записей
  → Sentiment analysis
  → Автоматический scoring качества разговора
```

---

## Синхронизация с workflow менеджера (обновление от владельца)

> [!IMPORTANT]
> **Текущая реальность**: Менеджеры звонят **с личных телефонов**. Корпоративной телефонии НЕТ. Это значит что **звонки не верифицируемы** системой.

### Влияние на HES (Hybrid Efficiency System)

В [08_EFFICIENCY_SYSTEM.md](./08_EFFICIENCY_SYSTEM.md) звонки классифицированы как **Tier 3 — Self-Reported** (низкая ценность):

| Канал | HES Channel Multiplier | Причина |
|-------|----------------------|---------|
| Email КП (CommercialOfferEmailLog) | 1.0 (100%) | Полностью верифицируемо |
| Звонок с записью (будущее, IP-телефония) | 1.0 (100%) | Верифицируемо |
| Мессенджер КП | 0.5 (50%) | Не верифицируемо |
| Звонок без записи (текущее) | 0.4 (40%) | Self-reported |

### Приоритет IP-телефонии в свете HES

Внедрение IP-телефонии **повысит точность HES**:
- Звонки станут Tier 2 (Verifiable) вместо Tier 3 (Self-Reported)
- Channel multiplier вырастет с 0.4 до 1.0 (×2.5)
- Это мотивирует менеджеров **реально звонить**, а не симулировать

### Связанные документы
- **[07_MANAGER_WORKFLOW.md](./07_MANAGER_WORKFLOW.md)** — Каналы связи, антиабьюз
- **[08_EFFICIENCY_SYSTEM.md](./08_EFFICIENCY_SYSTEM.md)** — HES формула, channel multipliers
