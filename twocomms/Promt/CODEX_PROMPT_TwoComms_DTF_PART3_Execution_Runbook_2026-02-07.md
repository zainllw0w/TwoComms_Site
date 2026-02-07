# CODEX PROMPT — Part 3 (AI-Optimized): Execution Protocol, QA Gates, Evidence, Rollback
**Project:** dtf.twocomms.shop (TwoComms DTF)  
**Scope:** This Part 3 defines *how* to execute Parts 1–2 safely: workflows, quality gates, evidence logging, deployment, rollback, and “don’t break main domain” constraints.  
**Non-negotiable:** Work **ONLY** on `dtf.twocomms.shop` subdomain codepaths. **NEVER** modify behavior/assets for `twocomms.shop` main domain.

---

## 0) Absolute Constraints (MUST)
1. **Isolation:** All changes MUST be isolated to DTF app/routing:
   - DTF routing via `twocomms/urls_dtf.py` → `include('dtf.urls')`.
   - DTF templates/assets live under `dtf/templates/dtf/` and `dtf/static/dtf/`.
2. **No main-domain regressions:** Never touch `twocomms.urls` main domain routes, main robots/sitemap, or shared templates unless explicitly scoped for dtf-only conditional rendering.
3. **Branching:** Work only in a dedicated branch:
   - `git checkout -b codex-refactor-v1`
   - No direct commits to main/master.
4. **MCP Usage:** Use MCP tools as specified:
   - **Sequential Thinking MCP:** use *almost everywhere* (planning, design decisions, refactors, tests, deploy steps).
   - **Context7 MCP:** use for decisions about *best patterns* and *consistency* with existing codebase.
   - **Lianer MCP:** every meaningful task MUST be tracked and updated (todo → doing → done) and mirrored into repo checklists.

---

## 1) Ground Truth of Current Stack (DO NOT FIGHT IT)
### Backend
- Python 3.13 + Django 5.2.x (DTF subdomain app: `dtf/`).
- Django REST Framework exists; Celery + Redis exist, but do not introduce background jobs unless required.

### Frontend
- **No React/Vue. No heavy bundlers.**
- HTMX is present (`dtf/static/dtf/js/vendor/htmx.min.js`).
- UI logic is custom Vanilla JS (`dtf/static/dtf/js/dtf.js`) and custom CSS (`dtf/static/dtf/css/dtf.css` + `tokens.css`).
- Fonts: Space Grotesk, Manrope, JetBrains Mono.

**Directive:** When adding UI effects/components, integrate as *progressive enhancement* on top of existing CSS/JS patterns.

---

## 2) Repository Map (Reference Paths)
- `dtf/templates/dtf/base.html` — global layout for dtf.
- `dtf/templates/dtf/index.html` — DTF home.
- `dtf/templates/dtf/order.html` — order flow.
- `dtf/templates/dtf/quality.html` — quality page (prod regression possible).
- `dtf/templates/dtf/partials/*` — HTMX partials.
- `dtf/templates/dtf/legal/*` — legal pages.
- `dtf/static/dtf/css/tokens.css` — design tokens (colors, etc).
- `dtf/static/dtf/css/dtf.css` — main stylesheet.
- `dtf/static/dtf/js/dtf.js` — main scripts (a11y, sliders, modals, etc).
- `dtf/forms.py`, `dtf/utils.py` — validation, upload security.
- `dtf/views.py`, `dtf/urls.py` — routes and controllers.
- `DEPLOY.md`, `EVIDENCE.md` — deployment/evidence docs (MUST keep updated).

---

## 3) Standard Working Loop (MUST)
For EVERY task (feature/bugfix/refactor), follow this loop:

### 3.1 Plan (Sequential Thinking MCP)
- Define the **user story**, **acceptance criteria**, **files touched**, **risk to main domain** (must be “none”).
- Add a task to Lianer MCP with:
  - Title: `[DTF] <short imperative>`
  - Description: problem → approach → files → acceptance criteria → tests.

### 3.2 Implement
- Make smallest cohesive change set.
- Prefer refactoring-by-extraction over inline spaghetti changes.
- Preserve existing tokens + CSS architecture; avoid creating parallel styling systems.

### 3.3 Test (Local)
MUST run before ANY deploy:
- `python manage.py test` (or at minimum dtf test suite).
- `python -m compileall` (fast sanity).
- If CSS/JS changed: quick smoke via local runserver and hard refresh.

### 3.4 Evidence
Append to `EVIDENCE.md`:
- What changed (1–3 sentences).
- Files touched.
- Before/after proof:
  - `curl -sI` outputs for key URLs (see Section 8).
  - Screenshot or short screen recording (if UI changed).
- Link the evidence entry to Lianer task ID.

### 3.5 Commit
Commit MUST be descriptive and scoped:
- `git commit -m "DTF: <what changed> (refs <Lianer-ID>)"`

### 3.6 Deploy (SSH Protocol)
Deploy only from `codex-refactor-v1` after tests pass (see Section 7).

---

## 4) Mandatory Project Artifacts (MUST maintain)
Maintain and update these files on EVERY iteration:

1. `DTF_CHECKLIST.md`
   - High-level tasks with checkboxes.
   - Each completed task references a commit hash and Lianer ID.

2. `EFFECTS_MAP.md`
   - Map effects/components to pages and DOM anchors.
   - Include “reduced motion behavior” and “mobile behavior” per effect.

3. `CHANGELOG_CODEX.md`
   - Append-only log: timestamp → change summary → files → commit.
   - Include rollback note for each meaningful change.

4. `EVIDENCE.md`
   - Proof logs (curl, screenshots, metric captures).
   - Include baseline/performance snapshots.

---

## 5) Quality Gates (MUST PASS)
### 5.1 No-regression gates
- `twocomms.shop` must not change:
  - robots/sitemap for main domain unaffected.
  - no main-domain templates/assets changed unless conditional for dtf-only.
- DTF pages still render and forms work.

### 5.2 Security gates
- Upload validation MUST remain enforced:
  - allowlist extensions
  - magic-bytes sniffing
  - size limits
  - safe filenames
- All forms MUST include CSRF tokens and reject cross-site requests.
- CSP/HSTS headers MUST remain.

### 5.3 Accessibility gates
- Focus visible, keyboard navigation, skip-link.
- `prefers-reduced-motion` respected:
  - no essential info is “animation only”.
  - disable heavy motion when reduce is enabled.

### 5.4 Performance gates
- Do not inflate payloads unnecessarily.
- Avoid long main-thread JS:
  - IntersectionObserver for lazy init.
  - pause animations offscreen.
- New libraries: only if truly needed and documented in `requirements.txt`/static vendor folder.

---

## 6) Production Known Risk (P0) — `/quality/` 500 in Browser
If `/quality/` returns 500 on prod browser (even if curl shows 200):
**Run the standard fix sequence:**
1. SSH into server (Section 7).
2. Run:
   - `python manage.py collectstatic --noinput`
   - `touch tmp/restart.txt`
3. If server uses LiteSpeed cache:
   - clear cache (method depends on host panel; document steps in `EVIDENCE.md`).
4. Validate:
   - browser load (not just curl)
   - devtools console & network (no missing static).

Document outcome + evidence.

---

## 7) SSH / Server Execution Protocol (MUST)
Use SSH to run server-side operations inside the project venv.

**Canonical SSH entry (use sshpass as provided):**
```bash
sshpass -p 'trs5m4t1' ssh -o StrictHostKeyChecking=no qlknpodo@195.191.24.169 "bash -lc '
  source /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.13/bin/activate &&
  cd /home/qlknpodo/TWC/TwoComms_Site/twocomms &&
  git status
'"
```

### 7.1 Deploy Steps (Standard)
Inside the server project directory:
1. `git fetch --all`
2. `git checkout codex-refactor-v1`
3. `git pull`
4. `python -m pip install -r requirements.txt` (ONLY if deps changed)
5. `python manage.py migrate` (ONLY if migrations exist)
6. `python manage.py collectstatic --noinput`
7. `python manage.py test` (optional on server, required locally)
8. Restart app:
   - `touch tmp/restart.txt` (Passenger/WSGI restart trigger)

Log every deploy in `DEPLOY.md` with timestamp + commit hash.

---

## 8) Post-Deploy QA Matrix (MUST)
After every deploy, run:

### 8.1 Curl Checks (HTTP)
```bash
curl -sI https://dtf.twocomms.shop/
curl -sI https://dtf.twocomms.shop/order/
curl -sI https://dtf.twocomms.shop/price/
curl -sI https://dtf.twocomms.shop/quality/
curl -sI https://dtf.twocomms.shop/gallery/
curl -sI https://dtf.twocomms.shop/requirements/
curl -sI https://dtf.twocomms.shop/robots.txt
curl -sI https://dtf.twocomms.shop/sitemap.xml
curl -sI https://dtf.twocomms.shop/prices/   # must 301 -> /price/
```
Paste outputs into `EVIDENCE.md`.

### 8.2 Browser Smoke (Manual)
- Desktop + Mobile viewport:
  - Menu open/close; focus-trap.
  - Order flow both tabs (“ready” + “help”).
  - Preflight preview appears and updates; no JS errors.
  - Manager modal opens; body scroll lock works.
  - Before/After slider draggable (mouse + touch).
  - Reduced-motion: verify animations disabled when enabled.
- Verify `/quality/` in browser (known risk).

---

## 9) Lighthouse / CWV Baseline (MUST create & maintain)
A baseline is required to prevent regressions.

### 9.1 Pages to profile
- `/`
- `/order/`
- `/price/`
- `/quality/`

### 9.2 Capture protocol
- Use PageSpeed Insights or Lighthouse (Chrome).
- Save:
  - screenshots
  - JSON report (if available)
  - summary metrics (LCP/CLS/INP/TBT) into `EVIDENCE.md`
- Repeat after major changes; keep “baseline” + “current”.

---

## 10) Dependency Hygiene (MUST)
### 10.1 pip-audit
Run periodically and after adding deps:
```bash
pip install pip-audit
pip-audit -r requirements.txt
```
Log results in `EVIDENCE.md` and open a Lianer task for any CVEs.

### 10.2 Dead code / unused deps
If you remove a feature or stop using a library:
- Remove unused imports/JS/CSS sections
- Remove unused Python packages from requirements
- Add a note to `CHANGELOG_CODEX.md` about the cleanup

---

## 11) SEO & Indexing Guardrails (MUST)
- `robots.txt` and `sitemap.xml` MUST remain dtf-scoped (no leakage to main domain).
- Ensure meta title/description exist per page.
- If `canonical` is missing, implement canonical consistently:
  - base template should set `<link rel="canonical" href="<absolute_current_url>">`
  - document this in `EVIDENCE.md` and add a regression test if feasible.
- JSON-LD blocks (Organization/Service/FAQ/Breadcrumb) should remain valid after edits.
- Validate sitemap remains correct count and contains required DTF URLs.

---

## 12) Preflight & Upload System (Execution Rules)
### 12.1 Must not weaken security
All new preflight logic MUST keep server-side validation as the source of truth.
Client-side preflight is advisory; server rejects invalid.

### 12.2 Multi-step loader protocol
If adding multi-step loader:
- Must be non-blocking (only overlays the preflight widget area, not the entire page).
- Must have reduced-motion fallback.
- Must not cause CLS.

### 12.3 Evidence
For preflight updates, include:
- example file(s) used
- screenshots of warnings/errors
- server-side validation result

---

## 13) Rollback Protocol (MUST)
If any deploy causes regressions:
1. Identify last good commit hash.
2. On server:
   - `git checkout <last_good_hash>`
   - `python manage.py collectstatic --noinput`
   - `touch tmp/restart.txt`
3. Document in:
   - `DEPLOY.md` (rollback event)
   - `CHANGELOG_CODEX.md` (rollback reason)
   - Lianer MCP: mark task as blocked/regressed and open a bug task.

---

## 14) Output Expectations (Definition of Done for any iteration)
A task is “DONE” only if:
- Lianer task is marked done.
- `DTF_CHECKLIST.md` updated.
- `EFFECTS_MAP.md` updated (if UI/effects touched).
- `CHANGELOG_CODEX.md` entry added.
- `EVIDENCE.md` entry added (curl + screenshot if UI).
- Tests pass locally.
- Post-deploy QA matrix completed.

---

## 15) When to ask the user (ONLY SUPER IMPORTANT)
Ask only when:
- A change might affect the main domain.
- A new dependency is required that increases risk/weight.
- A business rule is ambiguous (pricing logic, guarantees, legal phrasing).

Otherwise: proceed autonomously and keep logs.
