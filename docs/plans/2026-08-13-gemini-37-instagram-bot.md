# Gemini 3.7 Instagram Bot Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make `gemini-3.7-flash` the normal model for every Instagram bot AI route, preserve older models only as typed emergency fallbacks, and expose the exact model used for every AI message in the management chat UI and API.

**Architecture:** Centralize the new primary model in the existing role model chains and chat normalization/allowlist. Keep the checker role on its existing grounded 2.5 chain because that provider contract is separate from Instagram AI. Persist the provider-returned model on each model-authored Instagram message, expose it through the existing client conversation payload, and render a compact model badge in the management-only conversation timeline without changing outbound Instagram text.

**Tech Stack:** Django 5, MariaDB-compatible migrations, existing Gemini REST pool/failover service, Django TestCase/SimpleTestCase, management bot HTML/CSS/JavaScript.

---

### Task 1: Define model policy and telemetry contracts

**Files:**
- Modify: `twocomms/management/services/gemini_keys.py`
- Modify: `twocomms/management/ig_bot_models.py`
- Create: `twocomms/management/migrations/<generated>_gemini_37_message_model.py`
- Test: `twocomms/management/tests_gemini_37_model_policy.py`

**Steps:**
1. Add failing tests for 3.7-first chat/management chains, 3.7 normalization, rejection of untrusted chat model overrides, and the new bounded message model field.
2. Run the focused tests and confirm they fail because the old 3.6 policy and field are absent.
3. Implement the smallest policy change: 3.7 first in `chat` and `management`, 3.6/3.5 fallback order retained, 3.7 included in the free-quota and allowed-chat sets, and the bot setting default normalized to 3.7.
4. Add a nullable/blank bounded `gemini_model` field to model-authored message records and create the migration without changing historical rows.
5. Run the focused tests and migration drift check.

### Task 2: Persist actual model provenance on generated replies

**Files:**
- Modify: `twocomms/management/services/instagram_bot.py`
- Test: `twocomms/management/tests_gemini_37_model_policy.py`
- Test: `twocomms/management/tests_ig_live_reply_priority.py`

**Steps:**
1. Add a failing test proving the result model returned by the Gemini pool is copied to the persisted model message, while fallback results record the fallback model.
2. Run the test and confirm the model field remains empty.
3. Thread the provider result model through the existing reply persistence/delivery boundary and save only the bounded model identifier; leave manager, inbound, and deterministic messages empty.
4. Run the focused reply and delivery tests.

### Task 3: Expose model provenance and render the management badge

**Files:**
- Modify: `twocomms/management/bot_views.py`
- Modify: `twocomms/management/templates/management/bot.html`
- Test: `twocomms/management/tests_gemini_37_model_policy.py`
- Test: `twocomms/management/tests_ig_clients_ui.py`

**Steps:**
1. Add failing API/template contract tests for `gemini_model`, a short display label, and distinct primary/fallback styling.
2. Run the tests and confirm the current payload/UI has no per-message model marker.
3. Add the bounded model fields to the conversation JSON and render `AI-агент` plus a compact `3.7`/`3.6` badge with accessible text/title. Do not include it in outbound message text.
4. Run the focused UI/API tests and JavaScript syntax checks.

### Task 4: Verify all Instagram AI routes use the new policy

**Files:**
- Modify: `twocomms/management/templates/management/bot.html` (model selector labels)
- Modify: `twocomms/management/services/bot_catalog.py` (stale policy comment only if needed)
- Test: related Gemini/Instagram suites

**Steps:**
1. Update stale operator-facing defaults/comments and add assertions that chat, management analysis, vision, catalog/commerce decisions, and recovery use centralized 3.7-first chains.
2. Run the focused Gemini, conversation-analysis, vision, commerce, and live-reply suites.
3. Run `manage.py check`, `makemigrations --check --dry-run`, compile checks, and `git diff --check`.

### Task 5: Publish and prove production behavior

**Steps:**
1. Commit the isolated branch after all local verification passes.
2. Fast-forward/integrate into `main`, push `origin/main`, and pull on production.
3. Run migration/check/static/compress/restart and ensure the Instagram daemon.
4. Run the non-customer `probe_ig_gemini_pool --role chat --model gemini-3.7-flash` against the six aliases.
5. Verify production settings, recent AI message model values, analysis job/snapshot model values, daemon heartbeat, and no synthetic Instagram/Meta customer events were sent.
