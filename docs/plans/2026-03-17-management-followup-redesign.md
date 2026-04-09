# Management Follow-Up Redesign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Deliver one cohesive management-shell update that stabilizes the profile header, removes the duplicate sidebar parsing entry, unifies callback state around a Kyiv-time 2-hour grace policy, hides premature phase badges, and simplifies callback follow-up UX.

**Architecture:** Introduce one shared follow-up state helper and route shell serialization, reminder logic, and metrics through it instead of comparing raw client dates in multiple places. Keep the existing schema, reuse `ClientFollowUp.grace_until`, and then layer the UI refactor on top of the unified backend policy so profile/action-rail fixes do not sit on inconsistent callback state.

**Tech Stack:** Django, Django templates, Django timezone utilities, MySQL-backed models, vanilla JavaScript, CSS container queries, targeted Django test suites under `management`.

---

### Task 1: Add shared callback-state policy and grace-window tests

**Files:**
- Create: `twocomms/management/services/followup_state.py`
- Modify: `twocomms/management/services/followup_sync.py`
- Test: `twocomms/management/tests.py`

**Step 1: Write the failing test**

```python
def test_effective_callback_state_uses_two_hour_grace_and_recovery(self):
    now = self._stable_now()
    client = Client.objects.create(
        shop_name="Grace Shop",
        phone="+380000000001",
        full_name="Owner",
        owner=self.user,
        next_call_at=now - timedelta(minutes=30),
    )
    _sync_client_followup(client, None, client.next_call_at, now - timedelta(hours=1))
    followup = ClientFollowUp.objects.get(client=client, owner=self.user)

    state = get_effective_callback_state(client=client, now_dt=now)
    self.assertEqual(state.code, "due_now")

    followup.grace_until = now - timedelta(minutes=1)
    followup.save(update_fields=["grace_until"])
    state = get_effective_callback_state(client=client, now_dt=now)
    self.assertEqual(state.code, "missed")

    later_due = now + timedelta(days=1)
    prev_due = client.next_call_at
    client.next_call_at = later_due
    client.save(update_fields=["next_call_at"])
    _sync_client_followup(client, prev_due, later_due, now + timedelta(minutes=10))

    state = get_effective_callback_state(client=client, now_dt=now + timedelta(minutes=10))
    self.assertEqual(state.code, "scheduled")
```

**Step 2: Run test to verify it fails**

Run:

```bash
python manage.py test management.tests.FollowUpSyncTests.test_effective_callback_state_uses_two_hour_grace_and_recovery --settings=test_settings
```

Expected: fail because `get_effective_callback_state` does not exist and follow-up grace behavior is not unified.

**Step 3: Write minimal implementation**

Implement a small shared helper with:

```python
@dataclass(frozen=True)
class CallbackState:
    code: str
    due_at: datetime | None
    grace_until: datetime | None
    followup_id: int | None


def build_grace_until(due_at: datetime | None) -> datetime | None:
    if not due_at:
        return None
    return due_at + timedelta(hours=2)


def get_effective_callback_state(*, client: Client, now_dt) -> CallbackState:
    ...
```

Also stamp `grace_until` when `sync_client_followup()` creates a new open follow-up.

**Step 4: Run test to verify it passes**

Run:

```bash
python manage.py test management.tests.FollowUpSyncTests.test_effective_callback_state_uses_two_hour_grace_and_recovery --settings=test_settings
```

Expected: PASS.

**Step 5: Commit**

```bash
git add twocomms/management/services/followup_state.py twocomms/management/services/followup_sync.py twocomms/management/tests.py
git commit -m "feat: unify callback grace state policy"
```

### Task 2: Route shell rows, reminder digest, and metrics through the shared state

**Files:**
- Modify: `twocomms/management/views.py`
- Modify: `twocomms/management/context_processors.py`
- Modify: `twocomms/management/services/followups.py`
- Modify: `twocomms/management/stats_service.py`
- Test: `twocomms/management/tests_phase7_shell_bot.py`
- Test: `twocomms/management/tests_phase4_analytics.py`

**Step 1: Write the failing tests**

```python
def test_home_uses_due_now_before_missed_after_grace(self):
    ...
    self.assertEqual(flat["Grace Shop"][1]["callback_state"], "due_now")
    self.assertEqual(flat["Missed Shop"][1]["callback_state"], "missed")


def test_shell_secondary_counts_ignore_recovered_callback(self):
    ...
    self.assertEqual(response.context["management_shell_missed_callbacks"], 0)
```

```python
def test_followup_metrics_count_overdue_after_grace_not_same_day_date_only(self):
    ...
    self.assertEqual(payload["followups"]["missed_effective"], 1)
```

**Step 2: Run tests to verify they fail**

Run:

```bash
python manage.py test management.tests_phase7_shell_bot.HomeShellRenderTests management.tests_phase4_analytics --settings=test_settings
```

Expected: fail because shell serialization and metrics still rely on `next_call_at__date` and `due_date__lt today`.

**Step 3: Write minimal implementation**

Update the following behavior:

- `_serialize_client_for_home()` reads the effective callback state helper instead of comparing `client.next_call_at.date()` with today.
- `build_management_shell_metrics()` counts `today`, `due_now`, and `missed` from open follow-ups or helper-backed row state rather than `Client.next_call_at__date`.
- `build_reminder_digest()` keeps using `grace_until`, but ladder/status labels align with the same effective state names.
- `stats_service.py` treats open follow-ups as effectively missed only when `grace_until` is expired.

**Step 4: Run tests to verify they pass**

Run:

```bash
python manage.py test management.tests_phase7_shell_bot.HomeShellRenderTests management.tests_phase4_analytics --settings=test_settings
```

Expected: PASS.

**Step 5: Commit**

```bash
git add twocomms/management/views.py twocomms/management/context_processors.py twocomms/management/services/followups.py twocomms/management/stats_service.py twocomms/management/tests_phase7_shell_bot.py twocomms/management/tests_phase4_analytics.py
git commit -m "feat: drive shell and metrics from effective callback state"
```

### Task 3: Enforce Kyiv-time future scheduling and thresholded phase visibility

**Files:**
- Modify: `twocomms/management/views.py`
- Modify: `twocomms/management/lead_views.py`
- Modify: `twocomms/management/services/outcomes.py`
- Modify: `twocomms/management/templates/management/home.html`
- Test: `twocomms/management/tests_phase6_client_entry.py`
- Test: `twocomms/management/tests_phase7_shell_bot.py`

**Step 1: Write the failing tests**

```python
def test_client_entry_rejects_scheduled_callback_in_the_past(self):
    response = self.client.post(
        reverse("management_home"),
        {
            "shop_name": "Past Slot",
            "phone": "+380671111111",
            "full_name": "Owner",
            "call_result": Client.CallResult.THINKING,
            "next_call_type": "scheduled",
            "next_call_date": "2026-03-16",
            "next_call_time": "09:00",
        },
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )
    self.assertEqual(response.status_code, 400)
```

```python
def test_home_hides_phase_chip_until_real_third_phase(self):
    ...
    self.assertNotContains(response, "Фаза 2")
```

**Step 2: Run tests to verify they fail**

Run:

```bash
python manage.py test management.tests_phase6_client_entry management.tests_phase7_shell_bot.HomeShellRenderTests --settings=test_settings
```

Expected: fail because past times are accepted and phase labels appear too early.

**Step 3: Write minimal implementation**

Implement:

- a helper in `services/outcomes.py` that parses a scheduled datetime and validates it is strictly in the future in current Django timezone,
- view-level rejection for stale scheduled callbacks in both client-entry paths,
- client-side `setDefaultDateTime()` that rounds forward in local time instead of using `toISOString()`,
- dynamic `min` protection for current-day date/time inputs,
- phase-chip rendering only when callback history depth meets the agreed threshold.

**Step 4: Run tests to verify they pass**

Run:

```bash
python manage.py test management.tests_phase6_client_entry management.tests_phase7_shell_bot.HomeShellRenderTests --settings=test_settings
```

Expected: PASS.

**Step 5: Commit**

```bash
git add twocomms/management/views.py twocomms/management/lead_views.py twocomms/management/services/outcomes.py twocomms/management/templates/management/home.html twocomms/management/tests_phase6_client_entry.py twocomms/management/tests_phase7_shell_bot.py
git commit -m "feat: validate kyiv callback scheduling and phase thresholds"
```

### Task 4: Rebuild profile rail and callback action rail markup contracts

**Files:**
- Modify: `twocomms/management/templates/management/base.html`
- Modify: `twocomms/management/templates/management/home.html`
- Modify: `twocomms/twocomms_django_theme/static/css/management.css`
- Test: `twocomms/management/tests_phase7_shell_bot.py`

**Step 1: Write the failing tests**

```python
def test_home_renders_equal_profile_actions_and_single_parsing_entry(self):
    response = self.client.get("/", secure=True)
    self.assertContains(response, "user-profile__identity")
    self.assertContains(response, "user-actions")
    self.assertContains(response, "user-actions__item")
    self.assertEqual(response.content.decode("utf-8").count(">Парсинг<"), 1)
```

```python
def test_home_renders_overlay_callback_rail_contract(self):
    response = self.client.get("/", secure=True)
    self.assertContains(response, "action-rail--overlay")
    self.assertContains(response, "action-rail__callback-label")
```

**Step 2: Run tests to verify they fail**

Run:

```bash
python manage.py test management.tests_phase7_shell_bot.HomeShellRenderTests --settings=test_settings
```

Expected: fail because current markup still uses the old profile and action-rail contract.

**Step 3: Write minimal implementation**

Implement:

- profile top section with reserved avatar / identity / actions layout and equal action-button wrappers,
- remove the sidebar `Парсинг` item while preserving top navigation entry,
- action rail markup with a stable overlay container,
- simplified callback recap block and collapsible history in the follow-up modal,
- CSS updates for fixed action sizing, stacking context, hover expansion, and responsive fallback.

**Step 4: Run tests to verify they pass**

Run:

```bash
python manage.py test management.tests_phase7_shell_bot.HomeShellRenderTests --settings=test_settings
```

Expected: PASS.

**Step 5: Commit**

```bash
git add twocomms/management/templates/management/base.html twocomms/management/templates/management/home.html twocomms/twocomms_django_theme/static/css/management.css twocomms/management/tests_phase7_shell_bot.py
git commit -m "feat: rebuild management shell profile and callback rails"
```

### Task 5: Run full targeted verification and prepare release

**Files:**
- Modify if needed: `twocomms/management/tests_phase7_shell_bot.py`
- Modify if needed: `twocomms/management/tests.py`
- Modify if needed: `twocomms/management/tests_phase4_analytics.py`
- Modify if needed: `twocomms/management/tests_phase6_client_entry.py`

**Step 1: Run the targeted regression pack**

Run:

```bash
python manage.py test \
  management.tests.FollowUpSyncTests \
  management.tests_phase4_analytics \
  management.tests_phase6_client_entry \
  management.tests_phase7_shell_bot \
  --settings=test_settings
```

Expected: full PASS.

**Step 2: Run a browser verification pass**

Check:

- desktop sidebar profile with long names/roles,
- staff shell with one `Парсинг` entry,
- callback row hover/overlay behavior,
- card-mode action rail,
- due-now vs missed states,
- follow-up modal recap and hidden early phase chips.

**Step 3: Prepare release**

Run:

```bash
git status --short
git log --oneline --decorate -5
```

Expected: only intentional changes remain.

**Step 4: Commit final polish if needed**

```bash
git add twocomms/management twocomms/twocomms_django_theme/static/css/management.css
git commit -m "fix: finalize management callback redesign"
```

**Step 5: Release**

Run:

```bash
git push -u origin codex/management-followup-redesign
git switch main
git pull --ff-only
git merge --ff-only codex/management-followup-redesign
git push origin main
sshpass -p 'trs5m4t1' ssh -o StrictHostKeyChecking=no qlknpodo@195.191.24.169 "bash -lc 'source /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.14/bin/activate && cd /home/qlknpodo/TWC/TwoComms_Site/twocomms && git pull'"
```

Expected: branch and `main` are aligned, and the server repository points at the deployed `main` commit.
