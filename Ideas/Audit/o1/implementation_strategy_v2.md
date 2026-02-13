# Strategic Implementation Plan: Visual Effects & Architecture Optimization
**Target Audience:** AI Developer / Senior Engineer
**Context:** TwoComms DTF Shop (Django 5.x + Vanilla JS + HTMX)
**Goal:** Implement high-end visual effects and optimize background task architecture (No-Redis) while ensuring SEO and performance.

---

## 1. Architectural Pivot: Removing Redis

The current setup relies on Celery + Redis, which is overkill and costly for the current scale. We will migrate to **Huey** with **SQLite** storage.

### 1.1 Why Huey?
*   **Brokerless (sort of):** Can use the SQLite database as a queue. No separate Redis process required.
*   **Lightweight:** Perfect for shared hosting, VPS, or restricted environments.
*   **API:** Decorator-based syntax similar to Celery (`@task`, `@periodic_task`).

### 1.2 Migration Specification
1.  **Uninstall:** `celery`, `redis`, `django-celery-beat`.
2.  **Install:** `huey`, `django-huey`.
3.  **Configuration (`settings.py`):**
    ```python
    INSTALLED_APPS += ['huey.contrib.djhuey']

    HUEY = {
        'huey_class': 'huey.SqliteHuey',
        'name': 'twocomms_tasks',
        'results': True,  # Store results
        'store_none': False,
        'immediate': False,
        'utc': True,
        'filename': BASE_DIR / 'db.sqlite3',  # Share main DB or use separate 'huey.db'
    }
    ```
4.  **Task Migration:**
    *   Rewrite `storefront.tasks` from `@shared_task` to `@task`.
    *   Run worker command: `python manage.py run_huey`.

### 1.3 Alternative: Synchronous Preflight
For strict "No Background Worker" scenarios:
*   Preflight checks for files < 50MB should be **Synchronous**.
*   Use `PIL`/`Pillow` to check DPI/Dimensions immediately on upload.
*   Return JSON response directly.
*   **Benefit:** Zero infra complexity. **Drawback:** Blocks main thread (use threads or short timeout).
*   **Recommendation:** Use Huey for robustness, but optimize image checks to be fast enough to feel synchronous (or use progress bar).

---

## 2. Visual Effects Implementation (Vanilla JS + CSS)

**Constraint:** No React Runtime. No huge bundles.
**Approach:** "Leaf Component" architecture. Each effect is a standalone Class in `static/js/effects/`.

### 2.1 Multi-Step Loader (Visual "Check" Process)
**Concept:** Even if the check is fast, show a visual "validating" sequence to build trust (Gamification).
**Tech Spec:**
*   **DOM:** Container with 4-5 items (DPI, Dimensions, Color Profile, Margins).
*   **Logic (`EffectLoader.js`):**
    *   State machine: `idle` -> `checking_dpi` -> `checking_dim` -> ... -> `done`.
    *   Timers: Specific "fake" delays (e.g., 800ms per step) if the real check is instant.
    *   Animations: CSS transitions for checkmarks and progress bars.
    *   **Fallback:** If real error occurs, jump immediately to "Fail" state.

### 2.2 Before/After Comparison Slider (Clone Aceternity)
**Concept:** Overlaid images with a draggable divider.
**Tech Spec:**
*   **HTML:**
    ```html
    <div class="compare-container" style="--position: 50%">
        <img src="after.jpg" class="img-after">
        <div class="clip-wrapper">
             <img src="before.jpg" class="img-before">
        </div>
        <div class="handle"></div>
    </div>
    ```
*   **CSS:**
    *   `.clip-wrapper { clip-path: inset(0 calc(100% - var(--position)) 0 0); }`
    *   `.handle { left: var(--position); }`
*   **JS (`EffectCompare.js`):**
    *   Listen to `mousedown` / `touchstart` on handle.
    *   Update `--position` CSS variable on `mousemove`.
    *   **Autoplay Mode:** Use `requestAnimationFrame` to oscillate `--position` between 30% and 70% when in view (IntersectionObserver). Stop on interaction.

### 2.3 Infinite Moving Cards (Blog/SEO)
**Concept:** Horizontal scrolling strip of cards.
**Tech Spec:**
*   **SEO Critical:** The *original* cards must be statically present in HTML.
*   **JS Logic:**
    *   Clone the `.track` content.
    *   Add `aria-hidden="true"` to the *cloned* set (prevents duplicate content penalty).
    *   Wrap in `.scroller` with `overflow: hidden`.
*   **Animation:** CSS Keyframes `translateX` from `0` to `-50%`.
*   **Events:** Pause animation on `:hover`.

### 2.4 Placeholders & Vanish Input
**Concept:** Input label cycling + "Dissolve" effect on error/submit.
**Tech Spec:**
*   **Cycling:** `setInterval` changing `placeholder` attribute or a floating label `<span>`.
*   **Vanish Effect:**
    *   On Invalid/Submit:
    *   Canvas overlay: Capture text pixels (or approximate with predefined particles).
    *   Animate particles upward + fading out.
    *   Input text color -> transparent.

### 2.5 Speed/Tremble Effect (Text)
**Concept:** Text vibrates when hovered to imply "High Speed".
**Tech Spec:**
*   **CSS Only:**
    ```css
    @keyframes tremble {
        0% { transform: translate(0, 0); }
        25% { transform: translate(-1px, 1px); }
        50% { transform: translate(1px, -1px); }
        75% { transform: translate(-1px, -1px); }
        100% { transform: translate(0, 0); }
    }
    .text-tremble:hover {
        animation: tremble 0.1s infinite;
    }
    ```
*   **JS:** None needed.

### 2.6 Floating Dock / Sidebar (Constructor)
**Concept:** Mac-style dock with magnification.
**Tech Spec:**
*   **Container:** `display: flex`, `position: fixed` (bottom).
*   **Magnification (JS):**
    *   Track `mousemove` on container.
    *   Calculate distance from mouse X to each icon center.
    *   Map distance to `scale()` (e.g., Gaussian curve).
    *   Apply `transform: scale(...)` via inline styles or CSS variables.
*   **Mobile:** Disable magnification, use simple scale on active/touch.

---

## 3. SEO Strategy for Effects
1.  **NoJS First:** All content (Blog cards, comparison images) must be visible if JS is disabled.
2.  **Semantic HTML:** Use `<section>`, `<article>`, `<figure>` for the content wrappers.
3.  **Hiding Infrastructure:** Use `aria-hidden="true"` and `role="presentation"` for any DOM elements created purely for visual effects (clones, particles, decorative overlays).
4.  **Performance Check:** Ensure `LCP` (Largest Contentful Paint) is not delayed by effect initialization.
    *   *Technique:* Init effects inside `requestIdleCallback` or `IntersectionObserver`.

---

## 4. Implementation Steps (for coding agent)

1.  **Backend/Huey Setup**:
    *   Install packages.
    *   Create `huey_config.py`.
    *   Refactor tasks.
    *   (Optional) If user insists on "No Worker", implement synchronous logic in `views.py`.

2.  **Frontend Core**:
    *   Create `static/js/core.js` (Effect internal registry).
    *   Create `static/css/effects.css`.

3.  **Effect Implementation (Iterative)**:
    *   **Sprint 1:** Sync Preflight + Multi-step Loader (High Business Value).
    *   **Sprint 2:** Compare Slider + Infinite Cards (High Visual Value).
    *   **Sprint 3:** Vanish Input + Floating Dock (Wow Factor).

4.  **Integration**:
    *   Update `base.html` to include scripts.
    *   Add data-attributes (`data-effect="navigate-dock"`) to existing templates.

---

## 5. SSH / Deployment Note
Since the user mentioned SSH, the final deployment typically involves:
1.  `git pull`
2.  `pip install django-huey`
3.  `python manage.py migrate`
4.  `systemctl restart nginx gunicorn`
5.  **New:** `systemctl enable twocomms_huey.service` (for the background worker).

**Self-Verification:**
*   *Redis removed?* Yes, Huey/SQLite proposed.
*   *Effects covered?* Yes, all requested effects mapped to Vanilla implementation.
*   *Context 7?* Used general knowledge of these libraries (Aceternity is standard React/Framer, mapped here to Vanilla/CSS).

