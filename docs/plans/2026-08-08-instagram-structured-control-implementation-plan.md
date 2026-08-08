# Instagram Structured Control Boundary Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Close Implement 2 W1.6 with a strict structured Gemini reply contract,
fail-closed legacy compatibility, adversarial authority tests and one canonical
payment protocol.

**Architecture:** A dedicated immutable response-control module validates both
provider JSON and legacy strings. The bot worker receives only sanitized text
plus validated proposals; existing deterministic services remain the sole
operational authorities. A surgical migration removes exact legacy prompt
fragments while preserving custom text.

**Tech Stack:** Django 5.2, Python dataclasses/JSON schema, Gemini generateContent,
unittest/Django TestCase, MariaDB migration.

---

### Task 1: Typed response and fail-closed legacy adapter

**Files:**
- Create: `twocomms/management/services/ig_response_control.py`
- Test: `twocomms/management/tests_ig_agentic_dialog.py`

1. Add RED tests for valid structured commands, unknown kind/field, conflicting
   singleton commands, malformed item/option values and typo/lowercase legacy
   brackets. Assert invalid input returns no operational commands and sanitized
   customer text contains no control-shaped suffix.
2. Run only the new test class and confirm failures describe the missing module
   or behaviour.
3. Implement immutable `GeneratedReply`/`ReplyControl` values, a closed schema,
   strict structured validation and a legacy adapter covering every inventoried
   production tag.
4. Re-run the class, refactor duplication and keep it green.

### Task 2: Structured provider request and worker integration

**Files:**
- Modify: `twocomms/management/services/call_ai_analysis.py`
- Modify: `twocomms/management/services/instagram_bot.py`
- Test: `twocomms/management/tests_ig_agentic_dialog.py`
- Test: `twocomms/management/tests_ig_live_reply_priority.py`

1. Add RED provider tests asserting `application/json`, the closed response
   schema and application validation of `out['parsed']`.
2. Add RED worker tests proving structured and legacy replies converge at one
   typed boundary before price/product/payment/stage logic.
3. Add an opt-in `parse` parameter to the existing provider wrapper without
   changing its default callers; request parse mode only for customer chat.
4. Normalize the generated result once in the worker. Invalid controls execute
   no actions and sanitized text alone may be delivered.
5. Run focused tests and remove direct permissive regex consumption.

### Task 3: Adversarial authority regression suite

**Files:**
- Modify: `twocomms/management/tests_ig_agentic_dialog.py`
- Modify: `twocomms/management/tests_ig_live_reply_priority.py`
- Modify: `twocomms/management/tests_ig_audit_fixes.py` only if an existing
  authority fixture is the narrowest home.

1. Add RED cases where customer text asks to ignore rules, claim paid/done,
   invent stock/price, generate a paylink, opt in, suppress escalation or expose
   controls.
2. Make provider output propose each forbidden action and assert the existing
   system authority blocks it without leaking a control token.
3. Add positive controls for a valid non-hard stage and a properly evidenced
   proposal so fail-closed handling does not disable legitimate sales flow.
4. Run the adversarial class and adjacent payment/order gates.

### Task 4: Remove duplicate legacy payment protocol

**Files:**
- Modify: `twocomms/management/models.py`
- Modify: `twocomms/management/services/instagram_bot.py`
- Create: `twocomms/management/migrations/0151_*.py`
- Test: `twocomms/management/tests_ig_agentic_dialog.py`

1. Add RED prompt tests proving the assembled prompt has exactly one commerce
   protocol, no legacy tag instructions and still contains factual payment,
   price and checkout safeguards.
2. Add RED migration tests: exact legacy fragments are removed while arbitrary
   custom prefix/suffix text remains unchanged; an unrelated custom prompt is
   untouched; the migration is idempotent.
3. Rewrite the runtime protocol in structured-command terms and remove the
   duplicate blocks from the model default.
4. Generate a migration with an exact-fragment RunPython cleanup and AlterField;
   never replace a whole customized DB prompt.
5. Run migration tests and `makemigrations --check --dry-run management`.

### Task 5: Review and release gate

**Files:**
- Modify only files required by reviewer findings.

1. Run focused and adjacent suites, Django check, migration check, compileall
   and `git diff --check`.
2. Perform spec review, then code-quality review, and fix every blocker with
   re-review.
3. Commit the independently deployable W1.6 code, fast-forward local `main`,
   push `main`, deploy via the ordinary SSH path, apply migration and restart
   Passenger/daemon.
4. Verify exact SHA, migration, production prompt markers, provider-free parser
   probes, one daemon and healthy queues.
5. Only after production evidence mark all three W1.6 checkboxes `[x]`, commit
   the evidence, push and pull it on production.
