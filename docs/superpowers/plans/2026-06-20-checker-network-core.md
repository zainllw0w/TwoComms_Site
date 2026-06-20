# Checker Network Core (Блок A) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development або executing-plans. Кроки — checkbox `- [ ]`.

**Goal:** Додати сутність «мережа» (`LeadNetwork`+`NetworkAlias`) і детермінований резолвер, що класифікує лід як standalone / network / generic, ПЕРЕВИКОРИСТОВУЮЧИ наявні ключі матчингу (`normalized_name_match_key`, `website_match_key`, `phone_last7`) — без паралельної системи.

**Architecture:** Базова одиниця = лід. `LeadNetwork` — опціональний шар лише для підтверджених/сильних кандидатів. Резолвер групує за наявним `normalized_name_match_key` + транслітераційний ключ (arber/арбер) + `website_match_key`. Generic-родові назви НЕ зливаються. Бекофіл — окрема idempotent команда.

**Tech Stack:** Django 5, MySQL прод. Тести з кореня: `SECRET_KEY=test_local_secret python twocomms/manage.py test management.<m> --settings=test_settings`. makemigrations — на дефолтних settings (test_settings вимикає міграції).

**Контекст (спека §4-5):** `docs/superpowers/specs/2026-06-20-checker-networks-design.md`. Наявне: `ManagementLead.normalized_name_match_key`/`website_match_key`/`phone_last7`/`phone_group_id` (db_index, рахуються в `save()`); `normalize_name_for_match`/`normalize_website_for_match` у `models.py`; dedupe.py (точні дублі). Консолідація: резолвер ВИКОРИСТОВУЄ ці ключі.

---

## Task A1: `LeadNetwork` модель

**Files:** Modify `twocomms/management/models.py` (перед `LeadCheckerSettings`); Test `twocomms/management/tests_checker_networks.py` (новий).

- [ ] Step 1: падаючий тест — `tests_checker_networks.py`:

```python
from django.test import TestCase
from management.models import LeadNetwork


class LeadNetworkModelTests(TestCase):
    def test_create_defaults(self):
        n = LeadNetwork.objects.create(canonical_name="Rozetka", slug="rozetka")
        self.assertEqual(n.policy, LeadNetwork.Policy.NEEDS_REVIEW)
        self.assertEqual(n.kind, LeadNetwork.Kind.UNKNOWN)
        self.assertEqual(n.collaboration_evidence, "")
        self.assertEqual(n.members_count, 0)
        self.assertIsNone(n.confirmed_by_id)
```

- [ ] Step 2: запустити — FAIL (`ImportError: LeadNetwork`).
- [ ] Step 3: додати модель (перед `class LeadCheckerSettings`):

```python
class LeadNetwork(models.Model):
    class Kind(models.TextChoices):
        CHAIN_BRAND = "chain_brand", _("Мережа-бренд")
        FRANCHISE = "franchise", _("Франшиза")
        MARKETPLACE = "marketplace", _("Маркетплейс")
        VOENTORG_GROUP = "voentorg_group", _("Група військторгів")
        UNKNOWN = "unknown", _("Невідомо")

    class Policy(models.TextChoices):
        BLOCK_NO_COLLAB = "block_no_collab", _("Не співпрацює — пропускати")
        BLOCK_IRRELEVANT = "block_irrelevant", _("Не наш профіль — пропускати")
        APPLY_KNOWN_VERDICT = "apply_known_verdict", _("Застосувати вердикт мережі")
        RECHECK_EACH = "recheck_each", _("Перевіряти кожну точку")
        CUSTOM_PRINT_ONLY = "custom_print_only", _("Лише кастом-друк")
        NEEDS_REVIEW = "needs_review", _("Потребує рішення")
        PRIORITY_TARGET = "priority_target", _("Пріоритетна ціль")

    canonical_name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.UNKNOWN)
    policy = models.CharField(max_length=24, choices=Policy.choices, default=Policy.NEEDS_REVIEW, db_index=True)
    policy_params = models.JSONField(default=dict, blank=True)
    extra_instructions = models.TextField(blank=True)
    collaboration_evidence = models.CharField(max_length=10, blank=True)
    confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="confirmed_networks")
    confirmed_at = models.DateTimeField(null=True, blank=True)
    suggested_by_ai = models.BooleanField(default=False)
    ai_rationale = models.TextField(blank=True)
    members_count = models.PositiveIntegerField(default=0)
    checked_count = models.PositiveIntegerField(default=0)
    skipped_count = models.PositiveIntegerField(default=0)
    tokens_saved = models.PositiveBigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Мережа лідів")
        verbose_name_plural = _("Мережі лідів")
        ordering = ["-updated_at"]

    @property
    def is_confirmed(self) -> bool:
        return self.confirmed_by_id is not None

    def __str__(self):
        return f"LeadNetwork({self.canonical_name})"
```

- [ ] Step 4: міграція (`makemigrations management` на дефолт-settings) + тест → PASS.
- [ ] Step 5: commit (`-F tmp/_cmsg.txt`): `feat(checker): модель LeadNetwork`.

---

## Task A2: `NetworkAlias` модель

- [ ] Step 1: падаючий тест:

```python
from management.models import NetworkAlias


class NetworkAliasTests(TestCase):
    def test_alias_unique_per_type_value(self):
        n = LeadNetwork.objects.create(canonical_name="Arber", slug="arber")
        NetworkAlias.objects.create(network=n, key_type="name", key_value="arber")
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            NetworkAlias.objects.create(network=n, key_type="name", key_value="arber")
```

- [ ] Step 2: FAIL (`ImportError`).
- [ ] Step 3: модель (після `LeadNetwork`):

```python
class NetworkAlias(models.Model):
    class KeyType(models.TextChoices):
        NAME = "name", _("Назва")
        WEBSITE = "website", _("Сайт")
        INSTAGRAM = "instagram", _("Instagram")

    network = models.ForeignKey(LeadNetwork, on_delete=models.CASCADE, related_name="aliases")
    key_type = models.CharField(max_length=12, choices=KeyType.choices)
    key_value = models.CharField(max_length=500, db_index=True)
    source = models.CharField(max_length=8, default="auto")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Алиас мережі")
        verbose_name_plural = _("Алиаси мереж")
        constraints = [models.UniqueConstraint(fields=["key_type", "key_value"], name="uniq_network_alias_key")]

    def __str__(self):
        return f"NetworkAlias({self.key_type}={self.key_value})"
```

- [ ] Step 4: міграція + тест → PASS.
- [ ] Step 5: commit: `feat(checker): модель NetworkAlias`.

---

## Task A3: поля `ManagementLead` (network FK)

- [ ] Step 1: падаючий тест:

```python
class ManagementLeadNetworkFieldsTests(TestCase):
    def test_lead_network_defaults(self):
        from management.models import ManagementLead
        lead = ManagementLead.objects.create(shop_name="S", phone="0501112233")
        self.assertIsNone(lead.network_id)
        self.assertEqual(lead.network_membership_source, "")
        self.assertFalse(lead.needs_disambiguation)
```

- [ ] Step 2: FAIL.
- [ ] Step 3: у `ManagementLead`, після `niche_status`:

```python
    network = models.ForeignKey("LeadNetwork", on_delete=models.SET_NULL, null=True, blank=True, related_name="leads", db_index=True)
    network_membership_source = models.CharField(max_length=8, blank=True)
    needs_disambiguation = models.BooleanField(default=False, db_index=True)
```

- [ ] Step 4: міграція + тест → PASS.
- [ ] Step 5: commit: `feat(checker): поля network/needs_disambiguation на ManagementLead`.

---

## Task A4: транслітерація + generic-токени + `network_match_key`

**Files:** Create `twocomms/management/services/network_resolver.py`; Test `tests_checker_networks.py`.

- [ ] Step 1: падаючий тест:

```python
from management.services import network_resolver as nr


class NetworkKeyTests(TestCase):
    def test_translit_merges_cyrillic_latin(self):
        self.assertEqual(nr.network_match_key("Arber"), nr.network_match_key("Арбер"))

    def test_generic_detected(self):
        self.assertTrue(nr.is_generic_name("військторг"))
        self.assertTrue(nr.is_generic_name("Магазин"))
        self.assertFalse(nr.is_generic_name("Rozetka"))
```

- [ ] Step 2: FAIL (`ModuleNotFoundError`).
- [ ] Step 3: реалізація:

```python
"""Детермінований резолвер мереж: переві використовує наявні ключі матчингу."""
from __future__ import annotations

from management.models import normalize_name_for_match

# укр→лат транслітерація для злиття arber/арбер (мінімальна, достатня для назв)
_UA_LAT = {
    "а": "a", "б": "b", "в": "v", "г": "h", "ґ": "g", "д": "d", "е": "e", "є": "ie",
    "ж": "zh", "з": "z", "и": "y", "і": "i", "ї": "i", "й": "i", "к": "k", "л": "l",
    "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch", "ь": "",
    "ю": "iu", "я": "ia", "’": "", "ʼ": "", "'": "",
    # рос літери, що відрізняються
    "ё": "e", "ъ": "", "ы": "y", "э": "e",
}

GENERIC_NAME_TOKENS = {
    "військторг", "воєнторг", "воєнторґ", "магазин", "секонд", "секонд хенд",
    "одяг", "взуття", "маркет", "базар", "лавка", "крамниця", "спецодяг",
    "army shop", "military shop", "тактичний магазин", "військовий магазин",
}


def _translit(value: str) -> str:
    return "".join(_UA_LAT.get(ch, ch) for ch in value)


def network_match_key(name: str) -> str:
    """Канонічний ключ для злиття латиниці/кирилиці одного бренду.
    Базується на наявному normalize_name_for_match + транслітерація."""
    base = normalize_name_for_match(name)            # lower+strip punct+rm legal tokens
    return _translit(base).replace(" ", "")


def is_generic_name(name: str) -> bool:
    key = normalize_name_for_match(name)
    return key in GENERIC_NAME_TOKENS
```

- [ ] Step 4: тест → PASS.
- [ ] Step 5: commit: `feat(checker): network_match_key (транслит) + generic-токени`.

---

## Task A5: резолвер класифікації кластера

**Files:** Modify `network_resolver.py`; Test `tests_checker_networks.py`.

- [ ] Step 1: падаючий тест (з фікстурами лідів):

```python
from management.models import ManagementLead, LeadNetwork


class ClassifyClusterTests(TestCase):
    def _lead(self, name, phone, website=""):
        return ManagementLead.objects.create(shop_name=name, phone=phone, website_url=website,
                                              lead_source=ManagementLead.LeadSource.PARSER)

    def test_single_is_standalone(self):
        self._lead("Coyote Wear", "0501112233", "https://coyote.example")
        res = nr.resolve_all()
        self.assertEqual(res["standalone"], 1)
        self.assertEqual(LeadNetwork.objects.count(), 0)

    def test_shared_website_is_network(self):
        for i in range(3):
            self._lead("Rozetka", f"050111220{i}", "https://rozetka.com.ua")
        res = nr.resolve_all()
        self.assertEqual(LeadNetwork.objects.count(), 1)
        net = LeadNetwork.objects.first()
        self.assertEqual(net.leads.count(), 3)
        self.assertEqual(net.policy, LeadNetwork.Policy.NEEDS_REVIEW)

    def test_generic_not_merged(self):
        for i in range(4):
            self._lead("Військторг", f"050999100{i}")  # різні телефони, немає сайту
        res = nr.resolve_all()
        self.assertEqual(LeadNetwork.objects.count(), 0)
        self.assertTrue(all(l.needs_disambiguation for l in ManagementLead.objects.all()))

    def test_translit_cluster_merged(self):
        self._lead("Arber", "0501110001", "https://arber.ua")
        self._lead("Арбер", "0501110002", "https://arber.com.ua")
        nr.resolve_all()
        # один бренд за транслітом → одна мережа-кандидат
        self.assertEqual(LeadNetwork.objects.count(), 1)
```

- [ ] Step 2: FAIL (`resolve_all` немає).
- [ ] Step 3: реалізація `resolve_all` + `classify_cluster` + `attach_network` (idempotent; кластеризація за `network_match_key`; ≥2 зі спільним website→network-кандидат needs_review; родова/різні сайти+телефони→generic needs_disambiguation; інакше середній бренд→network-кандидат). Створює/оновлює `LeadNetwork`+`NetworkAlias`, проставляє `lead.network`/`needs_disambiguation`/`network_membership_source="auto"`, оновлює `members_count`.
- [ ] Step 4: тест → PASS.
- [ ] Step 5: повний набір management → 0 нових регресій.
- [ ] Step 6: commit: `feat(checker): резолвер класифікації (standalone/network/generic)`.

---

## Task A6: бекофіл-команда

**Files:** Create `twocomms/management/management/commands/checker_backfill_networks.py`.

- [ ] Step 1: реалізувати команду — викликає `network_resolver.resolve_all()`, друкує підсумок (created networks / standalone / generic / merged). Idempotent.
- [ ] Step 2: перевірити `manage.py help checker_backfill_networks` → OK.
- [ ] Step 3: commit: `feat(checker): команда checker_backfill_networks`.

---

## Деплой блоку A

- push; SSH: `git pull`; `migrate --no-input` (нові моделі); collectstatic НЕ треба; `touch tmp/restart.txt`. Sanity-curl 200/302.
- На проді запустити `python manage.py checker_backfill_networks` (idempotent) — створити мережі з наявних лідів, подивитися підсумок.

## Self-Review (проти спеки §4-5)

- LeadNetwork (A1) + NetworkAlias (A2) + ManagementLead-поля (A3) = модель §4 ✓.
- Транслит+generic (A4) + резолвер (A5) = детект §5 + консолідація наявних ключів ✓.
- Бекофіл (A6) — окрема idempotent команда §4.5 ✓.
- Авто-skip НЕ тут (Блок B); тут лише класифікація+привʼязка, policy=needs_review за замовч.
