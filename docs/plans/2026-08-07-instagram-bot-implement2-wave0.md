# Instagram Bot Implement2 Wave 0 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Establish a deterministic Python 3.14 dependency, deployment, no-network, and disposable MariaDB release gate before changing Instagram bot customer behavior.

**Architecture:** A stdlib lock verifier and a testable fail-closed `deploy.sh` protect the production release boundary. A cwd-independent baseline runner owns structural evidence, while a separate lifecycle-owning MariaDB runner provisions and destroys an isolated MariaDB 11.4 schema/user locally or in GitHub Actions.

**Tech Stack:** Bash, Python 3.14 stdlib, Django 5.2, pip hash-locked requirements, uv lock generation, MariaDB 11.4, GitHub Actions, unittest/Django TestCase.

---

## Execution Rules

- Work only in `/Users/zainllw0w/.config/superpowers/worktrees/site/instagram-bot-implement2`.
- Preserve the dirty root checkout and all historical IG worktrees.
- Apply strict RED -> verify RED -> minimal GREEN -> verify GREEN -> refactor.
- Dispatch one implementer at a time. After each task: spec review first, then code-quality review.
- Never write test rows to production MariaDB and never emit synthetic Meta, Gemini, Telegram, payment, or advertising events.
- Do not mark parent `IMP-094` complete until both P0.5A and P0.5B have actual release evidence.

### Task 1: Stabilize Serena schema and per-agent startup behavior

**Files:**
- Modify: `.serena/project.yml`
- Create: `.serena/.gitignore`
- Create: `tests/test_serena_project_contract.py`

**Step 1: Reproduce the old-schema failure**

Run before the edit:

```bash
serena start-mcp-server --project-from-cwd --context=codex
```

Expected: Serena 1.6.1 raises `KeyError: 'languages'` because the project uses the removed `language_servers` key.

**Step 2: Apply the configuration migration**

Rename only the key and its adjacent description:

```yaml
languages:
- python
- typescript
```

**Step 3: Verify the real MCP startup**

Keep Serena's per-agent STDIO isolation, but configure the local runtime outside
the repository with dashboard auto-open disabled at both levels:

```yaml
# ~/.serena/serena_config.yml
web_dashboard: true
web_dashboard_open_on_launch: false
```

```toml
# ~/.codex/config.toml
args = ["start-mcp-server", "--project-from-cwd", "--context=codex", "--open-web-dashboard=false"]
```

Migrate the same obsolete schema key in already registered local project
configs without reverting their unrelated dirty content. Run the server with
stdin closed and the explicit override, then run once in a PTY until both LSP
servers are ready. Stop only the manual probe process; do not kill
Codex-managed root/subagent STDIO instances.

Expected: all registered projects parse without `KeyError`; project `TwoComms`
activates; Python and TypeScript LSP initialize; MCP exports its tools; the
dashboard listens on loopback but no browser-open log/action occurs.

**Step 4: Commit**

```bash
git add .serena/project.yml .serena/.gitignore tests/test_serena_project_contract.py
git commit -m "chore(mcp): update Serena project schema"
```

### Task 2: Add the exact locked-requirements verifier

**Files:**
- Create: `scripts/verify_locked_requirements.py`
- Create: `tests/test_verify_locked_requirements.py`

**Step 1: Write parser RED tests**

Add tests proving that the verifier:

```python
def test_parses_multiline_hashed_lock_and_canonicalizes_names(): ...
def test_rejects_unpinned_recursive_vcs_and_conflicting_entries(): ...
```

The fixture must include `Django==5.2.11`, underscore/dot name variants,
continuation lines, hashes, a recursive `-r`, an unpinned requirement, and a VCS URL.

**Step 2: Verify RED**

```bash
python3 -m unittest tests.test_verify_locked_requirements -v
```

Expected: import failure because `scripts.verify_locked_requirements` does not exist.

**Step 3: Implement the minimal lock parser**

Use stdlib only:

```python
LOCKED_REQUIREMENT = re.compile(r"^([A-Za-z0-9_.-]+)==([^\\s;\\\\]+)")

def canonicalize_name(value):
    return re.sub(r"[-_.]+", "-", value).lower()
```

Reject recursive includes, editable/VCS/local references, unpinned entries, and conflicting duplicate canonical names. Ignore comments, blank lines, hash continuations, and environment markers only when the resolved lock still contains an exact version.

**Step 4: Verify parser GREEN**

Run the unittest command again.

Expected: parser tests pass.

**Step 5: Write installed-environment RED tests**

Add:

```python
def test_reports_missing_and_mismatched_distributions(): ...
def test_rejects_unexpected_distributions_outside_bootstrap_allowlist(): ...
def test_accepts_exact_versions_with_only_bootstrap_packaging_tools(): ...
def test_metadata_contains_python_version_lock_sha_and_requirement_count(): ...
def test_json_output_never_contains_environment_values(): ...
```

Patch `importlib.metadata.version`; do not create a real virtualenv in these unit tests.

**Step 6: Verify RED**

Expected: failures because environment comparison and JSON output are absent.

**Step 7: Implement environment verification**

Return non-zero on missing, mismatched, or unexpected installed distributions.
Allow only an explicit bootstrap allowlist (`pip`, `setuptools`, `wheel`) when
present in the fresh venv. Emit only:

```json
{
  "status": "ok|failed",
  "python": "3.14.x",
  "lock_sha256": "...",
  "requirement_count": 0,
  "missing": [],
  "mismatched": [],
  "unexpected": []
}
```

Never emit environment values or package installation URLs.

**Step 8: Verify GREEN and commit**

```bash
python3 -m unittest tests.test_verify_locked_requirements -v
git diff --check
git add scripts/verify_locked_requirements.py tests/test_verify_locked_requirements.py
git commit -m "test(deploy): verify locked runtime dependencies"
```

### Task 3: Produce a Python 3.14 production-platform lock

**Files:**
- Create: `twocomms/requirements.in`
- Create: `twocomms/requirements.lock`
- Modify: `twocomms/requirements.txt`
- Create: `scripts/compile_requirements.sh`
- Create: `tests/test_requirements_contract.py`
- Create: `twocomms/management/tests_dependency_runtime.py`

**Step 1: Write dependency-policy RED tests**

The source contract test must fail unless:

- every direct runtime package is exact-pinned in `requirements.in`;
- `google-analytics-data`, `google-auth`, and `openai` are pinned;
- `PyJWT==2.13.0` is a direct dependency because Google Indexing imports it;
- `cryptography==50.0.0` is the minimum accepted security-fixed version;
- `cffi` and `pycparser` are resolver-owned transitives, not stale direct pins;
- unused direct `pytz` is absent unless a production import site is documented;
- `requirements.txt` delegates only to `requirements.lock`;
- the lock contains hashes and every direct requirement.

Run:

```bash
python3 -m unittest tests.test_requirements_contract -v
```

Expected: RED because the files/policy do not exist.

**Step 2: Build the direct-dependency specification**

Start from current production-proven direct versions where they are newer than
the stale file, but verify every changed import surface. Pin
`google-analytics-data==0.22.0`, `google-auth==2.52.0`, and `openai==2.30.0`
for the first lock. Upgrade `cryptography` to `50.0.0` and add direct
`PyJWT==2.13.0`; both replace production versions with published advisories.
Let the resolver select `cffi==2.1.1` and `pycparser==3.0`. Do not perform
unrelated upgrades solely for freshness.

**Step 3: Generate the lock for the server compatibility floor**

Production is CPython 3.14.6, x86_64, glibc 2.28. Resolve against the matching
manylinux 2.28 floor:

```bash
./scripts/compile_requirements.sh
```

The script must require exact build-tool version `uv 0.12.2`, write to a
temporary file, and replace the lock only after successful resolution. Its
canonical command is:

```bash
uv pip compile twocomms/requirements.in \
  --output-file <temporary-lock> \
  --python-version 3.14.6 \
  --python-platform x86_64-manylinux_2_28 \
  --only-binary :all: \
  --generate-hashes \
  --resolution highest \
  --exclude-newer 2026-08-07T00:00:00Z \
  --no-emit-index-url \
  --custom-compile-command "./scripts/compile_requirements.sh"
```

Set `twocomms/requirements.txt` to:

```text
-r requirements.lock
```

**Step 4: Verify policy GREEN**

Run the source contract and verifier unit suites.

**Step 5: Verify a clean local Python 3.14 install**

Create a disposable venv outside the repository and run:

```bash
python3.14 -m venv <temp-venv>
<temp-venv>/bin/python -m pip install --require-hashes -r twocomms/requirements.lock
<temp-venv>/bin/python -m pip check
<temp-venv>/bin/python scripts/verify_locked_requirements.py --lock twocomms/requirements.lock
```

Then import Django, cffi, cryptography, Google Analytics/Auth, OpenAI, Facebook Business, and the project settings with a non-production `SECRET_KEY`.

Expected: install/imports succeed with no source build for cffi.

**Step 6: Verify the production compatibility floor**

Run the same wheel-only install, strict lock verification, security/import
contracts, and focused Django checks in an immutable x86_64 manylinux 2.28
container that provides CPython 3.14. Record the image digest, `ldd --version`,
Python version, lock digest, and installed wheel tags. A macOS venv or Ubuntu
24.04 runner does not satisfy this acceptance.

**Step 7: Write and run security/import runtime contracts**

Test real, no-network surfaces for Fernet/HKDF round trips, Monobank ECDSA
verification/signing primitives, PyJWT RS256 encode/decode, GA4/Auth imports,
OpenAI client construction, and Facebook Business imports. The tests must fail
if any required import is silently treated as optional.

**Step 8: Run focused application regressions**

```bash
<temp-venv>/bin/python twocomms/manage.py test \
  management.tests_test_settings_mariadb \
  management.tests_ig_production_contract \
  storefront.tests.test_external_analytics \
  storefront.tests.test_meta_pixel_configuration \
  --settings=test_settings --noinput
```

**Step 9: Commit**

```bash
git add twocomms/requirements.in twocomms/requirements.lock twocomms/requirements.txt \
  scripts/compile_requirements.sh tests/test_requirements_contract.py \
  twocomms/management/tests_dependency_runtime.py
git commit -m "build: lock Python 3.14 runtime dependencies"
```

### Task 4A: Stage and verify a release without mutating production

**Files:**
- Modify: `deploy.sh`
- Create: `scripts/deploy_release.py`
- Create: `tests/test_deploy_release.py`

`deploy.sh` is a thin wrapper that executes the stdlib orchestrator with the
CloudLinux system Python. The orchestrator accepts a target SHA plus path-only
test overrides; command names and arguments are fixed in code.

**Step 1: Write pre-switch RED tests**

Use temporary live/release/venv directories and an injected fake command
runner. Add one test per invariant:

```python
def test_dirty_live_checkout_is_rejected_before_fetch_or_stage(): ...
def test_target_must_be_origin_main_and_fast_forward_of_live_sha(): ...
def test_fresh_versioned_venv_is_created_at_final_immutable_path(): ...
def test_install_failure_leaves_live_checkout_venv_static_and_processes_untouched(): ...
def test_missing_or_mismatched_immutable_wheelhouse_fails_before_maintenance(): ...
def test_strict_lock_or_import_failure_leaves_live_state_untouched(): ...
def test_unapplied_migration_is_rejected_before_maintenance(): ...
def test_collectstatic_or_compress_failure_leaves_live_state_untouched(): ...
```

**Step 2: Verify RED**

```bash
python3 -m unittest tests.test_deploy_release.StagedReleaseTests -v
```

Expected: import failure because the orchestrator does not exist.

**Step 3: Implement the preparation phase**

The production defaults are:

```text
live app: /home/qlknpodo/TWC/TwoComms_Site/twocomms
active venv: /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.14
system Python: /opt/alt/python314/bin/python3.14
release root: /home/qlknpodo/TWC/TwoComms_Site/releases
CloudLinux app root: TWC/TwoComms_Site/twocomms
```

Before any maintenance/process mutation:

1. acquire a non-blocking deployment `flock`;
2. require a clean live tracked tree and exact known branch;
3. `git fetch origin main` and require the target to equal `origin/main` and be
   a fast-forward descendant of the live SHA;
4. create an isolated git worktree for the target SHA;
5. create a fresh versioned venv at its final immutable path,
   `/home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/releases/venvs/<sha>`,
   with `/opt/alt/python314/bin/python3.14 -m venv`; never rename a venv after
   creation because its entry-point shebangs are absolute;
6. require the CI-produced wheelhouse and its SHA256 manifest for the target
   SHA, then install wheel-only with
   `pip install --no-index --find-links <verified-wheelhouse> --require-hashes`;
   run `pip check`, strict lock verification against the reviewed lock digest,
   runtime import/security contracts, no-network baseline, and Django deploy
   check. This phase never regenerates or downloads a new dependency
   resolution;
7. run `migrate --check`; Wave 0 fails if any migration is unapplied;
8. build `collectstatic` and `compress --force` inside the staged worktree and
   validate a non-empty current manifest plus a representative compressed-page
   render in a new process.

Use `DJANGO_ENV_FILE` only as a path to the existing production environment;
never copy, parse into logs, or emit its contents.

**Step 4: Verify GREEN and commit preparation**

```bash
python3 -m unittest tests.test_deploy_release.StagedReleaseTests -v
bash -n deploy.sh
git diff --check
git add deploy.sh scripts/deploy_release.py tests/test_deploy_release.py
git commit -m "fix(deploy): stage verified release environments"
```

### Task 4B: Add atomic switch, rollback, and production evidence

**Files:**
- Modify: `scripts/deploy_release.py`
- Modify: `tests/test_deploy_release.py`

**Step 1: Write switch/rollback RED tests**

```python
def test_switch_enters_bot_maintenance_before_stopping_passenger(): ...
def test_switch_order_is_stop_fast_forward_swap_venv_swap_static_start(): ...
def test_venv_and_static_switches_retain_previous_release_for_rollback(): ...
def test_start_or_health_failure_restores_previous_sha_venv_and_static(): ...
def test_success_releases_owned_maintenance_and_ensures_current_daemon(): ...
def test_failure_does_not_release_an_unowned_maintenance_lease(): ...
def test_stop_failure_releases_owned_maintenance_and_restores_old_app(): ...
def test_fast_forward_failure_releases_owned_maintenance_and_restores_old_app(): ...
def test_first_switch_converts_real_venv_directory_to_retained_target_and_symlink(): ...
def test_first_switch_converts_real_static_directory_to_retained_target_and_symlink(): ...
def test_failed_first_switch_restores_original_real_directories(): ...
def test_evidence_is_mode_0600_and_contains_no_environment_or_credentials(): ...
def test_concurrent_deploy_is_rejected_by_flock(): ...
```

**Step 2: Implement the bounded switch**

After every preparation gate is green:

1. activate an owned bounded `run_instagram_bot --maintenance-on` lease and
   wait for the daemon singleton lock to clear;
2. stop Passenger through `cloudlinux-selector stop --interpreter python`;
3. fast-forward the live checkout to the verified target;
4. atomically replace the stable cPanel venv and static symlinks with the
   already-verified versioned release directories, retaining the previous
   symlink targets for rollback;
5. start Passenger, release only the owned maintenance lease, and run
   `run_instagram_bot --ensure` with the new interpreter;
6. verify exact SHA, venv Python/lock, Django check, compressor manifest,
   representative HTTP health, daemon code/heartbeat, and dangerous queues.

Before any database-bearing future slice, require a separate migration manifest
with backup and expand/contract/rollback proof. The default orchestrator never
applies an unapplied migration.

On any failure after maintenance acquisition, including Passenger stop,
fast-forward, symlink switch, static collection/compression, start, or health,
release the owned lease and restore the prior app/daemon state. On a
post-switch failure, stop the partial app, restore the retained branch
SHA/tracked tree, venv, and static root, restart the previous app/daemon, and
record both the original failure and rollback result. Never delete retained
releases during the same deploy. A cleanup failure is independently fatal and
must never be hidden by the original exception.

The first switch uses `lstat`, not `exists`, to distinguish real directories
from symlinks. While Passenger and the daemon are stopped, move the current
real venv/static directories to retained immutable paths, create stable
symlinks through temporary names plus `os.replace`, and only then point those
symlinks at the new release. If conversion or the later switch fails, restore
the original real directories or prior symlink targets before restarting the
old runtime.

For the first bootstrap, fetch the target SHA and create an isolated server
worktree, then run that worktree's orchestrator with the system Python. Do not
fast-forward the live checkout or start the app before the orchestrator's
pre-switch gates are green; the maintenance/Passenger transition is owned by
the orchestrator itself.

**Step 3: Verify GREEN and adjacent suites**

```bash
python3 -m unittest tests.test_deploy_release -v
python3 -m unittest tests.test_backup_mysql_script tests.test_install_nova_poshta_tracking_cron -v
bash -n deploy.sh
git diff --check
```

**Step 4: Commit**

```bash
git add scripts/deploy_release.py tests/test_deploy_release.py
git commit -m "fix(deploy): switch releases with bounded rollback"
```

### Task 4C: Close legacy deploy entry-point bypasses

**Files:**
- Create: `tests/test_deploy_entrypoint_contract.py`
- Modify or archive: `deploy_finance.sh`, `deploy_fixes.sh`,
  `deploy_optimizations.sh`, `deploy_promo_system.sh`, `deploy_redis.sh`,
  `scripts/deploy_finance.sh`, `infra/deploy_management_stats_placeholder.sh`,
  and any active operator wrapper discovered by the server inventory
- Modify: `docs/instagram_bot_audit/10_OPEN_QUESTIONS_AND_BLOCKERS.md`

**Step 1: Record the server usage boundary (read-only)**

Capture `crontab -l`, tracked script paths, and repository/operator references
on the production host. Do not inspect or alter secrets. The current cron
inventory runs management reconciliation commands and does not reference the
legacy deploy scripts; this evidence must be rechecked immediately before
retiring any entry point.

**Step 2: Write source-contract RED tests**

The contract must fail if a tracked deploy entry point contains or invokes an
alternate destructive path: the retired server IP, `git reset --hard`, runtime
`makemigrations`, direct production SCP overlay, in-place `pip install`, or an
unbounded restart. It must require every supported entry point to delegate to
the canonical staged orchestrator with an explicit target SHA.

**Step 3: Redirect or retire with evidence**

Active operator paths delegate to `deploy.sh`/`scripts/deploy_release.py` and
pass a target SHA. Inactive scripts are moved to a clearly named archive or
removed only after the read-only usage proof. No script may silently retain the
old IP, Python 3.13, destructive reset, runtime migration generation, or
password-based SCP.

**Step 4: Verify and commit**

```bash
python3 -m unittest tests.test_deploy_entrypoint_contract -v
git diff --check
git add -A -- deploy_finance.sh deploy_fixes.sh deploy_optimizations.sh \
  deploy_promo_system.sh deploy_redis.sh scripts/deploy_finance.sh \
  infra/deploy_management_stats_placeholder.sh \
  tests/test_deploy_entrypoint_contract.py \
  docs/instagram_bot_audit/10_OPEN_QUESTIONS_AND_BLOCKERS.md
git commit -m "fix(deploy): retire legacy release bypasses"
```

### Task 5A: Add the cwd-independent no-network baseline runner

**Files:**
- Create: `scripts/run_ig_baseline.py`
- Create: `twocomms/test_settings_no_network.py`
- Create: `tests/test_ig_baseline_runner.py`

**Step 1: Write runner RED tests**

Add subprocess tests proving:

```python
def test_runner_resolves_repo_from_its_file_from_two_cwds(): ...
def test_runner_supplies_only_a_nonproduction_structural_secret(): ...
def test_runner_rejects_unmocked_external_network(): ...
def test_runner_emits_sanitized_machine_readable_evidence(): ...
def test_runner_propagates_the_first_failed_gate(): ...
```

Use a fake Python executable for orchestration tests. The network-profile test
must attempt an external socket without mocks and fail before transmitting.

**Step 2: Verify RED**

```bash
python3 -m unittest tests.test_ig_baseline_runner -v
```

Expected: runner/settings modules do not exist.

**Step 3: Implement the network-denied profile**

Derive from `test_settings`. Deny external socket connections while allowing
loopback/Unix sockets required by isolated test infrastructure. Keep all
Telegram/provider credentials empty.

**Step 4: Implement the baseline runner**

Resolve Git root and Django app from `__file__`. Accept only a Python path and
evidence-output override. Run:

```bash
python twocomms/manage.py test \
  management.tests_test_settings_mariadb \
  management.tests_ig_production_contract \
  management.tests_ig_engine_health \
  management.tests_ig_webhook_security \
  management.tests_ig_live_reply_priority \
  management.tests_ig_conversation_analysis_jobs \
  management.tests_ig_followup_delivery_fsm \
  management.tests_telephony_call.AdminCallReviewTest \
  --settings=test_settings_no_network --noinput
python twocomms/manage.py check --settings=test_settings_no_network
python twocomms/manage.py makemigrations --check --dry-run \
  --settings=test_settings_no_network
python -m compileall -q twocomms/management
git diff --check
```

Evidence includes cwd, repo SHA, interpreter, settings, SQLite engine,
commands, counts/failures/skips, and network policy; never secrets.

**Step 5: Verify GREEN from two directories**

Run unit tests, then run the real runner once from the repository root and once
from `/tmp` using the project venv Python.

**Step 6: Commit**

```bash
git add scripts/run_ig_baseline.py twocomms/test_settings_no_network.py tests/test_ig_baseline_runner.py
git commit -m "test(ig): add deterministic no-network baseline gate"
```

### Task 5B: Root-cause the telephony order flake and prove suite stability

**Files:**
- Modify: `twocomms/management/tests_telephony_call.py`
- Modify if the reproduced data flow proves it necessary:
  `twocomms/management/services/call_review.py`

**Step 1: Reproduce before proposing a fix**

Run the isolated class repeatedly, then use Django's reverse/order controls and
the smallest surrounding modules needed to trigger
`AdminCallReviewTest.test_ack_state_reflected`. Capture the first failing
assertion, database rows, queryset ordering, cache/global state, and the test
that precedes the failure. Do not change code until one root-cause hypothesis
is reproduced.

**Step 2: Write a deterministic RED regression**

Add the minimal order/state sequence that fails for the confirmed reason. The
test must fail repeatedly before the fix, not by arbitrary sleeps or retries.

**Step 3: Implement one root-cause fix and verify focused GREEN**

Run the new regression, the entire `AdminCallReviewTest`, and the complete
`management.tests_telephony_call` module under the no-network profile.

**Step 4: Run three fresh full management suites**

```bash
python twocomms/manage.py test management --settings=test_settings_no_network --noinput
(cd twocomms && python manage.py test management --settings=test_settings_no_network --noinput)
python twocomms/manage.py test management --settings=test_settings_no_network --noinput
```

All three runs must record command, cwd, test count, skips, failures, duration,
SQLite engine, and network policy. A retry after an unexplained red does not
count toward the three-run acceptance.

**Step 5: Commit**

```bash
git add twocomms/management/tests_telephony_call.py \
  twocomms/management/services/call_review.py
git commit -m "test(management): remove telephony review order flake"
```

### Task 6A: Add the disposable MariaDB 11.4 lifecycle gate

**Files:**
- Create: `scripts/run_mariadb_gate.py`
- Create: `tests/test_mariadb_gate_runner.py`
- Create: `twocomms/management/tests_ig_mariadb_lifecycle.py`
- Modify: `twocomms/test_settings_mariadb.py`
- Modify: `twocomms/management/tests_test_settings_mariadb.py`

**Step 1: Write settings-guard RED tests**

Extend the current contract with:

```python
def test_rejects_non_loopback_host_without_explicit_remote_opt_in(): ...
def test_rejects_a_test_user_matching_configured_production_users(): ...
```

Expected: RED because the current profile validates names/hosts but not remote
opt-in or production-user identity.

**Step 2: Implement minimal settings guards and verify GREEN**

Permit a remote host only with explicit `TEST_MARIADB_REMOTE_ALLOWED=1`. Reject
`TEST_MARIADB_USER` equal to configured `DB_USER` or `DB_USER_DTF`.

**Step 3: Write lifecycle-runner RED tests**

Use fake MariaDB admin/client and fake Django commands to prove:

- managed schema/user names are generated, not externally injected;
- production/provider env is scrubbed from children;
- migration/test failure still drops schema and user;
- cleanup failure makes the gate red without hiding the original failure;
- generated passwords never appear in logs/evidence;
- execution is cwd independent.

**Step 4: Implement the lifecycle runner**

Support:

```text
--server-mode native
--server-mode external
```

External CI mode connects to a job-scoped root service. Native mode owns a
temporary data directory and loopback port. The runner creates an isolated
`test_twocomms_ig_<run-id>` schema and non-root user, grants only that schema,
runs migrations plus `management.tests_ig_mariadb_lifecycle` with `--keepdb`,
and drops user/schema in `finally`. This first slice proves lifecycle only;
Task 6F changes the final default to the full mandatory suite after all of its
modules exist.

**Step 5: Verify unit GREEN**

```bash
python3 -m unittest tests.test_mariadb_gate_runner -v
cd twocomms
python manage.py test management.tests_test_settings_mariadb --settings=test_settings --noinput
```

**Step 6: Run a lifecycle smoke against real disposable MariaDB**

```bash
python3.14 scripts/run_mariadb_gate.py --server-mode native --suite lifecycle
```

If the local binary is unavailable, the CI service-container run is the required
acceptance proof; do not substitute production MariaDB.

**Step 7: Commit**

```bash
git add scripts/run_mariadb_gate.py tests/test_mariadb_gate_runner.py \
  twocomms/management/tests_ig_mariadb_lifecycle.py \
  twocomms/test_settings_mariadb.py \
  twocomms/management/tests_test_settings_mariadb.py
git commit -m "test(ig): provision disposable MariaDB release gate"
```

### Task 6B: Prove MariaDB engine, schema, migration, and trigger contracts

**Files:**
- Create: `twocomms/management/tests_ig_mariadb_contract.py`

**Step 1: Write one RED test per DDL invariant**

```python
def test_server_schema_user_sql_mode_charset_collation_and_engine(): ...
def test_migration_graph_is_fully_applied_and_critical_ig_tables_are_innodb(): ...
def test_required_append_only_triggers_exist(): ...
def test_each_append_only_trigger_rejects_raw_mutation(): ...
```

Cover trigger-owning migrations `0090`, `0103`, `0116`, `0119`, and `0146`.
Read-only confirm the production database collation before hard-coding the
assertion (`utf8mb4_unicode_ci` on the current MariaDB database; do not assert
the unrelated server default `latin1_swedish_ci`).

**Step 2: Run RED, implement only test helpers, and run GREEN**

The production schema/code is already expected to satisfy these contracts; if
a test exposes a real defect, stop and fix that defect in its own RED/GREEN
commit instead of weakening the assertion.

**Step 3: Commit**

```bash
git add twocomms/management/tests_ig_mariadb_contract.py
git commit -m "test(ig): verify MariaDB schema and trigger contracts"
```

### Task 6C: Prove MariaDB length, Unicode JSON, and nullable uniqueness

**Files:**
- Modify: `twocomms/management/tests_ig_mariadb_contract.py`

**Step 1: Write separate RED tests**

```python
def test_quick_reply_payload_accepts_1000_and_rejects_1001_without_truncation(): ...
def test_json_round_trip_preserves_ukrainian_russian_and_emoji(): ...
def test_nullable_unique_open_slot_allows_nulls_but_only_one_active_value(): ...
```

**Step 2: Verify RED/GREEN on MariaDB and commit**

Do not simulate `DataError` or uniqueness with mocks.

```bash
git add twocomms/management/tests_ig_mariadb_contract.py
git commit -m "test(ig): verify MariaDB value constraints"
```

### Task 6D: Prove current MariaDB concurrency and named-lock contracts

**Files:**
- Modify: `twocomms/management/tests_ig_mariadb_contract.py`

**Step 1: Write one deterministic RED race per owned invariant**

```python
def test_concurrent_checkout_replacement_has_one_winner(): ...
def test_concurrent_due_job_claim_has_one_lease_owner_and_attempt(): ...
def test_paylink_named_lock_serializes_connections_and_releases_on_error(): ...
def test_commercial_episode_named_lock_serializes_and_releases_on_error(): ...
```

Use barriers/events and separate DB connections; no sleeps as correctness
signals. Preserve the first exception and include deadlock/retry evidence.

**Step 2: Verify RED/GREEN on MariaDB and commit**

```bash
git add twocomms/management/tests_ig_mariadb_contract.py
git commit -m "test(ig): verify MariaDB race and lock contracts"
```

### Task 6E: Extract an always-rollback fixture contract without weakening production guards

**Files:**
- Create: `twocomms/management/services/ig_contract_fixtures.py`
- Create: `twocomms/management/tests_ig_contract_fixtures.py`
- Modify: `twocomms/management/management/commands/verify_ig_production_contract.py`
- Modify: `twocomms/management/tests_ig_production_contract.py`
- Modify: `twocomms/management/tests_ig_mariadb_contract.py`

**Step 1: Write RED safety tests**

Prove the reusable fixture always marks its outer transaction for rollback,
leaves no rows, does not advance the owned notification `AUTO_INCREMENT`, and
performs no network. Separately prove the production command still rejects
SQLite, every `test_*` database, database identity mismatch, and missing
maintenance lease.

**Step 2: Extract the fixture implementation**

The reusable service owns only fixture creation/mocked delivery/rollback. It
has no flag that disables rollback or production authorization. The management
command retains `_assert_production_database` and maintenance checks, then
calls the reusable contract. The disposable MariaDB test calls the contract
directly inside its test schema; it never invokes the production command.

**Step 3: Verify focused SQLite and MariaDB GREEN, then commit**

```bash
git add twocomms/management/services/ig_contract_fixtures.py \
  twocomms/management/tests_ig_contract_fixtures.py \
  twocomms/management/management/commands/verify_ig_production_contract.py \
  twocomms/management/tests_ig_production_contract.py \
  twocomms/management/tests_ig_mariadb_contract.py
git commit -m "refactor(ig): share rollback-only contract fixtures"
```

### Task 6F: Lock the final mandatory MariaDB suite

**Files:**
- Modify: `scripts/run_mariadb_gate.py`
- Modify: `tests/test_mariadb_gate_runner.py`

**Step 1: Write default-suite RED tests**

Require the runner's no-argument/default test selection to invoke every label
below exactly once and reject an empty or lifecycle-only selection in release
mode:

```text
management.tests_ig_mariadb_lifecycle
management.tests_ig_mariadb_contract
management.tests_ig_contract_fixtures
management.tests_ig_checkout_models
management.tests_ig_commerce_state
management.tests_ig_engine_health
management.tests_ig_payment_review_truth
management.tests_ig_order_assignments
management.tests_ig_notifications
management.tests_ig_conversation_analysis_jobs
management.tests_ig_followup_delivery_fsm
management.tests_ig_inbox_refresh
management.tests_ig_production_contract
```

Keep an explicit developer-only `--suite lifecycle` diagnostic mode, but the
CI/release path must use the default full suite and record all labels in
evidence.

**Step 2: Implement the full default and run the real gate**

```bash
python3 -m unittest tests.test_mariadb_gate_runner -v
python3.14 scripts/run_mariadb_gate.py --server-mode native
```

The real run must report MariaDB 11.4, every mandatory label, test counts, and
verified schema/user cleanup. If native MariaDB is unavailable, the pinned CI
service-container run is the acceptance proof.

**Step 3: Commit**

```bash
git add scripts/run_mariadb_gate.py tests/test_mariadb_gate_runner.py
git commit -m "test(ig): lock full MariaDB release suite"
```

### Task 7: Add and prove the GitHub Actions Wave 0 gates

**Files:**
- Create: `.github/workflows/instagram-bot-wave0-gates.yml`
- Create: `tests/test_wave0_workflow_contract.py`

**Step 1: Write workflow-source RED tests**

Require:

- `ubuntu-24.04`, Python 3.14, `permissions: contents: read`;
- dependency/no-network job regenerates the lock through exact `uv 0.12.2`,
  requires `git diff --exit-code`, and installs with hashes;
- dependency job downloads/builds a wheel-only wheelhouse, writes a sorted
  SHA256 manifest keyed by the target SHA, and uploads the immutable artifact;
- a separate immutable x86_64 manylinux 2.28 container job uses CPython 3.14
  for wheel-only install, strict lock, import, and focused Django proof;
- MariaDB service is pinned to MariaDB 11.4 by immutable digest;
- MariaDB runner source explicitly passes the full mandatory suite listed in
  Task 6A, including `management.tests_ig_mariadb_contract` and
  `management.tests_ig_contract_fixtures`;
- the CI test job executes `tests.test_deploy_entrypoint_contract` and
  `tests.test_serena_project_contract`;
- health check, 30-minute timeout, and no production credentials;
- sanitized evidence upload with `if: always()`;
- push/PR path filters cover requirements, deploy, runners, tests, workflow,
  migrations, and management code.

**Step 2: Verify RED**

```bash
python3 -m unittest tests.test_wave0_workflow_contract -v
```

Expected: workflow does not exist.

**Step 3: Implement the workflow and verify source GREEN**

Use a job-scoped MariaDB root password only. The lifecycle runner creates and
destroys the application test schema/user. Do not use repository production secrets.

Pin the service image exactly:

```text
mariadb:11.4.12@sha256:67873d30a17f6a9c331f06363b2fa15f38abca415529966d67c84f87f82439fe
```

Pin the production-matching image exactly:

```text
quay.io/pypa/manylinux_2_28_x86_64@sha256:fdb9a9c223b215604dc7b6f7e8fff4b39bfea5fbaa7777a2e5544a60dfa437f8
```

The immutable image is dated `2026.07.25-1` and provides
`/opt/python/cp314-cp314` as CPython 3.14.6. CI must assert linux/amd64,
`glibc 2.28`, Python 3.14.6, and cp314 SOABI before downloading a wheelhouse,
then install from that wheelhouse with `--no-index --require-hashes`. Record
the image digest, glibc, Python, pip, wheel tags, and lock versions in sanitized
evidence. A current 3.14.7 image may run only as a non-blocking forward smoke.

**Step 4: Commit and push the branch**

```bash
git add .github/workflows/instagram-bot-wave0-gates.yml tests/test_wave0_workflow_contract.py
git commit -m "ci(ig): run Python and MariaDB Wave 0 gates"
git push -u origin codex/instagram-bot-implement2
```

**Step 5: Verify the actual workflow**

Use `gh run list` and `gh run watch --exit-status`. Record the run URL, exact
commit SHA, job conclusions, test counts, MariaDB version, and cleanup evidence.

Fix any failure with a new RED test before changing implementation.

### Task 8: Review and release P0.5A/P0.5B

**Files:**
- Modify: `docs/instagram_bot_audit/00_PROGRESS.md`
- Modify: relevant sections of `03_FINDINGS_REGISTER.md`
- Modify: `06_TEST_MATRIX.md`
- Modify: `07_IMPLEMENTATION_PLAN.md`
- Modify: `08_COMPLETION_LOG.md`
- Modify: `09_DEPLOYMENT_LOG.md`
- Modify: `10_OPEN_QUESTIONS_AND_BLOCKERS.md`
- Modify: `12_SOURCE_RECONCILIATION.md`
- Modify: `13_UNCLOSED_FINDINGS_RAW.md`
- Modify: `14_IMPLEMENT2.md`

**Step 1: Run the full Wave 0 verification matrix**

```bash
python3 -m unittest \
  tests.test_verify_locked_requirements \
  tests.test_requirements_contract \
  tests.test_deploy_release \
  tests.test_deploy_entrypoint_contract \
  tests.test_ig_baseline_runner \
  tests.test_mariadb_gate_runner \
  tests.test_wave0_workflow_contract \
  tests.test_serena_project_contract -v
python3 scripts/run_ig_baseline.py
bash -n deploy.sh
cd twocomms
python manage.py check --settings=test_settings
SECRET_KEY=p0-5-structural-only python manage.py makemigrations --check --dry-run
python -m compileall -q management
cd ..
git diff --check
```

Required external evidence: green GitHub dependency and MariaDB jobs.

**Step 2: Dispatch final spec and code-quality reviews**

Review the entire diff against the Wave 0 design and this plan. Resolve every
finding and repeat the relevant verification.

**Step 3: Commit pre-release findings without completion marks**

Update technical evidence, commands, CI URLs, and newly found risks, but keep
`IMP-094.A`, the MariaDB sub-slice, and parent `IMP-094` unchecked/PARTIAL until
production deploy and exact-SHA proof exist.

Record the two newly confirmed operational debts without broadening Wave 0:

- 18 terminal failed CRM analysis jobs;
- missing `GEMINI_KEY_PROJECT_GROUPS` mapping.

Also record the release-boundary findings discovered during Wave 0:

- production `cryptography 46.0.6` and `PyJWT 2.12.1` carry published
  advisories and must not be copied into the new lock;
- tracked legacy `deploy*.sh` entry points can bypass the canonical gate and
  must be inventoried against server cron/operator usage, then delegate to the
  canonical script or be retired in a separate evidence-backed cleanup slice.
- Serena 1.6.1 opened one dashboard tab per agent because
  `web_dashboard_open_on_launch` was enabled; record the corrected per-agent
  STDIO isolation with dashboard auto-open disabled and all registered project
  schemas migrated.

```bash
git add docs/instagram_bot_audit
git commit -m "docs(ig): prepare Wave 0 release evidence"
```

**Step 4: Integrate reviewed code to main**

Fetch `origin/main`, verify no divergence, fast-forward local `main` to the
reviewed branch, and push `origin/main`.

Do not discard root WIP. First fetch and incorporate the current
`origin/main` into this clean release worktree. Then snapshot the complete
dirty root with a named `git -C /Users/zainllw0w/TwoComms/site stash push -u`,
verify that root checkout is clean, and run the actual ref update in the
worktree that checks out `main`:

```bash
git -C /Users/zainllw0w/TwoComms/site merge --ff-only <reviewed-sha>
```

Re-apply the named stash and retain it until the restored root status and full
diff are verified; if reapply conflicts, stop with the stash intact rather
than resolving unrelated WIP. Finally verify `git -C ... rev-parse HEAD` and
`git rev-parse origin/main` are identical before pushing.

**Step 5: Deploy the exact target through the staged orchestrator**

On the server, do not `git pull` the live checkout before preparation. Fetch the
pushed target SHA, create an isolated server worktree, and run its orchestrator
with the system Python. The first Wave 0 bootstrap must enable maintenance and
stop Passenger only from inside that orchestrator; it must not fast-forward or
start the live app before the staged venv/static and all pre-switch checks are
green.

**Step 6: Verify production before marking anything complete**

Confirm:

- exact runtime/server SHA equals the pushed release SHA;
- the active venv is the fresh staged environment and strict lock/extras proof
  passes;
- Wave 0 applied no migration and migration state remains clean;
- static/compressor manifest and representative page render are current;
- Passenger HTTP health, bot daemon code/heartbeat, and webhook health are fresh;
- inbound/reply/notification queues have no dangerous backlog;
- analysis failed count is recorded, not silently cleared;
- no synthetic customer/provider/payment events were emitted;
- retained previous SHA/venv/static rollback artifacts and evidence exist.

**Step 7: Write the post-deploy completion evidence**

Only now mark `IMP-094.A` complete if the three full suite runs and release
evidence are present. Mark the MariaDB sub-slice complete only with an actual
MariaDB 11.4 run and cleanup proof. Keep parent `IMP-094` partial if any named
residue remains.

```bash
git add docs/instagram_bot_audit
git commit -m "docs(ig): record deployed Implement2 Wave 0 evidence"
git push origin main
```

Fast-forward the server checkout for this docs-only commit without restarting
the application, then verify final server `HEAD == origin/main`. The runtime
evidence continues to cite the prior deployed code SHA and the docs commit cites
both SHAs explicitly.

**Step 8: Start W1.1**

After production proof, create the W1.1 design/plan for bounded webhook reply-
permission transitions (`F-CORE-004` / `IMP-098.A`) and repeat the same
Superpowers/TDD/review/release protocol.
