# Gemini Key Pools + Model Chains — Implementation Plan (Phase 1)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline). Steps use checkbox (`- [ ]`).

**Goal:** Централизованный менеджер Gemini-ключей: пулы по ролям (основной+страховка), приоритетный каскад заимствования, цепочки моделей (gen-3 для чата/звонков, 2.5 для grounding чекера), авто-переключение по 429/503 с обратным отсчётом до сброса (полночь PT), авто-чекинг чекера и UI-панель статуса ключей.

**Architecture:** Новый сервис `management/services/gemini_keys.py` хранит конфиг ROLE_KEY_POOLS (own+borrow) и ROLE_MODEL_CHAINS, ведёт состояние ключей в БД (`GeminiKeyState`) и отдаёт итератор (key,model)-комбинаций в правильном порядке. Все вызовы Gemini (бот=chat, анализ звонков=management, чекер=checker) идут через единый исполнитель, который на 429 уводит КЛЮЧ в кулдаун (квота на проект — общая для всех моделей), на 503 уводит МОДЕЛЬ в краткий overload-кэш (модель перегружена на любом ключе), на 404 запоминает несуществующую модель. Авто-возврат на основной ключ/модель происходит автоматически по истечении кулдауна. Чекер на 429 ставит джобу на паузу с обратным отсчётом и (если включён auto_recheck) авто-возобновляется cron-командой.

**Tech Stack:** Django 5 (Python 3.13), прямой REST к generativelanguage.googleapis.com/v1beta, zoneinfo America/Los_Angeles для расчёта сброса, существующий движок call_ai_analysis.

---

## Установленные факты (живые тесты на 6 ключах-проектах + Context7)

- Квота считается **на проект, не на ключ**; дневной RPD сбрасывается в **полночь America/Los_Angeles (PT)**.
- Google Search **grounding бесплатен только на `gemini-2.5-flash`** (500 RPD/проект). На gen-3 моделях grounded = 429 «billing» (платно).
- Реальные API-ID (ListModels): существуют `gemini-3.5-flash` (часто 503 перегруз), `gemini-3.1-pro-preview` (429 без биллинга), `gemini-3.1-flash-lite` (стабильно 200), `gemini-2.5-flash` (200, grounding free). НЕ существуют: `gemini-3-flash`, `gemini-3.1-flash`, `gemini-3.1-pro` (без `-preview`).
- 429 типы: per-day (quotaId *PerDay*, сообщение plan/billing) → кулдаун до полуночи PT; per-minute (*PerMinute*, RetryInfo.retryDelay) → кулдаун ~retryDelay; «prepayment credits depleted» → платный проект без денег, длинный кулдаун + флаг topup.

## Конфиг ролей (по требованиям пользователя)

```
ROLE_KEY_POOLS = {
  "chat":       {"own": ["GEMINI_API", "GEMINI_API2"], "borrow": ["GEMINI_API5", "GEMINI_API6"]},
  "management": {"own": ["GEMINI_API3", "GEMINI_API4"], "borrow": ["GEMINI_API5", "GEMINI_API6"]},
  "checker":    {"own": ["GEMINI_API5", "GEMINI_API6"], "borrow": []},
}
ROLE_MODEL_CHAINS = {
  "chat":       ["gemini-3.5-flash", "gemini-3.1-pro-preview", "gemini-3.1-flash-lite"],
  "management": ["gemini-3.5-flash", "gemini-3.1-pro-preview", "gemini-3.1-flash-lite"],
  "checker":    ["gemini-3.5-flash", "gemini-2.5-flash"],
}
ATTEMPTS_PER_MODEL = {"chat": 3, "management": 3, "checker": 1}
```
Чат/менеджмент НИКОГДА не опускаются ниже gen-3. Чекер может до 2.5 (единственная роль). Все значения переопределяемы через ENV/settings; ручные ключи (InstagramBotSettings.custom_gemini_key, LeadCheckerSettings.gemini_api_key) приоритетнее пула.

## Структура файлов

**Создаём:**
- `twocomms/management/services/gemini_keys.py` — менеджер пулов (конфиг, состояние, итератор, отчёты, статус).
- `twocomms/management/management/commands/checker_tick.py` — cron-команда авто-чекинга.
- `twocomms/management/tests_gemini_keys.py` — тесты менеджера.

**Модифицируем:**
- `twocomms/management/models.py` — модель `GeminiKeyState`; поля `auto_recheck`, `auto_recheck_batch` в `LeadCheckerSettings`.
- `twocomms/management/services/call_ai_analysis.py` — единый исполнитель через gemini_keys; `gemini_generate_json(role=...)`, `gemini_generate_grounded(role='checker')`.
- `twocomms/management/services/instagram_bot.py` — `gemini_generate` через пул role='chat'.
- `twocomms/management/services/lead_check_job.py` — пауза по 429, авто-возобновление.
- `twocomms/management/checker_views.py` + `checker.html` — панель статуса ключей, тумблер auto_recheck.
- `twocomms/management/tests_checker_*.py` — обновить под новые сигнатуры.

---

## Task 2: Модель GeminiKeyState + поля auto_recheck

**Files:** Modify `models.py`; Test `tests_gemini_keys.py`.

Модель:
```python
class GeminiKeyState(models.Model):
    key_name = models.CharField(max_length=40, unique=True)
    role_hint = models.CharField(max_length=20, blank=True)
    cooldown_until = models.DateTimeField(null=True, blank=True, db_index=True)
    cooldown_scope = models.CharField(max_length=10, blank=True)  # minute|day|topup
    last_status = models.CharField(max_length=20, blank=True)
    last_429_at = models.DateTimeField(null=True, blank=True)
    last_ok_at = models.DateTimeField(null=True, blank=True)
    requests_today = models.PositiveIntegerField(default=0)
    day_date = models.DateField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    @classmethod
    def get(cls, key_name): obj,_=cls.objects.get_or_create(key_name=key_name); return obj
```
LeadCheckerSettings += `auto_recheck = BooleanField(default=False)`, `auto_recheck_batch = PositiveIntegerField(default=25)`.

Тесты: дефолты, get_or_create идемпотентность, доступность при пустом cooldown.

## Task 3: Сервис gemini_keys.py

- `next_midnight_pt(now_utc)` → datetime следующей полуночи PT в UTC.
- `parse_429(status, body)` → (scope, seconds): minute/day/topup.
- `is_available(state, now)` → cooldown_until пуст или в прошлом.
- `mark_429(key_name, scope, seconds)`, `mark_success(key_name)`, `mark_model_overloaded(model, seconds)`, `is_model_overloaded(model)`.
- `iter_attempts(role, now)` → yield (key_name, key_value, model): по порядку own→borrow (только доступные ключи, основной первым), для каждого ключа — модели из ROLE_MODEL_CHAINS (кроме overloaded/404). ENV-значения ключей резолвятся из os.environ.
- `pool_status(role|all)` → список статусов для UI (available/cooldown, seconds_remaining, reason, requests_today).

Тесты: расчёт midnight PT, parse_429 (minute/day/topup), каскад own→borrow при кулдауне основного, пропуск overloaded-модели, авто-возврат после истечения.

## Task 4: Рефактор call_ai_analysis.py

- Заменить `_resolve_models`/`DEFAULT_MODEL_CHAIN`/`GROUNDED_MODEL_CHAIN` на gemini_keys.
- `_run_with_pool(role, payload, *, manual_key=None, grounded=False)`: перебор `iter_attempts(role)`; на 200 → mark_success, вернуть; 429 → parse+mark_429(key), след. ключ; 503/таймаут → mark_model_overloaded(model) + ретрай в пределах ATTEMPTS_PER_MODEL, затем след. модель; 404 → запомнить, след. модель. manual_key (ручной) пробуется первым, вне пула.
- `gemini_generate_json(system, user, *, role="management", ...)`, `gemini_generate_grounded(system, user, *, role="checker", api_key=None, ...)`, `_gemini_analyze(...)` → role="management".

Тесты с моками requests: 200, 429-day (кулдаун до PT), 429-minute, 503→fallback модели, 404→skip, manual_key приоритет.

## Task 5: Подключить роли

- `instagram_bot.gemini_generate`: если `gemini_source==CUSTOM` → ручной ключ; иначе пул role='chat' через новый исполнитель (модель из цепочки чата, не s.gemini_model). Сохранить urllib? — перейти на общий исполнитель из call_ai_analysis для единообразия 429-учёта.
- call analysis → role='management' (уже).
- checker → role='checker' (уже), LeadCheckerSettings.gemini_api_key как manual_key.

## Task 6: Авто-чекинг чекера

- `checker_tick` command: если LeadCheckerSettings.auto_recheck и есть доступный ключ checker-пула и есть непроверенные лиды → обработать auto_recheck_batch шагов активной/новой авто-джобы; иначе выход. Идемпотентно, безопасно для частого cron.
- lead_check_job.run_step: на исчерпание ключей (acquire вернул None) → пауза джобы + stop_reason='keys_cooldown' + сохранить ближайший cooldown_until.
- UI: тумблер «Авто-чекінг» + поле batch.
- Деплой: добавить cron (каждые 5 мин) `manage.py checker_tick`.

## Task 7: UI-панель «Gemini ключі»

- Эндпоинт `management_gemini_keys_status` → pool_status(all).
- Панель в checker.html: по ключу — роль, статус (✅/⏳ до HH:MM PT, лишилось N), requests_today, причина, флаг topup. JS-таймер обратного отсчёта. Автообновление каждые 30с.

## Task 8: Тесты, деплой, живая проверка

- Полный прогон management-тестов; makemigrations --check.
- Деплой: migrate (новые миграции), collectstatic если нужно, cron checker_tick, restart.
- Живая проверка: статус ключей на проде, тестовый чек 3-5 лидов (должен сесть на gemini-2.5-flash grounding на checker-ключах), проверка бота (chat-цепочка).

---

## Self-Review
- Роли/пулы/цепочки — из требований пользователя (chat приоритет, borrow checker-ключей; management own 3/4; checker only 5/6 + 2.5). ✅
- Никогда ниже gen-3 для chat/management; checker до 2.5. ✅
- 429-типы (minute/day/topup) + обратный отсчёт до PT + авто-возврат. ✅
- Авто-чекинг тумблером + cron + пауза/возобновление. ✅
- UI статус + отсчёт. ✅
- Phase 2 (история пользователя бота + дожим) — отдельным заходом, поверх готовой key-инфры.
