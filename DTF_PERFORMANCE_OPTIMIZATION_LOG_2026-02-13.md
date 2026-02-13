# DTF Performance Optimization Log (2026-02-13)

## Goal
Maximally reduce perceived and real load latency for `https://dtf.twocomms.shop` (especially home hero + ambient), without visual breakage.

## Scope
- Verified third-party audit (`extended_audit_v3.md`) against real code and production behavior.
- Performed independent measurement of multiple DTF pages.
- Implemented server + frontend optimizations in one integrated pass.

## Baseline (before deploy of this patch)

### Production checks
- Cache backend on server was `django_redis` for `default/fragments/staticfiles`.
- Repeated probe: `cache.set(...)` succeeded but `cache.get(...)` returned `None` for all keys.
- `SESSION_ENGINE` was `django.contrib.sessions.backends.cached_db`.

### Latency pattern (independent)
- Across multiple URLs and repeated requests, observed bimodal TTFB:
  - fast bucket: ~0.05–0.11s
  - slow bucket: ~0.95–1.15s
- Example (`/about/`, n=40): avg `0.458s`, p50 `0.060s`, p95 `1.050s`, slow requests (`>=0.5s`) `17/40`.

### Frontend findings
- Home page loaded heavy `lens-macro-1.jpg` early via `data-lens-src` even when visually not needed initially.
- Hero scan effect introduced delayed visual activation after JS boot.
- Beam effect (“rays”) added extra visual noise and animation load.
- Dot-canvas ambient initialized early; moved to deferred strategy.

## Implemented Changes

### 1) Server-side performance and isolation

#### Cache/session strategy hardening
- `twocomms/twocomms/production_settings.py`
  - Added `CACHE_BACKEND` strategy switch:
    - `file` (default)
    - `redis` (explicit opt-in)
    - `locmem` (optional)
  - Implemented file-based cache locations for `default/staticfiles/fragments` with auto-create + fallback to project-local `.cache` directory.
  - Session backend default changed to `django.contrib.sessions.backends.db` (env-overridable).
  - `cached_db` remains possible via env override.

#### DTF host-aware middleware exclusions
- `twocomms/storefront/tracking.py`
  - `SimpleAnalyticsMiddleware`: skip for `dtf.*` host.
- `twocomms/storefront/utm_middleware.py`
  - `UTMTrackingMiddleware`: skip for `dtf.*` host.
- `twocomms/orders/nova_poshta_middleware.py`
  - `NovaPoshtaFallbackMiddleware`: skip fallback checks for `dtf.*` host.
- `twocomms/storefront/context_processors.py`
  - `orders_processing_count`: skip for `dtf.*` host.

#### Redirect fallback optimization for DTF
- `twocomms/twocomms/middleware.py`
  - Removed duplicate `dtf.*` branch in `SubdomainURLRoutingMiddleware`.
  - Added `SubdomainRedirectFallbackMiddleware` (bypasses redirect DB lookup on `dtf.*`).
- `twocomms/twocomms/settings.py`
  - Replaced `django.contrib.redirects.middleware.RedirectFallbackMiddleware` with `twocomms.middleware.SubdomainRedirectFallbackMiddleware`.

### 2) Frontend load/perceived-speed optimization

#### Hero and ambient
- `twocomms/dtf/static/dtf/js/dtf.js`
  - `enable_printhead_scan` default changed to `false`.
  - `initPrintheadScan()` now keeps static hero when feature disabled or reduced-motion.
  - Added `scheduleHomeDotBackground()`:
    - defers heavy canvas ambient init to `requestIdleCallback` (or timeout fallback),
    - runs earlier on first user intent (`pointermove`/`touchstart`/`keydown`).
  - `initCritical()` no longer starts heavy ambient/tilt/spotlight immediately.
  - Initial full `initAll(document)` now runs deferred (idle/short timeout), reducing first-frame pressure.

#### Remove rays and heavy early lens source
- `twocomms/dtf/templates/dtf/index.html`
  - Removed hero beam markup block.
  - Removed `bg-beams` effect from hero section.
  - Changed home lens source from full-size JPG to optimized AVIF (`lens-macro-1-768.avif`).

#### Cache-bust for updated JS
- `twocomms/dtf/templates/dtf/base.html`
  - Bumped `dtf.js` query version to `20260213h` in preload + script include.

## Validation Runbook

### Completed local/static checks
- Python syntax compile check on changed backend files: **OK**.
- JS syntax check (`node --check`) for `dtf.js`: **OK**.

### Deployment checks (to run after push/deploy)
1. Verify cache behavior in production shell:
   - `cache.set/get` for `default` and `fragments` should return stored value.
2. Verify middleware list and host-aware skips on `dtf.*`.
3. Re-run TTFB sampling (n>=20 per key URL):
   - expected: strong reduction of slow bucket frequency.
4. Check home network waterfall:
   - `lens-macro-1.jpg` should no longer be early critical fetch.
5. Visual QA:
   - hero appears immediately, no delayed scan/rays,
   - ambient remains visually consistent and responsive.

## Open Follow-ups / Next Branches
- Evaluate conditional loading of `effects-bundle.js` for non-effect pages.
- Optionally self-host fonts (remove Google Fonts dependency).
- Investigate persistent `csrftoken` set on every response (cacheability impact).
- Add explicit DTF-only middleware stack in settings for cleaner long-term architecture.
- Re-check whether any main-site integrations leak to DTF path at runtime.

## Notes
This log is intended as continuation context for future agents/sessions when context window resets.
