# AI-чекер спарсенных аккаунтов — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Добавить в субдомен менеджмента вкладку «Чекер», которая через Gemini (с Google Search grounding) оценивает спарсенные `ManagementLead` по 10 критериям, ставит балл 0-100, разбор бренда и рекомендацию по каналу сотрудничества, с браузер-driven движком старт/стоп/прогресс и красивым UI в стиле management.

**Architecture:** Браузер-driven stepping (как существующий парсер — на Passenger нет воркера): один лид на `step`, результат сразу в БД. Сервис скоринга вызывает один grounded-запрос к Gemini на лид, парсит JSON из текста, маппит в полосы вердикта и в `niche_status`. Новые модели `LeadAICheck`, `LeadCheckJob`, `LeadCheckRuntimeLock`, `LeadCheckerSettings` + кэш-поля на `ManagementLead`. UI повторяет паттерн `parsing.html`.

**Tech Stack:** Django 5 (Python 3.13), существующий Gemini REST-движок в `management/services/call_ai_analysis.py`, `requests` + `BeautifulSoup`(если есть)/regex для фетча сайта, ванильный JS (fetch + polling), `management.css`.

**Соглашения проекта:**
- Тесты: `SECRET_KEY=test_local_secret python manage.py test management.<module>` из каталога `twocomms/`. Стиль тестов — `django.test.TestCase`/`SimpleTestCase`, мок Gemini через `unittest.mock.patch`.
- Доступ к API чекера — `_require_admin_json` (Top Manager+), как в `parsing_views.py`.
- Все строки UI — украинский (как в парсере). Ответы пользователю — русский.
- Источник CSS истины для субдомена — `twocomms/twocomms_django_theme/static/css/management.css` (НЕ styles.css).

---

## Структура файлов

**Создаём:**
- `twocomms/management/services/lead_checker.py` — скоринг одного лида (контекст, фетч сайта, Gemini-вызов, парсинг, маппинг полос).
- `twocomms/management/services/lead_check_job.py` — движок job (start/step/pause/resume/stop/status, lock, выборка лидов, счётчики).
- `twocomms/management/checker_views.py` — HTTP-вьюхи (страница + JSON API).
- `twocomms/management/templates/management/checker.html` — UI (extends base.html).
- `twocomms/management/tests_checker_scoring.py` — тесты сервиса скоринга.
- `twocomms/management/tests_checker_job.py` — тесты движка job.
- `twocomms/management/tests_checker_views.py` — тесты вьюх/доступа.
- `twocomms/management/tests_checker_gemini.py` — тесты grounded-хелпера и парсинга.

**Модифицируем:**
- `twocomms/management/models.py` — новые модели + кэш-поля на `ManagementLead`.
- `twocomms/management/services/call_ai_analysis.py` — публичный `gemini_generate_grounded(...)` + skip-on-400-tools.
- `twocomms/management/urls.py` — маршруты `management_checker*`.
- `twocomms/management/templates/management/base.html` — вкладка «Чекер» в `header-tabs`.
- `twocomms/twocomms_django_theme/static/css/management.css` — стили чекера (хвост файла).

---

## Этап 1. Модели данных

### Task 1: Кэш-поля AI на `ManagementLead`

**Files:**
- Modify: `twocomms/management/models.py` (класс `ManagementLead`, рядом с `niche_status`)
- Test: `twocomms/management/tests_checker_scoring.py`

- [ ] **Step 1: Написать падающий тест**

Создать файл `twocomms/management/tests_checker_scoring.py`:

```python
from django.test import TestCase

from management.models import ManagementLead


class ManagementLeadAICacheFieldsTests(TestCase):
    def test_ai_cache_fields_default_empty(self):
        lead = ManagementLead.objects.create(shop_name="Test Shop", phone="0501112233")
        self.assertIsNone(lead.ai_score)
        self.assertEqual(lead.ai_verdict, "")
        self.assertIsNone(lead.ai_checked_at)

    def test_ai_cache_fields_persist(self):
        from django.utils import timezone
        lead = ManagementLead.objects.create(shop_name="Test Shop", phone="0501112233")
        lead.ai_score = 82
        lead.ai_verdict = "fit"
        lead.ai_checked_at = timezone.now()
        lead.save(update_fields=["ai_score", "ai_verdict", "ai_checked_at"])
        lead.refresh_from_db()
        self.assertEqual(lead.ai_score, 82)
        self.assertEqual(lead.ai_verdict, "fit")
        self.assertIsNotNone(lead.ai_checked_at)
```

- [ ] **Step 2: Запустить тест — должен упасть**

Run: `cd twocomms && SECRET_KEY=test_local_secret python manage.py test management.tests_checker_scoring -v 2`
Expected: FAIL (`AttributeError: 'ManagementLead' object has no attribute 'ai_score'` или ошибка миграций).

- [ ] **Step 3: Добавить поля в модель**

В `twocomms/management/models.py`, в класс `ManagementLead`, сразу после поля `niche_status`:

```python
    ai_score = models.PositiveSmallIntegerField(_("AI-оцінка"), null=True, blank=True, db_index=True)
    ai_verdict = models.CharField(_("AI-вердикт"), max_length=10, blank=True, db_index=True)
    ai_checked_at = models.DateTimeField(_("AI-перевірено"), null=True, blank=True, db_index=True)
```

- [ ] **Step 4: Создать миграцию**

Run: `cd twocomms && SECRET_KEY=test_local_secret python manage.py makemigrations management`
Expected: создан файл `management/migrations/00XX_managementlead_ai_cache_fields.py` (или с авто-именем).

- [ ] **Step 5: Запустить тест — должен пройти**

Run: `cd twocomms && SECRET_KEY=test_local_secret python manage.py test management.tests_checker_scoring -v 2`
Expected: PASS (2 теста).

- [ ] **Step 6: Commit**

```bash
git add twocomms/management/models.py twocomms/management/migrations/ twocomms/management/tests_checker_scoring.py
git commit -m "feat(checker): кэш-поля AI на ManagementLead"
```

---

### Task 2: Модель `LeadCheckerSettings` (singleton с ключом Gemini)

**Files:**
- Modify: `twocomms/management/models.py` (в конец файла, рядом с парсерными моделями)
- Test: `twocomms/management/tests_checker_job.py`

- [ ] **Step 1: Написать падающий тест**

Создать файл `twocomms/management/tests_checker_job.py`:

```python
from django.test import TestCase

from management.models import LeadCheckerSettings


class LeadCheckerSettingsTests(TestCase):
    def test_load_creates_singleton(self):
        obj = LeadCheckerSettings.load()
        self.assertEqual(obj.pk, 1)
        self.assertEqual(obj.gemini_api_key, "")
        self.assertEqual(obj.requests_per_minute, 8)

    def test_load_is_idempotent(self):
        a = LeadCheckerSettings.load()
        a.gemini_api_key = "secret-key"
        a.save()
        b = LeadCheckerSettings.load()
        self.assertEqual(b.gemini_api_key, "secret-key")
        self.assertEqual(LeadCheckerSettings.objects.count(), 1)
```

- [ ] **Step 2: Запустить тест — должен упасть**

Run: `cd twocomms && SECRET_KEY=test_local_secret python manage.py test management.tests_checker_job -v 2`
Expected: FAIL (`ImportError: cannot import name 'LeadCheckerSettings'`).

- [ ] **Step 3: Добавить модель**

В конец `twocomms/management/models.py`:

```python
class LeadCheckerSettings(models.Model):
    singleton_key = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    gemini_api_key = models.CharField(_("Ключ Gemini (опц.)"), max_length=255, blank=True)
    model_chain = models.CharField(_("Цепочка моделей (csv)"), max_length=255, blank=True)
    requests_per_minute = models.PositiveIntegerField(_("Запитів за хвилину"), default=8)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Налаштування чекера")
        verbose_name_plural = _("Налаштування чекера")

    @classmethod
    def load(cls) -> "LeadCheckerSettings":
        obj, _created = cls.objects.get_or_create(singleton_key=1)
        return obj

    def __str__(self):
        return "LeadCheckerSettings"
```

- [ ] **Step 4: Создать миграцию + прогнать тест**

Run: `cd twocomms && SECRET_KEY=test_local_secret python manage.py makemigrations management && SECRET_KEY=test_local_secret python manage.py test management.tests_checker_job -v 2`
Expected: миграция создана; PASS (2 теста).

- [ ] **Step 5: Commit**

```bash
git add twocomms/management/models.py twocomms/management/migrations/ twocomms/management/tests_checker_job.py
git commit -m "feat(checker): LeadCheckerSettings singleton"
```

---

### Task 3: Модель `LeadCheckJob` + `LeadCheckRuntimeLock`

**Files:**
- Modify: `twocomms/management/models.py`
- Test: `twocomms/management/tests_checker_job.py`

- [ ] **Step 1: Написать падающий тест**

Добавить в `twocomms/management/tests_checker_job.py`:

```python
from management.models import LeadCheckJob, LeadCheckRuntimeLock


class LeadCheckJobModelTests(TestCase):
    def test_create_defaults(self):
        job = LeadCheckJob.objects.create(scope=LeadCheckJob.Scope.UNCHECKED)
        self.assertEqual(job.status, LeadCheckJob.Status.RUNNING)
        self.assertEqual(job.processed, 0)
        self.assertEqual(job.scored, 0)
        self.assertEqual(job.errors, 0)
        self.assertEqual(job.cursor_id, 0)
        self.assertEqual(job.requests_per_minute, 8)

    def test_runtime_lock_singleton(self):
        lock, _ = LeadCheckRuntimeLock.objects.get_or_create(singleton_key=1)
        self.assertEqual(lock.pk, 1)
        self.assertIsNone(lock.active_job_id)
```

- [ ] **Step 2: Запустить — упадёт**

Run: `cd twocomms && SECRET_KEY=test_local_secret python manage.py test management.tests_checker_job.LeadCheckJobModelTests -v 2`
Expected: FAIL (`ImportError`).

- [ ] **Step 3: Добавить модели**

В конец `twocomms/management/models.py`:

```python
class LeadCheckJob(models.Model):
    class Status(models.TextChoices):
        RUNNING = "running", _("Працює")
        PAUSED = "paused", _("Пауза")
        STOPPED = "stopped", _("Зупинено")
        COMPLETED = "completed", _("Завершено")
        FAILED = "failed", _("Помилка")

    class Scope(models.TextChoices):
        UNCHECKED = "unchecked", _("Тільки неперевірені")
        ALL = "all", _("Усі (перепровірка)")
        BY_CITY = "by_city", _("За містом")
        BY_BAND = "by_band", _("За смугою вердикту")

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="lead_check_jobs", verbose_name=_("Створив"),
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RUNNING, db_index=True)
    scope = models.CharField(max_length=20, choices=Scope.choices, default=Scope.UNCHECKED)
    city = models.CharField(max_length=120, blank=True)
    band = models.CharField(max_length=10, blank=True)
    target_limit = models.PositiveIntegerField(default=0)
    requests_per_minute = models.PositiveIntegerField(default=8)
    total_selected = models.PositiveIntegerField(default=0)
    processed = models.PositiveIntegerField(default=0)
    scored = models.PositiveIntegerField(default=0)
    errors = models.PositiveIntegerField(default=0)
    fit_count = models.PositiveIntegerField(default=0)
    maybe_count = models.PositiveIntegerField(default=0)
    unfit_count = models.PositiveIntegerField(default=0)
    cursor_id = models.PositiveIntegerField(default=0)
    current_lead_id = models.PositiveIntegerField(null=True, blank=True)
    next_step_not_before = models.DateTimeField(null=True, blank=True, db_index=True)
    is_step_in_progress = models.BooleanField(default=False, db_index=True)
    last_step_started_at = models.DateTimeField(null=True, blank=True)
    avg_seconds = models.FloatField(default=0.0)
    last_error = models.TextField(blank=True)
    stop_reason_code = models.CharField(max_length=64, blank=True)
    started_at = models.DateTimeField(auto_now_add=True, db_index=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Сесія чекера")
        verbose_name_plural = _("Сесії чекера")
        ordering = ["-started_at"]
        indexes = [models.Index(fields=["status", "-started_at"], name="mgmt_check_status_dt")]

    def __str__(self):
        return f"CheckJob#{self.id} ({self.status})"


class LeadCheckRuntimeLock(models.Model):
    singleton_key = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    active_job = models.ForeignKey(
        LeadCheckJob, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Lock чекера")
        verbose_name_plural = _("Lock-и чекера")

    def __str__(self):
        return f"CheckLock(active_job={self.active_job_id or 'none'})"
```

- [ ] **Step 4: Миграция + тест**

Run: `cd twocomms && SECRET_KEY=test_local_secret python manage.py makemigrations management && SECRET_KEY=test_local_secret python manage.py test management.tests_checker_job.LeadCheckJobModelTests -v 2`
Expected: PASS (2 теста).

- [ ] **Step 5: Commit**

```bash
git add twocomms/management/models.py twocomms/management/migrations/ twocomms/management/tests_checker_job.py
git commit -m "feat(checker): LeadCheckJob + RuntimeLock"
```

---

### Task 4: Модель `LeadAICheck`

**Files:**
- Modify: `twocomms/management/models.py`
- Test: `twocomms/management/tests_checker_job.py`

- [ ] **Step 1: Написать падающий тест**

Добавить в `twocomms/management/tests_checker_job.py`:

```python
from management.models import LeadAICheck


class LeadAICheckModelTests(TestCase):
    def test_create_check_linked_to_lead(self):
        lead = ManagementLead.objects.create(shop_name="Shop", phone="0501112233")
        check = LeadAICheck.objects.create(
            lead=lead, status=LeadAICheck.Status.DONE, overall_score=75,
            criteria=[{"key": "product", "title": "Товар", "score": 8, "comment": "ok"}],
            verdict_category="brand", partnership_fit=["wholesale", "collab"],
            confidence="medium", sources=[{"title": "IG", "url": "https://instagram.com/x"}],
        )
        self.assertEqual(lead.ai_checks.count(), 1)
        self.assertEqual(check.partnership_fit, ["wholesale", "collab"])
        self.assertEqual(check.criteria[0]["score"], 8)
```

Добавить импорт `ManagementLead` в начало файла, если ещё нет.

- [ ] **Step 2: Запустить — упадёт**

Run: `cd twocomms && SECRET_KEY=test_local_secret python manage.py test management.tests_checker_job.LeadAICheckModelTests -v 2`
Expected: FAIL (`ImportError`).

- [ ] **Step 3: Добавить модель**

В конец `twocomms/management/models.py`:

```python
class LeadAICheck(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", _("В черзі")
        PROCESSING = "processing", _("Обробка")
        DONE = "done", _("Готово")
        ERROR = "error", _("Помилка")

    lead = models.ForeignKey(ManagementLead, on_delete=models.CASCADE, related_name="ai_checks")
    job = models.ForeignKey(LeadCheckJob, on_delete=models.SET_NULL, null=True, blank=True, related_name="checks")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    overall_score = models.PositiveSmallIntegerField(null=True, blank=True)
    criteria = models.JSONField(default=list, blank=True)
    verdict_category = models.CharField(max_length=40, blank=True)
    partnership_fit = models.JSONField(default=list, blank=True)
    confidence = models.CharField(max_length=10, blank=True)
    brand_summary = models.TextField(blank=True)
    audience_guess = models.TextField(blank=True)
    instagram_url = models.CharField(max_length=300, blank=True)
    comment = models.TextField(blank=True)
    recommendation = models.TextField(blank=True)
    sources = models.JSONField(default=list, blank=True)
    website_fetched = models.BooleanField(default=False)
    model_used = models.CharField(max_length=60, blank=True)
    tokens = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True)
    checked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="lead_ai_checks",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _("AI-перевірка ліда")
        verbose_name_plural = _("AI-перевірки лідів")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["lead", "-created_at"], name="mgmt_aicheck_lead_dt"),
            models.Index(fields=["status", "-created_at"], name="mgmt_aicheck_status_dt"),
        ]

    def __str__(self):
        return f"AICheck#{self.id} lead={self.lead_id} score={self.overall_score}"
```

- [ ] **Step 4: Миграция + тест**

Run: `cd twocomms && SECRET_KEY=test_local_secret python manage.py makemigrations management && SECRET_KEY=test_local_secret python manage.py test management.tests_checker_job.LeadAICheckModelTests -v 2`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add twocomms/management/models.py twocomms/management/migrations/ twocomms/management/tests_checker_job.py
git commit -m "feat(checker): LeadAICheck"
```

---

## Этап 2. Gemini grounded-хелпер и сервис скоринга

### Task 5: Публичный `gemini_generate_grounded` в `call_ai_analysis.py`

**Files:**
- Modify: `twocomms/management/services/call_ai_analysis.py` (после `gemini_generate_json`, ~строка 330)
- Test: `twocomms/management/tests_checker_gemini.py`

- [ ] **Step 1: Написать падающий тест**

Создать `twocomms/management/tests_checker_gemini.py`:

```python
from unittest.mock import patch

from django.test import SimpleTestCase

from management.services import call_ai_analysis as caa


class GeminiGroundedTests(SimpleTestCase):
    def test_builds_grounded_payload_and_returns_parsed(self):
        captured = {}

        def fake_call_once(model, payload, key):
            captured["model"] = model
            captured["payload"] = payload
            captured["key"] = key
            return {"overall_score": 80}, {"totalTokenCount": 123}

        with patch.object(caa, "_resolve_gemini_key", return_value="env-key"), \
             patch.object(caa, "_gemini_call_once", side_effect=fake_call_once):
            out = caa.gemini_generate_grounded("SYS", "USER", models=["gemini-2.5-flash"])

        self.assertEqual(out["parsed"], {"overall_score": 80})
        self.assertEqual(out["model"], "gemini-2.5-flash")
        # grounding tool включён, JSON-mime НЕ задан
        self.assertEqual(captured["payload"]["tools"], [{"google_search": {}}])
        self.assertNotIn("responseMimeType", captured["payload"]["generationConfig"])
        self.assertEqual(captured["key"], "env-key")

    def test_api_key_override_wins(self):
        with patch.object(caa, "_gemini_call_once", return_value=({"x": 1}, {})):
            out = caa.gemini_generate_grounded("S", "U", api_key="override-key", models=["m"])
        self.assertEqual(out["parsed"], {"x": 1})

    def test_400_skips_to_next_model(self):
        calls = []

        def fake_call_once(model, payload, key):
            calls.append(model)
            if model == "bad-model":
                raise caa._GeminiFatal("HTTP 400: tool not supported")
            return {"ok": True}, {}

        with patch.object(caa, "_resolve_gemini_key", return_value="k"), \
             patch.object(caa, "_gemini_call_once", side_effect=fake_call_once):
            out = caa.gemini_generate_grounded("S", "U", models=["bad-model", "good-model"])

        self.assertEqual(out["parsed"], {"ok": True})
        self.assertEqual(calls, ["bad-model", "good-model"])

    def test_no_key_raises(self):
        with patch.object(caa, "_resolve_gemini_key", return_value=""):
            with self.assertRaises(caa.CallAIAnalysisError):
                caa.gemini_generate_grounded("S", "U", models=["m"])
```

- [ ] **Step 2: Запустить — упадёт**

Run: `cd twocomms && SECRET_KEY=test_local_secret python manage.py test management.tests_checker_gemini -v 2`
Expected: FAIL (`AttributeError: module ... has no attribute 'gemini_generate_grounded'`).

- [ ] **Step 3: Реализовать хелпер**

В `twocomms/management/services/call_ai_analysis.py`, сразу после функции `gemini_generate_json`:

```python
GROUNDED_MODEL_CHAIN = ["gemini-2.5-flash", "gemini-3.5-flash"]


def _resolve_grounded_models() -> list[str]:
    raw = (getattr(settings, "GEMINI_CHECKER_MODELS", "") or "").strip()
    if not raw:
        raw = (os.environ.get("GEMINI_CHECKER_MODELS", "") or "").strip()
    if raw:
        models = [m.strip() for m in raw.split(",") if m.strip()]
        if models:
            return models
    return list(GROUNDED_MODEL_CHAIN)


def gemini_generate_grounded(
    system_instruction: str,
    user_text: str,
    *,
    api_key: str | None = None,
    models: list[str] | None = None,
    max_output_tokens: int = 4096,
) -> dict:
    """Grounded (Google Search) JSON-запрос к Gemini для AI-чекера.

    Grounding несовместим с responseMimeType=json, поэтому просим строгий JSON
    в промпте, а _gemini_call_once парсит его из текста. 400 (модель не
    поддерживает tools) трактуем как переход к следующей модели.
    """
    key = (api_key or "").strip() or _resolve_gemini_key()
    if not key:
        raise CallAIAnalysisError("Не задано ключ Gemini (ENV GEMINI_API або налаштування чекера).")
    model_list = models or _resolve_grounded_models()
    payload = {
        "contents": [{"role": "user", "parts": [{"text": user_text}]}],
        "system_instruction": {"parts": [{"text": system_instruction}]},
        "tools": [{"google_search": {}}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": max_output_tokens,
        },
    }
    attempts_log: list[str] = []
    for model in model_list:
        for attempt in range(PER_MODEL_ATTEMPTS):
            try:
                parsed, usage = _gemini_call_once(model, payload, key)
                attempts_log.append(f"{model}: ok (спроба {attempt + 1})")
                return {"parsed": parsed, "raw": parsed, "usage": usage, "model": model,
                        "meta": {"attempts": attempts_log, "used_model": model}}
            except _GeminiTransient as exc:
                attempts_log.append(f"{model}: transient {exc} (спроба {attempt + 1})")
                if attempt < PER_MODEL_ATTEMPTS - 1:
                    time.sleep(BACKOFF_BASE * (2 ** attempt))
            except _GeminiSkipModel as exc:
                attempts_log.append(f"{model}: skip {exc}")
                break
            except _GeminiFatal as exc:
                # З grounding 400 зазвичай = модель не підтримує google_search tool.
                attempts_log.append(f"{model}: fatal→skip {exc}")
                break
    raise CallAIAnalysisError(
        "Усі моделі Gemini недоступні для grounded-запиту. Спроби: " + "; ".join(attempts_log)
    )
```

- [ ] **Step 4: Запустить — пройдёт**

Run: `cd twocomms && SECRET_KEY=test_local_secret python manage.py test management.tests_checker_gemini -v 2`
Expected: PASS (4 теста).

- [ ] **Step 5: Commit**

```bash
git add twocomms/management/services/call_ai_analysis.py twocomms/management/tests_checker_gemini.py
git commit -m "feat(checker): gemini_generate_grounded helper"
```

---

### Task 6: Константы критериев и маппинг полос вердикта

**Files:**
- Create: `twocomms/management/services/lead_checker.py`
- Test: `twocomms/management/tests_checker_scoring.py`

- [ ] **Step 1: Написать падающий тест**

Добавить в `twocomms/management/tests_checker_scoring.py`:

```python
from management.services import lead_checker as lc


class BandMappingTests(TestCase):
    def test_band_for_score(self):
        self.assertEqual(lc.band_for_score(85), "fit")
        self.assertEqual(lc.band_for_score(70), "fit")
        self.assertEqual(lc.band_for_score(69), "maybe")
        self.assertEqual(lc.band_for_score(40), "maybe")
        self.assertEqual(lc.band_for_score(39), "unfit")
        self.assertEqual(lc.band_for_score(0), "unfit")

    def test_niche_for_band(self):
        from management.models import ManagementLead
        self.assertEqual(lc.niche_for_band("fit"), ManagementLead.NicheStatus.NICHE)
        self.assertEqual(lc.niche_for_band("maybe"), ManagementLead.NicheStatus.MAYBE)
        self.assertEqual(lc.niche_for_band("unfit"), ManagementLead.NicheStatus.NON_NICHE)

    def test_criteria_has_ten_keys(self):
        self.assertEqual(len(lc.CRITERIA), 10)
        keys = [c[0] for c in lc.CRITERIA]
        self.assertIn("custom_print_potential", keys)
        self.assertIn("collab_potential", keys)
        self.assertEqual(len(set(keys)), 10)
```

- [ ] **Step 2: Запустить — упадёт**

Run: `cd twocomms && SECRET_KEY=test_local_secret python manage.py test management.tests_checker_scoring.BandMappingTests -v 2`
Expected: FAIL (`ModuleNotFoundError: management.services.lead_checker`).

- [ ] **Step 3: Создать модуль с константами**

Создать `twocomms/management/services/lead_checker.py`:

```python
"""AI-чекер спарсенных аккаунтов: скоринг одного ManagementLead через Gemini
с Google Search grounding. Архитектура и паттерн вызова — как в
services/call_ai_analysis.py (прямой REST, цепочка моделей, ретраи)."""
from __future__ import annotations

import logging

from management.models import ManagementLead

logger = logging.getLogger("management.checker")

# 10 критериев (ключ, человекочитаемый заголовок). Каждый оценивается 0..10.
CRITERIA: list[tuple[str, str]] = [
    ("product_relevance", "Релевантність товару"),
    ("style_aesthetic", "Стиль та естетика"),
    ("audience_match", "Збіг цільової аудиторії"),
    ("military_tactical", "Мілітарі / тактика"),
    ("custom_print_potential", "Потенціал кастом-друку (white-label)"),
    ("wholesale_potential", "Потенціал опту готового"),
    ("collab_potential", "Потенціал колаборації"),
    ("online_presence", "Онлайн-присутність та охоплення"),
    ("business_profile", "Бізнес-профіль і масштаб"),
    ("approachability", "Реалістичність заходу"),
]

PARTNERSHIP_CHANNELS = ["wholesale", "custom_print", "collab", "dropship", "test_batch", "shelf"]
VERDICT_CATEGORIES = [
    "physical_store", "retail_chain", "dropshipper", "brand",
    "voentorg", "marketplace_seller", "irrelevant",
]

FIT_THRESHOLD = 70
MAYBE_THRESHOLD = 40


def band_for_score(score: int) -> str:
    if score >= FIT_THRESHOLD:
        return "fit"
    if score >= MAYBE_THRESHOLD:
        return "maybe"
    return "unfit"


def niche_for_band(band: str) -> str:
    if band == "fit":
        return ManagementLead.NicheStatus.NICHE
    if band == "maybe":
        return ManagementLead.NicheStatus.MAYBE
    return ManagementLead.NicheStatus.NON_NICHE
```

- [ ] **Step 4: Запустить — пройдёт**

Run: `cd twocomms && SECRET_KEY=test_local_secret python manage.py test management.tests_checker_scoring.BandMappingTests -v 2`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add twocomms/management/services/lead_checker.py twocomms/management/tests_checker_scoring.py
git commit -m "feat(checker): критерии и маппинг полос вердикта"
```

---

### Task 7: Сборка контекста лида + фетч сайта

**Files:**
- Modify: `twocomms/management/services/lead_checker.py`
- Test: `twocomms/management/tests_checker_scoring.py`

- [ ] **Step 1: Написать падающий тест**

Добавить в `twocomms/management/tests_checker_scoring.py`:

```python
from unittest.mock import patch


class ContextBuildTests(TestCase):
    def test_build_lead_context_includes_key_fields(self):
        lead = ManagementLead.objects.create(
            shop_name="Coyote Wear", phone="0501112233", city="Харків",
            website_url="https://coyotewear.example",
            extra_data={"types": ["clothing_store"], "formattedAddress": "вул. Сумська, 1"},
        )
        ctx = lc.build_lead_context(lead)
        self.assertIn("Coyote Wear", ctx)
        self.assertIn("Харків", ctx)
        self.assertIn("coyotewear.example", ctx)
        self.assertIn("clothing_store", ctx)
        self.assertIn("Сумська", ctx)

    def test_fetch_website_text_strips_html_and_truncates(self):
        html = "<html><head><style>x{}</style></head><body><h1>Hello</h1><p>" + ("A" * 9000) + "</p></body></html>"

        class FakeResp:
            status_code = 200
            text = html
            headers = {"content-type": "text/html"}

        with patch.object(lc.requests, "get", return_value=FakeResp()):
            text, ok = lc.fetch_website_text("https://x.example")
        self.assertTrue(ok)
        self.assertIn("Hello", text)
        self.assertNotIn("<h1>", text)
        self.assertLessEqual(len(text), lc.WEBSITE_TEXT_LIMIT)

    def test_fetch_website_text_handles_failure(self):
        with patch.object(lc.requests, "get", side_effect=Exception("boom")):
            text, ok = lc.fetch_website_text("https://x.example")
        self.assertFalse(ok)
        self.assertEqual(text, "")

    def test_fetch_website_text_empty_url(self):
        text, ok = lc.fetch_website_text("")
        self.assertFalse(ok)
        self.assertEqual(text, "")
```

- [ ] **Step 2: Запустить — упадёт**

Run: `cd twocomms && SECRET_KEY=test_local_secret python manage.py test management.tests_checker_scoring.ContextBuildTests -v 2`
Expected: FAIL.

- [ ] **Step 3: Реализовать сборку контекста и фетч**

Добавить в начало `lead_checker.py` импорты и константы, и функции:

```python
import re
import requests

WEBSITE_TIMEOUT = (5, 6)        # (connect, read) сек
WEBSITE_TEXT_LIMIT = 6000       # символов текста сайта
_TAG_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)
_ANY_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def build_lead_context(lead: ManagementLead) -> str:
    extra = lead.extra_data if isinstance(lead.extra_data, dict) else {}
    types = extra.get("types") or []
    address = extra.get("formattedAddress") or ""
    parts = [
        f"Назва: {lead.shop_name}",
        f"Місто: {lead.city}" if lead.city else "",
        f"Сайт: {lead.website_url}" if lead.website_url else "Сайт: невідомо",
        f"Google Maps: {lead.google_maps_url}" if lead.google_maps_url else "",
        f"Google-категорії: {', '.join(types)}" if types else "",
        f"Адреса: {address}" if address else "",
        f"Деталі парсера: {lead.details}" if lead.details else "",
    ]
    return "\n".join(p for p in parts if p)


def fetch_website_text(url: str) -> tuple[str, bool]:
    url = (url or "").strip()
    if not url:
        return "", False
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        resp = requests.get(url, timeout=WEBSITE_TIMEOUT, headers={"User-Agent": "Mozilla/5.0 TwoCommsChecker/1.0"})
    except Exception:
        return "", False
    if resp.status_code != 200 or "html" not in (resp.headers.get("content-type", "")):
        return "", False
    html = resp.text or ""
    html = _TAG_RE.sub(" ", html)
    text = _ANY_TAG_RE.sub(" ", html)
    text = _WS_RE.sub(" ", text).strip()
    return text[:WEBSITE_TEXT_LIMIT], bool(text)
```

- [ ] **Step 4: Запустить — пройдёт**

Run: `cd twocomms && SECRET_KEY=test_local_secret python manage.py test management.tests_checker_scoring.ContextBuildTests -v 2`
Expected: PASS (4 теста).

- [ ] **Step 5: Commit**

```bash
git add twocomms/management/services/lead_checker.py twocomms/management/tests_checker_scoring.py
git commit -m "feat(checker): сборка контекста лида и фетч сайта"
```

---

## Этап 3. System-prompt, парсинг ответа и `score_lead`

### Task 8: System-prompt чекера

**Files:**
- Modify: `twocomms/management/services/lead_checker.py`
- Test: `twocomms/management/tests_checker_scoring.py`

- [ ] **Step 1: Написать падающий тест**

Добавить в `twocomms/management/tests_checker_scoring.py`:

```python
class SystemPromptTests(TestCase):
    def test_prompt_mentions_brand_audience_and_channels(self):
        prompt = lc.build_system_prompt()
        # бренд и аудитория
        self.assertIn("TwoComms", prompt)
        self.assertIn("streetwear", prompt.lower())
        self.assertIn("40", prompt)  # доля военных
        # каналы
        self.assertIn("custom_print", prompt)
        self.assertIn("wholesale", prompt)
        self.assertIn("collab", prompt)
        # все 10 ключей критериев перечислены
        for key, _title in lc.CRITERIA:
            self.assertIn(key, prompt)
        # требование строгого JSON
        self.assertIn("JSON", prompt)
        self.assertIn("overall_score", prompt)
```

- [ ] **Step 2: Запустить — упадёт**

Run: `cd twocomms && SECRET_KEY=test_local_secret python manage.py test management.tests_checker_scoring.SystemPromptTests -v 2`
Expected: FAIL.

- [ ] **Step 3: Реализовать промпт**

Добавить в `lead_checker.py`:

```python
def build_system_prompt() -> str:
    criteria_lines = "\n".join(f"  - {key} ({title}, 0..10)" for key, title in CRITERIA)
    return (
        "Ти — B2B-аналітик розвитку партнерств бренду TwoComms. Твоє завдання — "
        "оцінити, наскільки знайдений магазин/бренд підходить TwoComms для співпраці.\n\n"
        "ПРО TwoComms:\n"
        "Український streetwear-бренд із Харкова з military-adjacent ДНК і патріотикою. "
        "Асортимент: футболки, худі, лонгсліви, мерч і КАСТОМНИЙ DTF-друк (можемо надрукувати "
        "будь-який принт під бренд клієнта). Унісекс, сегмент «доступний streetwear-преміум». "
        "Орієнтир-конкуренти: українські streetwear-бренди, що живуть в Instagram, з drop-культурою "
        "і авторськими принтами.\n\n"
        "ХТО КУПУЄ TwoComms: ~40% військові; ~20% волонтери / навколовоєнні / українська військова "
        "спільнота; ~40% цивільні, яким близька urban / streetwear / military-adjacent естетика. "
        "Купують і чоловіки, і жінки. ЕСТЕТИКА ВАЖЛИВІША ЗА СТАТЬ — жіночий streetwear-магазин теж "
        "підходить, якщо збігається стиль.\n\n"
        "КАНАЛИ СПІВПРАЦІ (partnership_fit, обери всі релевантні):\n"
        "  - wholesale: опт готового асортименту TwoComms\n"
        "  - custom_print: кастом-друк під їхній бренд (white-label; друкуємо будь-який принт)\n"
        "  - collab: спільний дроп\n"
        "  - dropship: дропшипінг\n"
        "  - test_batch: тестова партія\n"
        "  - shelf: фізмагазин/військторг ставить наш товар на полицю\n\n"
        "КРИТЕРІЇ (кожен 0..10):\n"
        f"{criteria_lines}\n\n"
        "Тобі дають дані магазину (назва, місто, сайт, Google-категорії, адреса) і, якщо вдалося, "
        "текст головної сторінки сайту. Використай Google Search, щоб дослідити бренд: знайти "
        "Instagram/соцмережі, історію, чи продають своє чи перепродають, чи були колаборації, "
        "чи це військторг, маркетплейс-продавець, мережа тощо.\n\n"
        "ВАЖЛИВО: не вигадуй. Якщо даних недостатньо — став confidence='low' і чесно пиши "
        "'недостатньо даних'. Усі твердження про бренд підкріплюй джерелами (sources).\n\n"
        "overall_score (0..100) — холістична оцінка придатності (НЕ проста сума критеріїв, "
        "а зважений висновок з урахуванням усіх сигналів).\n\n"
        "Відповідай СУВОРО валідним JSON (без markdown, без ```), українською, за схемою:\n"
        "{\n"
        '  "overall_score": <0..100>,\n'
        '  "verdict_category": "physical_store|retail_chain|dropshipper|brand|voentorg|marketplace_seller|irrelevant",\n'
        '  "partnership_fit": ["wholesale", "custom_print", ...],\n'
        '  "confidence": "low|medium|high",\n'
        '  "brand_summary": "що це за магазин/бренд (2-4 речення)",\n'
        '  "audience_guess": "хто їхня аудиторія",\n'
        '  "instagram_url": "https://instagram.com/... або порожньо",\n'
        '  "criteria": [ {"key": "product_relevance", "score": <0..10>, "comment": "обґрунтування"}, ... усі 10 ],\n'
        '  "comment": "загальний висновок для модератора",\n'
        '  "recommendation": "що менеджеру пропонувати цьому магазину (який канал і питч)",\n'
        '  "sources": [ {"title": "...", "url": "https://..."} ]\n'
        "}\n"
    )
```

- [ ] **Step 4: Запустить — пройдёт**

Run: `cd twocomms && SECRET_KEY=test_local_secret python manage.py test management.tests_checker_scoring.SystemPromptTests -v 2`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add twocomms/management/services/lead_checker.py twocomms/management/tests_checker_scoring.py
git commit -m "feat(checker): system-prompt чекера"
```

---

### Task 9: Нормализация и валидация ответа модели

**Files:**
- Modify: `twocomms/management/services/lead_checker.py`
- Test: `twocomms/management/tests_checker_scoring.py`

- [ ] **Step 1: Написать падающий тест**

Добавить в `twocomms/management/tests_checker_scoring.py`:

```python
class NormalizeResultTests(TestCase):
    def test_normalize_full_result(self):
        raw = {
            "overall_score": 82,
            "verdict_category": "brand",
            "partnership_fit": ["wholesale", "collab", "bogus_channel"],
            "confidence": "high",
            "brand_summary": "UA streetwear бренд",
            "audience_guess": "молодь, патріоти",
            "instagram_url": "https://instagram.com/coyote",
            "criteria": [{"key": k, "score": 8, "comment": "ok"} for k, _ in lc.CRITERIA],
            "comment": "гарний кандидат",
            "recommendation": "пропонувати колаб",
            "sources": [{"title": "IG", "url": "https://instagram.com/coyote"}],
        }
        norm = lc.normalize_result(raw)
        self.assertEqual(norm["overall_score"], 82)
        self.assertEqual(norm["verdict_category"], "brand")
        # bogus_channel отфильтрован
        self.assertEqual(norm["partnership_fit"], ["wholesale", "collab"])
        self.assertEqual(len(norm["criteria"]), 10)

    def test_normalize_clamps_and_defaults(self):
        norm = lc.normalize_result({"overall_score": 250, "criteria": []})
        self.assertEqual(norm["overall_score"], 100)
        self.assertEqual(norm["confidence"], "low")
        self.assertEqual(norm["verdict_category"], "irrelevant")
        self.assertEqual(norm["partnership_fit"], [])
        # критерии добиты до 10 со score 0
        self.assertEqual(len(norm["criteria"]), 10)
        self.assertEqual(norm["criteria"][0]["score"], 0)

    def test_normalize_derives_score_when_missing(self):
        crit = [{"key": k, "score": 5, "comment": ""} for k, _ in lc.CRITERIA]
        norm = lc.normalize_result({"criteria": crit})
        # среднее 5/10 → 50
        self.assertEqual(norm["overall_score"], 50)

    def test_normalize_bad_score_value(self):
        norm = lc.normalize_result({"overall_score": "abc", "criteria": []})
        self.assertEqual(norm["overall_score"], 0)
```

- [ ] **Step 2: Запустить — упадёт**

Run: `cd twocomms && SECRET_KEY=test_local_secret python manage.py test management.tests_checker_scoring.NormalizeResultTests -v 2`
Expected: FAIL.

- [ ] **Step 3: Реализовать нормализацию**

Добавить в `lead_checker.py`:

```python
def _coerce_int(value, lo: int, hi: int, default: int) -> int:
    try:
        n = int(round(float(value)))
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, n))


def _as_str(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _as_list(value) -> list:
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [value]


def normalize_result(raw: dict) -> dict:
    raw = raw if isinstance(raw, dict) else {}
    title_by_key = dict(CRITERIA)

    # критерии: добиваем до 10 по фиксированному порядку
    by_key = {}
    for item in _as_list(raw.get("criteria")):
        if isinstance(item, dict) and item.get("key") in title_by_key:
            by_key[item["key"]] = item
    criteria = []
    for key, title in CRITERIA:
        item = by_key.get(key, {})
        criteria.append({
            "key": key,
            "title": title,
            "score": _coerce_int(item.get("score"), 0, 10, 0),
            "comment": _as_str(item.get("comment")),
        })

    # overall_score: из модели или производный (среднее*10)
    if raw.get("overall_score") in (None, ""):
        avg = sum(c["score"] for c in criteria) / len(criteria) if criteria else 0
        overall = _coerce_int(avg * 10, 0, 100, 0)
    else:
        overall = _coerce_int(raw.get("overall_score"), 0, 100, 0)

    category = _as_str(raw.get("verdict_category")) or "irrelevant"
    if category not in VERDICT_CATEGORIES:
        category = "irrelevant"

    fit = [c for c in _as_list(raw.get("partnership_fit")) if c in PARTNERSHIP_CHANNELS]

    confidence = _as_str(raw.get("confidence")).lower()
    if confidence not in ("low", "medium", "high"):
        confidence = "low"

    sources = []
    for s in _as_list(raw.get("sources")):
        if isinstance(s, dict) and s.get("url"):
            sources.append({"title": _as_str(s.get("title")) or s["url"], "url": _as_str(s["url"])})

    return {
        "overall_score": overall,
        "verdict_category": category,
        "partnership_fit": fit,
        "confidence": confidence,
        "brand_summary": _as_str(raw.get("brand_summary")),
        "audience_guess": _as_str(raw.get("audience_guess")),
        "instagram_url": _as_str(raw.get("instagram_url"))[:300],
        "criteria": criteria,
        "comment": _as_str(raw.get("comment")),
        "recommendation": _as_str(raw.get("recommendation")),
        "sources": sources,
    }
```

- [ ] **Step 4: Запустить — пройдёт**

Run: `cd twocomms && SECRET_KEY=test_local_secret python manage.py test management.tests_checker_scoring.NormalizeResultTests -v 2`
Expected: PASS (4 теста).

- [ ] **Step 5: Commit**

```bash
git add twocomms/management/services/lead_checker.py twocomms/management/tests_checker_scoring.py
git commit -m "feat(checker): нормализация ответа модели"
```

---

### Task 10: `score_lead` — главная функция скоринга

**Files:**
- Modify: `twocomms/management/services/lead_checker.py`
- Test: `twocomms/management/tests_checker_scoring.py`

- [ ] **Step 1: Написать падающий тест**

Добавить в `twocomms/management/tests_checker_scoring.py`:

```python
from management.models import LeadAICheck


class ScoreLeadTests(TestCase):
    def _raw(self, score):
        return {
            "overall_score": score,
            "verdict_category": "brand",
            "partnership_fit": ["wholesale"],
            "confidence": "high",
            "brand_summary": "ok",
            "criteria": [{"key": k, "score": 8, "comment": "c"} for k, _ in lc.CRITERIA],
            "comment": "good",
            "recommendation": "pitch",
            "sources": [{"title": "t", "url": "https://x"}],
        }

    def test_score_lead_saves_check_and_updates_cache(self):
        lead = ManagementLead.objects.create(shop_name="Shop", phone="0501112233", website_url="")
        fake = {"parsed": self._raw(82), "usage": {"totalTokenCount": 100}, "model": "gemini-2.5-flash"}
        with patch.object(lc, "gemini_generate_grounded", return_value=fake) as gm, \
             patch.object(lc, "fetch_website_text", return_value=("", False)):
            check = lc.score_lead(lead)
        self.assertEqual(check.status, LeadAICheck.Status.DONE)
        self.assertEqual(check.overall_score, 82)
        self.assertEqual(check.model_used, "gemini-2.5-flash")
        gm.assert_called_once()
        lead.refresh_from_db()
        self.assertEqual(lead.ai_score, 82)
        self.assertEqual(lead.ai_verdict, "fit")
        self.assertIsNotNone(lead.ai_checked_at)
        self.assertEqual(lead.niche_status, ManagementLead.NicheStatus.NICHE)

    def test_score_lead_maybe_band_maps_niche(self):
        lead = ManagementLead.objects.create(shop_name="Shop2", phone="0501112244")
        fake = {"parsed": self._raw(55), "usage": {}, "model": "m"}
        with patch.object(lc, "gemini_generate_grounded", return_value=fake), \
             patch.object(lc, "fetch_website_text", return_value=("", False)):
            lc.score_lead(lead)
        lead.refresh_from_db()
        self.assertEqual(lead.ai_verdict, "maybe")
        self.assertEqual(lead.niche_status, ManagementLead.NicheStatus.MAYBE)

    def test_score_lead_handles_gemini_error(self):
        from management.services.call_ai_analysis import CallAIAnalysisError
        lead = ManagementLead.objects.create(shop_name="Shop3", phone="0501112255")
        with patch.object(lc, "gemini_generate_grounded", side_effect=CallAIAnalysisError("boom")), \
             patch.object(lc, "fetch_website_text", return_value=("", False)):
            check = lc.score_lead(lead)
        self.assertEqual(check.status, LeadAICheck.Status.ERROR)
        self.assertIn("boom", check.error)
        lead.refresh_from_db()
        self.assertEqual(lead.ai_verdict, "error")
        self.assertIsNotNone(lead.ai_checked_at)

    def test_score_lead_passes_api_key(self):
        lead = ManagementLead.objects.create(shop_name="Shop4", phone="0501112266")
        fake = {"parsed": self._raw(70), "usage": {}, "model": "m"}
        with patch.object(lc, "gemini_generate_grounded", return_value=fake) as gm, \
             patch.object(lc, "fetch_website_text", return_value=("", False)):
            lc.score_lead(lead, api_key="custom-key")
        _, kwargs = gm.call_args
        self.assertEqual(kwargs.get("api_key"), "custom-key")
```

- [ ] **Step 2: Запустить — упадёт**

Run: `cd twocomms && SECRET_KEY=test_local_secret python manage.py test management.tests_checker_scoring.ScoreLeadTests -v 2`
Expected: FAIL.

- [ ] **Step 3: Реализовать `score_lead`**

Добавить в `lead_checker.py` (вверху добавить `from django.utils import timezone` и импорты моделей `LeadAICheck`):

```python
from django.utils import timezone

from management.models import LeadAICheck
from management.services.call_ai_analysis import CallAIAnalysisError, gemini_generate_grounded


def score_lead(lead: ManagementLead, *, api_key: str | None = None, checked_by=None, job=None) -> LeadAICheck:
    """Оценивает один лид через Gemini grounding. Всегда возвращает LeadAICheck
    (status=done или error). Идемпотентно обновляет кэш-поля лида."""
    check = LeadAICheck.objects.create(
        lead=lead, job=job, status=LeadAICheck.Status.PROCESSING, checked_by=checked_by,
    )
    started = timezone.now()
    try:
        website_text, fetched = fetch_website_text(lead.website_url)
        context = build_lead_context(lead)
        user_text = context
        if fetched and website_text:
            user_text += "\n\nТЕКСТ ГОЛОВНОЇ СТОРІНКИ САЙТУ (фрагмент):\n" + website_text

        result = gemini_generate_grounded(
            build_system_prompt(), user_text, api_key=api_key, max_output_tokens=4096,
        )
        norm = normalize_result(result.get("parsed") or {})
        band = band_for_score(norm["overall_score"])

        check.status = LeadAICheck.Status.DONE
        check.overall_score = norm["overall_score"]
        check.criteria = norm["criteria"]
        check.verdict_category = norm["verdict_category"]
        check.partnership_fit = norm["partnership_fit"]
        check.confidence = norm["confidence"]
        check.brand_summary = norm["brand_summary"]
        check.audience_guess = norm["audience_guess"]
        check.instagram_url = norm["instagram_url"]
        check.comment = norm["comment"]
        check.recommendation = norm["recommendation"]
        check.sources = norm["sources"]
        check.website_fetched = fetched
        check.model_used = result.get("model", "")
        check.tokens = result.get("usage") or {}
        check.save()

        lead.ai_score = norm["overall_score"]
        lead.ai_verdict = band
        lead.ai_checked_at = timezone.now()
        lead.niche_status = niche_for_band(band)
        lead.save(update_fields=["ai_score", "ai_verdict", "ai_checked_at", "niche_status", "updated_at"])
    except CallAIAnalysisError as exc:
        check.status = LeadAICheck.Status.ERROR
        check.error = str(exc)
        check.model_used = ""
        check.save(update_fields=["status", "error", "model_used"])
        lead.ai_verdict = "error"
        lead.ai_checked_at = timezone.now()
        lead.save(update_fields=["ai_verdict", "ai_checked_at", "updated_at"])
    except Exception as exc:  # noqa: BLE001 — любая иная ошибка не должна ронять движок
        logger.exception("score_lead failed for lead=%s", lead.id)
        check.status = LeadAICheck.Status.ERROR
        check.error = f"{type(exc).__name__}: {exc}"
        check.save(update_fields=["status", "error"])
        lead.ai_verdict = "error"
        lead.ai_checked_at = timezone.now()
        lead.save(update_fields=["ai_verdict", "ai_checked_at", "updated_at"])
    finally:
        check._duration_seconds = (timezone.now() - started).total_seconds()
    return check
```

- [ ] **Step 4: Запустить — пройдёт**

Run: `cd twocomms && SECRET_KEY=test_local_secret python manage.py test management.tests_checker_scoring.ScoreLeadTests -v 2`
Expected: PASS (4 теста).

- [ ] **Step 5: Прогнать весь модуль скоринга**

Run: `cd twocomms && SECRET_KEY=test_local_secret python manage.py test management.tests_checker_scoring -v 2`
Expected: PASS (все классы).

- [ ] **Step 6: Commit**

```bash
git add twocomms/management/services/lead_checker.py twocomms/management/tests_checker_scoring.py
git commit -m "feat(checker): score_lead — скоринг одного лида"
```

---

## Этап 4. Движок job

### Task 11: Выборка кандидатов и резолв API-ключа

**Files:**
- Create: `twocomms/management/services/lead_check_job.py`
- Test: `twocomms/management/tests_checker_job.py`

- [ ] **Step 1: Написать падающий тест**

Добавить в `twocomms/management/tests_checker_job.py`:

```python
from django.utils import timezone

from management.models import LeadCheckerSettings
from management.services import lead_check_job as ljob


class CandidateQuerysetTests(TestCase):
    def _lead(self, **kw):
        defaults = dict(shop_name="S", phone="050" + str(1000000 + ManagementLead.objects.count()),
                        lead_source=ManagementLead.LeadSource.PARSER)
        defaults.update(kw)
        return ManagementLead.objects.create(**defaults)

    def test_unchecked_scope_excludes_checked(self):
        a = self._lead()
        b = self._lead(ai_checked_at=timezone.now(), ai_verdict="fit")
        qs = ljob.candidate_queryset(scope="unchecked", city="", band="")
        self.assertIn(a, qs)
        self.assertNotIn(b, qs)

    def test_all_scope_includes_everything_parser(self):
        a = self._lead()
        b = self._lead(ai_checked_at=timezone.now())
        qs = ljob.candidate_queryset(scope="all", city="", band="")
        self.assertIn(a, qs)
        self.assertIn(b, qs)

    def test_by_city_scope(self):
        a = self._lead(city="Харків")
        b = self._lead(city="Київ")
        qs = ljob.candidate_queryset(scope="by_city", city="Харків", band="")
        self.assertIn(a, qs)
        self.assertNotIn(b, qs)

    def test_by_band_scope(self):
        a = self._lead(ai_checked_at=timezone.now(), ai_verdict="maybe")
        b = self._lead(ai_checked_at=timezone.now(), ai_verdict="fit")
        qs = ljob.candidate_queryset(scope="by_band", city="", band="maybe")
        self.assertIn(a, qs)
        self.assertNotIn(b, qs)

    def test_excludes_manual_leads(self):
        manual = self._lead(lead_source=ManagementLead.LeadSource.MANUAL)
        qs = ljob.candidate_queryset(scope="all", city="", band="")
        self.assertNotIn(manual, qs)


class ResolveKeyTests(TestCase):
    def test_returns_settings_key_when_set(self):
        s = LeadCheckerSettings.load()
        s.gemini_api_key = "settings-key"
        s.save()
        self.assertEqual(ljob.resolve_checker_api_key(), "settings-key")

    def test_returns_empty_when_unset(self):
        self.assertEqual(ljob.resolve_checker_api_key(), "")
```

- [ ] **Step 2: Запустить — упадёт**

Run: `cd twocomms && SECRET_KEY=test_local_secret python manage.py test management.tests_checker_job.CandidateQuerysetTests management.tests_checker_job.ResolveKeyTests -v 2`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Создать модуль с выборкой и ключом**

Создать `twocomms/management/services/lead_check_job.py`:

```python
"""Движок AI-чекера: браузер-driven stepping (как парсер). Один лид на шаг,
результат сразу в БД, единственная активная сессия через RuntimeLock."""
from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone

from management.models import (
    LeadAICheck,
    LeadCheckJob,
    LeadCheckRuntimeLock,
    LeadCheckerSettings,
    ManagementLead,
)
from management.services import lead_checker

logger = logging.getLogger("management.checker")

ACTIVE_STATUSES = {LeadCheckJob.Status.RUNNING, LeadCheckJob.Status.PAUSED}


class CheckerServiceError(Exception):
    pass


def resolve_checker_api_key() -> str:
    return (LeadCheckerSettings.load().gemini_api_key or "").strip()


def candidate_queryset(*, scope: str, city: str, band: str):
    base = ManagementLead.objects.filter(lead_source=ManagementLead.LeadSource.PARSER)
    if scope == "all":
        return base.order_by("id")
    if scope == "by_city":
        return base.filter(city__iexact=(city or "").strip(), ai_checked_at__isnull=True).order_by("id")
    if scope == "by_band":
        return base.filter(ai_verdict=(band or "").strip()).order_by("id")
    # default: unchecked
    return base.filter(ai_checked_at__isnull=True).order_by("id")
```

- [ ] **Step 4: Запустить — пройдёт**

Run: `cd twocomms && SECRET_KEY=test_local_secret python manage.py test management.tests_checker_job.CandidateQuerysetTests management.tests_checker_job.ResolveKeyTests -v 2`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add twocomms/management/services/lead_check_job.py twocomms/management/tests_checker_job.py
git commit -m "feat(checker): выборка кандидатов и резолв ключа"
```

---

### Task 12: Создание/пауза/возобновление/стоп сессии + lock

**Files:**
- Modify: `twocomms/management/services/lead_check_job.py`
- Test: `twocomms/management/tests_checker_job.py`

- [ ] **Step 1: Написать падающий тест**

Добавить в `twocomms/management/tests_checker_job.py`:

```python
class JobLifecycleTests(TestCase):
    def setUp(self):
        for i in range(3):
            ManagementLead.objects.create(
                shop_name=f"S{i}", phone=f"05010000{i}",
                lead_source=ManagementLead.LeadSource.PARSER,
            )

    def test_create_sets_total_and_lock(self):
        job = ljob.create_check_job(user=None, scope="unchecked", city="", band="", target_limit=0, requests_per_minute=10)
        self.assertEqual(job.status, LeadCheckJob.Status.RUNNING)
        self.assertEqual(job.total_selected, 3)
        lock = LeadCheckRuntimeLock.objects.get(singleton_key=1)
        self.assertEqual(lock.active_job_id, job.id)

    def test_second_active_job_rejected(self):
        ljob.create_check_job(user=None, scope="unchecked", city="", band="", target_limit=0, requests_per_minute=10)
        with self.assertRaises(ljob.CheckerServiceError):
            ljob.create_check_job(user=None, scope="unchecked", city="", band="", target_limit=0, requests_per_minute=10)

    def test_pause_resume_stop(self):
        job = ljob.create_check_job(user=None, scope="unchecked", city="", band="", target_limit=0, requests_per_minute=10)
        job = ljob.pause_job(job.id)
        self.assertEqual(job.status, LeadCheckJob.Status.PAUSED)
        job = ljob.resume_job(job.id)
        self.assertEqual(job.status, LeadCheckJob.Status.RUNNING)
        job = ljob.stop_job(job.id)
        self.assertEqual(job.status, LeadCheckJob.Status.STOPPED)
        lock = LeadCheckRuntimeLock.objects.get(singleton_key=1)
        self.assertIsNone(lock.active_job_id)

    def test_stop_allows_new_job(self):
        j1 = ljob.create_check_job(user=None, scope="unchecked", city="", band="", target_limit=0, requests_per_minute=10)
        ljob.stop_job(j1.id)
        j2 = ljob.create_check_job(user=None, scope="all", city="", band="", target_limit=0, requests_per_minute=10)
        self.assertEqual(j2.status, LeadCheckJob.Status.RUNNING)
```

- [ ] **Step 2: Запустить — упадёт**

Run: `cd twocomms && SECRET_KEY=test_local_secret python manage.py test management.tests_checker_job.JobLifecycleTests -v 2`
Expected: FAIL.

- [ ] **Step 3: Реализовать lifecycle**

Добавить в `lead_check_job.py`:

```python
def _lock_for_update() -> LeadCheckRuntimeLock:
    lock, _ = LeadCheckRuntimeLock.objects.select_for_update().get_or_create(singleton_key=1)
    return lock


def _normalize_active(lock: LeadCheckRuntimeLock) -> LeadCheckJob | None:
    job = lock.active_job
    if job and job.status not in ACTIVE_STATUSES:
        lock.active_job = None
        lock.save(update_fields=["active_job", "updated_at"])
        return None
    return job


def create_check_job(*, user, scope, city, band, target_limit, requests_per_minute) -> LeadCheckJob:
    total = candidate_queryset(scope=scope, city=city, band=band).count()
    with transaction.atomic():
        lock = _lock_for_update()
        if _normalize_active(lock):
            raise CheckerServiceError("Вже є активна сесія чекера. Зупиніть її перед новим запуском.")
        job = LeadCheckJob.objects.create(
            created_by=user, status=LeadCheckJob.Status.RUNNING,
            scope=scope or "unchecked", city=(city or "").strip(), band=(band or "").strip(),
            target_limit=max(0, int(target_limit or 0)),
            requests_per_minute=max(1, min(20, int(requests_per_minute or 8))),
            total_selected=total,
        )
        lock.active_job = job
        lock.save(update_fields=["active_job", "updated_at"])
        return job


def pause_job(job_id) -> LeadCheckJob:
    with transaction.atomic():
        job = LeadCheckJob.objects.select_for_update().get(id=job_id)
        if job.status == LeadCheckJob.Status.RUNNING:
            job.status = LeadCheckJob.Status.PAUSED
            job.next_step_not_before = None
            job.save(update_fields=["status", "next_step_not_before", "updated_at"])
        return job


def resume_job(job_id) -> LeadCheckJob:
    with transaction.atomic():
        lock = _lock_for_update()
        active = _normalize_active(lock)
        job = LeadCheckJob.objects.select_for_update().get(id=job_id)
        if active and active.id != job.id:
            raise CheckerServiceError("Вже є інша активна сесія чекера.")
        if job.status == LeadCheckJob.Status.PAUSED:
            job.status = LeadCheckJob.Status.RUNNING
            job.last_error = ""
            job.save(update_fields=["status", "last_error", "updated_at"])
            lock.active_job = job
            lock.save(update_fields=["active_job", "updated_at"])
        return job


def stop_job(job_id, *, reason_code="user_stop") -> LeadCheckJob:
    with transaction.atomic():
        lock = _lock_for_update()
        job = LeadCheckJob.objects.select_for_update().get(id=job_id)
        if job.status in ACTIVE_STATUSES:
            job.status = LeadCheckJob.Status.STOPPED
            job.stop_reason_code = reason_code
            job.finished_at = timezone.now()
            job.next_step_not_before = None
            job.save(update_fields=["status", "stop_reason_code", "finished_at", "next_step_not_before", "updated_at"])
        if lock.active_job_id == job.id:
            lock.active_job = None
            lock.save(update_fields=["active_job", "updated_at"])
        return job


def dashboard_job(job_id=None) -> LeadCheckJob | None:
    if job_id:
        return LeadCheckJob.objects.filter(id=job_id).first()
    with transaction.atomic():
        lock = _lock_for_update()
        active = _normalize_active(lock)
    if active:
        return active
    return LeadCheckJob.objects.order_by("-started_at", "-id").first()
```

- [ ] **Step 4: Запустить — пройдёт**

Run: `cd twocomms && SECRET_KEY=test_local_secret python manage.py test management.tests_checker_job.JobLifecycleTests -v 2`
Expected: PASS (4 теста).

- [ ] **Step 5: Commit**

```bash
git add twocomms/management/services/lead_check_job.py twocomms/management/tests_checker_job.py
git commit -m "feat(checker): lifecycle сессии чекера + lock"
```

---

### Task 13: `run_step` — обработка одного лида за шаг

**Files:**
- Modify: `twocomms/management/services/lead_check_job.py`
- Test: `twocomms/management/tests_checker_job.py`

- [ ] **Step 1: Написать падающий тест**

Добавить в `twocomms/management/tests_checker_job.py`:

```python
from unittest.mock import patch

from management.models import LeadAICheck


class RunStepTests(TestCase):
    def setUp(self):
        self.leads = [
            ManagementLead.objects.create(shop_name=f"S{i}", phone=f"05011100{i}",
                                          lead_source=ManagementLead.LeadSource.PARSER)
            for i in range(3)
        ]

    def _fake_check(self, lead, **kw):
        # имитируем score_lead: создаём done-проверку и проставляем кэш
        check = LeadAICheck.objects.create(lead=lead, status=LeadAICheck.Status.DONE, overall_score=75)
        check._duration_seconds = 1.5
        lead.ai_score = 75
        lead.ai_verdict = "fit"
        lead.ai_checked_at = timezone.now()
        lead.save(update_fields=["ai_score", "ai_verdict", "ai_checked_at"])
        return check

    def test_step_processes_one_lead_and_advances(self):
        job = ljob.create_check_job(user=None, scope="unchecked", city="", band="", target_limit=0, requests_per_minute=60)
        with patch.object(ljob.lead_checker, "score_lead", side_effect=self._fake_check):
            job = ljob.run_step(job)
        self.assertEqual(job.processed, 1)
        self.assertEqual(job.scored, 1)
        self.assertEqual(job.fit_count, 1)
        self.assertGreater(job.cursor_id, 0)

    def test_step_completes_when_no_more_leads(self):
        job = ljob.create_check_job(user=None, scope="unchecked", city="", band="", target_limit=0, requests_per_minute=60)
        with patch.object(ljob.lead_checker, "score_lead", side_effect=self._fake_check):
            for _ in range(5):
                job = ljob.run_step(job)
        self.assertEqual(job.processed, 3)
        self.assertEqual(job.status, LeadCheckJob.Status.COMPLETED)

    def test_step_respects_target_limit(self):
        job = ljob.create_check_job(user=None, scope="unchecked", city="", band="", target_limit=2, requests_per_minute=60)
        with patch.object(ljob.lead_checker, "score_lead", side_effect=self._fake_check):
            for _ in range(5):
                job = ljob.run_step(job)
        self.assertEqual(job.processed, 2)
        self.assertEqual(job.status, LeadCheckJob.Status.COMPLETED)

    def test_step_counts_errors(self):
        def err_check(lead, **kw):
            check = LeadAICheck.objects.create(lead=lead, status=LeadAICheck.Status.ERROR, error="x")
            check._duration_seconds = 0.5
            lead.ai_verdict = "error"
            lead.ai_checked_at = timezone.now()
            lead.save(update_fields=["ai_verdict", "ai_checked_at"])
            return check
        job = ljob.create_check_job(user=None, scope="unchecked", city="", band="", target_limit=0, requests_per_minute=60)
        with patch.object(ljob.lead_checker, "score_lead", side_effect=err_check):
            job = ljob.run_step(job)
        self.assertEqual(job.errors, 1)
        self.assertEqual(job.scored, 0)
```

- [ ] **Step 2: Запустить — упадёт**

Run: `cd twocomms && SECRET_KEY=test_local_secret python manage.py test management.tests_checker_job.RunStepTests -v 2`
Expected: FAIL.

- [ ] **Step 3: Реализовать `run_step`**

Добавить в `lead_check_job.py`:

```python
import datetime


def _next_lead(job: LeadCheckJob):
    qs = candidate_queryset(scope=job.scope, city=job.city, band=job.band)
    return qs.filter(id__gt=job.cursor_id).first()


def _complete(job: LeadCheckJob, reason="completed"):
    job.status = LeadCheckJob.Status.COMPLETED
    job.stop_reason_code = reason
    job.finished_at = timezone.now()
    job.next_step_not_before = None
    job.save()
    with transaction.atomic():
        lock = _lock_for_update()
        if lock.active_job_id == job.id:
            lock.active_job = None
            lock.save(update_fields=["active_job", "updated_at"])


def run_step(job: LeadCheckJob) -> LeadCheckJob:
    job.refresh_from_db()
    if job.status != LeadCheckJob.Status.RUNNING:
        return job

    now = timezone.now()
    if job.next_step_not_before and now < job.next_step_not_before:
        return job

    if job.target_limit and job.processed >= job.target_limit:
        _complete(job, reason="target_reached")
        return job

    lead = _next_lead(job)
    if lead is None:
        _complete(job, reason="exhausted")
        return job

    job.current_lead_id = lead.id
    job.is_step_in_progress = True
    job.last_step_started_at = now
    job.save(update_fields=["current_lead_id", "is_step_in_progress", "last_step_started_at", "updated_at"])

    api_key = resolve_checker_api_key()
    try:
        check = lead_checker.score_lead(lead, api_key=api_key or None, checked_by=job.created_by, job=job)
    except Exception as exc:  # noqa: BLE001
        logger.exception("run_step score_lead crashed lead=%s", lead.id)
        job.errors += 1
        job.last_error = f"{type(exc).__name__}: {exc}"
        check = None

    job.processed += 1
    job.cursor_id = lead.id
    if check is not None:
        if check.status == LeadAICheck.Status.DONE:
            job.scored += 1
            band = lead.ai_verdict
            if band == "fit":
                job.fit_count += 1
            elif band == "maybe":
                job.maybe_count += 1
            elif band == "unfit":
                job.unfit_count += 1
        else:
            job.errors += 1
        dur = getattr(check, "_duration_seconds", 0.0) or 0.0
        if job.processed:
            job.avg_seconds = ((job.avg_seconds * (job.processed - 1)) + dur) / job.processed

    interval = 60.0 / max(1, job.requests_per_minute)
    job.next_step_not_before = timezone.now() + datetime.timedelta(seconds=interval)
    job.is_step_in_progress = False
    job.current_lead_id = None
    job.save()

    if job.target_limit and job.processed >= job.target_limit:
        _complete(job, reason="target_reached")
    elif _next_lead(job) is None:
        _complete(job, reason="exhausted")
    return job
```

- [ ] **Step 4: Запустить — пройдёт**

Run: `cd twocomms && SECRET_KEY=test_local_secret python manage.py test management.tests_checker_job.RunStepTests -v 2`
Expected: PASS (4 теста).

- [ ] **Step 5: Commit**

```bash
git add twocomms/management/services/lead_check_job.py twocomms/management/tests_checker_job.py
git commit -m "feat(checker): run_step — обработка лида за шаг"
```

---

### Task 14: Payload статуса для UI

**Files:**
- Modify: `twocomms/management/services/lead_check_job.py`
- Test: `twocomms/management/tests_checker_job.py`

- [ ] **Step 1: Написать падающий тест**

Добавить в `twocomms/management/tests_checker_job.py`:

```python
class StatusPayloadTests(TestCase):
    def setUp(self):
        ManagementLead.objects.create(shop_name="S0", phone="0501230000",
                                      lead_source=ManagementLead.LeadSource.PARSER)

    def test_payload_shape(self):
        job = ljob.create_check_job(user=None, scope="unchecked", city="", band="", target_limit=0, requests_per_minute=12)
        payload = ljob.job_status_payload(job)
        self.assertEqual(payload["id"], job.id)
        self.assertEqual(payload["status"], "running")
        self.assertEqual(payload["total_selected"], 1)
        self.assertEqual(payload["processed"], 0)
        self.assertIn("fit_count", payload)
        self.assertIn("maybe_count", payload)
        self.assertIn("unfit_count", payload)
        self.assertIn("errors", payload)
        self.assertIn("avg_seconds", payload)
        self.assertIn("next_step_eta_ms", payload)
        self.assertIn("elapsed_seconds", payload)

    def test_payload_none_job(self):
        self.assertIsNone(ljob.job_status_payload(None))
```

- [ ] **Step 2: Запустить — упадёт**

Run: `cd twocomms && SECRET_KEY=test_local_secret python manage.py test management.tests_checker_job.StatusPayloadTests -v 2`
Expected: FAIL.

- [ ] **Step 3: Реализовать payload**

Добавить в `lead_check_job.py`:

```python
def job_status_payload(job: LeadCheckJob | None) -> dict | None:
    if job is None:
        return None
    now = timezone.now()
    eta_ms = 0
    if job.status == LeadCheckJob.Status.RUNNING and job.next_step_not_before:
        delta = (job.next_step_not_before - now).total_seconds()
        eta_ms = max(0, int(delta * 1000))
    elapsed = 0
    if job.started_at:
        end = job.finished_at or now
        elapsed = int((end - job.started_at).total_seconds())
    remaining = max(0, job.total_selected - job.processed)
    return {
        "id": job.id,
        "status": job.status,
        "scope": job.scope,
        "city": job.city,
        "band": job.band,
        "total_selected": job.total_selected,
        "processed": job.processed,
        "scored": job.scored,
        "errors": job.errors,
        "remaining": remaining,
        "fit_count": job.fit_count,
        "maybe_count": job.maybe_count,
        "unfit_count": job.unfit_count,
        "avg_seconds": round(job.avg_seconds, 1),
        "requests_per_minute": job.requests_per_minute,
        "current_lead_id": job.current_lead_id,
        "is_step_in_progress": job.is_step_in_progress,
        "next_step_eta_ms": eta_ms,
        "elapsed_seconds": elapsed,
        "last_error": job.last_error,
        "stop_reason_code": job.stop_reason_code,
    }
```

- [ ] **Step 4: Запустить — пройдёт + весь модуль job**

Run: `cd twocomms && SECRET_KEY=test_local_secret python manage.py test management.tests_checker_job -v 2`
Expected: PASS (все классы).

- [ ] **Step 5: Commit**

```bash
git add twocomms/management/services/lead_check_job.py twocomms/management/tests_checker_job.py
git commit -m "feat(checker): payload статуса для UI"
```

---

## Этап 5. Вьюхи и маршруты

### Task 15: Сериализация результата проверки

**Files:**
- Create: `twocomms/management/checker_views.py`
- Test: `twocomms/management/tests_checker_views.py`

- [ ] **Step 1: Написать падающий тест**

Создать `twocomms/management/tests_checker_views.py`:

```python
from django.test import TestCase

from management.models import LeadAICheck, ManagementLead
from management import checker_views as cv


class SerializeCheckTests(TestCase):
    def test_serialize_lead_with_check(self):
        lead = ManagementLead.objects.create(
            shop_name="Coyote", phone="0501112233", city="Харків",
            website_url="https://coyote.example", ai_score=82, ai_verdict="fit",
            lead_source=ManagementLead.LeadSource.PARSER,
        )
        LeadAICheck.objects.create(
            lead=lead, status=LeadAICheck.Status.DONE, overall_score=82,
            verdict_category="brand", partnership_fit=["wholesale", "collab"],
            confidence="high", brand_summary="UA streetwear",
            criteria=[{"key": "product_relevance", "title": "Товар", "score": 9, "comment": "ok"}],
            recommendation="колаб", sources=[{"title": "IG", "url": "https://instagram.com/x"}],
            instagram_url="https://instagram.com/x",
        )
        data = cv.serialize_lead_check(lead)
        self.assertEqual(data["lead_id"], lead.id)
        self.assertEqual(data["shop_name"], "Coyote")
        self.assertEqual(data["ai_score"], 82)
        self.assertEqual(data["ai_verdict"], "fit")
        self.assertEqual(data["verdict_category"], "brand")
        self.assertEqual(data["partnership_fit"], ["wholesale", "collab"])
        self.assertEqual(len(data["criteria"]), 1)
        self.assertEqual(data["instagram_url"], "https://instagram.com/x")

    def test_serialize_lead_without_check(self):
        lead = ManagementLead.objects.create(shop_name="NoCheck", phone="0501112299",
                                             lead_source=ManagementLead.LeadSource.PARSER)
        data = cv.serialize_lead_check(lead)
        self.assertEqual(data["lead_id"], lead.id)
        self.assertIsNone(data["ai_score"])
        self.assertEqual(data["criteria"], [])
```

- [ ] **Step 2: Запустить — упадёт**

Run: `cd twocomms && SECRET_KEY=test_local_secret python manage.py test management.tests_checker_views.SerializeCheckTests -v 2`
Expected: FAIL (`ModuleNotFoundError: management.checker_views`).

- [ ] **Step 3: Создать модуль вьюх с сериализатором**

Создать `twocomms/management/checker_views.py`:

```python
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from .models import LeadAICheck, LeadCheckerSettings, ManagementLead
from .parsing_views import _require_admin_json
from .services import lead_check_job as ljob
from .services import lead_checker

RESULTS_PAGE_SIZE_OPTIONS = (10, 25, 50, 100)
DEFAULT_RESULTS_PAGE_SIZE = 25


def serialize_lead_check(lead: ManagementLead) -> dict:
    check = lead.ai_checks.order_by("-created_at").first()
    base = {
        "lead_id": lead.id,
        "shop_name": lead.shop_name,
        "city": lead.city,
        "website_url": lead.website_url,
        "google_maps_url": lead.google_maps_url,
        "phone": lead.phone,
        "ai_score": lead.ai_score,
        "ai_verdict": lead.ai_verdict or "",
        "niche_status": lead.niche_status,
        "status": lead.status,
    }
    if check is None:
        base.update({
            "check_status": "", "verdict_category": "", "partnership_fit": [],
            "confidence": "", "brand_summary": "", "audience_guess": "",
            "instagram_url": "", "comment": "", "recommendation": "",
            "criteria": [], "sources": [], "error": "", "model_used": "",
            "checked_at": None,
        })
        return base
    base.update({
        "check_status": check.status,
        "verdict_category": check.verdict_category,
        "partnership_fit": check.partnership_fit or [],
        "confidence": check.confidence,
        "brand_summary": check.brand_summary,
        "audience_guess": check.audience_guess,
        "instagram_url": check.instagram_url,
        "comment": check.comment,
        "recommendation": check.recommendation,
        "criteria": check.criteria or [],
        "sources": check.sources or [],
        "error": check.error,
        "model_used": check.model_used,
        "checked_at": check.created_at.isoformat() if check.created_at else None,
    })
    return base
```

- [ ] **Step 4: Запустить — пройдёт**

Run: `cd twocomms && SECRET_KEY=test_local_secret python manage.py test management.tests_checker_views.SerializeCheckTests -v 2`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add twocomms/management/checker_views.py twocomms/management/tests_checker_views.py
git commit -m "feat(checker): сериализация результата проверки"
```

---

### Task 16: JSON API (start/step/pause/resume/stop/status/results/recheck/settings)

**Files:**
- Modify: `twocomms/management/checker_views.py`
- Test: `twocomms/management/tests_checker_views.py`

- [ ] **Step 1: Написать падающий тест**

Добавить в `twocomms/management/tests_checker_views.py`:

```python
from django.contrib.auth import get_user_model
from django.test import Client as DjangoClient
from django.urls import reverse
from unittest.mock import patch

User = get_user_model()


class CheckerApiTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user("boss", password="x", is_staff=True)
        self.client = DjangoClient()
        self.client.force_login(self.staff)
        for i in range(2):
            ManagementLead.objects.create(shop_name=f"S{i}", phone=f"05055500{i}",
                                          lead_source=ManagementLead.LeadSource.PARSER)

    def test_start_status_stop_flow(self):
        r = self.client.post(reverse("management_checker_start_api"),
                             {"scope": "unchecked", "requests_per_minute": "20"})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["success"])
        job_id = body["job"]["id"]

        r = self.client.get(reverse("management_checker_status_api"), {"job_id": job_id})
        self.assertEqual(r.json()["job"]["total_selected"], 2)

        r = self.client.post(reverse("management_checker_stop_api"), {"job_id": job_id})
        self.assertEqual(r.json()["job"]["status"], "stopped")

    def test_step_scores_one(self):
        start = self.client.post(reverse("management_checker_start_api"),
                                 {"scope": "unchecked", "requests_per_minute": "60"}).json()
        job_id = start["job"]["id"]
        fake = {"parsed": {"overall_score": 78, "criteria": []}, "usage": {}, "model": "m"}
        with patch.object(lead_checker, "gemini_generate_grounded", return_value=fake), \
             patch.object(lead_checker, "fetch_website_text", return_value=("", False)):
            r = self.client.post(reverse("management_checker_step_api"), {"job_id": job_id})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["job"]["processed"], 1)

    def test_results_api_filters_band(self):
        lead = ManagementLead.objects.first()
        lead.ai_score = 85
        lead.ai_verdict = "fit"
        from django.utils import timezone
        lead.ai_checked_at = timezone.now()
        lead.save()
        LeadAICheck.objects.create(lead=lead, status=LeadAICheck.Status.DONE, overall_score=85)
        r = self.client.get(reverse("management_checker_results_api"), {"band": "fit"})
        self.assertEqual(r.status_code, 200)
        rows = r.json()["results"]["rows"]
        self.assertTrue(any(row["lead_id"] == lead.id for row in rows))

    def test_settings_api_saves_key(self):
        r = self.client.post(reverse("management_checker_settings_api"),
                             {"gemini_api_key": "new-key", "requests_per_minute": "10"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(LeadCheckerSettings.load().gemini_api_key, "new-key")

    def test_non_staff_denied(self):
        plain = User.objects.create_user("plain", password="x")
        c = DjangoClient()
        c.force_login(plain)
        r = c.post(reverse("management_checker_start_api"), {"scope": "unchecked"})
        self.assertEqual(r.status_code, 403)
```

- [ ] **Step 2: Запустить — упадёт**

Run: `cd twocomms && SECRET_KEY=test_local_secret python manage.py test management.tests_checker_views.CheckerApiTests -v 2`
Expected: FAIL (нет вьюх/маршрутов).

- [ ] **Step 3: Реализовать вьюхи**

Добавить в `checker_views.py`:

```python
@login_required(login_url="management_login")
@require_POST
def checker_start_api(request):
    denied = _require_admin_json(request)
    if denied:
        return denied
    try:
        job = ljob.create_check_job(
            user=request.user,
            scope=request.POST.get("scope", "unchecked"),
            city=request.POST.get("city", ""),
            band=request.POST.get("band", ""),
            target_limit=request.POST.get("target_limit", 0),
            requests_per_minute=request.POST.get("requests_per_minute", 8),
        )
    except ljob.CheckerServiceError as exc:
        return JsonResponse({"success": False, "error": str(exc)}, status=409)
    return JsonResponse({"success": True, "job": ljob.job_status_payload(job)})


@login_required(login_url="management_login")
@require_POST
def checker_step_api(request):
    denied = _require_admin_json(request)
    if denied:
        return denied
    job = ljob.dashboard_job(request.POST.get("job_id"))
    if job is None:
        return JsonResponse({"success": False, "error": "Сесію не знайдено."}, status=404)
    job = ljob.run_step(job)
    return JsonResponse({"success": True, "job": ljob.job_status_payload(job)})


def _simple_job_action(request, action):
    denied = _require_admin_json(request)
    if denied:
        return denied
    job_id = request.POST.get("job_id")
    if not job_id:
        return JsonResponse({"success": False, "error": "job_id обовʼязковий."}, status=400)
    try:
        job = action(job_id)
    except ljob.CheckerServiceError as exc:
        return JsonResponse({"success": False, "error": str(exc)}, status=409)
    except ljob.LeadCheckJob.DoesNotExist:
        return JsonResponse({"success": False, "error": "Сесію не знайдено."}, status=404)
    return JsonResponse({"success": True, "job": ljob.job_status_payload(job)})


@login_required(login_url="management_login")
@require_POST
def checker_pause_api(request):
    return _simple_job_action(request, ljob.pause_job)


@login_required(login_url="management_login")
@require_POST
def checker_resume_api(request):
    return _simple_job_action(request, ljob.resume_job)


@login_required(login_url="management_login")
@require_POST
def checker_stop_api(request):
    return _simple_job_action(request, ljob.stop_job)


@login_required(login_url="management_login")
@require_GET
def checker_status_api(request):
    denied = _require_admin_json(request)
    if denied:
        return denied
    job = ljob.dashboard_job(request.GET.get("job_id"))
    return JsonResponse({"success": True, "job": ljob.job_status_payload(job)})


def _results_queryset(band, city):
    qs = ManagementLead.objects.filter(lead_source=ManagementLead.LeadSource.PARSER,
                                       ai_checked_at__isnull=False)
    if band and band != "all":
        qs = qs.filter(ai_verdict=band)
    if city:
        qs = qs.filter(city__iexact=city.strip())
    return qs.order_by("-ai_score", "-ai_checked_at")


@login_required(login_url="management_login")
@require_GET
def checker_results_api(request):
    denied = _require_admin_json(request)
    if denied:
        return denied
    band = request.GET.get("band", "all")
    city = request.GET.get("city", "")
    try:
        page = max(1, int(request.GET.get("page", 1)))
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = int(request.GET.get("page_size", DEFAULT_RESULTS_PAGE_SIZE))
    except (TypeError, ValueError):
        page_size = DEFAULT_RESULTS_PAGE_SIZE
    if page_size not in RESULTS_PAGE_SIZE_OPTIONS:
        page_size = DEFAULT_RESULTS_PAGE_SIZE

    qs = _results_queryset(band, city).prefetch_related("ai_checks")
    paginator = Paginator(qs, page_size)
    page_obj = paginator.get_page(page)
    rows = [serialize_lead_check(lead) for lead in page_obj.object_list]
    return JsonResponse({"success": True, "results": {
        "rows": rows,
        "page": page_obj.number,
        "num_pages": paginator.num_pages,
        "total": paginator.count,
        "page_size": page_size,
        "band": band,
        "city": city,
    }})


@login_required(login_url="management_login")
@require_POST
def checker_recheck_api(request, lead_id):
    denied = _require_admin_json(request)
    if denied:
        return denied
    lead = ManagementLead.objects.filter(id=lead_id).first()
    if lead is None:
        return JsonResponse({"success": False, "error": "Лід не знайдено."}, status=404)
    api_key = ljob.resolve_checker_api_key() or None
    lead_checker.score_lead(lead, api_key=api_key, checked_by=request.user)
    lead.refresh_from_db()
    return JsonResponse({"success": True, "row": serialize_lead_check(lead)})


@login_required(login_url="management_login")
@require_POST
def checker_settings_api(request):
    denied = _require_admin_json(request)
    if denied:
        return denied
    s = LeadCheckerSettings.load()
    if "gemini_api_key" in request.POST:
        s.gemini_api_key = request.POST.get("gemini_api_key", "").strip()
    if request.POST.get("model_chain") is not None:
        s.model_chain = request.POST.get("model_chain", "").strip()
    try:
        s.requests_per_minute = max(1, min(20, int(request.POST.get("requests_per_minute", s.requests_per_minute))))
    except (TypeError, ValueError):
        pass
    s.save()
    return JsonResponse({"success": True, "settings": {
        "has_key": bool(s.gemini_api_key),
        "requests_per_minute": s.requests_per_minute,
        "model_chain": s.model_chain,
    }})
```

- [ ] **Step 4: Добавить маршруты (Task 17), затем запустить тесты**

(Тесты пройдут только после Task 17 — маршруты нужны для `reverse`. Выполни Task 17, затем вернись и запусти.)

Run (после Task 17): `cd twocomms && SECRET_KEY=test_local_secret python manage.py test management.tests_checker_views.CheckerApiTests -v 2`
Expected: PASS (5 тестов).

- [ ] **Step 5: Commit (вместе с Task 17)**

---

### Task 17: Маршруты + страница `checker_dashboard`

**Files:**
- Modify: `twocomms/management/checker_views.py` (страница)
- Modify: `twocomms/management/urls.py`
- Test: `twocomms/management/tests_checker_views.py`

- [ ] **Step 1: Написать падающий тест страницы**

Добавить в `twocomms/management/tests_checker_views.py`:

```python
class CheckerPageTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user("boss2", password="x", is_staff=True)
        self.client = DjangoClient()
        self.client.force_login(self.staff)

    def test_page_renders(self):
        r = self.client.get(reverse("management_checker"))
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"checker-endpoints", r.content)

    def test_page_redirects_anon(self):
        c = DjangoClient()
        r = c.get(reverse("management_checker"))
        self.assertIn(r.status_code, (302, 301))
```

- [ ] **Step 2: Реализовать страницу**

Добавить в `checker_views.py`:

```python
@login_required(login_url="management_login")
def checker_dashboard(request):
    if not (request.user.is_staff or request.user.is_superuser):
        # менеджеры Top+ тоже допускаются — мягкая проверка как на странице парсинга
        denied = _require_admin_json(request)
        if denied:
            return redirect("management_home")
    job = ljob.dashboard_job()
    settings_obj = LeadCheckerSettings.load()
    cities = list(
        ManagementLead.objects.filter(lead_source=ManagementLead.LeadSource.PARSER)
        .exclude(city="").values_list("city", flat=True).distinct().order_by("city")[:300]
    )
    counters = {
        "checked": ManagementLead.objects.filter(lead_source=ManagementLead.LeadSource.PARSER, ai_checked_at__isnull=False).count(),
        "unchecked": ManagementLead.objects.filter(lead_source=ManagementLead.LeadSource.PARSER, ai_checked_at__isnull=True).count(),
        "fit": ManagementLead.objects.filter(ai_verdict="fit").count(),
        "maybe": ManagementLead.objects.filter(ai_verdict="maybe").count(),
        "unfit": ManagementLead.objects.filter(ai_verdict="unfit").count(),
        "errors": ManagementLead.objects.filter(ai_verdict="error").count(),
    }
    context = {
        "active_job_json": ljob.job_status_payload(job),
        "checker_counters": counters,
        "checker_cities": cities,
        "checker_settings": {
            "has_key": bool(settings_obj.gemini_api_key),
            "requests_per_minute": settings_obj.requests_per_minute,
            "model_chain": settings_obj.model_chain,
        },
    }
    return render(request, "management/checker.html", context)
```

- [ ] **Step 3: Добавить маршруты в `urls.py`**

В `twocomms/management/urls.py` добавить импорт и маршруты. Рядом с импортом `parsing_views` (вверху файла) добавить:

```python
from . import checker_views
```

В список `urlpatterns`, сразу после блока `parsing/...` маршрутов, добавить:

```python
    # AI-чекер спарсенных аккаунтов
    path('checker/', checker_views.checker_dashboard, name='management_checker'),
    path('checker/api/start/', checker_views.checker_start_api, name='management_checker_start_api'),
    path('checker/api/step/', checker_views.checker_step_api, name='management_checker_step_api'),
    path('checker/api/pause/', checker_views.checker_pause_api, name='management_checker_pause_api'),
    path('checker/api/resume/', checker_views.checker_resume_api, name='management_checker_resume_api'),
    path('checker/api/stop/', checker_views.checker_stop_api, name='management_checker_stop_api'),
    path('checker/api/status/', checker_views.checker_status_api, name='management_checker_status_api'),
    path('checker/api/results/', checker_views.checker_results_api, name='management_checker_results_api'),
    path('checker/api/leads/<int:lead_id>/recheck/', checker_views.checker_recheck_api, name='management_checker_recheck_api'),
    path('checker/api/settings/', checker_views.checker_settings_api, name='management_checker_settings_api'),
```

- [ ] **Step 4: Создать минимальный шаблon-заглушку, чтобы страница рендерилась**

(Полный UI — в Этапе 6. Сейчас создать минимальный `twocomms/management/templates/management/checker.html`, чтобы тесты прошли.)

Создать `twocomms/management/templates/management/checker.html`:

```html
{% extends "management/base.html" %}
{% block title %}Чекер — TwoComms Management{% endblock %}
{% block content %}
<div id="checker-endpoints"
     data-start-url="{% url 'management_checker_start_api' %}"
     data-step-url="{% url 'management_checker_step_api' %}"
     data-pause-url="{% url 'management_checker_pause_api' %}"
     data-resume-url="{% url 'management_checker_resume_api' %}"
     data-stop-url="{% url 'management_checker_stop_api' %}"
     data-status-url="{% url 'management_checker_status_api' %}"
     data-results-url="{% url 'management_checker_results_api' %}"
     data-settings-url="{% url 'management_checker_settings_api' %}"
     data-recheck-url-template="{% url 'management_checker_recheck_api' 0 %}"></div>
{{ active_job_json|json_script:"checker-initial-job" }}
{{ checker_counters|json_script:"checker-initial-counters" }}
{{ checker_settings|json_script:"checker-initial-settings" }}
<h1>AI-чекер (UI в Этапе 6)</h1>
{% endblock %}
```

- [ ] **Step 5: Запустить тесты страницы и API**

Run: `cd twocomms && SECRET_KEY=test_local_secret python manage.py test management.tests_checker_views -v 2`
Expected: PASS (все классы: SerializeCheck, CheckerApi, CheckerPage).

- [ ] **Step 6: Commit**

```bash
git add twocomms/management/checker_views.py twocomms/management/urls.py twocomms/management/templates/management/checker.html twocomms/management/tests_checker_views.py
git commit -m "feat(checker): API-вьюхи, маршруты и страница-заглушка"
```

---

## Этап 6. Визуал (вкладка, UI, стили)

### Task 18: Вкладка «Чекер» в навигации

**Files:**
- Modify: `twocomms/management/templates/management/base.html` (блок `header-tabs`, под `{% if request.user.is_staff %}`)
- Test: `twocomms/management/tests_checker_views.py`

- [ ] **Step 1: Написать падающий тест**

Добавить в `twocomms/management/tests_checker_views.py`:

```python
class CheckerTabTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user("boss3", password="x", is_staff=True)
        self.client = DjangoClient()
        self.client.force_login(self.staff)

    def test_tab_present_for_staff(self):
        r = self.client.get(reverse("management_parsing"))
        self.assertEqual(r.status_code, 200)
        self.assertIn(reverse("management_checker").encode(), r.content)
        self.assertIn("Чекер".encode(), r.content)
```

- [ ] **Step 2: Запустить — упадёт**

Run: `cd twocomms && SECRET_KEY=test_local_secret python manage.py test management.tests_checker_views.CheckerTabTests -v 2`
Expected: FAIL.

- [ ] **Step 3: Добавить вкладку**

В `twocomms/management/templates/management/base.html`, в блоке `<nav class="header-tabs">`, сразу ПОСЛЕ строки со ссылкой `management_parsing` (Парсинг), добавить:

```html
            <a href="{% url 'management_checker' %}" class="tab{% if request.resolver_match.url_name == 'management_checker' %} active{% endif %}">Чекер</a>
```

- [ ] **Step 4: Запустить — пройдёт**

Run: `cd twocomms && SECRET_KEY=test_local_secret python manage.py test management.tests_checker_views.CheckerTabTests -v 2`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add twocomms/management/templates/management/base.html twocomms/management/tests_checker_views.py
git commit -m "feat(checker): вкладка Чекер в навигации"
```

---

### Task 19: Полный UI чекера (HTML-разметка `content`)

**Files:**
- Modify: `twocomms/management/templates/management/checker.html`

> Заменяем шаблон-заглушку на полный UI. Это разметка (hero, форма, метрики,
> вкладки-фильтры, таблица, модалка). Стили — в Task 20 (extra_css),
> JS — в Task 21 (extra_js).

- [ ] **Step 1: Переписать `content`-блок**

Полностью заменить содержимое `twocomms/management/templates/management/checker.html` на:

```html
{% extends "management/base.html" %}
{% load static %}
{% block title %}Чекер — TwoComms Management{% endblock %}

{% block content %}
<div id="checker-endpoints"
     data-start-url="{% url 'management_checker_start_api' %}"
     data-step-url="{% url 'management_checker_step_api' %}"
     data-pause-url="{% url 'management_checker_pause_api' %}"
     data-resume-url="{% url 'management_checker_resume_api' %}"
     data-stop-url="{% url 'management_checker_stop_api' %}"
     data-status-url="{% url 'management_checker_status_api' %}"
     data-results-url="{% url 'management_checker_results_api' %}"
     data-settings-url="{% url 'management_checker_settings_api' %}"
     data-recheck-url-template="{% url 'management_checker_recheck_api' 0 %}"></div>
{{ active_job_json|json_script:"checker-initial-job" }}
{{ checker_counters|json_script:"checker-initial-counters" }}
{{ checker_settings|json_script:"checker-initial-settings" }}

<div class="checker-shell">
  <section class="checker-hero">
    <div class="checker-hero__main">
      <p class="eyebrow">AI Lead Checker</p>
      <h1 class="checker-hero__title">Чекер спарсених акаунтів</h1>
      <p class="checker-hero__lead">Gemini з веб-пошуком оцінює кожен магазин за 10 критеріями (0–100), визначає бренд, канал співпраці та дає рекомендацію менеджеру.</p>
      <div class="checker-controls">
        <span class="status-chip" id="checker-status-chip">Очікування</span>
        <button type="button" class="btn-primary" id="checker-start-btn">Старт</button>
        <button type="button" class="btn-ghost" id="checker-pause-btn" hidden>Пауза</button>
        <button type="button" class="btn-ghost" id="checker-resume-btn" hidden>Відновити</button>
        <button type="button" class="btn-ghost" id="checker-stop-btn" hidden>Стоп</button>
      </div>
    </div>
    <aside class="checker-hero__metrics">
      <div class="checker-metric"><span class="checker-metric__label">Перевірено</span><span class="checker-metric__value" id="m-processed">0</span></div>
      <div class="checker-metric"><span class="checker-metric__label">Залишилось</span><span class="checker-metric__value" id="m-remaining">0</span></div>
      <div class="checker-metric"><span class="checker-metric__label">Минуло, с</span><span class="checker-metric__value" id="m-elapsed">0</span></div>
      <div class="checker-metric"><span class="checker-metric__label">Сер. час, с</span><span class="checker-metric__value" id="m-avg">0</span></div>
      <div class="checker-metric checker-metric--fit"><span class="checker-metric__label">Підходить</span><span class="checker-metric__value" id="m-fit">0</span></div>
      <div class="checker-metric checker-metric--maybe"><span class="checker-metric__label">Під питанням</span><span class="checker-metric__value" id="m-maybe">0</span></div>
      <div class="checker-metric checker-metric--unfit"><span class="checker-metric__label">Не підходить</span><span class="checker-metric__value" id="m-unfit">0</span></div>
      <div class="checker-metric checker-metric--error"><span class="checker-metric__label">Помилки</span><span class="checker-metric__value" id="m-errors">0</span></div>
    </aside>
  </section>

  <div class="checker-progress"><div class="progress-track"><div class="progress-fill" id="checker-progress-fill" style="width:0%"></div></div><span class="checker-progress__label" id="checker-progress-label">0 / 0</span></div>

  <div class="offer-grid offer-grid-single">
    <div class="offer-card">
      <div class="parsing-card-header">
        <div><p class="eyebrow">Запуск</p><h3 class="offer-title">Налаштування перевірки</h3></div>
        <p>Оберіть, які ліди перевіряти, і запустіть. Усе перевірене одразу зберігається — можна зупинити будь-коли.</p>
      </div>
      <form id="checker-form" class="checker-form">
        {% csrf_token %}
        <div class="field-grid">
          <div class="field">
            <label>Обсяг</label>
            <select name="scope" id="checker-scope">
              <option value="unchecked">Тільки неперевірені</option>
              <option value="all">Усі (перепровірка)</option>
              <option value="by_city">За містом</option>
              <option value="by_band">За смугою вердикту</option>
            </select>
          </div>
          <div class="field" id="checker-city-field" hidden>
            <label>Місто</label>
            <select name="city" id="checker-city">
              <option value="">— оберіть —</option>
              {% for c in checker_cities %}<option value="{{ c }}">{{ c }}</option>{% endfor %}
            </select>
          </div>
          <div class="field" id="checker-band-field" hidden>
            <label>Смуга вердикту</label>
            <select name="band" id="checker-band">
              <option value="fit">Підходить</option>
              <option value="maybe">Під питанням</option>
              <option value="unfit">Не підходить</option>
              <option value="error">Помилки</option>
            </select>
          </div>
          <div class="field"><label>Ліміт (0 = усі)</label><input type="number" name="target_limit" id="checker-limit" min="0" value="0"></div>
          <div class="field"><label>Запитів за хвилину</label><input type="number" name="requests_per_minute" id="checker-rpm" min="1" max="20" value="8"></div>
        </div>
      </form>
    </div>

    <details class="offer-card checker-settings-card">
      <summary class="offer-title">Ключ Gemini та налаштування</summary>
      <form id="checker-settings-form" class="checker-form">
        {% csrf_token %}
        <p class="offer-help">Якщо поле порожнє — використовується спільний ключ (ENV <code>GEMINI_API</code>), той самий, що в боті та аналізі дзвінків.</p>
        <div class="field-grid">
          <div class="field field-span-2"><label>Ключ Gemini (опц.)</label><input type="password" name="gemini_api_key" id="checker-key" placeholder="{% if checker_settings.has_key %}•••••• збережено{% else %}не задано{% endif %}"></div>
          <div class="field"><label>Моделі (csv, опц.)</label><input type="text" name="model_chain" id="checker-models" value="{{ checker_settings.model_chain }}" placeholder="gemini-2.5-flash,gemini-3.5-flash"></div>
          <div class="field"><label>RPM за замовч.</label><input type="number" name="requests_per_minute" id="checker-settings-rpm" min="1" max="20" value="{{ checker_settings.requests_per_minute }}"></div>
        </div>
        <button type="submit" class="btn-ghost">Зберегти налаштування</button>
        <span id="checker-settings-status" class="checker-inline-status" hidden></span>
      </form>
    </details>
  </div>

  <div class="checker-results offer-card">
    <div class="checker-results__head">
      <div><p class="eyebrow">Результати</p><h3 class="offer-title">Перевірені акаунти</h3></div>
      <div class="checker-results__tools">
        <select id="checker-results-city" class="checker-mini-select"><option value="">Усі міста</option>{% for c in checker_cities %}<option value="{{ c }}">{{ c }}</option>{% endfor %}</select>
        <select id="checker-results-page-size" class="checker-mini-select"><option value="10">10</option><option value="25" selected>25</option><option value="50">50</option><option value="100">100</option></select>
      </div>
    </div>
    <div class="checker-tabs" id="checker-tabs">
      <button type="button" class="checker-tab is-active" data-band="all">Усі</button>
      <button type="button" class="checker-tab" data-band="fit">Підходить</button>
      <button type="button" class="checker-tab" data-band="maybe">Під питанням</button>
      <button type="button" class="checker-tab" data-band="unfit">Не підходить</button>
      <button type="button" class="checker-tab" data-band="error">Помилки</button>
    </div>
    <div class="table-shell">
      <table class="nexus-table checker-table" id="checker-results-table">
        <thead><tr>
          <th>Магазин</th><th>Оцінка</th><th>Категорія</th><th>Бренд</th><th>Канали</th><th>Сайт / IG</th><th>Дія</th>
        </tr></thead>
        <tbody></tbody>
      </table>
    </div>
    <div class="checker-pagination" id="checker-pagination"></div>
  </div>
</div>

<div id="checker-detail-modal" class="modal-overlay">
  <div class="modal-card modal-card--wide">
    <div class="modal-header">
      <div><p class="eyebrow">Розбір ШІ</p><h3 id="checker-detail-title">—</h3></div>
      <button type="button" class="modal-close" aria-label="Закрити">×</button>
    </div>
    <div class="modal-body" id="checker-detail-body"></div>
    <div class="modal-footer">
      <button type="button" class="btn-ghost" id="checker-recheck-btn">Перевірити знову</button>
      <a href="#" target="_blank" rel="noopener" class="btn-ghost" id="checker-detail-site" hidden>Відкрити сайт</a>
    </div>
  </div>
</div>
{% endblock %}
```

- [ ] **Step 2: Проверить рендер страницы**

Run: `cd twocomms && SECRET_KEY=test_local_secret python manage.py test management.tests_checker_views.CheckerPageTests -v 2`
Expected: PASS (страница рендерится с новой разметкой).

- [ ] **Step 3: Commit**

```bash
git add twocomms/management/templates/management/checker.html
git commit -m "feat(checker): полная HTML-разметка UI"
```

---

### Task 20: Стили чекера (`extra_css`)

**Files:**
- Modify: `twocomms/management/templates/management/checker.html` (добавить блок `extra_css` перед `{% block content %}`)

- [ ] **Step 1: Добавить блок стилей**

В `checker.html`, между `{% endblock %}` заголовка и `{% block content %}`, вставить:

```html
{% block extra_css %}
<style>
.checker-shell{display:flex;flex-direction:column;gap:18px;}
.checker-hero{display:flex;gap:20px;justify-content:space-between;flex-wrap:wrap;background:var(--panel-strong);border:1px solid var(--border);border-radius:var(--radius-lg);padding:22px 24px;box-shadow:var(--shadow-lg);}
.checker-hero__title{margin:6px 0 8px;font-size:1.5rem;color:var(--text-primary);}
.checker-hero__lead{color:var(--text-secondary);max-width:560px;margin:0 0 14px;font-size:.92rem;}
.checker-controls{display:flex;align-items:center;gap:10px;flex-wrap:wrap;}
.checker-hero__metrics{display:grid;grid-template-columns:repeat(2,minmax(120px,1fr));gap:10px;align-content:start;}
.checker-metric{background:var(--bg-850);border:1px solid var(--border);border-radius:var(--radius-md,12px);padding:10px 12px;display:flex;flex-direction:column;gap:2px;min-width:120px;}
.checker-metric__label{font-size:.72rem;color:var(--muted);text-transform:uppercase;letter-spacing:.04em;}
.checker-metric__value{font-size:1.3rem;font-weight:600;color:var(--text-primary);}
.checker-metric--fit .checker-metric__value{color:#4ade80;}
.checker-metric--maybe .checker-metric__value{color:var(--accent);}
.checker-metric--unfit .checker-metric__value{color:#f87171;}
.checker-metric--error .checker-metric__value{color:#fb7185;}
.checker-progress{display:flex;align-items:center;gap:12px;}
.checker-progress .progress-track{flex:1;height:8px;background:var(--bg-850);border-radius:99px;overflow:hidden;}
.checker-progress .progress-fill{height:100%;background:linear-gradient(90deg,var(--accent),var(--accent-strong));width:0;transition:width .4s ease;}
.checker-progress__label{font-size:.8rem;color:var(--text-secondary);min-width:90px;text-align:right;}
.checker-form .field-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;}
.checker-form .field{display:flex;flex-direction:column;gap:6px;}
.checker-form label{font-size:.78rem;color:var(--text-secondary);}
.checker-form input,.checker-form select{background:var(--bg-850);border:1px solid var(--border);border-radius:10px;padding:9px 11px;color:var(--text-primary);font-size:.9rem;}
.field-span-2{grid-column:span 2;}
.checker-inline-status{font-size:.8rem;color:#4ade80;margin-left:10px;}
.checker-results__head{display:flex;justify-content:space-between;align-items:flex-end;gap:12px;flex-wrap:wrap;}
.checker-results__tools{display:flex;gap:8px;}
.checker-mini-select{background:var(--bg-850);border:1px solid var(--border);border-radius:8px;color:var(--text-primary);padding:6px 9px;font-size:.82rem;}
.checker-tabs{display:flex;gap:6px;margin:14px 0;flex-wrap:wrap;}
.checker-tab{background:var(--bg-850);border:1px solid var(--border);border-radius:99px;color:var(--text-secondary);padding:7px 16px;font-size:.84rem;cursor:pointer;transition:all .2s;}
.checker-tab:hover{color:var(--text-primary);}
.checker-tab.is-active{background:var(--accent);border-color:var(--accent);color:#1a1205;font-weight:600;}
.checker-table th,.checker-table td{padding:10px 12px;text-align:left;vertical-align:middle;}
.checker-score{display:inline-flex;align-items:center;justify-content:center;min-width:46px;height:30px;border-radius:8px;font-weight:700;font-size:.95rem;}
.checker-score--fit{background:rgba(74,222,128,.16);color:#4ade80;}
.checker-score--maybe{background:rgba(243,164,61,.16);color:var(--accent);}
.checker-score--unfit{background:rgba(248,113,113,.16);color:#f87171;}
.checker-score--error{background:rgba(148,163,184,.16);color:var(--muted);}
.checker-chip{display:inline-block;background:var(--bg-850);border:1px solid var(--border);border-radius:99px;padding:2px 9px;font-size:.72rem;color:var(--text-secondary);margin:2px 3px 0 0;}
.checker-brand-cell{max-width:280px;color:var(--text-secondary);font-size:.84rem;}
.checker-link-btn{color:var(--accent);text-decoration:none;font-size:.8rem;}
.checker-detail-btn{background:transparent;border:1px solid var(--border);border-radius:8px;color:var(--text-primary);padding:6px 12px;cursor:pointer;font-size:.8rem;}
.checker-detail-btn:hover{border-color:var(--accent);}
.checker-pagination{display:flex;gap:6px;align-items:center;justify-content:center;margin-top:14px;flex-wrap:wrap;}
.checker-pagination button{background:var(--bg-850);border:1px solid var(--border);border-radius:8px;color:var(--text-secondary);padding:6px 12px;cursor:pointer;}
.checker-pagination button.is-active{background:var(--accent);color:#1a1205;border-color:var(--accent);}
.modal-card--wide{max-width:760px;width:94vw;}
.checker-criteria{display:flex;flex-direction:column;gap:8px;margin:12px 0;}
.checker-criterion{display:grid;grid-template-columns:1fr auto;gap:6px 12px;background:var(--bg-850);border:1px solid var(--border);border-radius:10px;padding:9px 12px;}
.checker-criterion__title{color:var(--text-primary);font-size:.86rem;font-weight:600;}
.checker-criterion__bar{grid-column:1/-1;height:6px;background:var(--bg-900);border-radius:99px;overflow:hidden;}
.checker-criterion__bar i{display:block;height:100%;background:linear-gradient(90deg,var(--accent),var(--accent-strong));}
.checker-criterion__comment{grid-column:1/-1;color:var(--text-secondary);font-size:.8rem;}
.checker-detail-section{margin:12px 0;}
.checker-detail-section h4{margin:0 0 6px;color:var(--text-primary);font-size:.9rem;}
.checker-detail-section p{color:var(--text-secondary);font-size:.86rem;margin:0;}
.checker-sources a{display:block;color:var(--accent);font-size:.8rem;margin:2px 0;text-decoration:none;}
.checker-confidence{font-size:.74rem;padding:2px 8px;border-radius:99px;border:1px solid var(--border);color:var(--text-secondary);}
@media(max-width:720px){.checker-hero__metrics{grid-template-columns:repeat(2,1fr);}.field-span-2{grid-column:span 1;}}
</style>
{% endblock %}
```

- [ ] **Step 2: Commit**

```bash
git add twocomms/management/templates/management/checker.html
git commit -m "feat(checker): стили UI"
```

---

### Task 21: JS чекера (`extra_js`)

**Files:**
- Modify: `twocomms/management/templates/management/checker.html` (добавить блок `extra_js` перед закрывающим тегом)

- [ ] **Step 1: Добавить блок JS**

В `checker.html`, после `{% endblock %}` блока `content`, добавить:

```html
{% block extra_js %}
<script>
function initCheckerPage(){
  const root = document.getElementById('checker-endpoints');
  if(!root || root.dataset.bound === '1') return;
  root.dataset.bound = '1';
  const url = (k) => root.dataset[k];
  const recheckTpl = root.dataset.recheckUrlTemplate;

  const readJson = (id) => { const el = document.getElementById(id); if(!el) return null; try{return JSON.parse(el.textContent);}catch(e){return null;} };
  let activeJob = readJson('checker-initial-job');
  let curBand = 'all', curPage = 1;
  let stepTimer = null, pollTimer = null, stepInFlight = false, statusInFlight = false;

  const getCookie = (name) => { const m = document.cookie.match('(^|;)\\s*'+name+'\\s*=\\s*([^;]+)'); return m ? m.pop() : ''; };
  async function apiRequest(u, data, method){
    method = method || (data ? 'POST' : 'GET');
    const opts = { method, headers: {} };
    if(method !== 'GET'){
      opts.headers['X-CSRFToken'] = getCookie('csrftoken');
      const fd = new FormData();
      if(data instanceof FormData){ data.forEach((v,k)=>fd.append(k,v)); }
      else if(data){ Object.entries(data).forEach(([k,v])=>fd.append(k,v)); }
      fd.append('csrfmiddlewaretoken', getCookie('csrftoken'));
      opts.body = fd;
    }
    const res = await fetch(u, opts);
    let payload = {};
    try{ payload = await res.json(); }catch(e){}
    if(!res.ok || payload.success === false){ const err = new Error(payload.error || ('HTTP '+res.status)); err.payload = payload; throw err; }
    return payload;
  }

  const $ = (id) => document.getElementById(id);
  const setText = (id,v) => { const el=$(id); if(el) el.textContent = v; };

  function applyJob(job){
    activeJob = job;
    const chip = $('checker-status-chip');
    const labels = {running:'Працює',paused:'Пауза',stopped:'Зупинено',completed:'Завершено',failed:'Помилка'};
    if(job){
      setText('m-processed', job.processed);
      setText('m-remaining', job.remaining);
      setText('m-elapsed', job.elapsed_seconds);
      setText('m-avg', job.avg_seconds);
      setText('m-fit', job.fit_count);
      setText('m-maybe', job.maybe_count);
      setText('m-unfit', job.unfit_count);
      setText('m-errors', job.errors);
      const pct = job.total_selected ? Math.min(100, Math.round(job.processed*100/job.total_selected)) : 0;
      const fill = $('checker-progress-fill'); if(fill) fill.style.width = pct+'%';
      setText('checker-progress-label', job.processed+' / '+job.total_selected);
      if(chip){ chip.textContent = labels[job.status] || job.status; }
    } else if(chip){ chip.textContent = 'Очікування'; }
    const running = job && job.status === 'running';
    const paused = job && job.status === 'paused';
    $('checker-start-btn').hidden = running || paused;
    $('checker-pause-btn').hidden = !running;
    $('checker-resume-btn').hidden = !paused;
    $('checker-stop-btn').hidden = !(running || paused);
  }

  const canStep = () => activeJob && activeJob.status === 'running';
  function scheduleStep(delay){ if(stepTimer){clearTimeout(stepTimer);stepTimer=null;} if(!canStep()) return; stepTimer = setTimeout(runStep, Math.max(250, Number(delay||0))); }
  async function runStep(){
    if(stepInFlight || !canStep()) return; stepInFlight = true;
    try{ const p = await apiRequest(url('stepUrl'), {job_id: activeJob.id}); applyJob(p.job); }
    catch(e){ console.error(e); }
    finally{ stepInFlight = false; if(canStep()){ scheduleStep(activeJob.next_step_eta_ms||0); } else { loadResults(); } }
  }
  function schedulePoll(delay){ if(pollTimer){clearTimeout(pollTimer);pollTimer=null;} const d = delay!=null?delay:(activeJob && activeJob.status==='running'?3500:6000); pollTimer = setTimeout(pollStatus, Math.max(1500,d)); }
  async function pollStatus(){
    if(statusInFlight){return;} statusInFlight = true;
    try{ const q = activeJob ? ('?job_id='+activeJob.id) : ''; const p = await apiRequest(url('statusUrl')+q, null, 'GET'); applyJob(p.job); }
    catch(e){ console.warn(e); }
    finally{ statusInFlight = false; schedulePoll(); }
  }

  // ---- форма scope: показ city/band ----
  const scopeSel = $('checker-scope');
  function syncScope(){
    $('checker-city-field').hidden = scopeSel.value !== 'by_city';
    $('checker-band-field').hidden = scopeSel.value !== 'by_band';
  }
  scopeSel.addEventListener('change', syncScope); syncScope();

  // ---- запуск ----
  $('checker-start-btn').addEventListener('click', async () => {
    const fd = new FormData($('checker-form'));
    try{ const p = await apiRequest(url('startUrl'), fd); applyJob(p.job); if(p.job && p.job.status==='running'){ scheduleStep(0); } }
    catch(e){ alert(e.message || 'Не вдалося запустити чекер'); }
  });
  $('checker-pause-btn').addEventListener('click', async () => { try{ const p = await apiRequest(url('pauseUrl'), {job_id:activeJob.id}); applyJob(p.job); }catch(e){ alert(e.message);} });
  $('checker-resume-btn').addEventListener('click', async () => { try{ const p = await apiRequest(url('resumeUrl'), {job_id:activeJob.id}); applyJob(p.job); if(canStep()) scheduleStep(0);}catch(e){ alert(e.message);} });
  $('checker-stop-btn').addEventListener('click', async () => { try{ const p = await apiRequest(url('stopUrl'), {job_id:activeJob.id}); applyJob(p.job); loadResults(); }catch(e){ alert(e.message);} });

  // ---- настройки ----
  $('checker-settings-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    try{ await apiRequest(url('settingsUrl'), fd); const s=$('checker-settings-status'); s.hidden=false; s.textContent='Збережено'; setTimeout(()=>{s.hidden=true;},2500); }
    catch(err){ alert(err.message || 'Не вдалося зберегти'); }
  });

  // ---- результаты ----
  const VERDICT_LABELS = {physical_store:'Фізмагазин',retail_chain:'Мережа',dropshipper:'Дропшипер',brand:'Бренд',voentorg:'Військторг',marketplace_seller:'Маркетплейс',irrelevant:'Нерелевантно'};
  const CHANNEL_LABELS = {wholesale:'Опт',custom_print:'Кастом-друк',collab:'Колаб',dropship:'Дропшип',test_batch:'Тест-партія',shelf:'Полиця'};
  const bandClass = (v) => ({fit:'fit',maybe:'maybe',unfit:'unfit',error:'error'}[v] || 'error');
  const esc = (s) => (s==null?'':String(s)).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

  function rowHtml(r){
    const cls = bandClass(r.ai_verdict);
    const scoreTxt = r.ai_verdict==='error' ? '—' : (r.ai_score==null?'—':r.ai_score);
    const channels = (r.partnership_fit||[]).map(c=>`<span class="checker-chip">${esc(CHANNEL_LABELS[c]||c)}</span>`).join('');
    const site = r.website_url ? `<a class="checker-link-btn" href="${esc(r.website_url)}" target="_blank" rel="noopener">сайт</a>` : '';
    const ig = r.instagram_url ? `<a class="checker-link-btn" href="${esc(r.instagram_url)}" target="_blank" rel="noopener">IG</a>` : '';
    return `<tr>
      <td>${esc(r.shop_name)}<div class="muted-detail">${esc(r.city||'')}</div></td>
      <td><span class="checker-score checker-score--${cls}">${scoreTxt}</span></td>
      <td>${esc(VERDICT_LABELS[r.verdict_category]||'')}</td>
      <td class="checker-brand-cell">${esc((r.brand_summary||'').slice(0,140))}</td>
      <td>${channels}</td>
      <td>${site} ${ig}</td>
      <td><button type="button" class="checker-detail-btn" data-lead="${r.lead_id}">Деталі</button></td>
    </tr>`;
  }

  let lastRows = [];
  async function loadResults(){
    const city = $('checker-results-city').value;
    const ps = $('checker-results-page-size').value;
    const params = new URLSearchParams({band:curBand, city, page:curPage, page_size:ps});
    try{
      const p = await apiRequest(url('resultsUrl')+'?'+params.toString(), null, 'GET');
      lastRows = p.results.rows;
      const tb = document.querySelector('#checker-results-table tbody');
      tb.innerHTML = lastRows.length ? lastRows.map(rowHtml).join('') : '<tr><td colspan="7" class="table-empty">Немає даних</td></tr>';
      renderPagination(p.results);
    }catch(e){ console.warn(e); }
  }
  function renderPagination(res){
    const box = $('checker-pagination'); box.innerHTML='';
    if(res.num_pages<=1) return;
    for(let i=1;i<=res.num_pages;i++){
      if(i>1 && i<res.num_pages && Math.abs(i-res.page)>2) { if(box.lastChild && box.lastChild.textContent!=='…'){const e=document.createElement('span');e.textContent='…';e.className='checker-chip';box.appendChild(e);} continue; }
      const b=document.createElement('button'); b.textContent=i; if(i===res.page) b.classList.add('is-active');
      b.addEventListener('click',()=>{curPage=i;loadResults();}); box.appendChild(b);
    }
  }

  document.getElementById('checker-tabs').addEventListener('click',(e)=>{
    const btn=e.target.closest('.checker-tab'); if(!btn) return;
    document.querySelectorAll('.checker-tab').forEach(t=>t.classList.remove('is-active'));
    btn.classList.add('is-active'); curBand=btn.dataset.band; curPage=1; loadResults();
  });
  $('checker-results-city').addEventListener('change',()=>{curPage=1;loadResults();});
  $('checker-results-page-size').addEventListener('change',()=>{curPage=1;loadResults();});

  // ---- модалка деталей ----
  const modal=$('checker-detail-modal');
  let modalLead=null;
  function openModal(r){
    modalLead=r;
    $('checker-detail-title').textContent = r.shop_name;
    const conf = r.confidence?`<span class="checker-confidence">впевненість: ${esc(r.confidence)}</span>`:'';
    const crit = (r.criteria||[]).map(c=>`<div class="checker-criterion"><span class="checker-criterion__title">${esc(c.title||c.key)}</span><b>${c.score}/10</b><div class="checker-criterion__bar"><i style="width:${(c.score||0)*10}%"></i></div>${c.comment?`<div class="checker-criterion__comment">${esc(c.comment)}</div>`:''}</div>`).join('');
    const channels = (r.partnership_fit||[]).map(c=>`<span class="checker-chip">${esc(CHANNEL_LABELS[c]||c)}</span>`).join('') || '—';
    const sources = (r.sources||[]).map(s=>`<a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.title||s.url)}</a>`).join('') || '<p>немає</p>';
    const errBlock = r.error?`<div class="checker-detail-section"><h4>Помилка</h4><p>${esc(r.error)}</p></div>`:'';
    $('checker-detail-body').innerHTML = `
      <div class="checker-detail-section"><h4>Оцінка: ${r.ai_score==null?'—':r.ai_score}/100 ${conf}</h4><p>${esc(VERDICT_LABELS[r.verdict_category]||'')}</p></div>
      <div class="checker-detail-section"><h4>Бренд</h4><p>${esc(r.brand_summary||'—')}</p></div>
      <div class="checker-detail-section"><h4>Аудиторія</h4><p>${esc(r.audience_guess||'—')}</p></div>
      <div class="checker-detail-section"><h4>Канали</h4><p>${channels}</p></div>
      <div class="checker-detail-section"><h4>Критерії</h4><div class="checker-criteria">${crit||'<p>—</p>'}</div></div>
      <div class="checker-detail-section"><h4>Висновок</h4><p>${esc(r.comment||'—')}</p></div>
      <div class="checker-detail-section"><h4>Рекомендація менеджеру</h4><p>${esc(r.recommendation||'—')}</p></div>
      <div class="checker-detail-section checker-sources"><h4>Джерела</h4>${sources}</div>
      ${errBlock}`;
    const siteBtn=$('checker-detail-site');
    if(r.website_url){ siteBtn.hidden=false; siteBtn.href=r.website_url; } else { siteBtn.hidden=true; }
    modal.classList.add('is-open'); modal.style.display='flex';
  }
  function closeModal(){ modal.classList.remove('is-open'); modal.style.display='none'; modalLead=null; }
  document.querySelector('#checker-results-table').addEventListener('click',(e)=>{
    const btn=e.target.closest('.checker-detail-btn'); if(!btn) return;
    const r = lastRows.find(x=>String(x.lead_id)===btn.dataset.lead); if(r) openModal(r);
  });
  modal.querySelector('.modal-close').addEventListener('click', closeModal);
  modal.addEventListener('click',(e)=>{ if(e.target===modal) closeModal(); });
  $('checker-recheck-btn').addEventListener('click', async () => {
    if(!modalLead) return;
    const u = recheckTpl.replace('/0/', '/'+modalLead.lead_id+'/');
    try{ const p = await apiRequest(u, {}); openModal(p.row); loadResults(); }
    catch(e){ alert(e.message || 'Не вдалося перевірити'); }
  });

  applyJob(activeJob);
  loadResults();
  if(canStep()) scheduleStep(0);
  schedulePoll();
}
if(document.readyState==='loading'){ document.addEventListener('DOMContentLoaded', initCheckerPage); } else { initCheckerPage(); }
</script>
{% endblock %}
```

- [ ] **Step 2: Проверить рендер**

Run: `cd twocomms && SECRET_KEY=test_local_secret python manage.py test management.tests_checker_views -v 2`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add twocomms/management/templates/management/checker.html
git commit -m "feat(checker): JS — движок, результаты, модалка"
```

---

## Этап 7. Интеграция, проверка, деплой

### Task 22: Полный прогон тестов management + проверка миграций

**Files:** —

- [ ] **Step 1: Прогнать все тесты чекера**

Run: `cd twocomms && SECRET_KEY=test_local_secret python manage.py test management.tests_checker_scoring management.tests_checker_job management.tests_checker_gemini management.tests_checker_views -v 2`
Expected: PASS (все).

- [ ] **Step 2: Проверить, что нет незакоммиченных миграций**

Run: `cd twocomms && SECRET_KEY=test_local_secret python manage.py makemigrations --check --dry-run management`
Expected: `No changes detected` (все миграции уже созданы и закоммичены).

- [ ] **Step 3: Прогнать смежные management-тесты (регрессия парсера/моделей)**

Run: `cd twocomms && SECRET_KEY=test_local_secret python manage.py test management.tests_parser_usage management.tests_phase2_dedupe -v 1`
Expected: PASS (наши изменения не сломали парсер/дедуп). Допустимы пред-существующие 301-редиректы из i18n (см. steering), если всплывут в других сьютах — это не регрессия чекера.

- [ ] **Step 4: Commit (если что-то правили)**

```bash
git add -A && git commit -m "test(checker): полный прогон и фикс регрессий" || echo "нечего коммитить"
```

---

### Task 23: Локальный smoke-тест страницы (рендер + статика)

**Files:** —

- [ ] **Step 1: Проверить системные ошибки Django**

Run: `cd twocomms && SECRET_KEY=test_local_secret python manage.py check`
Expected: `System check identified no issues`.

- [ ] **Step 2: Отрендерить страницу чекера через тестовый клиент и проверить ключевые узлы**

Run:
```bash
cd twocomms && SECRET_KEY=test_local_secret python manage.py shell -c "
from django.test import Client
from django.contrib.auth import get_user_model
U=get_user_model()
u=U.objects.filter(is_staff=True).first() or U.objects.create_user('smoke_staff',password='x',is_staff=True)
c=Client(); c.force_login(u)
r=c.get('/checker/')
html=r.content.decode()
print('status', r.status_code)
for token in ['checker-endpoints','checker-form','checker-results-table','checker-detail-modal','initCheckerPage']:
    print(token, token in html)
"
```
Expected: `status 200` и `True` для всех токенов.

- [ ] **Step 3: Очистить тестового пользователя**

Run:
```bash
cd twocomms && SECRET_KEY=test_local_secret python manage.py shell -c "
from django.contrib.auth import get_user_model
get_user_model().objects.filter(username='smoke_staff').delete()
print('cleaned')
"
```
Expected: `cleaned`.

---

### Task 24: Деплой и реальный прогон на 5-6 спарсенных лидах

> Деплой выполняется SSH-командой из сообщения пользователя (с секретом — НЕ
> сохранять в файлы/логи/коммиты, см. steering). Изменения трогают `models.py`
> (миграции), CSS не меняем в styles.css → collectstatic нужен из-за нового
> шаблона со `{% static %}`? Шаблон чекера НЕ использует новых статических
> ассетов (только существующие через base.html). Новых файлов в `static/` нет.

Чек-лист деплоя (одна SSH-сессия, активированный venv, см. workflow.md):

- [ ] **Step 1: Push ветки**

```bash
git -C /Users/zainllw0w/TwoComms/site push origin HEAD
```

- [ ] **Step 2: На сервере** `git pull` → `python manage.py migrate --no-input` (есть новые миграции management) → `python manage.py check` → `touch tmp/restart.txt`.

`collectstatic`/`compress` НЕ требуются: новых файлов в `static/` нет, CSS/JS чекера инлайнятся в шаблон (внутри `{% block extra_css/extra_js %}`), которые не проходят через `{% compress %}` парсинг-шаблона. Если после рестарта `/checker/` отдаёт 500 с `ManifestStaticFilesStorage` — значит base.html подтянул что-то новое: тогда выполнить `collectstatic --no-input` и снова `touch tmp/restart.txt`.

- [ ] **Step 3: Sanity-curl после рестарта** (ждать ~10с)

Проверить `/` (200), `/checker/` (302 без авторизации — редирект на логин, это ок), `/parsing/` (302/200). Через авторизованную сессию `/checker/` должен быть 200.

- [ ] **Step 4: Реальный прогон AI на 5-6 лидах**

На сервере (или локально через прод-БД, если доступна) запустить чек-сессию с `target_limit=5` и `scope=unchecked`, замерить время/токены:

```bash
# на сервере, в активированном venv, из каталога twocomms:
python manage.py shell -c "
import time
from management.services import lead_check_job as ljob
from management.services import lead_checker
job = ljob.create_check_job(user=None, scope='unchecked', city='', band='', target_limit=5, requests_per_minute=20)
t0=time.time()
for _ in range(20):
    job = ljob.run_step(job)
    if job.status != 'running': break
    time.sleep(0.2)
print('processed', job.processed, 'scored', job.scored, 'errors', job.errors)
print('avg_seconds', job.avg_seconds, 'elapsed', round(time.time()-t0,1))
from management.models import LeadAICheck
for ch in LeadAICheck.objects.order_by('-id')[:5]:
    print(ch.lead.shop_name, '->', ch.overall_score, ch.verdict_category, ch.partnership_fit, 'conf=', ch.confidence)
"
```
Expected: 5 проверок со статусами `done`/`error`, осмысленные баллы/категории, разумное среднее время (ориентир 5–15 c/лид с grounding). Зафиксировать наблюдения (время, токены, доля ошибок) в отчёте пользователю.

- [ ] **Step 5: Финальный отчёт пользователю (русский)**

Кратко: что задеплоено, результаты прогона (сколько проверено, среднее время, примеры оценок), что работает, замеченные ограничения (например, мёртвые сайты / низкая confidence по IG-бредам).

---

## Self-Review плана (выполнено автором)

**1. Покрытие спеки:**
- §2 аудитория/эталон → Task 8 (system-prompt с %-разбивкой и брендом). ✅
- §3 каналы (список) → Task 6 (PARTNERSHIP_CHANNELS), Task 9 (нормализация списка), Task 8 (промпт). ✅
- §4 10 критериев + поля вердикта → Task 6 (CRITERIA), Task 9 (normalize), Task 8 (промпт). ✅
- §4 полосы → niche_status → Task 6 (band_for_score/niche_for_band), Task 10 (применение). ✅
- §5 конвейер (контекст+фетч+1 grounded-вызов+парс) → Task 7, Task 5, Task 10. ✅
- §6 бэкенд (1 лид/step, lock, rpm) → Task 11-14. ✅
- §6 ключ (settings→ENV) → Task 2, Task 11 (resolve), Task 5 (fallback в gemini_generate_grounded). ✅
- §7 модели → Task 1-4. ✅
- §8 эндпоинты → Task 16-17. ✅
- §9 UI → Task 18-21. ✅
- §10 риски → покрыты: JSON-парс (Task 5 reuse _parse_model_json), 400→skip (Task 5), idемпотентность (ai_checked_at, Task 10/11), троттлинг (Task 13). ✅
- §11 тесты + реальный прогон → Task 22-24. ✅

**2. Плейсхолдеры:** не обнаружено — везде конкретный код/команды.

**3. Консистентность имён:** `score_lead`, `gemini_generate_grounded`, `candidate_queryset`, `run_step`, `job_status_payload`, `serialize_lead_check`, `resolve_checker_api_key`, маршруты `management_checker_*` — используются одинаково во всех задачах. Поля моделей (`ai_score/ai_verdict/ai_checked_at`, `overall_score`, `partnership_fit`, `cursor_id`) согласованы между Task 1-4, 10, 13, 15.

**Замечание для исполнителя:** `_require_admin_json` импортируется из `parsing_views` — он допускает staff/superuser/Top Manager+. Страница `checker_dashboard` для не-staff Top-менеджеров делает мягкую проверку; если нужен доступ обычным менеджерам — скорректировать в Task 17.
