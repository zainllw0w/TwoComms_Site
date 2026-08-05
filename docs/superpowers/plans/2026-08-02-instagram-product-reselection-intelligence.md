# Instagram Product Reselection Intelligence Implementation Plan

> **Execution status (2026-08-05): PARTIAL.** Task 2 foundation is deployed;
> Tasks 3-4 have a current-base price-aware implementation in `7b5d5cc7` plus
> typed compatibility corrections in `1c4d6d48`, verified by 162 focused tests.
> They remain unchecked until independent review, main integration, production
> deploy and live proof. Later availability/session/allocation tasks remain open.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an explainable multilingual catalog recommender and durable commerce state machine that lets an Instagram customer change products at any pre-payment point, validates exact MariaDB-backed availability, suppresses repeated failures, and creates one correct assisted-checkout proposal.

**Architecture:** A typed catalog graph and deterministic URL resolver turn verified catalog facts into candidates. A durable session reducer owns pre-proposal selection while a separate availability/allocation layer owns warehouse truth and reservation transitions. Gemini extracts bounded constraints and natural wording; deterministic services authorize product identity, availability, stock effects, and proposal creation.

**Tech Stack:** Django, MariaDB/MySQL, Python dataclasses, existing Gemini wrapper, storefront/Fable5/warehouse models, Django transactions and row locks, Django TestCase/TransactionTestCase, migration executor tests.

---

## File Structure

New focused modules:

- `twocomms/storefront/services/product_sales_semantics.py`: validate controlled semantic traits and immutable profile revisions.
- `twocomms/management/services/ig_commerce_types.py`: immutable request, selection, candidate, availability, and decision value objects.
- `twocomms/management/services/ig_product_references.py`: trusted TwoComms URL parsing and exact slug resolution.
- `twocomms/management/services/ig_catalog_graph.py`: immutable verified catalog topology and digest.
- `twocomms/management/services/ig_catalog_candidates.py`: deterministic filtering, scoring, ambiguity, and explainable alternatives.
- `twocomms/management/services/ig_availability.py`: configurable/allocatable/unknown decisions and exact allocation lookup.
- `twocomms/management/services/ig_commerce_state.py`: transactional session reducer, legacy projection, transition audit, and replay idempotency.
- `twocomms/management/services/ig_commerce_projection.py`: legacy bootstrap and one-way compatibility projection from the authoritative active basket line.
- `twocomms/management/services/ig_commerce_turns.py`: deterministic phrase parsing, Gemini schema validation, and compound-turn reduction.
- `twocomms/management/services/ig_commerce_replies.py`: localized decision-to-reply rendering without commerce authority.
- `twocomms/management/management/commands/audit_ig_commerce_readiness.py`: dry-run semantic, inventory-policy, and allocation coverage report.
- `twocomms/management/management/commands/replay_ig_commerce_incident.py`: transport-disabled sanitized decision replay.
- `twocomms/test_settings_mariadb.py`: explicit disposable MariaDB settings for migrations, locks, triggers, and race tests; it must refuse production database names/hosts.

Existing files changed together with their owning behavior:

- `twocomms/storefront/models.py`, `admin.py`, migration `0088`: semantic profile identity/revisions.
- `twocomms/fable5/models.py`, `services.py`, `size_grid_services.py`, migration `0008`: explicit inventory policy and warehouse-aware compatibility mode.
- `twocomms/management/ig_bot_models.py`, `models.py`, migrations `0128`-`0130`: sessions, transitions, turn decisions, manager reviews, proposal digest, allocation fields/states.
- `twocomms/management/services/ig_checkout.py`, `ig_inventory.py`, `bot_orders.py`, `instagram_bot.py`: final validation and integration.
- `twocomms/warehouse/services/inventory.py`, `views/write_off.py`: exact allocation fulfillment/reversal and negative-adjustment guards.
- `twocomms/management/bot_views.py`, `templates/management/bot.html`: operational manager-review visibility.

The observed migration leaves before implementation are `management.0127`, `storefront.0087`, `fable5.0007`, and `warehouse.0011`. Re-run leaf discovery before generating migrations. Never edit historical `management.0116`.

### Task 1: Establish a Clean Baseline and Freeze Contracts

**Current status (2026-08-03): BRANCH-ONLY BASELINE.** Выполнялось в
`codex/instagram-assisted-checkout` от старого checkpoint; перед интеграцией
обязателен новый baseline на `origin/main`.

**Files:**
- Read: `docs/superpowers/specs/2026-08-02-instagram-product-reselection-intelligence-design.md`
- Read: `docs/plans/2026-07-30-instagram-assisted-checkout-checklist.md`
- Test: `twocomms/management/tests_ig_paylink_fix.py`
- Test: `twocomms/management/tests_ig_checkout_service.py`

- [ ] **Step 1: Confirm isolation and preserve unrelated UI changes**

Run from the worktree root:

```bash
git rev-parse --show-toplevel
git branch --show-current
git status --short
git diff -- tests/instagram-checkout-ui-contract.test.cjs twocomms/twocomms_django_theme/static/css/instagram-checkout.css
```

Expected: branch `codex/instagram-assisted-checkout`; only the known UI files are dirty outside committed docs. Do not stage or edit them in this program.

- [ ] **Step 2: Verify migration leaves**

```bash
find twocomms/management/migrations twocomms/storefront/migrations twocomms/fable5/migrations twocomms/warehouse/migrations -maxdepth 1 -name '[0-9]*.py' -print
```

Expected: the highest current files match or supersede `management.0127`, `storefront.0087`, `fable5.0007`, and `warehouse.0011`. Update only new migration dependencies if the leaves moved.

- [ ] **Step 3: Run the focused baseline**

Run from `twocomms/`:

```bash
python manage.py test --settings=test_settings management.tests_ig_paylink_fix management.tests_ig_checkout_service management.tests_ig_checkout_models management.tests_bot_catalog
```

Expected: existing baseline passes or every pre-existing failure is recorded before implementation.

### Task 2: Add Immutable Verified Product Semantics and Inventory Policy

**Current status (2026-08-05): PARTIAL, IN MAIN/PRODUCTION.** Foundation was
ported as `bf4e0d80`, hardened by `674d6858` and `3678ddf4`, and deployed.
Generic/punctuation aliases and unauthoritative revocation are rejected;
MariaDB tables/triggers and 77 inventory policies are verified. Remaining:
full runtime/admin consumer and a separate disposable MariaDB test gate.

**Files:**
- Modify: `twocomms/storefront/models.py`
- Modify: `twocomms/storefront/admin.py`
- Create: `twocomms/storefront/services/product_sales_semantics.py`
- Create: `twocomms/storefront/tests/test_product_sales_semantics.py`
- Create: `twocomms/storefront/migrations/0088_product_sales_semantic_profiles.py`
- Modify: `twocomms/fable5/models.py`
- Create: `twocomms/fable5/tests/test_product_inventory_policy.py`
- Create: `twocomms/fable5/migrations/0008_product_inventory_policy.py`

- [ ] **Step 1: Write failing semantic revision tests**

```python
class ProductSalesSemanticRevisionTests(TestCase):
    def test_verified_revision_is_append_only_and_exactly_versioned(self):
        profile = ProductSalesSemanticProfile.objects.create(product=self.product)
        revision = ProductSalesSemanticProfileRevision.objects.create(
            profile=profile,
            revision=1,
            status="verified",
            schema_version=1,
            aliases={"ru": ["обычная черная футболка"]},
            traits={"front_decoration": "logo", "back_decoration": "none"},
            source="manager",
        )
        revision.traits["back_decoration"] = "print"
        with self.assertRaises(ValidationError):
            revision.save()

    def test_bot_vision_cannot_create_verified_revision(self):
        with self.assertRaises(ValidationError):
            validate_semantic_revision(
                status="verified",
                source="bot_vision",
                traits={"back_decoration": "none"},
            )

    def test_verified_revision_queryset_update_and_delete_are_blocked(self):
        revision = self.create_verified_revision()
        with self.assertRaises(ValueError):
            ProductSalesSemanticProfileRevision.objects.filter(pk=revision.pk).update(traits={})
        with self.assertRaises(ValueError):
            ProductSalesSemanticProfileRevision.objects.filter(pk=revision.pk).delete()

    def test_generic_fit_color_size_or_garment_word_cannot_be_verified_alias(self):
        for alias in ("classic", "классика", "класична", "oversize", "black", "чорний", "M"):
            with self.subTest(alias=alias), self.assertRaises(ValidationError):
                validate_semantic_revision(
                    status="verified",
                    source="manager",
                    aliases={"uk": [alias]},
                    traits={},
                )

    def test_revocation_tombstone_removes_previous_verified_head(self):
        first = self.create_verified_revision(revision=1)
        self.create_revocation(revision=2, target=first)
        self.assertIsNone(first.profile.effective_verified_revision())

    def test_verified_successor_is_the_only_effective_head(self):
        first = self.create_verified_revision(revision=1)
        second = self.create_verified_revision(revision=2, supersedes=first)
        self.assertEqual(first.profile.effective_verified_revision(), second)
```

- [ ] **Step 2: Write failing inventory-policy tests**

```python
class ProductInventoryPolicyTests(TestCase):
    def test_warehouse_policy_never_falls_back_to_variant_stock(self):
        policy = ProductInventoryPolicy(product=self.product, source="warehouse")
        policy.full_clean()
        self.assertEqual(policy.source, "warehouse")

    def test_policy_source_is_required_for_checkout_truth(self):
        with self.assertRaises(ValidationError):
            ProductInventoryPolicy(product=self.product, source="").full_clean()
```

- [ ] **Step 3: Run tests to verify RED**

```bash
python manage.py test --settings=test_settings storefront.tests.test_product_sales_semantics fable5.tests.test_product_inventory_policy
```

Expected: import/model failures because the new contracts do not exist.

- [ ] **Step 4: Implement models and strict validators**

Implement the core model contract:

```python
class _AppendOnlySemanticRevisionQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValueError("Verified semantic revisions are append-only")

    def delete(self):
        raise ValueError("Verified semantic revisions are append-only")


class ProductSalesSemanticProfile(models.Model):
    product = models.OneToOneField(Product, on_delete=models.CASCADE, related_name="sales_semantic_profile", db_constraint=False)
    created_at = models.DateTimeField(auto_now_add=True)


class ProductSalesSemanticProfileRevision(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft"
        VERIFIED = "verified"
        REVOKED = "revoked"

    profile = models.ForeignKey(ProductSalesSemanticProfile, on_delete=models.PROTECT, related_name="revisions")
    revision = models.PositiveIntegerField()
    status = models.CharField(max_length=16, choices=Status.choices)
    schema_version = models.PositiveIntegerField(default=1)
    aliases = models.JSONField(default=dict, blank=True)
    traits = models.JSONField(default=dict, blank=True)
    source = models.CharField(max_length=32)
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT)
    verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    supersedes = models.OneToOneField("self", null=True, blank=True, on_delete=models.PROTECT)
    objects = models.Manager.from_queryset(_AppendOnlySemanticRevisionQuerySet)()

    class Meta:
        constraints = [models.UniqueConstraint(fields=("profile", "revision"), name="product_semantic_revision_once")]
```

`validate_semantic_revision()` must accept only controlled keys and codes, normalize locale aliases, reject verified `bot_vision`/free-text provenance, and reject mutation/deletion of an existing verified row. Admin save creates a new revision instead of editing verified history. Verified aliases also reject controlled color, size, garment, fit, decoration, and construction vocabulary, including generic multiword combinations, so phrases such as `black classic T-shirt` cannot authorize exact product identity. Product-specific aliases remain valid. Lock the profile while publishing or revoking a revision. A verified replacement explicitly supersedes the current effective head; an append-only revocation tombstone targets that exact same-profile head and clears effective catalog truth. Targetless, cross-profile, and stale-head transitions fail, and graph construction reads only the deterministic effective head.

Implement inventory source explicitly:

```python
class ProductInventoryPolicy(models.Model):
    class Source(models.TextChoices):
        WAREHOUSE = "warehouse"
        CATALOG_VARIANT = "catalog_variant"
        UNTRACKED = "untracked"

    product = models.OneToOneField(Product, on_delete=models.CASCADE, related_name="fable5_inventory_policy", db_constraint=False)
    source = models.CharField(max_length=24, choices=Source.choices)
    updated_at = models.DateTimeField(auto_now=True)
```

All new semantic, session, and allocation tables must be InnoDB. Foreign keys
pointing at legacy Product, IgClient, InstagramBotMessage, or other tables whose
production engine is not yet proven compatible use `db_constraint=False` while
retaining ORM ownership and explicit service validation. Migration tests inspect
actual table engines rather than assuming Django model declarations changed
legacy engines.

The policy data migration assigns `warehouse` only when a product has existing
structured `VariantBlankLink` evidence. Every other published product starts as
`untracked`; it must not infer `catalog_variant` from a positive stock number,
title, description, or `bot_vision`. Managers explicitly review remaining
policies before they authorize checkout.

- [ ] **Step 5: Generate and inspect migrations**

```bash
python manage.py makemigrations storefront fable5
python manage.py makemigrations --check --dry-run
```

Expected: exactly the semantic-profile and inventory-policy migrations; no unrelated model drift.

The semantic migration installs vendor-specific append-only triggers for
verified revision updates/deletes. MariaDB uses `SIGNAL SQLSTATE '45000'`;
SQLite equivalents exist only for local migration-executor coverage. Trigger
tests run again under `test_settings_mariadb` before deployment.

- [ ] **Step 6: Run GREEN and commit**

```bash
python manage.py test --settings=test_settings storefront.tests.test_product_sales_semantics fable5.tests.test_product_inventory_policy fable5.tests.test_variant_resources
git add twocomms/storefront/models.py twocomms/storefront/admin.py twocomms/storefront/services/product_sales_semantics.py twocomms/storefront/tests/test_product_sales_semantics.py twocomms/storefront/migrations/0088_product_sales_semantic_profiles.py twocomms/fable5/models.py twocomms/fable5/tests/test_product_inventory_policy.py twocomms/fable5/migrations/0008_product_inventory_policy.py
git commit -m "feat(catalog): add verified sales semantics"
```

Expected: tests pass and only Task 2 files are committed.

### Task 3: Build Trusted URL Resolution and the Typed Catalog Graph

**Current status (2026-08-05): PARTIAL, commits `7b5d5cc7` + `1c4d6d48`, NOT INTEGRATED.**
Price-aware graph/resolver uses variant/fit configuration prices, validates
combined color/fit/size compatibility, avoids the variant N+1 and includes
digest invalidation. Focused 162-test gate is green; independent review,
current-main integration and production proof remain.
Trusted resolver, graph и тесты есть в feature-ветке. Canonical option-path,
принадлежность опций товару и конфликтующие option URL остаются открытыми.

**Files:**
- Create: `twocomms/management/services/ig_commerce_types.py`
- Create: `twocomms/management/services/ig_product_references.py`
- Create: `twocomms/management/services/ig_catalog_graph.py`
- Create: `twocomms/management/tests_ig_catalog_intelligence.py`

- [ ] **Step 1: Write failing resolver and graph tests**

```python
class TrustedProductReferenceTests(TestCase):
    def test_exact_localized_storefront_url_resolves_published_slug(self):
        result = resolve_trusted_product_reference("https://twocomms.shop/ru/product/classic-tshirt/?utm=x#size")
        self.assertEqual(result.product_id, self.product.pk)
        self.assertTrue(result.is_exact)

    def test_lookalike_host_userinfo_port_and_unknown_slug_fail_closed(self):
        for value in (
            "https://twocomms.shop.evil.test/product/classic-tshirt/",
            "https://user@twocomms.shop/product/classic-tshirt/",
            "https://twocomms.shop:444/product/classic-tshirt/",
            "https://twocomms.shop/product/missing/",
        ):
            self.assertFalse(resolve_trusted_product_reference(value).is_exact)

    def test_two_distinct_trusted_product_urls_require_choice(self):
        result = resolve_trusted_product_reference(
            "https://twocomms.shop/product/classic-tshirt/ "
            "https://twocomms.shop/product/reality-bends/"
        )
        self.assertFalse(result.is_exact)
        self.assertEqual(result.reason, "multiple_products")

    def test_canonical_option_path_resolves_exact_product_and_owned_constraints(self):
        result = resolve_trusted_product_reference(
            "https://twocomms.shop/product/classic-tshirt/black/classic/"
        )
        self.assertEqual(result.product_id, self.product.pk)
        self.assertEqual(dict(result.constraints), {"color": "black", "fit": "classic"})

    def test_unknown_or_foreign_option_path_fails_closed(self):
        result = resolve_trusted_product_reference(
            "https://twocomms.shop/product/classic-tshirt/not-a-real-option/"
        )
        self.assertFalse(result.is_exact)
        self.assertEqual(result.reason, "invalid_product_option")

    def test_conflicting_option_urls_for_same_product_require_clarification(self):
        result = resolve_trusted_product_reference(
            "https://twocomms.shop/product/classic-tshirt/black/ "
            "https://twocomms.shop/product/classic-tshirt/pink/"
        )
        self.assertFalse(result.is_exact)
        self.assertEqual(result.reason, "conflicting_product_options")

    def test_graph_digest_changes_only_when_verified_topology_changes(self):
        first = build_catalog_graph()
        self.create_draft_semantics()
        self.assertEqual(build_catalog_graph().digest, first.digest)
        self.create_verified_semantics()
        self.assertNotEqual(build_catalog_graph().digest, first.digest)
```

- [ ] **Step 2: Run RED**

```bash
python manage.py test --settings=test_settings management.tests_ig_catalog_intelligence
```

Expected: missing module failures.

- [ ] **Step 3: Implement immutable value objects and resolver**

```python
import re
from dataclasses import dataclass
from urllib.parse import unquote, urlsplit

from django.conf import settings

from storefront.models import Product, ProductStatus


_URL_RE = re.compile(r"https://[^\s<>\"']+", re.IGNORECASE)


@dataclass(frozen=True)
class TrustedProductReference:
    product_id: int | None
    slug: str
    is_exact: bool
    reason: str
    constraints: tuple[tuple[str, str], ...] = ()


def resolve_trusted_product_reference(text: str) -> TrustedProductReference:
    configured = {str(value).casefold() for value in getattr(settings, "IG_COMMERCE_TRUSTED_STOREFRONT_HOSTS", ())}
    base_host = urlsplit(getattr(settings, "SITE_BASE_URL", "")).hostname
    if base_host:
        configured.add(base_host.casefold())
    configured.update({"twocomms.shop", "www.twocomms.shop"})
    matches = {}
    for raw in _URL_RE.findall(str(text or "")):
        parts = urlsplit(raw.rstrip(".,!?;:)]}"))
        try:
            port = parts.port
        except ValueError:
            continue
        if parts.scheme.casefold() != "https" or parts.username or parts.password or port not in (None, 443):
            continue
        if not parts.hostname or parts.hostname.casefold() not in configured:
            continue
        segments = [unquote(value) for value in parts.path.split("/") if value]
        if segments and segments[0].casefold() in {"uk", "ru", "en"}:
            segments = segments[1:]
        if len(segments) < 2 or segments[0].casefold() != "product":
            continue
        product = Product.objects.filter(slug__iexact=segments[1], status=ProductStatus.PUBLISHED).first()
        constraints = resolve_owned_product_option_segments(product, segments[2:])
        if product and constraints.is_valid:
            register_non_conflicting_match(matches, product, constraints.values)
    if len(matches) == 1:
        product_id, match = next(iter(matches.items()))
        return TrustedProductReference(
            product_id,
            match.slug,
            True,
            "exact_url",
            tuple(sorted(match.constraints.items())),
        )
    if len(matches) > 1:
        return TrustedProductReference(None, "", False, "multiple_products")
    return TrustedProductReference(None, "", False, "not_resolved")
```

Implement `CatalogGraphSnapshot` with product/category/variant/fit/size/verified-trait/print/blank/media nodes, stable sorted edges, exact verified revision IDs, and a SHA-256 digest over canonical JSON. Draft/revoked traits and `bot_vision` never enter authoritative edges.

- [ ] **Step 4: Run GREEN and commit**

```bash
python manage.py test --settings=test_settings management.tests_ig_catalog_intelligence management.tests_bot_catalog management.tests_bot_vision
git add twocomms/management/services/ig_commerce_types.py twocomms/management/services/ig_product_references.py twocomms/management/services/ig_catalog_graph.py twocomms/management/tests_ig_catalog_intelligence.py
git commit -m "feat(ig): build verified catalog knowledge graph"
```

### Task 4: Implement Explainable Candidate Filtering and Ranking

**Current status (2026-08-05): PARTIAL, commits `7b5d5cc7` + `1c4d6d48`, NOT INTEGRATED.**
Hard filtering now uses typed garment/size compatibility; ranking includes
catalog priority and preference evidence, with revoked/BOT_VISION regressions.
Remaining within IMP-083: relaxed alternatives after complete hard mismatch;
durable candidate generation/session revision binding belongs to Task 7/IMP-087.
Фильтрация/ranking реализованы в feature-ветке. Acceptance stale candidate
после смены published state, graph digest или semantic head не реализован.

**Files:**
- Create: `twocomms/management/services/ig_catalog_candidates.py`
- Modify: `twocomms/management/services/ig_commerce_types.py`
- Modify: `twocomms/management/tests_ig_catalog_intelligence.py`

- [ ] **Step 1: Write failing candidate tests**

```python
def test_black_classic_is_color_and_fit_not_reality_bends_title(self):
    request = CommerceTurnRequest(field_updates={"color": "black", "fit": "classic"})
    result = rank_candidates(self.graph, request)
    self.assertGreater(len(result.candidates), 1)
    self.assertFalse(result.auto_select)

def test_only_exact_url_unique_alias_or_single_hard_match_auto_selects(self):
    exact = rank_candidates(self.graph, self.request(exact_product_id=self.classic.pk))
    self.assertEqual(exact.selected_product_id, self.classic.pk)
    self.assertTrue(exact.auto_select)

def test_negative_back_print_is_never_silently_relaxed(self):
    result = rank_candidates(self.graph, self.request(hard={"back_decoration": "none"}))
    self.assertTrue(all(c.traits["back_decoration"] == "none" for c in result.candidates))

def test_candidate_acceptance_rebuilds_when_product_or_semantic_head_changed(self):
    prompt = self.persist_candidate_prompt(self.graph)
    self.product.status = "archived"
    self.product.save(update_fields=["status"])
    accepted = accept_candidate_choice(prompt, "1")
    self.assertEqual(accepted.reason, "candidate_graph_changed")
    self.assertFalse(accepted.auto_select)
```

- [ ] **Step 2: Run RED**

```bash
python manage.py test --settings=test_settings management.tests_ig_catalog_intelligence
```

- [ ] **Step 3: Implement deterministic ranking**

```python
@dataclass(frozen=True)
class CandidateDecision:
    candidates: tuple[CatalogCandidate, ...]
    auto_select: bool
    selected_product_id: int | None
    pending_question: str
    relaxed_alternatives: tuple[CatalogCandidate, ...]


def rank_candidates(graph, request, availability=None) -> CandidateDecision:
    hard_matches = apply_mandatory_constraints(graph.products, request)
    ordered = stable_explainable_score(hard_matches, request)
    auto = request.exact_product_id is not None or request.exact_unique_alias or len(ordered) == 1
    return CandidateDecision(tuple(ordered[:3]), auto, ordered[0].product_id if auto and ordered else None, discriminating_question(ordered), build_explicit_relaxed_alternatives(graph, request))
```

Never auto-select from `relaxed_alternatives`. Candidate numbering is bound later to session revision and candidate-set digest.
Acceptance revalidates published state, graph digest, and every effective
semantic revision used by the prompt; stale candidates are refreshed rather
than pinned.

- [ ] **Step 4: Run GREEN and commit**

```bash
python manage.py test --settings=test_settings management.tests_ig_catalog_intelligence
git add twocomms/management/services/ig_catalog_candidates.py twocomms/management/services/ig_commerce_types.py twocomms/management/tests_ig_catalog_intelligence.py
git commit -m "feat(ig): rank explainable catalog candidates"
```

### Task 5: Add Exact Warehouse-Aware Availability

**Current status (2026-08-03): PARTIAL, commit `e9d982df`, NOT INTEGRATED.**
Typed availability реализована в feature-ветке. Aggregate quantity для строк,
которые делят одну allocation identity, и полный wiring всех checkout readers
остаются открытыми.

**Files:**
- Create: `twocomms/management/services/ig_availability.py`
- Create: `twocomms/management/tests_ig_availability.py`
- Modify: `twocomms/fable5/services.py`
- Modify: `twocomms/fable5/size_grid_services.py`
- Modify: `twocomms/management/services/ig_checkout.py`
- Modify: `twocomms/management/services/bot_orders.py`
- Modify: `twocomms/management/services/instagram_bot.py`
- Modify: `twocomms/management/services/bot_catalog.py`

- [ ] **Step 1: Write failing availability tests**

```python
class CommerceAvailabilityTests(TestCase):
    def test_warehouse_policy_ignores_legacy_zero_variant_and_size_stock(self):
        self.variant.stock = 0
        self.variant.save(update_fields=["stock"])
        VariantSizeRule.objects.create(variant=self.variant, fit_code="classic", size="M", stock=0, is_enabled=True)
        self.link_blank(quantity=2, size="M", color=self.variant.color)
        result = resolve_allocation(self.spec(size="M", fit="classic", qty=1))
        self.assertEqual(result.status, AvailabilityStatus.ALLOCATABLE)

    def test_missing_blank_link_is_unknown_not_catalog_fallback(self):
        result = resolve_allocation(self.spec(size="M", fit="classic", qty=1))
        self.assertEqual(result.status, AvailabilityStatus.UNKNOWN)

    def test_exact_checkout_match_never_uses_graceful_category_fallback(self):
        self.link_wrong_size_stock()
        result = resolve_allocation(self.spec(size="M", fit="classic", qty=1))
        self.assertEqual(result.status, AvailabilityStatus.UNAVAILABLE)

    def test_lines_sharing_one_allocation_are_checked_as_aggregate_quantity(self):
        self.link_blank(quantity=1, size="M", color=self.variant.color)
        result = resolve_basket_allocations((self.spec(qty=1), self.spec(qty=1)))
        self.assertEqual(result.status, AvailabilityStatus.UNAVAILABLE)
```

- [ ] **Step 2: Run RED**

```bash
python manage.py test --settings=test_settings management.tests_ig_availability
```

- [ ] **Step 3: Implement typed availability**

```python
class AvailabilityStatus(StrEnum):
    CONFIGURABLE = "configurable"
    ALLOCATABLE = "allocatable"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class StockAllocation:
    source: str
    stock_item_id: int | None
    color_variant_id: int | None
    quantity: int


def resolve_allocation(spec, *, lock=False) -> AvailabilityDecision:
    policy = require_inventory_policy(spec.product_id)
    if policy.source == "warehouse":
        return resolve_exact_warehouse_allocation(spec, lock=lock)
    if policy.source == "catalog_variant":
        return resolve_exact_catalog_variant_allocation(spec, lock=lock)
    return AvailabilityDecision.unknown("inventory_untracked")
```

Add `inventory_source` or equivalent parameter to Fable compatibility helpers so warehouse checkout respects `is_enabled`, fit/options, and size-grid membership but ignores numeric legacy stock fields.

Group requested lines by exact allocation identity before authorizing any one
of them. Sum quantity per `stock_item_id` or catalog variant so two lines cannot
both claim the same final unit. Canonically merge identical configured lines or
reject them before proposal persistence.

Replace checkout authorization and alternative discovery based on raw
`ProductColorVariant.stock` in `ig_checkout.py`, `bot_orders.py`,
`instagram_bot.py`, and `bot_catalog.py` with this shared service. Existing
catalog-variant tests must create an explicit `CATALOG_VARIANT` policy;
warehouse tests must create `WAREHOUSE`, `VariantBlankLink`, and exact
`StockItem` fixtures. `bot_catalog` may describe configurable/made-to-order or
unknown policy states but cannot translate an unexplained zero counter into a
customer out-of-stock statement.

- [ ] **Step 4: Run GREEN and commit**

```bash
python manage.py test --settings=test_settings management.tests_ig_availability management.tests_ig_checkout_service management.tests_bot_catalog fable5.tests.test_variant_resources
git add twocomms/management/services/ig_availability.py twocomms/management/tests_ig_availability.py twocomms/fable5/services.py twocomms/fable5/size_grid_services.py twocomms/management/services/ig_checkout.py twocomms/management/services/bot_orders.py twocomms/management/services/instagram_bot.py twocomms/management/services/bot_catalog.py
git commit -m "feat(ig): resolve authoritative garment availability"
```

### Task 6: Upgrade Reservation and Warehouse Allocation Lifecycle

**Current status (2026-08-03): OPEN.** Production implementation commit
отсутствует; описанные reservation/state-machine/multi-line guarantees не
проверялись на актуальном MariaDB graph.

**Files:**
- Modify: `twocomms/management/ig_bot_models.py`
- Modify: `twocomms/management/services/ig_checkout.py`
- Modify: `twocomms/management/services/ig_inventory.py`
- Modify: `twocomms/management/services/ig_checkout_payment.py`
- Create: `twocomms/management/tests_ig_inventory_allocations.py`
- Create: `twocomms/management/migrations/0128_ig_inventory_allocations.py`
- Modify: `twocomms/warehouse/services/inventory.py`
- Modify: `twocomms/warehouse/views/write_off.py`
- Modify: `twocomms/warehouse/tests/test_sale_flow.py`
- Modify: `twocomms/warehouse/tests/test_write_off.py`

- [ ] **Step 1: Write RED lifecycle and concurrency tests**

```python
class IgInventoryAllocationTests(TransactionTestCase):
    def test_last_unit_is_reserved_when_proposal_is_created_not_when_delivery_is_submitted(self):
        self.set_warehouse_quantity(1)
        first = self.create_proposal()
        second = self.try_create_same_allocation_proposal_for_another_client()
        self.assertTrue(first.inventory_reservations.filter(state="active").exists())
        self.assertEqual(second.reason, "unavailable")

    def test_warehouse_payment_commits_without_decrement_then_writeoff_decrements_once(self):
        reservation = self.reserve_warehouse(quantity=1, physical=2)
        commit_paid_inventory(reservation.proposal, order=self.order)
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, 2)
        fulfill_paid_allocation(order_item=self.order_item, stock_item=self.stock, quantity=1)
        self.stock.refresh_from_db()
        reservation.refresh_from_db()
        self.assertEqual(self.stock.quantity, 1)
        self.assertEqual(reservation.state, "fulfilled")

    def test_late_paid_released_reservation_becomes_overbooked_review(self):
        reservation = self.released_reservation(physical=0)
        commit_paid_inventory(reservation.proposal, order=self.order)
        reservation.refresh_from_db()
        self.assertEqual(reservation.state, "overbooked_review")

    def test_two_lines_sharing_one_stock_item_are_checked_as_one_quantity(self):
        self.set_warehouse_quantity(1)
        result = self.try_create_proposal(lines=[self.spec(qty=1), self.spec(qty=1)])
        self.assertEqual(result.reason, "unavailable")
        self.assertFalse(IgCheckoutInventoryReservation.objects.exists())

    def test_late_multi_line_payment_records_all_deficits_atomically(self):
        result = self.commit_late_payment_with_partially_available_allocations()
        self.assertEqual(result.review.reason, "late_payment_overbooked")
        self.assertEqual(set(result.review.deficient_line_ids), set(self.expected_deficient_line_ids))
```

Add warehouse tests proving exact allocation match, negative adjustment guard, and `reverse_write_off()` returning `fulfilled` to `paid_committed` atomically.

- [ ] **Step 2: Run RED**

```bash
python manage.py test --settings=test_settings management.tests_ig_inventory_allocations warehouse.tests.test_sale_flow warehouse.tests.test_write_off
```

- [ ] **Step 3: Implement migration and state machine**

Extend `IgCheckoutInventoryReservation` with states and exact links:

```python
class State(models.TextChoices):
    ACTIVE = "active"
    PAID_COMMITTED = "paid_committed"
    FULFILLED = "fulfilled"
    RELEASED = "released"
    OVERBOOKED_REVIEW = "overbooked_review"

allocation_source = models.CharField(max_length=24)
stock_item = models.ForeignKey("warehouse.StockItem", null=True, blank=True, on_delete=models.PROTECT, db_constraint=False)
order = models.ForeignKey("orders.Order", null=True, blank=True, on_delete=models.PROTECT)
order_item = models.ForeignKey("orders.OrderItem", null=True, blank=True, on_delete=models.PROTECT)
write_off_request = models.ForeignKey("warehouse.WriteOffRequest", null=True, blank=True, on_delete=models.PROTECT)
stock_movement = models.OneToOneField("warehouse.StockMovement", null=True, blank=True, on_delete=models.PROTECT)
paid_committed_at = models.DateTimeField(null=True, blank=True)
fulfilled_at = models.DateTimeField(null=True, blank=True)
```

Implement allowed transitions and unconditional uniqueness per immutable proposal
item, which is MariaDB-compatible. For warehouse allocations, the verified
payment binding in `ig_checkout_payment.bind_verified_payment` changes state
only. For catalog-variant allocations, retain guarded payment-time decrement.
Proposal creation, not the later delivery-details submit, locks the exact live
allocation and creates the 25-minute active reservation. Concurrent proposal
creation for the final unit has one winner; the losing client receives a fresh
unavailable decision and no payable link.
Before locking, group every proposal line by immutable allocation identity and
sum its quantity. Duplicate identical configured lines are merged canonically
or rejected; they are never validated independently against the same stock.
Late multi-line payment classifies all allocations in one transaction and
creates one review containing all deficient lines without losing payment truth.
The migration depends on current `orders.0053` (or its new leaf) and includes a
data migration: legacy `CONSUMED` rows become `FULFILLED` with
`catalog_variant`; legacy active/released rows retain state and receive
`catalog_variant`. Do not invent warehouse links for legacy rows.

- [ ] **Step 4: Guard all negative warehouse adjustments**

Inside `adjust_stock_item`, re-read the exact row with `select_for_update()`. For negative deltas, subtract other `active` and `paid_committed` allocations unless the call supplies the exact matching allocation being fulfilled. Reject any adjustment below committed availability.

`write_off_submit` must call a service that validates order, order item, stock item, and quantity against the paid commitment. `reverse_write_off` restores quantity and the same allocation in one transaction.

- [ ] **Step 5: Run GREEN and commit**

```bash
python manage.py test --settings=test_settings management.tests_ig_inventory_allocations management.tests_ig_checkout_service management.tests_ig_checkout_reconciliation management.tests_ig_checkout_workspace warehouse.tests.test_sale_flow warehouse.tests.test_write_off warehouse.tests.test_models
python manage.py makemigrations --check --dry-run
git add twocomms/management/ig_bot_models.py twocomms/management/services/ig_checkout.py twocomms/management/services/ig_inventory.py twocomms/management/services/ig_checkout_payment.py twocomms/management/tests_ig_inventory_allocations.py twocomms/management/migrations/0128_ig_inventory_allocations.py twocomms/warehouse/services/inventory.py twocomms/warehouse/views/write_off.py twocomms/warehouse/tests/test_sale_flow.py twocomms/warehouse/tests/test_write_off.py
git commit -m "feat(ig): bind checkout reservations to warehouse stock"
```

### Task 7: Add Durable Commerce Sessions, Transitions, Decisions, and Reviews

**Current status (2026-08-03): OPEN.** Модели, миграции и durable outbox не
реализованы.

**Files:**
- Modify: `twocomms/management/ig_bot_models.py`
- Create: `twocomms/management/services/ig_commerce_state.py`
- Create: `twocomms/management/services/ig_commerce_projection.py`
- Create: `twocomms/management/tests_ig_commerce_state.py`
- Create: `twocomms/management/migrations/0129_ig_commerce_selection_state.py`

- [ ] **Step 1: Write RED model and replay tests**

```python
class CommerceStateTests(TransactionTestCase):
    def test_session_is_authoritative_and_projects_legacy_fields_atomically(self):
        decision = apply_turn(self.client, self.message, self.change_product(self.classic))
        self.client.refresh_from_db()
        self.assertEqual(decision.session.lines[0]["product_id"], self.classic.pk)
        self.assertEqual(self.client.current_product_id, self.classic.pk)
        self.assertNotIn("stale", self.client.sales_context.get("assisted_checkout_selection", {}))

    def test_same_source_message_replay_returns_stored_decision_after_revision_changes(self):
        first = apply_turn(self.client, self.message, self.change_product(self.classic))
        self.advance_session()
        replay = apply_turn(self.client, self.message, self.change_product(self.classic))
        self.assertEqual(replay.pk, first.pk)
        self.assertEqual(IgCommerceSelectionTransition.objects.filter(source_message=self.message).count(), 1)

    def test_late_imported_older_message_cannot_overwrite_newer_selection(self):
        fresh = self.message_at("2026-08-02T10:00:00Z", "беру черную классику")
        delayed = self.message_at("2026-08-02T09:00:00Z", "розовая reality bends")
        apply_turn(self.client, fresh, self.change_product(self.classic))
        stale = apply_turn(self.client, delayed, self.change_product(self.reality))
        self.assertTrue(stale.is_stale)
        self.assertEqual(self.current_session().lines[0]["product_id"], self.classic.pk)

    def test_crash_before_transport_resumes_persisted_outbox_without_reducing_again(self):
        decision = self.persist_decision_without_starting_transport()
        replay = resume_turn_delivery(decision.source_message)
        self.assertEqual(replay.pk, decision.pk)
        self.assertEqual(self.transition_count(), 1)
        self.assertEqual(self.transport_calls(), 1)

    def test_ambiguous_or_partially_delivered_outbox_never_blind_resends(self):
        for state in ("sending", "unknown", "partial", "sent"):
            with self.subTest(state=state):
                decision = self.decision_with_outbox_state(state)
                resume_turn_delivery(decision.source_message)
                self.assertEqual(self.transport_calls_for(decision), 0)

    def test_information_turn_keeps_candidate_generation_but_replaced_prompt_invalidates_number(self):
        self.persist_candidate_prompt(provider_ids=["mid-1"])
        self.apply_information_only_turn()
        self.assertTrue(self.select_number(1, reply_to="mid-1").accepted)
        self.replace_candidate_prompt(provider_ids=["mid-2"])
        self.assertFalse(self.select_number(1, reply_to="mid-1").accepted)

    def test_candidate_generation_survives_information_only_revision(self):
        prompt = self.create_candidate_prompt()
        self.apply_info_only_turn("покажи размерную сетку")
        self.assertEqual(self.current_session().candidate_generation, prompt.generation)

    def test_delivery_outbox_is_separate_from_effect_idempotency(self):
        decision = self.persist_decision_without_crossing_transport_boundary()
        replay = claim_decision_delivery(decision)
        self.assertEqual(replay.pk, decision.pk)
        self.assertEqual(replay.delivery_state, "sending")
        self.assertEqual(IgCommerceSelectionTransition.objects.count(), 1)
```

- [ ] **Step 2: Run RED**

```bash
python manage.py test --settings=test_settings management.tests_ig_commerce_state
```

- [ ] **Step 3: Implement durable models**

Add `IgCommerceSelectionSession`, append-only `IgCommerceSelectionTransition`, unique-source `IgCommerceTurnDecision`, and SLA-backed `IgCommerceManagerReview`. Session stores generation, commercial episode, ordered lines, active index, selection/query constraints, candidate digest, candidate generation, candidate prompt provider IDs, rejected selection, pending field, semantic block key, graph digest, last provider event time/message ID, and optimistic revision. The inbound message stores reply-to/quick-reply identity when Meta supplies it. The decision owns immutable reply payload plus outbox state (`pending`, `sending`, `unknown`, `partial`, `sent`), provider IDs for every text/media part, attempt timestamps, and reconciliation/review result. Use nullable `open_slot=1` plus a MariaDB-compatible unique constraint on `(client, open_slot)` so one client has one open generation while closed rows use `NULL`. Constraints to legacy `IgClient` and `InstagramBotMessage` are logical (`db_constraint=False`); new tables remain InnoDB. Effective ordering is provider event time, then message ID. A delayed older message receives a durable stale decision but cannot mutate selection or send a new commerce reply.

Store `candidate_generation` separately from session revision, plus outbound
candidate-prompt provider IDs and inbound reply-to/quick-reply identity where
Meta supplies them. `IgCommerceTurnDecision` also stores durable delivery state
(`pending`, `sending`, `unknown`, `sent`), attempt timestamps, text/media chunk
receipts, and all provider message IDs. Replaying effects never means blindly
resending across an ambiguous transport boundary.

`ig_commerce_projection.py` provides `bootstrap_session_from_legacy`,
`authoritative_session_for`, and `project_active_line_to_legacy_client`. The
ordered session lines are basket truth; legacy `current_*` exposes only the
active line. A product switch replaces only that active line, preserving other
explicit basket lines.

The transactional API is:

```python
@transaction.atomic
def apply_turn(client, source_message, request, *, expected_revision=None) -> IgCommerceTurnDecision:
    existing = IgCommerceTurnDecision.objects.select_for_update().filter(source_message=source_message).first()
    if existing:
        return existing
    session = lock_or_create_current_session(client)
    next_snapshot, effects = reduce_session(session.snapshot(), request)
    transition = persist_transition(session, source_message, next_snapshot, effects)
    project_legacy_client_fields(client, next_snapshot)
    return IgCommerceTurnDecision.objects.create(source_message=source_message, transition=transition)
```

Application and MariaDB protections reject transition mutation/deletion. Existing sessions eliminate fallback to stale legacy fields.

Migration `0129` installs MariaDB append-only update/delete triggers for
transitions and immutable decision identity. Add migration-executor tests and
raw-SQL MariaDB assertions rather than relying on migration-disabled SQLite
syncdb to prove production triggers.

Replay returns the stored transition/effects and never reduces the turn again.
Delivery may resume only from `pending` or a definite pre-request cancellation.
`sending`, timeout/unknown, partial delivery, and success-before-local-ack require
provider reconciliation or one manager review; they never blind-resend.

- [ ] **Step 4: Run GREEN and commit**

```bash
python manage.py test --settings=test_settings management.tests_ig_commerce_state management.tests_ig_checkout_models
python manage.py makemigrations --check --dry-run
git add twocomms/management/ig_bot_models.py twocomms/management/services/ig_commerce_state.py twocomms/management/services/ig_commerce_projection.py twocomms/management/tests_ig_commerce_state.py twocomms/management/migrations/0129_ig_commerce_selection_state.py
git commit -m "feat(ig): persist reversible commerce selection state"
```

### Task 8: Implement Compound-Turn Parsing and Exact State Reduction

**Current status (2026-08-03): PARTIAL, commit `dc9889c3`, NOT INTEGRATED.**
Детерминированный parser и его unit-тесты есть в feature-ветке. Reducer,
client/session lock, burst ordering, multilingual composition и durable
decision per inbound ещё не реализованы.

**Files:**
- Create: `twocomms/management/services/ig_commerce_turns.py`
- Modify: `twocomms/management/services/ig_commerce_state.py`
- Create: `twocomms/management/tests_ig_commerce_turns.py`

- [ ] **Step 1: Write RED transition matrix tests**

```python
def test_size_guide_topic_never_changes_payable_fit(self):
    state = self.state(product=self.classic, fit="classic", intent="payment")
    result = reduce_session(state, parse_turn("Покажи на оверсайз размерную сетку"))
    self.assertEqual(result.selection["fit"], "classic")
    self.assertEqual(result.info_topics, ("size_guide:oversize",))
    self.assertFalse(result.checkout_requested)

def test_product_switch_clears_product_scoped_fields_and_applies_explicit_new_constraints(self):
    state = self.state(product=self.reality, color="pink", fit="oversize", size="L", quantity=1)
    result = reduce_session(state, parse_turn("Ок, давай стандартную черную классическую"))
    self.assertIsNone(result.selection.get("product_id"))
    self.assertEqual(result.selection["color"], "black")
    self.assertEqual(result.selection["fit"], "classic")
    self.assertNotIn("size", result.selection)

def test_without_print_asks_placement_but_explicit_front_logo_no_back_print_does_not(self):
    self.assertEqual(parse_turn("без принта").pending_clarification, "print_placement")
    exact = parse_turn("логотип спереди, без принта сзади")
    self.assertEqual(exact.hard_constraints["front_decoration"], "logo")
    self.assertEqual(exact.hard_constraints["back_decoration"], "none")

def test_negated_or_multiple_exact_urls_do_not_auto_select(self):
    negated = parse_turn("не хочу https://twocomms.shop/product/reality-bends/")
    self.assertIsNone(negated.exact_product_id)
    self.assertIn(self.reality.pk, negated.rejected_product_ids)
    multiple = parse_turn(self.classic_url + " " + self.reality_url)
    self.assertEqual(multiple.pending_clarification, "multiple_product_links")

def test_invalid_gemini_payload_falls_back_to_one_safe_clarification(self):
    request = understand_turn("давай другую обычную", model_payload={"product_id": 999999})
    self.assertIsNone(request.exact_product_id)
    self.assertEqual(request.pending_clarification, "which_product")

def test_quantity_change_resets_only_obsolete_unavailable_block_and_review(self):
    state = self.unavailable_state(quantity=2, review_open=True)
    result = reduce_session(state, parse_turn("тогда одну"))
    self.assertEqual(result.selection["quantity"], 1)
    self.assertNotEqual(result.semantic_block_key, state.semantic_block_key)
    self.assertTrue(result.effects.cancel_obsolete_review)

def test_mixed_language_constraints_are_composed_without_guessing_product(self):
    request = parse_turn("давай black класичну M")
    self.assertEqual(request.field_updates, {"color": "black", "fit": "classic", "size": "M"})
    self.assertIsNone(request.exact_product_id)

def test_paid_repeat_purchase_exchange_and_ambiguous_change_are_distinct(self):
    self.assertTrue(parse_turn("хочу еще одну черную M").new_purchase_requested)
    self.assertTrue(parse_turn("хочу поменять размер в полученной").exchange_requested)
    self.assertEqual(parse_turn("хочу другую").pending_clarification, "new_purchase_or_exchange")
```

- [ ] **Step 2: Run RED**

```bash
python manage.py test --settings=test_settings management.tests_ig_commerce_turns
```

- [ ] **Step 3: Implement deterministic parser and reducer**

`CommerceTurnRequest` must contain separate exact reference, corrections, field updates, info topics, hard constraints, preferences, and checkout/reset/support flags. Deterministic rules handle trusted URL, URL negation/multiple links, correction verbs, classic/oversize, colors, size-guide phrases, and print-placement negation in Russian, Ukrainian, and English. Gemini uses the existing JSON-generation wrapper to fill the same strict schema but returns no authoritative product ID; unknown fields, IDs, invalid enums, and malformed payloads are discarded into the deterministic clarification fallback.

Reducer order is reference/corrections, explicit updates, info response, validation, optional checkout. Use the invalidation matrix from the spec. Product, fit, size, color, quantity, semantic constraints, and stable affected basket-line identity participate in the semantic unavailable key; a relevant change clears only the obsolete block and manager review, while unrelated turns do not. Reduce already-persisted rapid bursts under one client lock in provider-event order, compose complementary fragments, persist a decision for each inbound, and emit only the final useful reply. Deterministic multilingual rules compose mixed-language turns; transliteration that cannot be mapped safely asks one clarification. Paid-history classification is not a permanent sales gate: explicit repeat purchase opens a new commercial episode, exchange wording routes to the existing exchange workflow, and genuinely ambiguous wording asks which action is meant.

- [ ] **Step 4: Run GREEN and commit**

```bash
python manage.py test --settings=test_settings management.tests_ig_commerce_turns management.tests_ig_commerce_state
git add twocomms/management/services/ig_commerce_turns.py twocomms/management/services/ig_commerce_state.py twocomms/management/tests_ig_commerce_turns.py
git commit -m "feat(ig): reduce compound commerce turns safely"
```

### Task 9: Integrate Candidate Choices, Replies, and Manager Recovery

**Current status (2026-08-03): OPEN.** Интеграция до Gemini/legacy classifier,
provider receipts и manager recovery отсутствуют.

**Files:**
- Create: `twocomms/management/services/ig_commerce_replies.py`
- Modify: `twocomms/management/services/ig_commerce_state.py`
- Modify: `twocomms/management/services/instagram_bot.py`
- Modify: `twocomms/management/services/bot_sales_classifier.py`
- Modify: `twocomms/management/services/bot_memory.py`
- Modify: `twocomms/management/services/bot_playbooks.py`
- Modify: `twocomms/management/services/ig_funnel_reset.py`
- Create: `twocomms/management/tests_ig_product_reselection.py`

- [ ] **Step 1: Write the full `zainllw0w` RED regression**

```python
def test_unavailable_pink_can_switch_to_classic_url_without_stale_spam(self):
    self.seed_unavailable_reality_selection()
    self.turn("Ок давай классическую черную без ничего")
    guide = self.turn("Покажи на оверсайз размерную сетку")
    self.assertIn("size_guide", guide.decision.info_topics)
    self.assertEqual(self.proposals.count(), 0)
    switched = self.turn("https://twocomms.shop/product/classic-tshirt/")
    self.assertEqual(switched.session.lines[0]["product_id"], self.classic.pk)
    self.assertNotIn("reality", switched.reply.casefold())
    self.assertEqual(self.identical_unavailable_replies(), 1)

def test_persisted_burst_reduces_to_one_final_reply_without_losing_fields(self):
    self.persist_pending_turns("розовую", "нет, черную", "M", "две")
    process_client_commerce_batch(self.client)
    self.assertEqual(self.sent_replies.count(), 1)
    self.assertEqual(self.session_line(), {"color": "black", "size": "M", "quantity": 2})

def test_trusted_url_wins_over_conflicting_attached_photo(self):
    result = self.turn(self.classic_url, attachment=self.reality_photo)
    self.assertEqual(result.session.lines[0]["product_id"], self.classic.pk)

def test_delivery_retry_only_occurs_before_provider_boundary(self):
    pending = self.crash_before_send()
    self.replay(pending)
    self.assertEqual(self.transport_calls(pending), 1)
    for decision in self.ambiguous_partial_and_sent_decisions():
        self.replay(decision)
        self.assertEqual(self.transport_calls(decision), 0)
```

Add cases for multi-candidate numbered selection with digest, stale `1`, garment switch, `black classic`, explicit front-logo/no-back-print, unknown mapping, one review, and new selection leaving manager review.

- [ ] **Step 2: Run RED**

```bash
python manage.py test --settings=test_settings management.tests_ig_product_reselection
```

- [ ] **Step 3: Integrate before Gemini reply generation**

At `_process_one_inside_reply_boundary`, after the existing permission/opt-out
gate but before generic history/Gemini reply generation, call the commerce
session service. A handled commerce turn uses its reply/media/proposal and skips
the legacy `gemini_generate`/`finalize_paylink` path. A non-commerce turn
continues unchanged. Persist the provider receipt returned by
`send_text(..., return_receipt=True)` on `IgCommerceTurnDecision`. Commerce URL
resolution must run before rule classification or either media/vision pinning
path can mutate product state. `send_text` returns a structured receipt on all
early-error paths and the decision stores every text-chunk/media provider ID.

Claim and reduce all already-persisted pending messages for one client in
provider-event order under the client/session lock. Persist a decision for each
source event, compose complementary fields, and send only the final useful
decision. Delivery replay never recomputes transitions, proposals, reservations,
or reviews; it retries only a persisted `pending` delivery whose provider
boundary is known not to have been crossed. `sending`, timeout/ambiguous,
partial, and sent states reconcile or escalate without blind resend.

When an authoritative session is active, `bot_sales_classifier` may still write
classification evidence but cannot independently mutate commerce `current_*`.
Route context readers in `bot_memory`, `bot_playbooks`, CRM card construction,
and funnel reset through the projection/session boundary. Convert
`_checkout_selection_state`, `_persist_checkout_selection`,
`_is_checkout_selection_reply`, `_current_color_variant_id`,
`_checkout_alternative_labels`, `payment_link_allowed`, `finalize_paylink`, and
`bot_orders.pin_product` into compatibility wrappers or remove their authority
after all readers migrate.

`ig_commerce_replies.py` localizes safe templates for candidate choices, missing fields, size guide, unavailable, unknown mapping, review already open, and exact URL acknowledgement. It never claims availability or manager action absent the corresponding decision/effect.

Commerce routing precedes the legacy paid/post-sale classifier. An explicit
repeat purchase opens a new commercial episode/session while leaving the paid
order immutable; an exchange stays in the existing exchange workflow and an
ambiguous request asks which one is intended.

- [ ] **Step 4: Run GREEN and commit**

```bash
python manage.py test --settings=test_settings management.tests_ig_product_reselection management.tests_ig_paylink_fix management.tests_ig_sales_automation management.tests_ig_bot_resilience
git add twocomms/management/services/ig_commerce_replies.py twocomms/management/services/ig_commerce_state.py twocomms/management/services/instagram_bot.py twocomms/management/services/bot_sales_classifier.py twocomms/management/services/bot_memory.py twocomms/management/services/bot_playbooks.py twocomms/management/services/ig_funnel_reset.py twocomms/management/tests_ig_product_reselection.py
git commit -m "fix(ig): recover cleanly from product reselection"
```

### Task 10: Enforce Proposal Digest Idempotency and Safe Replacement

**Current status (2026-08-03): OPEN.** Payable digest, uniqueness и безопасная
замена при неоднозначной provider truth не реализованы.

**Files:**
- Modify: `twocomms/management/ig_bot_models.py`
- Modify: `twocomms/management/services/ig_checkout.py`
- Modify: `twocomms/management/services/bot_orders.py`
- Modify: `twocomms/management/services/ig_inventory.py`
- Create: `twocomms/management/migrations/0130_ig_checkout_payable_digest.py`
- Modify: `twocomms/management/tests_ig_checkout_service.py`
- Modify: `twocomms/management/tests_ig_paylink_fix.py`

- [ ] **Step 1: Write RED proposal tests**

```python
def test_new_evidence_message_returns_same_active_proposal_for_same_payable_digest(self):
    first = create_checkout_proposal_link(self.client, item_specs=self.items, evidence={"message_ids": [1]})
    second = create_checkout_proposal_link(self.client, item_specs=self.items, evidence={"message_ids": [1, 2]})
    self.assertEqual(first["proposal_id"], second["proposal_id"])
    self.assertEqual(IgCheckoutProposal.objects.count(), 1)

def test_ready_uninvoiced_proposal_is_revoked_before_changed_selection(self):
    old = self.ready_proposal_without_attempt()
    change_product_after_proposal(self.session, self.new_selection)
    old.refresh_from_db()
    self.assertEqual(old.status, "revoked")
    self.assertFalse(old.inventory_reservations.filter(state="active").exists())

def test_checkout_revalidates_unpublished_price_and_allocation_changes(self):
    selection = self.ready_selection()
    self.product.status = "archived"
    self.product.save(update_fields=["status"])
    with self.assertRaisesMessage(CheckoutConfigurationError, "unpublished_product"):
        create_proposal_from_selection(selection)

def test_processing_or_ambiguous_invoice_keeps_reselection_pending(self):
    for state in ("details_locked", "processing", "invoice_creation_ambiguous"):
        old = self.proposal_with_attempt_state(state)
        result = change_product_after_proposal(self.session, self.new_selection)
        old.refresh_from_db()
        self.assertEqual(result.reason, "awaiting_provider_truth")
        self.assertNotEqual(old.status, "revoked")
        self.assertFalse(result.replacement_proposal_created)
```

Add an invoiced-unpaid case proving replacement waits for provider-confirmed cancellation, and a paid case proving immutability/new episode routing.
Treat `details_locked`, provider processing, and invoice-creation ambiguity as
possible provider side effects even when an invoice ID is not yet stored. Keep
the requested replacement pending and retain the old allocation/link until
trusted terminal provider truth permits release; only a definite pre-provider
failure may release and retry safely.

- [ ] **Step 2: Run RED**

```bash
python manage.py test --settings=test_settings management.tests_ig_checkout_service management.tests_ig_paylink_fix
```

- [ ] **Step 3: Implement canonical payable digest and database uniqueness**

Digest canonical ordered lines, exact product/variant/fit/size/quantity, catalog and quoted prices, pay type, deal/commercial episode, semantic revision IDs, and allocation identities. Evidence watermark remains audit evidence but is not part of the uniqueness permission. Immediately before persistence, re-read published status, current authoritative price, semantic revisions, configuration compatibility, and exact locked allocation; a stale session never freezes outdated commerce truth.

Return or reissue a valid token for the same active proposal rather than creating another proposal/reservation. Apply safe revoke/cancel/paid rules before accepting a changed session.

- [ ] **Step 4: Run GREEN and commit**

```bash
python manage.py test --settings=test_settings management.tests_ig_checkout_service management.tests_ig_checkout_models management.tests_ig_paylink_fix management.tests_ig_inventory_allocations
python manage.py makemigrations --check --dry-run
git add twocomms/management/ig_bot_models.py twocomms/management/services/ig_checkout.py twocomms/management/services/bot_orders.py twocomms/management/services/ig_inventory.py twocomms/management/migrations/0130_ig_checkout_payable_digest.py twocomms/management/tests_ig_checkout_service.py twocomms/management/tests_ig_paylink_fix.py
git commit -m "fix(ig): create one proposal per payable selection"
```

### Task 11: Add Operational Review UI and Safe Audit/Backfill Commands

**Current status (2026-08-03): OPEN.** UI, resolution revalidation и read-only
audit/backfill команды отсутствуют.

**Files:**
- Modify: `twocomms/management/bot_views.py`
- Modify: `twocomms/management/templates/management/bot.html`
- Create: `twocomms/management/management/commands/audit_ig_commerce_readiness.py`
- Create: `twocomms/management/management/commands/replay_ig_commerce_incident.py`
- Create: `twocomms/management/tests_ig_commerce_operations.py`

- [ ] **Step 1: Write RED operations tests**

```python
def test_manager_review_is_visible_with_reason_selection_and_sla(self):
    review = self.create_review(reason="inventory_unknown")
    response = self.client.get(self.crm_url)
    self.assertContains(response, "inventory_unknown")
    self.assertContains(response, review.due_at.isoformat()[:10])

def test_readiness_audit_dry_run_performs_no_writes(self):
    before = self.snapshot_counts()
    call_command("audit_ig_commerce_readiness", "--dry-run")
    self.assertEqual(self.snapshot_counts(), before)

def test_manager_resolution_revalidates_current_stock_and_selection_digest(self):
    review = self.create_review(reason="inventory_unknown")
    self.deplete_stock_and_change_active_line()
    result = resolve_manager_review(review, resolution="available")
    self.assertEqual(result.reason, "stale_review")
    self.assertFalse(result.proposal_created)

def test_manager_alternative_requires_customer_acceptance(self):
    review = self.create_review(reason="inventory_unavailable")
    result = resolve_manager_review(review, alternative=self.other_product)
    self.assertEqual(result.session.state, "awaiting_alternative")
    self.assertNotEqual(result.session.lines[0]["product_id"], self.other_product.pk)
```

- [ ] **Step 2: Run RED**

```bash
python manage.py test --settings=test_settings management.tests_ig_commerce_operations
```

- [ ] **Step 3: Implement UI and commands**

The CRM panel shows current line selection, pending field, rejected selection, candidate reasons, review status/SLA, and resolution action without exposing raw transcript/PII JSON. Resolution checks generation and selection digest before applying.
Every resolution re-runs current inventory policy, exact allocation, published
state, and effective semantic revisions under lock. A manager's stale
`available` result cannot bypass checkout authorization, and a substituted
product/size/color remains an offered alternative until the customer explicitly
accepts it. Double resolution is idempotent.

`audit_ig_commerce_readiness --dry-run` reports semantic coverage, inventory-policy coverage, missing/ambiguous `VariantBlankLink`, exact size/color allocations, and products blocked only by legacy zero stock. It never auto-verifies free text.

`replay_ig_commerce_incident --username <name> --read-only --no-send` reads sanitized message order by provider event time and runs only pure decision construction; it refuses execution without `--no-send` outside a dedicated test account.

- [ ] **Step 4: Run GREEN and commit**

```bash
python manage.py test --settings=test_settings management.tests_ig_commerce_operations
git add twocomms/management/bot_views.py twocomms/management/templates/management/bot.html twocomms/management/management/commands/audit_ig_commerce_readiness.py twocomms/management/management/commands/replay_ig_commerce_incident.py twocomms/management/tests_ig_commerce_operations.py
git commit -m "feat(ig): expose commerce recovery operations"
```

### Task 12: Run the Full Regression Matrix and Production-Like MariaDB Proof

**Current status (2026-08-03): OPEN.** Старые focused-тесты отдельных commits
не заменяют unified regression и MariaDB proof на актуальном `main`.

**Files:**
- Modify as required by failures only: files already owned by Tasks 2-11
- Create: `twocomms/test_settings_mariadb.py`
- Create: `docs/superpowers/reports/2026-08-02-instagram-reselection-verification.md`

- [ ] **Step 1: Run focused commerce suites**

```bash
python manage.py test --settings=test_settings management.tests_ig_catalog_intelligence management.tests_ig_availability management.tests_ig_inventory_allocations management.tests_ig_commerce_state management.tests_ig_commerce_turns management.tests_ig_product_reselection management.tests_ig_commerce_operations management.tests_ig_checkout_models management.tests_ig_checkout_service management.tests_ig_paylink_fix
```

Expected: all new and checkout-focused tests pass.

- [ ] **Step 2: Run related regression suites**

```bash
python manage.py test --settings=test_settings management.tests_bot_catalog management.tests_bot_orders management.tests_bot_payments management.tests_ig_sales_automation management.tests_ig_bot_resilience fable5.tests warehouse.tests
```

Expected: no new failures. Report baseline-only failures separately with reproduction on `origin/main`.

- [ ] **Step 3: Run structural checks**

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python -m compileall management storefront fable5 warehouse
git diff --check
```

Expected: exit code 0 for every command.

- [ ] **Step 4: Verify against production-like MariaDB**

Create explicit disposable settings; do not reuse `test_settings` because it
disables migrations:

```python
from os import environ

from django.core.exceptions import ImproperlyConfigured

from test_settings import *


name = environ.get("TEST_MARIADB_NAME", "")
if not name.startswith("test_twocomms_"):
    raise ImproperlyConfigured("TEST_MARIADB_NAME must name a disposable test_twocomms_* database")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": name,
        "USER": environ["TEST_MARIADB_USER"],
        "PASSWORD": environ["TEST_MARIADB_PASSWORD"],
        "HOST": environ.get("TEST_MARIADB_HOST", "127.0.0.1"),
        "PORT": environ.get("TEST_MARIADB_PORT", "3306"),
        "TEST": {"NAME": name},
        "OPTIONS": {"charset": "utf8mb4"},
    }
}
MIGRATION_MODULES = {}
```

Run the migration graph and transaction tests using the repository's MariaDB
test configuration. Assert `connection.vendor == "mysql"` and verify through
`information_schema` that proposal/item/reservation, `warehouse_stockitem`,
`warehouse_stockmovement`, write-off, and affected order tables are InnoDB.
Use two independent database connections/threads to prove `SELECT FOR UPDATE`
last-unit winner behavior and the concurrent negative-adjustment guard. Test
raw-SQL constraint violations and inspect `EXPLAIN` for the exact allocation
query indexes.

Prove payment commitment, write-off, reverse write-off, late payment, and manual
adjustment races. SQLite tests cover pure semantics only and are never reported
as lock/trigger proof; migration-executor coverage must fail honestly when a
backend cannot provide the required constraint.

```bash
python manage.py test --settings=test_settings_mariadb management.tests_ig_inventory_allocations management.tests_ig_commerce_state warehouse.tests.test_sale_flow warehouse.tests.test_write_off
```

Expected: migrations execute on disposable MariaDB; race and raw-SQL constraint
tests pass with InnoDB evidence.

- [ ] **Step 5: Perform sanitized read-only incident replay**

```bash
python manage.py replay_ig_commerce_incident --username zainllw0w --read-only --no-send
```

Expected: exact URL selects `classic-tshirt`; size-guide turn creates no proposal; repeated unavailable decision is suppressed; no outbound transport, proposal, reservation, or review write is called.

- [ ] **Step 6: Commit verification evidence**

Document commands, counts, MariaDB backend/version, migration leaves, replay decisions, and remaining baseline risk without PII.

```bash
git add docs/superpowers/reports/2026-08-02-instagram-reselection-verification.md
git commit -m "test(ig): verify intelligent product reselection"
```

### Task 13: Integrate, Push, Deploy, and Prove Production

**Current status (2026-08-03): OPEN.** Ни один из пяти branch-only code commits
не находится в `origin/main` или на production; server SHA остаётся `1380db8e`.

**Files:**
- No new source files unless final current-main conflicts require a scoped compatibility fix.

- [ ] **Step 1: Reconcile current main and dirty scope**

```bash
git fetch origin
git status --short
git log --oneline --decorate --graph -20
git diff --name-only origin/main...HEAD
```

Expected: only intended commits are ahead; unrelated UI files remain uncommitted and excluded.

- [ ] **Step 2: Integrate current `origin/main` without rewriting migrations**

Merge or rebase according to current repository policy, resolve only true overlapping IG-commerce conflicts, rerun Tasks 12.1-12.4 on the final unified HEAD, and verify migration leaf dependencies again.

- [ ] **Step 3: Push the approved unified HEAD to main**

Push only after local final verification. Confirm local `main`, `origin/main`, and the intended unified commit agree.

- [ ] **Step 4: Deploy in maintenance order**

On the production host: fast-forward pull, activate the configured virtualenv, apply migrations, run semantic/inventory readiness audit in dry-run first, apply only explicitly reviewed backfill inputs, collect static assets if CRM UI changed, run Django checks, and restart Passenger/application workers.

- [ ] **Step 5: Prove production without messaging real customers**

Verify server SHA equals `origin/main`, migration leaves are applied, MariaDB policies/links have expected coverage, the dedicated test account completes browse -> choice -> configure -> proposal, and read-only replay for `zainllw0w` produces the expected decisions with transports disabled. Do not send a test message to `zainllw0w` or any other real customer.

- [ ] **Step 6: Record final proof**

Report exact unified SHA, server SHA, applied migrations, test counts, readiness coverage, dedicated-account proposal ID, and any intentionally open catalog-review rows. Do not claim completion without this fresh evidence.
