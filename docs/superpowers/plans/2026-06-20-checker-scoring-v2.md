# Checker Scoring v2 (Блок C) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Зробити вердикт чекера функцією не лише балу, а й гейтів — додати collaboration-гейт і стан «під питанням» (`question`), щоб магазини без доказів співпраці з чужими брендами не отримували «fit».

**Architecture:** Розширюємо чистий сервіс `lead_checker.py`: AI повертає 2 нові прапори (`sells_third_party_brands`, `own_production`) + `collaboration_evidence`; сервер рахує `verdict_band = f(score, apparel_gate, collab_gate, confidence)`. Нові поля складаємо у `LeadAICheck` (критичні — колонками, описові — у JSON `signals`). Промпт ужорсточуємо. Жодних змін у pipeline/мережах (Блоки A/B) — лише скоринг.

**Tech Stack:** Django 5 (Py 3.13), прод MySQL. Тести з кореня репо: `SECRET_KEY=test_local_secret python twocomms/manage.py test management.<module> --settings=test_settings`. Мок Gemini через `unittest.mock.patch`.

**Контекст блоку (спека):** `docs/superpowers/specs/2026-06-20-checker-networks-design.md` §7. Поточний код: `lead_checker.py` має 11 `CRITERIA`, `CRITERION_WEIGHTS` (сума 100, apparel_focus=22, collab_potential=4), `compute_overall_from_criteria` + apparel-гейт, `band_for_score` (fit≥70/maybe≥40), `niche_for_band`, `normalize_result`, `score_lead`, `build_system_prompt`. `LeadAICheck` має `overall_score`, `criteria`, `verdict_category`, `partnership_fit`, `confidence` — але НЕ має `verdict_band`/`collaboration_evidence`/`signals`.

---

## File Structure

- Modify `twocomms/management/services/lead_checker.py` — нові константи, `compute_collaboration_gate`, `compute_verdict_band`, оновити `normalize_result` + `score_lead` + `build_system_prompt`.
- Modify `twocomms/management/models.py` — `LeadAICheck`: `+verdict_band`, `+collaboration_evidence`, `+signals` (JSON).
- Create `twocomms/management/migrations/00XX_leadaicheck_scoring_v2.py` (автоген).
- Modify `twocomms/management/checker_views.py` + `parsing_views.py` — пробросити `verdict_band`/`collaboration_evidence`/`signals` у serialize (для UI пізніше; зараз — щоб не загубити).
- Test `twocomms/management/tests_checker_scoring_v2.py` (новий).
- Create `twocomms/management/management/commands/checker_calibrate.py` — офлайн-переоцінка прочеканих (read-only звіт).

---

## Task 1: Нові константи + `LeadAICheck` поля

**Files:**
- Modify: `twocomms/management/models.py` (клас `LeadAICheck`, після `confidence`)
- Modify: `twocomms/management/services/lead_checker.py` (вгорі, біля `FIT_THRESHOLD`)
- Test: `twocomms/management/tests_checker_scoring_v2.py`

- [ ] **Step 1: Написати падаючий тест**

Створити `twocomms/management/tests_checker_scoring_v2.py`:

```python
from django.test import TestCase
from management.models import ManagementLead, LeadAICheck


class LeadAICheckScoringV2FieldsTests(TestCase):
    def test_new_fields_default_empty(self):
        lead = ManagementLead.objects.create(shop_name="Shop", phone="0501112233")
        c = LeadAICheck.objects.create(lead=lead)
        self.assertEqual(c.verdict_band, "")
        self.assertEqual(c.collaboration_evidence, "")
        self.assertEqual(c.signals, {})

    def test_new_fields_persist(self):
        lead = ManagementLead.objects.create(shop_name="Shop", phone="0501112233")
        c = LeadAICheck.objects.create(
            lead=lead, verdict_band="question", collaboration_evidence="unknown",
            signals={"own_production": "yes"},
        )
        c.refresh_from_db()
        self.assertEqual(c.verdict_band, "question")
        self.assertEqual(c.collaboration_evidence, "unknown")
        self.assertEqual(c.signals["own_production"], "yes")
```

- [ ] **Step 2: Запустити — впаде**

Run: `SECRET_KEY=test_local_secret python twocomms/manage.py test management.tests_checker_scoring_v2 --settings=test_settings`
Expected: FAIL (`TypeError`/`FieldError`: немає `verdict_band`).

- [ ] **Step 3: Додати поля в модель**

У `twocomms/management/models.py`, клас `LeadAICheck`, після поля `confidence = models.CharField(...)`:

```python
    verdict_band = models.CharField(max_length=10, blank=True, db_index=True)
    collaboration_evidence = models.CharField(max_length=10, blank=True, db_index=True)
    signals = models.JSONField(default=dict, blank=True)
```

- [ ] **Step 4: Міграція**

Run: `SECRET_KEY=test_local_secret python twocomms/manage.py makemigrations management --settings=test_settings`
Expected: створено `management/migrations/00XX_leadaicheck_scoring_v2.py`.

- [ ] **Step 5: Запустити тест — пройде**

Run: `SECRET_KEY=test_local_secret python twocomms/manage.py test management.tests_checker_scoring_v2 --settings=test_settings`
Expected: PASS (2 теста).

- [ ] **Step 6: Commit**

```bash
git add twocomms/management/models.py twocomms/management/migrations/ twocomms/management/tests_checker_scoring_v2.py
git commit -F tmp/_cmsg.txt   # повідомлення: feat(checker): поля verdict_band/collaboration_evidence/signals на LeadAICheck
```

---

## Task 2: `compute_collaboration_gate`

**Files:**
- Modify: `twocomms/management/services/lead_checker.py`
- Test: `twocomms/management/tests_checker_scoring_v2.py`

Гейт повертає `(cap, evidence)`: `cap` — стеля балу, `evidence` ∈ {positive,negative,unknown}.

- [ ] **Step 1: Падаючий тест** (додати в `tests_checker_scoring_v2.py`):

```python
from management.services import lead_checker as lc


class CollaborationGateTests(TestCase):
    def test_positive_no_cap(self):
        cap, ev = lc.compute_collaboration_gate(sells_third_party="yes", own_production="no")
        self.assertEqual(ev, "positive")
        self.assertEqual(cap, 100)

    def test_negative_own_production_blocks_resale(self):
        # продає лише своє + має виробництво (Militarist) → потолок unfit
        cap, ev = lc.compute_collaboration_gate(sells_third_party="no", own_production="yes")
        self.assertEqual(ev, "negative")
        self.assertLessEqual(cap, lc.COLLAB_GATE_NEGATIVE_MAX)

    def test_negative_no_own_production_allows_custom_print(self):
        # продає лише своє, але БЕЗ виробництва → кандидат на кастом-друк, м'якший потолок
        cap, ev = lc.compute_collaboration_gate(sells_third_party="no", own_production="no")
        self.assertEqual(ev, "negative")
        self.assertGreater(cap, lc.COLLAB_GATE_NEGATIVE_MAX)
        self.assertLessEqual(cap, lc.COLLAB_GATE_MAYBE_MAX)

    def test_unknown_caps_below_fit(self):
        cap, ev = lc.compute_collaboration_gate(sells_third_party="unknown", own_production="unknown")
        self.assertEqual(ev, "unknown")
        self.assertLess(cap, lc.FIT_THRESHOLD)
```

- [ ] **Step 2: Запустити — впаде** (`AttributeError: compute_collaboration_gate`).

- [ ] **Step 3: Реалізація** — у `lead_checker.py` після apparel-констант:

```python
# Collaboration-гейт: стелі балу залежно від доказів співпраці з ЧУЖИМИ брендами.
COLLAB_GATE_NEGATIVE_MAX = 40   # продає лише своє + має виробництво → unfit-зона
COLLAB_GATE_MAYBE_MAX = 60      # лише своє, але без виробництва → кандидат на кастом-друк
COLLAB_GATE_UNKNOWN_MAX = 69    # немає даних про співпрацю → не вище maybe/question


def compute_collaboration_gate(*, sells_third_party: str, own_production: str) -> tuple[int, str]:
    """Повертає (cap, evidence). cap — стеля overall_score; evidence — позиція гейта."""
    stp = (sells_third_party or "unknown").strip().lower()
    own = (own_production or "unknown").strip().lower()
    if stp == "yes":
        return 100, "positive"
    if stp == "no":
        # продає лише своє: блокуємо опт/полицю; кастом-друк можливий лише без власного виробництва
        if own == "yes":
            return COLLAB_GATE_NEGATIVE_MAX, "negative"
        return COLLAB_GATE_MAYBE_MAX, "negative"
    return COLLAB_GATE_UNKNOWN_MAX, "unknown"
```

- [ ] **Step 4: Запустити — пройде** (4 теста).
- [ ] **Step 5: Commit** (`-F tmp/_cmsg.txt`, msg: `feat(checker): compute_collaboration_gate`).

---

## Task 3: `compute_verdict_band` (вердикт = f(score, гейти, confidence))

**Files:**
- Modify: `twocomms/management/services/lead_checker.py`
- Test: `twocomms/management/tests_checker_scoring_v2.py`

- [ ] **Step 1: Падаючий тест:**

```python
class VerdictBandTests(TestCase):
    def test_fit_requires_positive_collab_and_confidence(self):
        b = lc.compute_verdict_band(score=82, apparel=8, collab_evidence="positive", confidence="high")
        self.assertEqual(b, "fit")

    def test_high_score_unknown_collab_becomes_question(self):
        # хороший бал, але немає даних про співпрацю → НЕ fit, а question
        b = lc.compute_verdict_band(score=82, apparel=8, collab_evidence="unknown", confidence="high")
        self.assertEqual(b, "question")

    def test_low_confidence_blocks_fit(self):
        b = lc.compute_verdict_band(score=80, apparel=8, collab_evidence="positive", confidence="low")
        self.assertIn(b, ("question", "maybe"))

    def test_negative_collab_unfit(self):
        b = lc.compute_verdict_band(score=70, apparel=8, collab_evidence="negative", confidence="high")
        self.assertEqual(b, "unfit")

    def test_apparel_gate_unfit(self):
        b = lc.compute_verdict_band(score=20, apparel=1, collab_evidence="positive", confidence="high")
        self.assertEqual(b, "unfit")

    def test_mid_is_maybe(self):
        b = lc.compute_verdict_band(score=55, apparel=6, collab_evidence="positive", confidence="medium")
        self.assertEqual(b, "maybe")
```

- [ ] **Step 2: Запустити — впаде.**
- [ ] **Step 3: Реалізація** (після `band_for_score`):

```python
def compute_verdict_band(*, score: int, apparel: int, collab_evidence: str, confidence: str) -> str:
    """Вердикт = функція балу + гейтів + впевненості (не чистий бал)."""
    ev = (collab_evidence or "unknown").strip().lower()
    conf = (confidence or "low").strip().lower()
    # apparel-блокер
    if apparel <= 2 or score < MAYBE_THRESHOLD:
        return "unfit"
    # негативний collab — явний блокер
    if ev == "negative":
        return "unfit" if score < FIT_THRESHOLD else "maybe"
    # немає даних про співпрацю АБО низька впевненість → «під питанням», не fit
    if ev == "unknown" or conf == "low":
        return "question" if score >= MAYBE_THRESHOLD else "maybe"
    # позитивний collab + достатня впевненість
    if score >= FIT_THRESHOLD and conf in ("medium", "high"):
        return "fit"
    return "maybe"
```

- [ ] **Step 4: Запустити — пройде** (6 тестів).
- [ ] **Step 5: Commit** (msg: `feat(checker): compute_verdict_band — вердикт як функція гейтів`).

---

## Task 4: Оновити `normalize_result` (нові поля + гейт + банд)

**Files:**
- Modify: `twocomms/management/services/lead_checker.py` (`normalize_result`)
- Test: `twocomms/management/tests_checker_scoring_v2.py`

- [ ] **Step 1: Падаючий тест:**

```python
class NormalizeResultV2Tests(TestCase):
    def _raw(self, **over):
        crit = [{"key": k, "score": 8} for k, _ in lc.CRITERIA]
        base = {"criteria": crit, "confidence": "high",
                "sells_third_party_brands": "yes", "own_production": "no",
                "verdict_category": "brand", "partnership_fit": ["wholesale"]}
        base.update(over)
        return base

    def test_outputs_band_and_evidence(self):
        out = lc.normalize_result(self._raw())
        self.assertEqual(out["collaboration_evidence"], "positive")
        self.assertIn(out["verdict_band"], ("fit", "maybe", "question", "unfit"))
        self.assertEqual(out["signals"]["sells_third_party_brands"], "yes")
        self.assertEqual(out["signals"]["own_production"], "no")

    def test_unknown_collab_not_fit_even_if_high_score(self):
        out = lc.normalize_result(self._raw(sells_third_party_brands="unknown", own_production="unknown"))
        self.assertEqual(out["collaboration_evidence"], "unknown")
        self.assertNotEqual(out["verdict_band"], "fit")

    def test_score_capped_by_collab_gate(self):
        out = lc.normalize_result(self._raw(sells_third_party_brands="no", own_production="yes"))
        self.assertLessEqual(out["overall_score"], lc.COLLAB_GATE_NEGATIVE_MAX)
```

- [ ] **Step 2: Запустити — впаде.**
- [ ] **Step 3: Реалізація** — у `normalize_result`, після обчислення `overall = compute_overall_from_criteria(...)`:

```python
    sells_third_party = _as_str(raw.get("sells_third_party_brands")).lower() or "unknown"
    if sells_third_party not in ("yes", "no", "unknown"):
        sells_third_party = "unknown"
    own_production = _as_str(raw.get("own_production")).lower() or "unknown"
    if own_production not in ("yes", "no", "unknown"):
        own_production = "unknown"

    collab_cap, collab_evidence = compute_collaboration_gate(
        sells_third_party=sells_third_party, own_production=own_production,
    )
    overall = min(overall, collab_cap)
    apparel_score = next((c["score"] for c in criteria if c["key"] == "apparel_focus"), 0)
    verdict_band = compute_verdict_band(
        score=overall, apparel=apparel_score, collab_evidence=collab_evidence, confidence=confidence,
    )
```

І додати у `return {...}`:

```python
        "collaboration_evidence": collab_evidence,
        "verdict_band": verdict_band,
        "signals": {
            "sells_third_party_brands": sells_third_party,
            "own_production": own_production,
            "canonical_network_name": _as_str(raw.get("canonical_network_name")),
            "network_kind": _as_str(raw.get("network_kind")),
            "suggested_policy": _as_str(raw.get("suggested_policy")),
        },
```

- [ ] **Step 4: Запустити — пройде** (3 теста + попередні).
- [ ] **Step 5: Commit** (msg: `feat(checker): normalize_result рахує collab-гейт + verdict_band`).

---

## Task 5: Записати нові поля в `score_lead` + оновити промпт

**Files:**
- Modify: `twocomms/management/services/lead_checker.py` (`score_lead`, `build_system_prompt`)
- Test: `twocomms/management/tests_checker_scoring_v2.py`

- [ ] **Step 1: Падаючий тест** (мок Gemini, перевіряємо що `LeadAICheck` зберіг нові поля + `lead.ai_verdict` = band):

```python
from unittest.mock import patch


class ScoreLeadV2Tests(TestCase):
    def test_score_lead_persists_band_and_signals(self):
        lead = ManagementLead.objects.create(shop_name="Brand X", phone="0501112233")
        crit = [{"key": k, "score": 8} for k, _ in lc.CRITERIA]
        parsed = {"criteria": crit, "confidence": "high",
                  "sells_third_party_brands": "unknown", "own_production": "unknown"}
        with patch.object(lc, "gemini_generate_grounded",
                          return_value={"parsed": parsed, "model": "m", "usage": {}}), \
             patch.object(lc, "fetch_website_text", return_value=("", False)):
            check = lc.score_lead(lead, api_key="k")
        check.refresh_from_db(); lead.refresh_from_db()
        self.assertEqual(check.verdict_band, "question")
        self.assertEqual(check.collaboration_evidence, "unknown")
        self.assertEqual(check.signals["own_production"], "unknown")
        self.assertEqual(lead.ai_verdict, "question")
```

- [ ] **Step 2: Запустити — впаде** (поля не зберігаються).
- [ ] **Step 3: Реалізація** — у `score_lead`, де заповнюється `check` (після `check.confidence = norm["confidence"]`):

```python
        check.verdict_band = norm["verdict_band"]
        check.collaboration_evidence = norm["collaboration_evidence"]
        check.signals = norm["signals"]
```

І замінити `band = band_for_score(norm["overall_score"])` на `band = norm["verdict_band"]` (вердикт тепер з банда, не з балу). `niche_for_band` має приймати `question` → MAYBE; оновити:

```python
def niche_for_band(band: str) -> str:
    if band == "fit":
        return ManagementLead.NicheStatus.NICHE
    if band in ("maybe", "question"):
        return ManagementLead.NicheStatus.MAYBE
    return ManagementLead.NicheStatus.NON_NICHE
```

- [ ] **Step 4: Оновити промпт** — у `build_system_prompt`, у JSON-схему додати поля та інструкції:

```
'  "sells_third_party_brands": "yes|no|unknown — чи бере магазин на продаж ЧУЖІ бренди одягу (НЕ лише свій)",\n'
'  "own_production": "yes|no|unknown — чи має власне виробництво/пошив",\n'
'  "canonical_network_name": "канонічна назва мережі/бренду, якщо це мережа, інакше порожньо",\n'
'  "network_kind": "chain_brand|franchise|marketplace|voentorg_group|unknown",\n'
'  "suggested_policy": "block_no_collab|block_irrelevant|recheck_each|priority_target| (порожньо якщо не мережа)",\n'
```

І в текст інструкцій додати абзац (перед схемою):

```
"КЛЮЧОВЕ ПРАВИЛО СПІВПРАЦІ: ми постачаємо НАШ одяг або друкуємо під бренд клієнта. "
"Магазин придатний для опту/полиці ЛИШЕ якщо бере на продаж ЧУЖІ бренди одягу. "
"Якщо магазин продає ВИКЛЮЧНО свій бренд і має власне виробництво (як великі мілітарі-бренди) — "
"опт/полиця закриті; кастом-друк можливий лише якщо в них НЕМАЄ власного виробництва. "
"Якщо доказів співпраці з чужими брендами НЕ знайдено — постав sells_third_party_brands='unknown' "
"і чесно напиши в comment, що це треба уточнити дзвінком (НЕ вигадуй співпрацю).\n\n"
```

- [ ] **Step 5: Запустити — пройде** (всі тести `tests_checker_scoring_v2`).
- [ ] **Step 6: Повний набір** — `SECRET_KEY=test_local_secret python twocomms/manage.py test management --settings=test_settings`. Очікувати: лише відомі date/flaky-падіння (10 + reminder_digest), 0 нових. За сумніву — stash своїх файлів і повторити.
- [ ] **Step 7: Commit** (msg: `feat(checker): score_lead зберігає band/signals + строгий collab-промпт`).

---

## Task 6: serialize — пробросити нові поля (для UI/модерації)

**Files:**
- Modify: `twocomms/management/checker_views.py` (`serialize_lead_check`)
- Modify: `twocomms/management/parsing_views.py` (`_serialize_moderation_lead`)
- Test: `twocomms/management/tests_checker_scoring_v2.py`

- [ ] **Step 1: Падаючий тест:**

```python
class SerializeV2Tests(TestCase):
    def test_serialize_includes_band_and_evidence(self):
        from management import checker_views
        lead = ManagementLead.objects.create(shop_name="S", phone="0501112233",
                                              ai_verdict="question")
        LeadAICheck.objects.create(lead=lead, status=LeadAICheck.Status.DONE,
                                   verdict_band="question", collaboration_evidence="unknown",
                                   signals={"own_production": "yes"})
        row = checker_views.serialize_lead_check(lead)
        self.assertEqual(row["verdict_band"], "question")
        self.assertEqual(row["collaboration_evidence"], "unknown")
        self.assertEqual(row["signals"]["own_production"], "yes")
```

- [ ] **Step 2: Запустити — впаде** (KeyError).
- [ ] **Step 3: Реалізація** — у `serialize_lead_check`, у блок `base.update({...})` (де є `check`):

```python
        "verdict_band": check.verdict_band,
        "collaboration_evidence": check.collaboration_evidence,
        "signals": check.signals or {},
```

І у гілку `if check is None:` додати `"verdict_band": "", "collaboration_evidence": "", "signals": {},`.

- [ ] **Step 4: Запустити — пройде.**
- [ ] **Step 5: Commit** (msg: `feat(checker): serialize band/evidence/signals`).

---

## Task 7: Офлайн-калібрування (read-only звіт по прочеканих)

**Files:**
- Create: `twocomms/management/management/commands/checker_calibrate.py`
- Test: ручний прогін на проді (read-only).

- [ ] **Step 1: Реалізувати команду** — для кожного DONE-чека переоцінити `verdict_band` за збереженими `criteria`+`confidence`+`signals` (якщо є) і вивести розподіл «до/після» БЕЗ запису:

```python
from collections import Counter
from django.core.management.base import BaseCommand
from management.models import LeadAICheck
from management.services import lead_checker as lc


class Command(BaseCommand):
    help = "Read-only: переоцінка вердиктів чекера за scoring v2 (розподіл до/після)"

    def handle(self, *args, **opts):
        before, after = Counter(), Counter()
        for c in LeadAICheck.objects.filter(status=LeadAICheck.Status.DONE).iterator():
            before[c.lead.ai_verdict or ""] += 1
            crit = c.criteria if isinstance(c.criteria, list) else []
            by = {x.get("key"): x.get("score", 0) for x in crit if isinstance(x, dict)}
            score = lc.compute_overall_from_criteria(by)
            sig = c.signals or {}
            cap, ev = lc.compute_collaboration_gate(
                sells_third_party=sig.get("sells_third_party_brands", "unknown"),
                own_production=sig.get("own_production", "unknown"),
            )
            band = lc.compute_verdict_band(
                score=min(score, cap), apparel=by.get("apparel_focus", 0),
                collab_evidence=ev, confidence=c.confidence,
            )
            after[band] += 1
        self.stdout.write(f"BEFORE: {dict(before)}")
        self.stdout.write(f"AFTER : {dict(after)}")
```

- [ ] **Step 2: Прогнати на проді** (read-only): SSH → `python manage.py checker_calibrate`. Подивитися, чи `question` не поглинув усе і `fit` не зник. За потреби підкрутити `COLLAB_GATE_*`/пороги (повернутися до Task 2-3, оновити тести).
- [ ] **Step 3: Commit** (msg: `feat(checker): команда checker_calibrate (офлайн-розподіл вердиктів)`).

---

## Деплой блоку C

- `git push origin main`.
- SSH-деплой: `git pull --no-edit`; `python manage.py migrate --no-input` (нові поля LeadAICheck); collectstatic НЕ треба (статику не чіпали); `touch tmp/restart.txt`.
- Sanity-curl `https://twocomms.shop/` + `https://management.twocomms.shop/parsing/` → 200/302.
- Прогнати `checker_calibrate` на проді — зафіксувати розподіл.

---

## Self-Review (проти спеки §7)

- Покриття: collab-гейт (Task2), 3 стани evidence (Task2/3), вердикт=f(гейти) (Task3), `question`-банд (Task3), нові AI-поля+промпт (Task5), custom_print-виняток (Task2: own_production=no → м'якший cap), калібрування офлайн (Task7). ✓
- Типи: `compute_collaboration_gate(sells_third_party, own_production)` і `compute_verdict_band(score, apparel, collab_evidence, confidence)` — однакові імена скрізь. ✓
- Плейсхолдерів немає; код у кожному кроці повний. ✓
- НЕ покрито тут (інші блоки): мережі (A), pipeline-skip (B), UI-карточки (D) — окремі плани.

> Примітка: для коміт-повідомлень створюй `tmp/_cmsg.txt` і використовуй `git commit -F tmp/_cmsg.txt` (zsh схлопує багаторядкові `-m`). Видаляй файл після.
