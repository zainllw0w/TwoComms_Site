# CODEX PROMPT — Part 6 (AI-Optimized): Core Business Engine (Quotes/Orders/Preflight 2.0/Status/Automation)
**Project:** dtf.twocomms.shop (TwoComms DTF)  
**Date:** 2026-02-07  
**Purpose:** Parts 4–5 introduce WOW visuals + Free Sample + Constructor MVP. **Part 6 builds the “business core”** that makes the platform *operationally unbeatable*: pricing/quotes, order lifecycle, robust preflight pipeline, status tracking, manager automation, admin ops, and analytics — while preserving the existing stack and subdomain isolation.

**Dependencies:** MUST follow Part 3 (execution runbook) and use the effect infra from Part 5.  
**Non‑negotiable:** Changes are **DTF-scoped** only; do not break `twocomms.shop`.

---

## 0) Principles (MUST)
1. **Sequential Thinking MCP almost everywhere**: plan → implement → test → evidence → deploy.
2. **Context7 MCP** for architecture decisions and consistency with existing codebase patterns.
3. **Lianer MCP** for task tracking; every deliverable must map to:
   - `DTF_CHECKLIST.md`, `CHANGELOG_CODEX.md`, `EVIDENCE.md`, `MCP_TODO.md`
4. **Server is source of truth** for pricing, validation, and order status.
5. **Progressive enhancement**: HTMX/JS improve UX, but no feature must be “JS-only”.
6. **Performance & security are part of the feature**: don’t ship core flows that regress CWV or weaken uploads.

---

## 1) What Part 6 Adds (High-Level)
### 1.1 Business outcomes
- Instant **accurate estimates** (pricing engine) → higher conversion + fewer manager clarifications.
- **Preflight 2.0**: deterministic checks + repeatable reports → fewer print mistakes.
- **Order lifecycle**: consistent statuses + customer-facing tracking → trust + reduced support.
- **Automation**: manager receives structured data; customers get updates → operational scale.
- **Analytics**: measure funnel, preflight failures, drop-offs → iterate intelligently (even without A/B).

### 1.2 New “core system modules”
- Quote/Pricing Engine
- Order Lifecycle & Status Events
- Preflight Pipeline (async-ready)
- Notification Layer (email + messenger hooks)
- Admin Ops Dashboard (lightweight)
- Analytics + Event Logging

---

## 2) Domain Model & State Machine (MUST implement cleanly)
### 2.1 Entities (DTF app)
Implement/confirm models (or adapt existing):
1) `DtfUpload`
   - file, size, mime, hash, created_at, owner/lead/order
2) `DtfPreflightReport`
   - upload FK
   - result: PASS/WARN/FAIL
   - json: checks, metrics, warnings, errors
   - preview assets: thumbnail, overlay image(s)
   - versioning: `preflight_version`, `engine_version`
3) `DtfQuote`
   - source: order form / constructor / sample lead
   - inputs: width_cm, length_m, urgency, services (cutting, weeding, etc), shipping
   - computed: unit price, totals, discount, min order rules, validity
4) `DtfOrder`
   - customer info, shipping info
   - status (state machine)
   - quote FK, upload(s) FK
   - manager notes + internal flags
5) `DtfStatusEvent`
   - order FK
   - status_from, status_to
   - timestamp, actor (system/manager/customer)
   - public_message, internal_message
6) `DtfCustomerProfile` (optional, for cabinet/loyalty)
   - phone/email identity, created_at
   - loyalty points, tier, manager assigned

### 2.2 Status state machine (MUST)
Define statuses (minimal but complete):
- `NEW` (created)
- `NEEDS_REVIEW` (preflight WARN/FAIL or special request)
- `CONFIRMED` (manager confirmed)
- `IN_PRODUCTION`
- `QA_CHECK`
- `PACKED`
- `SHIPPED`
- `DELIVERED`
- `CANCELLED`

Rules:
- Customer can create order → `NEW`.
- Preflight FAIL blocks submit OR forces `NEEDS_REVIEW` with explicit consent. (Business rule: default FAIL blocks unless user selected “I accept risk + manager review”.)
- System transitions must log `DtfStatusEvent`.
- Customer tracking page reads current status + timeline from events.

---

## 3) Pricing / Quote Engine (P0 core)
### 3.1 Requirements (MUST)
- Implement a **single source** of pricing logic:
  - `dtf/pricing.py` with deterministic functions
  - NO pricing calculations duplicated in JS (JS only mirrors server response)
- Support:
  - width fixed 60 cm (but allow future widths via config)
  - length in meters (float; validate min step)
  - base price per meter (from admin config)
  - tiered discounts (volume thresholds)
  - urgency multiplier (optional)
  - “help with layout” service fee
  - shipping (optional estimate)
- Output includes:
  - breakdown (base, discount, services, shipping)
  - disclaimers (estimate vs final after review)
  - validity (e.g., 7 days)

### 3.2 Config strategy
- Prefer admin-editable settings:
  - `DtfPricingConfig` model OR Django settings + admin UI
- Include effective date for configs and version pin.

### 3.3 UI integration (HTMX)
- Home calculator and Order summary must:
  - send inputs to `/api/quote/` (DTF scoped)
  - receive JSON (or partial HTML) with breakdown
  - update UI without full page reload
- Provide graceful fallback (full submit).

### 3.4 Tests (MUST)
- Unit tests for pricing scenarios:
  - small length no discount
  - volume discount
  - invalid inputs (negative, too small)
  - urgency and service fee impact
- Snapshot tests for output JSON schema.

---

## 4) Preflight 2.0 Pipeline (P0 core)
### 4.1 Goals
- Detect common production risks early, present them clearly, and store a reproducible report.

### 4.2 Checks (MUST implement as structured “rules”)
Implement in `dtf/preflight/engine.py`:
- File type allowlist + magic-bytes sniff
- Pixel size → compute physical at 300 DPI
- DPI detection if available (metadata), else infer
- Transparency presence (alpha)
- Bounding box of non-transparent content
- Margins/safe zone checks
- Overprint/white layer heuristics (basic)
- Color space detection (RGB/CMYK) where possible
- PDF page count; for multi-page, block or require review
- Max file size; max pixel dimensions
- Optional: detect “tiny text” risk using heuristic (edge density)

Return:
- PASS/WARN/FAIL
- list of findings with codes: `PF_DPI_LOW`, `PF_MARGIN_SMALL`, etc.

### 4.3 Preview + overlays (MUST)
- Generate:
  - thumbnail preview
  - optional overlay image with highlighted issues (margin box, bounding box)
- Store assets under DTF static/media path; ensure access permissions.

### 4.4 Async readiness (IMPORTANT)
Prefer Celery if already configured and stable:
- Upload → enqueue preflight job
- UI shows multi-step loader while waiting
- Poll endpoint `/preflight/<id>/status/` via HTMX
Fallback (if async not feasible):
- run preflight synchronously with timeouts; show loader only for UI

### 4.5 Evidence + versioning
- Each report stores engine version:
  - bump `engine_version` when logic changes
- Save sample files used for validation only if allowed; otherwise store only hashes.

### 4.6 Tests (MUST)
- Golden-file tests with known PASS/WARN/FAIL cases
- Security tests: reject spoofed mime, huge images, bad PDFs

---

## 5) Order Creation & Manager Workflow (P0)
### 5.1 Unified “Lead → Quote → Order” flow
- All entrypoints produce structured data:
  - `/order/` (ready/help)
  - `/constructor/submit/` (Part 4)
  - `/sample/` (Part 4)
- Standardize payload:
  - contact
  - source
  - quote inputs
  - upload/preflight references
  - user notes

### 5.2 Admin ops (MUST)
Create minimal admin UX:
- List orders with filters by status, preflight result, urgency, source
- Order detail view shows:
  - quote breakdown
  - preflight report summary
  - files & previews
  - timeline events
  - actions: transition status (with note), add internal note

If building a custom admin page is too much, implement via Django Admin with good list_display and custom actions.

### 5.3 Notifications layer (P1 but important)
Implement an internal notification interface:
- `dtf/notify.py` with adapters:
  - Email (baseline)
  - Telegram/Viber link placeholders (for later)
- On new order:
  - notify manager (email) with structured summary + links
- On status change:
  - optionally notify customer (email) with status + timeline

Keep it configurable.

---

## 6) Customer Status Tracking (P0)
### 6.1 `/status/` UX upgrades
- Accept: order number + phone (or email)
- Show:
  - current status label
  - timeline list (events)
  - ETA hint (optional)
  - contact CTA

### 6.2 Security
- Prevent enumeration:
  - rate limit
  - generic error messages
  - require phone/email match

### 6.3 Events
- Ensure every transition logs `DtfStatusEvent`.
- Customer view shows only “public” messages.

---

## 7) Cabinet + Loyalty (ties into Part 4, but now “real”)
### 7.1 Authentication scope
If dtf login already exists:
- `/cabinet/` shows:
  - last orders
  - saved constructor sessions
  - points/tier
Else:
- implement “magic link” login or phone OTP later; for now keep cabinet behind existing auth.

### 7.2 Loyalty minimal rules
- Points from order totals or count thresholds.
- Tier thresholds:
  - Bronze/Silver/Gold (labels)
- Perks:
  - personal manager flag
  - faster SLA flag

Implement as config constants.

---

## 8) Analytics & Event Logging (P1 but must start now)
### 8.1 Events to capture (server-side preferred)
- `view_home`, `click_cta_order`, `click_cta_sample`
- `upload_started`, `upload_completed`
- `preflight_pass/warn/fail`, top error codes
- `order_submitted`, `order_confirmed`
- `constructor_step_change`, `constructor_submit`
- `status_check_success/fail`

### 8.2 Storage
- Minimal: DB table `DtfEventLog` or structured logs.
- Must not store sensitive personal data in raw form; hash where possible.

### 8.3 Reporting
Create a simple admin report page or admin action export:
- weekly counts
- most common preflight failures
- drop-off points

---

## 9) SEO Technical (DTF scoped; align with blog from Part 2)
- Ensure canonical per page.
- Ensure sitemap includes dtf pages (and blog articles once stable).
- Add JSON-LD:
  - Organization + Service (DTF printing)
  - BreadcrumbList
  - FAQPage on requirements/order if appropriate
- Ensure OpenGraph image default for dtf subdomain (dtf-specific).

---

## 10) Implementation Plan (Lianer tasks in exact order)
Create and execute tasks in this order:
1) `[DTF] Define domain models + migrations for Quote/Order/PreflightReport/StatusEvent`
2) `[DTF] Implement pricing engine + API endpoint + unit tests`
3) `[DTF] Wire calculator UI to quote endpoint (home + order)`
4) `[DTF] Implement preflight engine rules + report schema + tests`
5) `[DTF] Add preflight asset generation (thumb + overlay) + evidence`
6) `[DTF] Integrate async preflight (Celery) OR sync fallback with loader`
7) `[DTF] Implement order creation pipeline (lead→quote→order) across entrypoints`
8) `[DTF] Add admin workflows (filters, actions, status transitions)`
9) `[DTF] Implement status tracking secure lookup + timeline UI`
10) `[DTF] Add notifications baseline (email) for new order + status updates`
11) `[DTF] Add cabinet order list + sessions list (auth permitting)`
12) `[DTF] Add analytics event log + admin export`
13) `[DTF] SEO technical hardening (canonical, JSON-LD, sitemap updates)`

Every task must comply with Part 3 runbook (tests, evidence, deploy, rollback).

---

## 11) Acceptance Criteria (DoD) for Part 6
Part 6 is DONE when:
- Pricing engine exists, tested, used by home/order calculators.
- Preflight 2.0 produces reproducible reports with codes and stored outputs.
- Orders have status machine + event timeline + secure customer tracking page.
- Manager/admin can view and update orders without guesswork.
- Notifications send at least an email to manager on new order.
- Basic analytics exists for funnel and preflight failure reasons.
- No regressions to main domain.

Proceed autonomously; ask user only on ambiguous business rules (FAIL block policy, discount thresholds, shipping/payment policy).

