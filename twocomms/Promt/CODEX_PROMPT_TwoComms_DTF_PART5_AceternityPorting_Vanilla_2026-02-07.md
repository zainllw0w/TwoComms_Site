# CODEX PROMPT — Part 5 (AI-Optimized): Porting Aceternity UI Effects to Django + HTMX + Vanilla (No React)
**Project:** dtf.twocomms.shop (TwoComms DTF)  
**Date:** 2026-02-07  
**Purpose:** This document is the *engineering playbook* for implementing the “Aceternity UI” effect ideas **without React** and without introducing a front-end framework/bundler.  
You MUST integrate effects as **progressive enhancement** on top of existing Django templates, HTMX partial swaps, and the current `dtf.css`/`dtf.js` architecture.

**Related docs:** Part 3 (execution runbook) + Part 4 (what to build: WOW + constructor + sample). Part 5 focuses on **how to implement each visual effect and the shared infrastructure**.

---

## 0) Hard Constraints (MUST)
1. **No React/Vue/Next. No bundlers.** Effects must run in vanilla JS + CSS (optional tiny vendor in `/static/dtf/js/vendor/`).
2. **DTF-scoped only.** All assets under `dtf/static/dtf/`. Templates under `dtf/templates/dtf/`.
3. **Progressive enhancement:** Content must remain readable and functional without JS, and with reduced-motion.
4. **Idempotent init:** Effects MUST handle repeated init due to HTMX swaps and page transitions.
5. **Motion & performance:** Effects must be lazy-initialized, pause offscreen, and respect `prefers-reduced-motion`.

---

## 1) Shared Effect Infrastructure (Build Once, Use Everywhere)
### 1.1 Folder structure (MUST)
Create:
- `dtf/static/dtf/js/components/`
- `dtf/static/dtf/css/components/`

Naming convention:
- JS: `effect.<name>.js`
- CSS: `effect.<name>.css`

Example:
- `effect.bg-beams.js` + `effect.bg-beams.css`
- `effect.encrypted-text.js` + `effect.encrypted-text.css`

### 1.2 Base utilities (MUST)
Create a small utility library (no external deps):
- `dtf/static/dtf/js/components/_utils.js`
  - `qs(root, sel)`, `qsa(root, sel)`
  - `on(el, evt, fn, opts)` returns unsubscribe
  - `rafThrottle(fn)`
  - `clamp(v, a, b)`, `lerp(a, b, t)`
  - `inViewportObserver(callback, options)` (wraps IntersectionObserver)
  - `prefersReducedMotion()` (media query)
  - `isCoarsePointer()` (matchMedia pointer: coarse)
  - `oncePerEl(el, key)` (data guard), e.g. sets `data-init-<key>=1`

### 1.3 Effect registry + init (MUST)
In `dtf/static/dtf/js/dtf.js` implement:
- `DTF.effects = []` registry
- `DTF.registerEffect(name, selector, initFn)`
- `DTF.initEffects(root=document)`:
  - loops registry
  - finds matching nodes under `root`
  - calls `initFn(node, {root, reducedMotion, coarsePointer})`
  - ensures idempotency via `oncePerEl`

Also add HTMX re-init:
- listen `htmx:afterSwap` → `DTF.initEffects(evt.target)`
- listen `htmx:beforeCleanupElement` (if you attach window-level listeners per component, you must detach them when element removed)  
  - pattern: store cleanup fns in `el._dtfCleanup = []`, push unsub functions, run on cleanup.

### 1.4 CSS loading strategy (MUST)
- Import all component CSS into `dtf/static/dtf/css/dtf.css` (or via `@import` if you already use it).
- Keep each effect CSS isolated via attribute selectors like:
  - `[data-effect="bg-beams"] { ... }`

### 1.5 DOM anchor convention (MUST)
All effect targets MUST have:
- `data-effect="<name>"` for effect node
- `data-ui="dtf:<page>:<section>"` for stable mapping (from Part 4)

Example:
```html
<section data-ui="dtf:home:hero">
  <div data-effect="bg-beams"></div>
  <h1>DTF ...</h1>
</section>
```

---

## 2) Global UX Rules for Effects (MUST)
1. **Reduced motion:** If `prefersReducedMotion()` true:
   - no continuous animation loops
   - no aggressive transforms
   - text effects become static instantly
2. **Coarse pointer:** if `isCoarsePointer()`:
   - disable mouse-tracking hover effects
   - replace with tap-friendly alternatives or static
3. **Lazy init:** heavy effects only init when element becomes visible (IntersectionObserver).
4. **Pause offscreen:** for any RAF/canvas loop:
   - stop loop when element not intersecting
5. **No CLS:** pre-allocate sizes; never inject content above existing layout without reserved space.
6. **A11y:** text effects must not remove text from DOM; preserve semantics; add `aria-label` if necessary.

---

## 3) “Aceternity-like” Effects — Vanilla Implementation Specs
Below: each effect includes:
- **Goal & fit** (where it goes per Part 4)
- **Markup** (minimal HTML)
- **CSS approach**
- **JS approach**
- **Perf + reduced-motion**
- **A11y notes**
- **Testing checklist**

> IMPORTANT: If you can implement an effect using CSS only, do so. JS is a last resort.

---

### 3.1 Dotted Glow Background (background texture)
**Use:** Home (How it works), Sample page hero blocks, subtle section separators.  
**Markup:**
```html
<div data-effect="dotted-glow" class="dtf-dotted-glow" aria-hidden="true"></div>
```
**CSS approach:**
- Use repeating radial-gradient for dot grid.
- Add soft glow via `filter: blur()` or layered gradients.
- Set `pointer-events:none; position:absolute; inset:0;`
**JS:** none (optional slow parallax via CSS).
**Reduced motion:** N/A.
**Testing:** verify readability and contrast; ensure it doesn’t band on low-end devices.

---

### 3.2 Background Beams (hero animated beams)
**Use:** Home hero background (signature); optional on Sample page.  
**Markup:**
```html
<div data-effect="bg-beams" class="dtf-bg-beams" aria-hidden="true"></div>
```
**Implementation option A (CSS-only preferred):**
- Create 3–6 pseudo-elements with linear-gradients.
- Animate via `@keyframes` shifting background-position and opacity.
**Option B (Canvas, only if needed):**
- Draw beams as blurred lines; animate with RAF; disable on reduced motion.
**JS approach:**
- If CSS-only: JS not required.
- If Canvas: init canvas size on resize; RAF loop while visible.
**Perf:** CSS-only is cheaper; Canvas only if you require complex beam motion.
**Reduced motion:** freeze to static beams.
**Testing:** ensure no jank; check mobile; no overdraw causing battery drain.

---

### 3.3 Encrypted / Scrambled Text (text scramble)
**Use:** Home hero micro-line, Templates “checksum verified”, Trust micro proof.  
**Markup:**
```html
<span data-effect="encrypted-text" data-encrypted="preflight checksum: OK">preflight checksum: OK</span>
```
**JS approach:**
- Keep original text as final string.
- On intersection, animate scramble for 500–900ms then settle.
- Use a limited charset (`A-Z0-9#@$%`) and deterministic duration.
- Guard with `data-init` and avoid repeating.
**Reduced motion:** set final text immediately.
**A11y:** do NOT scramble `aria-label` (set `aria-label` to final). Screen readers should read stable final text.
**Testing:** ensure text is selectable; avoid layout shifts.

---

### 3.4 Images Badge (photo folder badge / overlay)
**Use:** Gallery cards, Home works preview.  
**Markup:**
```html
<div class="dtf-card">
  <img ...>
  <div data-effect="images-badge" class="dtf-badge" data-badge="Макро">Макро</div>
</div>
```
**CSS:** position badge; animate on hover with transform + opacity.
**JS:** none.
**Testing:** badges not block clicks; responsive.

---

### 3.5 Text Hover Effect (mouse-driven hover distort)
**Use:** Key words in hero, section headers, but sparingly.  
**Markup:**
```html
<span data-effect="text-hover" class="dtf-text-hover">без брака</span>
```
**JS approach:**
- On mousemove inside element, compute relative position.
- Set CSS vars `--mx`, `--my` to drive gradient mask or letter spacing.
- Use `rafThrottle` for mousemove.
**Reduced motion / coarse pointer:** disable; keep normal hover underline.
**A11y:** keep text normal.
**Testing:** ensure no CPU spikes; disable on mobile.

---

### 3.6 Compare Slider (before/after)
**Use:** Home and Gallery; Quality page if needed.  
**Markup:**
```html
<div data-effect="compare" class="dtf-compare">
  <img class="dtf-compare__before" ...>
  <img class="dtf-compare__after" ...>
  <input class="dtf-compare__range" type="range" min="0" max="100" value="50" aria-label="Compare slider">
</div>
```
**JS:** 
- Bind range input updates to CSS clip-path width.
- Add pointer drag handle for direct manipulation (mouse/touch).
**Reduced motion:** allowed (not a motion effect).
**Testing:** touch works, keyboard works, no layout shifts.

---

### 3.7 Container Text Flip / Flip Words
**Use:** Home hero subline; Sample page micro pitch; not multiple on same page section.  
**Markup:**
```html
<span data-effect="text-flip" data-words="Hot Peel|24–48 год|60 см|Ручна перевірка">Hot Peel</span>
```
**JS:** interval loop (3–4s) while visible; uses fade/translate; stops offscreen.
**Reduced motion:** pick first word only (static).
**Testing:** no CLS; ensure font metrics stable.

---

### 3.8 Container Cover (magnetic / acceleration on hover)
**Use:** CTA text or rare callouts, not body copy.  
**JS:** adjust transform based on cursor proximity; apply subtle scale.
**Disable** on coarse pointer.
**Testing:** confirm not nauseating; reduce amplitude.

---

### 3.9 Floating Dock (quick actions)
**Use:** Desktop only; inside Home and/or Constructor app.  
**Markup:** list of icons/buttons.
**JS:** handle open/close, focus trap for accessibility if expanded, or keep simple.
**Reduced motion:** minimal transitions.
**Testing:** doesn’t cover important UI; can be hidden.

---

### 3.10 Loader (inline) + Multi-Step Loader (preflight)
**Use:** Order upload/preflight area; Constructor upload; Status check.  
**JS:** show/hide via class toggles; multi-step driven by state machine (see Stateful button).
**Reduced motion:** no spinning; use opacity or progress.
**Testing:** not blocking entire page; only local widget.

---

### 3.11 Resizable Navbar (local feature flag)
**Use:** Only on Order/Constructor (optional).  
**JS:** on scroll, toggle compact class; use CSS transitions.
**Reduced motion:** instant toggle.
**Testing:** no content jumps; fixed header sizes reserved.

---

### 3.12 Pointer Highlight (animated highlight underline)
**Use:** Trust phrases across pages, Requirements key specs.  
**Implementation (CSS-only):**
- Use background linear-gradient highlight with `background-size` animation on hover or on intersection.
**JS (optional):**
- trigger highlight once on intersection.
**Testing:** not overused.

---

### 3.13 Stateful Button (finite state machine button)
**Use:** All CTAs: submit order, request sample, check status, submit constructor.  
**Markup:**
```html
<button data-effect="stateful-button" data-state="idle" class="dtf-btn">
  <span class="dtf-btn__label">Надіслати</span>
</button>
```
**JS approach:**
- Implement states: `idle → loading → success|error → idle`.
- Provide API: `DTF.Button.setState(btn, state)`.
- Ensure it integrates with HTMX requests:
  - on `htmx:beforeRequest` set loading; `htmx:afterRequest` success/error.
**A11y:** keep button label accessible; announce success via aria-live region.
**Testing:** double-click prevented; state resets.

---

### 3.14 Tracing Beam (scroll progress line)
**Use:** Requirements page, Blog month groups.  
**Implementation:**
- Use a positioned pseudo element + CSS variable for progress.
- JS calculates progress from container scroll position; update on scroll with rafThrottle.
**Reduced motion:** static line.
**Testing:** no jank on long pages.

---

### 3.15 Animated Tooltip (team, hints)
**Use:** About page, Gallery labels, maybe Cabinet loyalty explanation.  
**JS:** 
- Create a single tooltip layer appended to body.
- On hover/focus, set content + compute position using `getBoundingClientRect`.
- Clamp to viewport.
**Vendor optional:** If you must, use a tiny positioning util (but prefer homegrown).
**A11y:** use `aria-describedby` and allow focus-trigger.
**Testing:** works on keyboard; closes on ESC.

---

### 3.16 Background Beams (variant) / Background beams 2
If you need a second background style, implement as a variant of 3.2 to avoid extra code.

---

### 3.17 Cards on Click (modal)
**Use:** Gallery and Blog cards.  
**JS:** 
- Use `<dialog>` if supported, fallback to div overlay.
- Ensure focus trap.
- Integrate with HTMX partial fetch for content.
**SEO note:** do NOT rely on modal only for blog content; each article has a page URL.

---

### 3.18 Infinite Moving Cards (marquee)
**Use:** testimonials/brands ticker on home or gallery bottom.  
**CSS-only:** duplicate list and animate translateX.
**Reduced motion:** stop animation; show static list.

---

### 3.19 Placeholders and Vanish Input
**Use:** Status check fields; form micro delight.  
**JS:** on invalid, animate placeholder vanish; on valid restore.
**Reduced motion:** no vanish.

---

### 3.20 Sidebar + Tabs (constructor/cabinet)
**Use:** Constructor steps; Cabinet sections.  
**Implementation:**
- Use HTMX for step content swap OR simple JS show/hide.
- Tabs: ensure keyboard accessible (left/right arrows optional).
**Testing:** deep link to step via query param, e.g. `?step=upload`.

---

### 3.21 Sparkles (subtle particle)
**Use:** very rare accents near “Hot Peel” or “без брака”.  
**Implementation:**
- CSS-only sparkle via pseudo elements OR small canvas with limited particles.
**Reduced motion:** static.

---

### 3.22 3D Pin (link card with perspective)
**Use:** About page linking to main brand site.  
**CSS:** perspective + rotate on hover; disabled on coarse pointer.
**Testing:** not nauseating.

---

### 3.23 Text Generate Effect (type-in)
**Use:** Requirements headers, Blog article hero headings.  
**JS:** reveals letters over time; skip in reduced motion.

---

### 3.24 Text Animations Pack (generic)
**Directive:** Do not implement redundant variants. Use 1–2 text patterns and reuse.

---

## 4) Implementation Order (MUST to reduce chaos)
1) Build registry + init/re-init + reduced motion util.
2) Implement CSS-only effects first: dotted glow, badges, infinite cards, pointer highlight basic.
3) Implement core JS effects: encrypted text, compare slider, stateful button.
4) Add heavier motion: background beams (CSS or canvas), tracing beam.
5) Only then implement hover/magnetic effects and sparkles (optional).

---

## 5) Local “Effects Lab” (MUST for QA, dtf-only)
Create a dtf-only route **not in sitemap**:
- `/effects-lab/` (protected by a setting flag, or staff-only if auth exists)
This page demonstrates each effect with toggles:
- reduced motion on/off simulation
- coarse pointer simulation
- mobile width simulation (CSS)
This prevents regressions and helps future changes.

---

## 6) Testing Checklist per Effect (MUST)
For each effect you implement, verify:
- Init works on first load
- Init works after HTMX swap (if applicable)
- No memory leaks after element removed
- Reduced motion works
- Coarse pointer disables tracking effects
- No CLS introduced
- Performance: no long tasks, no continuous loops offscreen

Add test evidence in `EVIDENCE.md` (Part 3 requirement).

---

## 7) Deliverable for this Part (DoD)
You are DONE with Part 5 when:
1) `components/` scaffolding exists.
2) `DTF.registerEffect` + `DTF.initEffects` exists and is wired to HTMX.
3) At least these effects are fully implemented (as foundations):
   - dotted glow
   - bg beams (CSS)
   - encrypted text
   - compare slider
   - stateful button
   - infinite moving cards (CSS)
   - pointer highlight (CSS)
   - tracing beam (basic)
4) `EFFECTS_MAP.md` includes each effect with DOM anchors and behavior rules.
5) `/effects-lab/` exists for QA (dtf-only, non-indexed).
6) Evidence + changelog updated.

Proceed autonomously; ask user only if a business rule is ambiguous or a new dependency is unavoidable.

