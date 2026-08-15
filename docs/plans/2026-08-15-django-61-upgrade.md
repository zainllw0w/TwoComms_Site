# Django 6.1 Upgrade Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Upgrade the TwoComms application from Django 5.2.11 to Django 6.1 with no intentional business-behavior changes and with verified local and production runtime compatibility.

**Architecture:** Keep the existing Django/Passenger/MariaDB architecture unchanged. Update the exact-pinned direct dependency and regenerate the reproducible Python 3.14 lock; only add source changes when a failing compatibility test proves they are needed. Deploy the reviewed Git SHA and lock to production, then verify the live runtime before declaring the release complete.

**Tech Stack:** Django 6.1, Python 3.14, uv 0.12.2, hash-locked pip requirements, Django `manage.py` tests/checks, MariaDB production, Passenger.

---

### Task 1: Establish a clean Django 5.2 baseline

**Files:**
- Read: `twocomms/requirements.in`
- Read: `twocomms/requirements.lock`
- Read: `tests/test_requirements_contract.py`
- Read: `docs/plans/2026-08-15-django-61-upgrade-design.md`

**Step 1: Verify branch and worktree baseline**

Run:

~~~bash
git status --short --branch
git rev-parse HEAD origin/main
~~~

Expected: only the committed design document is present; the branch starts at the current `origin/main` plus that design commit.

**Step 2: Verify the current runtime and lock**

Run:

~~~bash
python3.14 --version
rg -n '^Django==|^django==' twocomms/requirements.in twocomms/requirements.lock
~~~

Expected: Python 3.14 is available and both requirement files report Django 5.2.11.

**Step 3: Run the dependency contract tests before changing the pin**

Run:

~~~bash
python3 -m unittest tests.test_requirements_contract tests.test_verify_locked_requirements -v
~~~

Expected: PASS on the unchanged 5.2.11 contract. Any pre-existing failure is recorded and investigated before the upgrade.

**Step 4: Capture deprecation warnings on the current version**

Run from `twocomms/` with a test-only secret:

~~~bash
SECRET_KEY=codex-django-upgrade-test python3.14 -Wa manage.py test --settings=test_settings --noinput
~~~

Expected: the current suite completes; every deprecation warning is captured for comparison with the 6.1 run.

---

### Task 2: Update the direct Django pin and reproducible lock

**Files:**
- Modify: `twocomms/requirements.in`
- Modify: `twocomms/requirements.lock`
- Modify: `tests/test_requirements_contract.py`

**Step 1: Write the contract expectation for Django 6.1**

Update the `EXPECTED_DIRECT` value in `tests/test_requirements_contract.py` from `5.2.11` to `6.1`. Do not change parser fixtures that intentionally exercise arbitrary version strings.

**Step 2: Run the contract test to verify the expected red state**

Run:

~~~bash
python3 -m unittest tests.test_requirements_contract.RequirementsContractTests.test_direct_runtime_requirements_are_exactly_pinned -v
~~~

Expected: FAIL because `requirements.in` still pins 5.2.11. This confirms the test detects the requested upgrade.

**Step 3: Update the framework-coupled direct pins**

Change `Django==5.2.11` to `Django==6.1` and move
`djangorestframework==3.15.2` to `djangorestframework==3.18.0` in
`twocomms/requirements.in`. The DRF change is required, not opportunistic:
DRF 3.15.2 imports the removed Django 6.1 symbol `django.utils.cache.cc_delim_re`
and fails before the application can start; DRF 3.18.0 is the first supported
release for Django 6.1.

**Step 4: Compile the lock with the repository toolchain**

Install or invoke the exact `uv 0.12.2` binary and run:

~~~bash
UV_BIN=/path/to/uv-0.12.2 PYTHON_BIN=python3.14 ./scripts/compile_requirements.sh
~~~

Expected: the script exits 0, atomically replaces `twocomms/requirements.lock`, and includes a single hashed `django==6.1` entry. Resolver-owned dependencies may move only when required by the new framework and the lock remains reproducible.

**Step 5: Verify the contract turns green**

Run:

~~~bash
python3 -m unittest tests.test_requirements_contract tests.test_verify_locked_requirements -v
git diff --check
~~~

Expected: all tests pass, the lock contains hashes for every exact requirement, and there is no whitespace error.

---

### Task 3: Build a clean Python 3.14 Django 6.1 environment

**Files:**
- Read: `twocomms/requirements.lock`
- Read: `scripts/verify_locked_requirements.py`

**Step 1: Create an isolated test environment outside the repository**

Run:

~~~bash
python3.14 -m venv /tmp/twocomms-django-61-venv
/tmp/twocomms-django-61-venv/bin/python -m pip install --upgrade pip
~~~

Expected: a clean Python 3.14 environment is created without changing tracked files.

**Step 2: Install the committed lock with hashes**

Run:

~~~bash
/tmp/twocomms-django-61-venv/bin/python -m pip install --require-hashes -r twocomms/requirements.lock
~~~

Expected: installation succeeds without resolver conflicts.

**Step 3: Verify the environment contract**

Run:

~~~bash
/tmp/twocomms-django-61-venv/bin/python scripts/verify_locked_requirements.py --lock twocomms/requirements.lock
/tmp/twocomms-django-61-venv/bin/python -m pip check
/tmp/twocomms-django-61-venv/bin/python -m django --version
~~~

Expected: the verifier and `pip check` exit 0 and Django reports `6.1`.

---

### Task 4: Run compatibility checks and fix only proven breakage

**Files:**
- Modify: only files named by a failing compatibility test
- Test: add or update a focused regression test beside every source fix

**Step 1: Run Django system and migration checks**

From `twocomms/`, run:

~~~bash
SECRET_KEY=codex-django-upgrade-test /tmp/twocomms-django-61-venv/bin/python manage.py check --settings=test_settings
SECRET_KEY=codex-django-upgrade-test /tmp/twocomms-django-61-venv/bin/python manage.py check --deploy --settings=test_settings
SECRET_KEY=codex-django-upgrade-test /tmp/twocomms-django-61-venv/bin/python manage.py makemigrations --check --dry-run --settings=test_settings
~~~

Expected: all commands exit 0 and no migration files are generated.

**Step 2: Run the full Django suite with warnings enabled**

Run:

~~~bash
SECRET_KEY=codex-django-upgrade-test /tmp/twocomms-django-61-venv/bin/python -Wa manage.py test --settings=test_settings --noinput
~~~

Expected: all available tests pass. Compare warnings against the Task 1 baseline and resolve warnings introduced by the upgrade. Django 6.1's `RemovedInDjango70Warning` items (including email settings, `fail_silently`, and third-party `list_select_related`) are tracked separately unless they block current behavior.

**Step 3: Run Python compilation and repository contract tests**

Run:

~~~bash
/tmp/twocomms-django-61-venv/bin/python -m compileall -q twocomms scripts tests
/tmp/twocomms-django-61-venv/bin/python -m unittest tests.test_requirements_contract tests.test_verify_locked_requirements -v
~~~

Expected: no syntax errors and all contract tests pass.

**Step 4: For each real incompatibility, add a failing regression test first**

Run the smallest affected test and confirm it fails for the Django 6.1 incompatibility. Implement the smallest compatible change, rerun the focused test, then rerun the full suite. Do not introduce fetch modes, database-level `on_delete`, `MAILERS`, ORM rewrites, or unrelated refactors in this task.

---

### Task 5: Verify static/compressor and release artifacts

**Files:**
- Read: `twocomms/twocomms/settings.py`
- Read: `twocomms/twocomms_django_theme/`

**Step 1: Collect static files into the ignored project output**

`twocomms.settings` currently fixes `STATIC_ROOT` to
`twocomms/staticfiles`; it does not honor an environment override. The
directory is ignored by Git, so run the collection there and confirm the
release diff remains clean afterwards:

~~~bash
SECRET_KEY=codex-django-upgrade-test /tmp/twocomms-django-61-venv/bin/python manage.py collectstatic --noinput --settings=test_settings
~~~

Expected: collection completes and the manifest is valid.

**Step 2: Rebuild offline compression in that test environment**

Run:

~~~bash
SECRET_KEY=codex-django-upgrade-test /tmp/twocomms-django-61-venv/bin/python manage.py compress --force --settings=test_settings
~~~

Expected: compression completes without template/compiler errors; generated artifacts are kept out of the commit unless the repository contract requires them.

**Step 3: Review the release diff**

Run:

~~~bash
git diff --stat origin/main...HEAD
git diff --check origin/main...HEAD
~~~

Expected: only the design/plan documents, dependency pin/lock, contract expectation, and proven compatibility fixes are present.

---

### Task 6: Commit and publish the verified upgrade to `main`

**Files:**
- Commit only the scoped Django upgrade files listed by the release diff.

**Step 1: Run the final local gate**

Repeat the complete checks from Tasks 3-5 after all fixes, then inspect:

~~~bash
git status --short
git diff --check
~~~

Expected: all commands pass and no unrelated file is staged.

**Step 2: Commit the upgrade**

Run:

~~~bash
git add twocomms/requirements.in twocomms/requirements.lock tests/test_requirements_contract.py docs/plans/2026-08-15-django-61-upgrade-design.md docs/plans/2026-08-15-django-61-upgrade.md [proven-compatibility-files]
git commit -m "build: upgrade Django to 6.1"
~~~

Expected: one scoped commit with a clean diff.

**Step 3: Push the reviewed SHA to GitHub `main`**

After confirming `origin/main` has not advanced beyond the branch base, run:

~~~bash
git push origin HEAD:main
~~~

Expected: GitHub `main` points to the verified commit. If the remote advanced, stop and rebase/reverify instead of force-pushing.

---

### Task 7: Install and verify Django 6.1 on production

**Files:**
- Production checkout only; no production source mutation outside the supported pull/install/check path.

**Step 1: Fast-forward production to the exact Git SHA**

Use the repository-approved SSH path with `TWOCOMMS_DEPLOY_PASSWORD` supplied by the caller environment. Pull `main` in the Python 3.14 virtualenv and verify the resulting SHA.

Before installing the lock, query the production database server version and stop unless it is MariaDB `10.11` or newer, as required by Django 6.1.

**Step 2: Install the committed lock**

In the same activated virtualenv, run:

~~~bash
python -m pip install --require-hashes -r requirements.lock
~~~

Expected: Django 6.1 and all locked dependencies are installed; no unpinned install is used.

**Step 3: Run production checks without customer test data**

Run:

~~~bash
python manage.py check
python manage.py migrate --plan
python manage.py collectstatic --noinput
python manage.py compress --force
~~~

Apply `migrate --noinput` only if the pulled `main` contains pending reviewed migrations; this framework-only change is expected to have none. Restart Passenger through the repository's restart marker after checks/static/compression complete.

**Step 4: Prove live runtime**

Record the production SHA, `python -m django --version`, `pip check`, migration state, Passenger restart result, and representative `/healthz/`, `/`, `/cart/`, and localized storefront responses. Any failed gate leaves the release unverified and triggers rollback to the prior SHA/lock.
