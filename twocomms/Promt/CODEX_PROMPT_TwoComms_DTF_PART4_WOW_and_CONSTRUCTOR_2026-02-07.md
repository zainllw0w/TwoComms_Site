# CODEX PROMPT — Part 4 (AI-Optimized): WOW-Visuals + Конструктор + Free Sample + Ready Products + Loyalty (DTF Subdomain Only)
**Project:** dtf.twocomms.shop (TwoComms DTF)  
**Date:** 2026-02-07  
**This Part’s Purpose:** You said you “don’t see the big visual upgrades / constructor / etc.” — correct: Part 3 was the *runbook* (how to ship safely). **Part 4 is the missing “WHAT to build” for the next wave**: visual effects (Aceternity-style), a DTF-to-product constructor, free sample CTA/flow, “ready products” direction, and loyalty hooks — all *inside the current dtf subdomain*.

**Non‑negotiable:** Do **NOT** change main domain `twocomms.shop` behavior. All additions are dtf‑scoped.

---

## 0) Ground Truth: Existing Pages & UI Anchors (DTF)
Use current dtf pages as anchors for new insertions:
- Home `/` — hero “DTF друк в рулоні 60 см… 350–280 грн/м”, CTAs: “Розрахувати/Замовити”, “Потрібна допомога…”, quick calculator block, “Як це працює”, “Ціни та знижки”, “Наші роботи” preview grid, before/after blocks, requirements preview + FAQ, manager modal.
- Order `/order/` — 2 tabs (ready gang sheet / help layout), upload + preview + **preflight terminal** + risk checkbox, delivery fields, summary.
- Gallery `/gallery/` — filter tabs (Всі/Макро/Процес/Готове), placeholder cases, **before/after compare pairs** + macro hover zoom modal.
- Requirements `/requirements/` — file rules list + OK vs RISK image + template links.
- Templates `/templates/` — template download links (PDF/AI/Figma).
- Status `/status/` — tracking form (order number + phone).
- Footer links: delivery/payment, quality, contacts, legal, etc.

**MANDATORY FIRST STEP FOR THIS PART:** introduce stable DOM anchors (data attributes) so effects can be attached deterministically:
- In every template section that will receive an effect, wrap with: `data-ui="dtf:<page>:<section>"`.
- Example: hero wrapper on `/` → `data-ui="dtf:home:hero"`, CTA cluster → `data-ui="dtf:home:hero-cta"`, “Наші роботи” → `data-ui="dtf:home:works"`, etc.
Document anchors in `EFFECTS_MAP.md` (required by Part 3).

---

## 1) Delivery Strategy (Because This Is Big)
This wave must ship in controlled increments. Implement in **4 slices**, each shippable:
- **Slice A:** Free Sample (CTA + page + form) + light WOW visuals on Home.
- **Slice B:** Visual system & component pack (Aceternity-style) + apply to existing pages (Home/Order/Gallery/Requirements/Status).
- **Slice C:** Конструктор (MVP) — product selection + print placement + upload + preview + request quote.
- **Slice D:** Loyalty hooks + Cabinet pages (MVP) + Ready Products direction.

Each slice:
1) Lianer tasks created; 2) DTF_CHECKLIST updated; 3) Evidence captured; 4) Deploy via Part 3 runbook.

---

## 2) Visual Effects Library Plan (Aceternity-style, but Django + Vanilla)
**Constraint:** No React build system. Therefore implement effects as:
- **Pure CSS** (preferred)
- **Vanilla JS** + small CSS
- **HTMX partials** where needed
- Optional small vendor snippets in `dtf/static/dtf/js/vendor/` if truly needed (document in `CHANGELOG_CODEX.md`)

### 2.1 Component foldering (MUST)
Create:
- `dtf/static/dtf/js/components/`  
- `dtf/static/dtf/css/components/`

Each effect = 1 JS file + 1 CSS file (or CSS-only). Naming:
- `bg-beams.js/css`, `dotted-glow.js/css`, `text-encrypted.js/css`, etc.

### 2.2 Global init pattern (MUST)
In `dtf/static/dtf/js/dtf.js`:
- Add a global `DTF.init()` that:
  - calls `initEffects(root=document)`
  - re-calls `initEffects(evt.target)` on HTMX swaps (use `htmx:afterSwap`)
- Effects MUST be idempotent (safe to init twice). Use `data-init="1"` guards.

### 2.3 Motion control (MUST)
Respect:
- `prefers-reduced-motion: reduce` → disable heavy motion, keep static.
- Mobile: reduce effect density; prefer static backgrounds.

Implement a small utility:
- `dtf/static/dtf/js/components/motion.js` exposing `isReducedMotion()`, `isMobile()`.

---

## 3) Effect Placement Matrix (Use ALL you listed, but intelligently)
**Rule:** We do NOT “spray effects everywhere”. We place **one signature heavy effect per page**, and multiple micro-effects.

### 3.1 Home `/` (Signature = Background Beams + Ink/Grain already exists)
Add/upgrade:
1) **Background Beams** behind hero (`data-ui="dtf:home:hero"`).
2) **Flip Words / Container Text Flip** inside hero H1 subline: rotate value props (“Hot Peel”, “Ручна перевірка”, “24–48 год”, “60 см”).
3) **Encrypted Text** micro line below subheader, used as “tech proof” (e.g., “preflight checksum: OK / manager_review: pending”).
4) **Dotted Glow Background** behind “Як це працює” section to add depth without clutter.
5) **Pointer Highlight** on key trust phrases inside hero and FAQ.
6) **Images Badge** on “Наші роботи” preview cards: add badges (Макро/Процес/Готове) with hover.
7) **Compare** (before/after) block: upgrade slider visuals; make it drag-friendly on touch.
8) **Sparkles**: micro sparkle around “Hot Peel” and “без брака” callouts (VERY subtle).
9) **Stateful Buttons**: hero CTA buttons animate through idle → loading → success when they trigger scroll or open modal.
10) **Floating Dock** (desktop only) pinned lower-right: quick actions (“Замовити”, “Зразок”, “Менеджер”, “Шаблони”). On mobile keep current bottom action pattern; do not duplicate.

### 3.2 Order `/order/` (Signature = Multi‑Step Loader + Terminal polish)
You already have preflight terminal; enhance:
1) **Multi-step loader** on upload: “Upload → Preflight → Preview → Ready”.
2) **Loader (inline)** within preview area while generating PDF frame / simulation.
3) **Vanish Input** for fields with validation (phone/order etc) ONLY where it improves UX (not everywhere).
4) **Stateful Button** on submit: “Надіслати замовлення / заявку” state changes.
5) **Pointer Highlight** on the risk disclaimer and “WARN не блокує”.
6) **Resizable Navbar** (optional) ONLY inside order page as a fun micro: on scroll collapse header slightly (do NOT change global nav behavior site-wide). If it feels risky, implement as A/B-ready toggle via `data-feature="resizable-nav"`.

### 3.3 Gallery `/gallery/` (Signature = Cards on Click + Macro badge)
1) **Cards on Click**: clicking a case opens a modal with:
   - bigger images
   - description (for SEO add separate URL support later; for now modal)
2) **Images Badge**: overlays “60 см / Макро / 24–48 год”.
3) **Animated Tooltip** for “що означає Макро/Процес/Готове”.
4) **Infinite Moving Cards** (optional on gallery bottom) for “mini testimonials” or “brands we printed for” (can be placeholders now).

### 3.4 Requirements `/requirements/` (Signature = Tracing Beam doc-line)
1) **Tracing Beam** along the rules list (format/quality/errors) to make it feel like “spec doc”.
2) **Pointer Highlight** on “300 DPI”, “60 см”, “прозорий фон”.
3) **Text Generate Effect** for the page H1/H2 (subtle, once).

### 3.5 Status `/status/` (Signature = Vanish + Stateful)
1) **Vanish input** on “Номер замовлення” / “Телефон” when invalid.
2) **Stateful button** on “Перевірити” with mini spinner + success state.
3) Inline error presentation uses terminal-like style.

### 3.6 Templates `/templates/` (Signature = Tabs + Download UX)
1) Replace static links with **animated Tabs** (PDF/AI/Figma) inside one component.
2) Add an **encrypted microline** that shows “template checksum verified” to reinforce trust.

### 3.7 “About / Team” (NEW) (Signature = Animated Tooltip)
Create `/about/` for trust:
1) **Animated Tooltip** team cards (even if placeholders).
2) **3D Pin** linking to your main brand site (twocomms.shop) as proof you understand production quality.
3) Pointer highlight on “без брака”, “24/7”, “бренд‑рівень”.

---

## 4) NEW FEATURE: Free Sample (БЕЗКОШТОВНИЙ ЗРАЗОК) — CTA + Page + Flow
### 4.1 CTA placement (MUST)
Add a 3rd hero CTA on home next to:
- “Розрахувати / Замовити”
- “Потрібна допомога…”
Add:
- **“Отримати безкоштовний зразок”** (opens `/sample/` or scrolls to sample block on home then continues).

Also add a small CTA in footer quick actions.

### 4.2 Sample sizing decision (MUST implement options)
Offer a *choice* (not one size):
- **A4 sample** (default) — best cost/impact.
- **A3 sample** (optional, “для брендів/опту”) — gated by “I’m a brand / planning volume”.
- **Calibration strip 60×10 cm** (cheap) — “тест кольору і білого шару”.
Explain in microcopy that shipping via Nova Poshta is paid by receiver (or define policy).

### 4.3 `/sample/` page content blocks (MUST)
- Hero with dotted-glow background + pointer highlight.
- “Що в зразку”: materials, adhesion, wash resistance.
- “Як ми надсилаємо”: process timeline (use container text flip / text hover).
- Form (Stateful button):
  - Name, phone, city/NP branch, channel, niche, estimated monthly volume (optional).
  - Consent checkbox.

### 4.4 Backend (MUST)
Add:
- Model: `DtfSampleLead` (or reuse existing lead model if suitable).
- View + Form with spam protection (honeypot + rate limit).
- Admin: list and export.

---

## 5) NEW FEATURE: Конструктор (MVP) — DTF on готових виробах / ваші вироби
This is the “Everfox‑killer” direction. Build MVP now, expandable later.

### 5.1 Goals for MVP
- Customer chooses product (T‑shirt / hoodie / tote / “my item”).
- Chooses color + size + quantity.
- Chooses print placement: front/back/left chest/sleeve (as allowed by product).
- Upload design (PNG/PDF); reuse preflight system (already exists on /order/).
- Shows a **2D preview** on a product mock image (no real 3D yet).
- Produces an “Estimate” + “Request quote” (manager confirms).
- Saves “session” so user can come back (cookie/session or user account).

### 5.2 Routes (NEW)
- `/constructor/` (landing + choose mode)
- `/constructor/app/` (the actual builder UI)
- `/constructor/submit/` (HTMX endpoint)
- Optional: `/constructor/sessions/<id>/`

Add to sitemap only when stable.

### 5.3 UI Layout (MUST)
Use **Sidebar** pattern:
- Left sidebar = controls (steps as Tabs):
  1) Product
  2) Print
  3) Upload
  4) Delivery
  5) Summary
- Main panel = preview
- Bottom sticky = stateful primary CTA

Add a **Floating Dock** (desktop) inside constructor for “Help / Manager / Requirements”.

### 5.4 Data model (MVP)
Implement minimal:
- `DtfBuilderSession`:
  - user (nullable), created_at, updated_at
  - product_type, product_color, sizes_json, placements_json
  - upload_file (FK to existing upload model or new)
  - preflight_json
  - preview_image (generated)
  - status: draft/submitted
- `DtfProductPreset` (optional):
  - product type, allowed placements, base price, mock images.

### 5.5 Preview generation (MVP)
- Use Pillow to composite the uploaded design onto a static product mock PNG (front/back).
- Provide scale + position controls (simple):
  - scale slider
  - drag to reposition (JS)
- For “my item” mode: allow selecting a generic blank silhouette.

### 5.6 Preflight integration (MUST)
Reuse the existing preflight checks from `/order/`:
- show the same “terminal” warnings
- user must accept risk if WARN/FAIL is present (policy decision: FAIL blocks, WARN does not)

### 5.7 Submission
On submit:
- create `DtfLead`/`DtfOrder` record with “constructor payload”
- notify manager channel (existing system if any; otherwise email)
- show success screen with stateful button finishing animation

---

## 6) NEW FEATURE: “Ready Products” Direction (No Main-Domain Changes)
You want “already-made products / outsource end-to-end”.
Implement dtf‑side as:
- `/products/` (DTF subdomain) — curated landing:
  - cards for product categories (hoodies, tees, etc)
  - “we can source blanks” copy
  - not a full ecommerce checkout yet
  - CTA leads into `/constructor/` or `/order/?tab=help` (manager confirms)

Use:
- **Cards** (click-to-expand modal with spec).
- **Pointer highlight** for quality claims.
- **3D Pin** to your main brand as “proof of quality” (link only; no integration).

---

## 7) Loyalty + Cabinet (MVP, dtf-scoped)
You already have a login modal; implement dtf cabinet pages:
- `/cabinet/` home (requires auth) showing:
  - last orders
  - saved builder sessions
  - loyalty points (even if minimal now)
- `/cabinet/orders/`
- `/cabinet/sessions/`

### 7.1 Loyalty MVP rules (simple)
- Points accrue per order meterage threshold or per order count (define constants in settings).
- Add badges: “персональний менеджер” after N orders.

UI:
- Use Tabs for sections.
- Use animated tooltip for “how points work”.

---

## 8) Content & Copy updates (DTF pages)
You must make copy “more trust, less friction” without changing the “dark tech” vibe:
- Home hero microcopy: add 1 line “Ручна перевірка макета перед друком (без сюрпризів)”.
- Remove confusing “≈ ЦІНА —” states: show placeholder “Вкажіть метраж → покажемо орієнтир”.
- Add small reassurance under CTAs: “Не спамимо. Відповідь протягом робочого дня.”

Use pointer-highlight and text-hover effects for key words, but keep readability.

---

## 9) Engineering Non‑Negotiables (because effects can explode complexity)
1) No global JS framework.
2) Every effect is:
   - lazy‑initialized via IntersectionObserver
   - disabled for reduced motion
   - doesn’t block initial render
3) All new pages must use existing base layout and tokens.
4) All changes recorded via Part 3 artifacts: CHECKLIST, EFFECTS_MAP, CHANGELOG, EVIDENCE.

---

## 10) Acceptance Criteria (DoD) for Part 4
### Slice A (Free Sample)
- Home has new CTA and it works.
- `/sample/` exists, form works, stored in DB, visible in admin.
- Evidence: screenshots + curl headers + DB check.

### Slice B (Effects)
- At least 1 heavy + 3 micro effects on Home; 1 signature effect on Order; 1 on Requirements; Status updated.
- Reduced-motion works.

### Slice C (Constructor MVP)
- `/constructor/` live, can create a session, upload, see preview, run preflight, submit lead/order.
- Evidence includes a sample PNG/PDF upload and preflight terminal output.

### Slice D (Cabinet + Loyalty + Products)
- `/products/` exists and routes to constructor/order.
- `/cabinet/` shows saved sessions/orders (mock if needed, but structural).
- Loyalty points show (even if 0) with explanation tooltip.

---

## 11) What to do NOW (first Lianer tasks)
Create these tasks in order:
1) `[DTF] Add stable data-ui anchors across templates`
2) `[DTF] Add Free Sample CTA + /sample/ page + model/form/admin`
3) `[DTF] Implement effects component pack scaffolding (components folder + init + reduced-motion)`
4) `[DTF] Apply Home effects set (beams, dotted, flip, encrypted, pointer, sparkles)`
5) `[DTF] Apply Order enhancements (multi-step loader polish, stateful buttons)`
6) `[DTF] Build Constructor MVP (routes, sidebar UI, preview compositing, submit)`
7) `[DTF] Add Products landing + Cabinet MVP`

Proceed autonomously; ask user only if a business rule is truly ambiguous.

