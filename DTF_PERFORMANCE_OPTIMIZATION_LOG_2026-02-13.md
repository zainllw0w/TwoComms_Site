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

## Unified Git Tree (as of 2026-02-13)

```text
* bc8171a (HEAD -> codex/codex-refactor-v1, origin/codex/codex-refactor-v1) fix: keep twocomms/passenger_wsgi.py unchanged for deploy
* e974368 perf: unify full tree and optimize dtf load path
* cfb2497 Inline critical ambient and reveal bootstrap
* 51329f6 Prioritize ambient boot and smooth canvas handoff
* e419105 Tighten reveal trigger timing for fast scroll
* 16ba95a Optimize ambient startup and remove deferred reveal gaps
* 46fe28e Delay ambient background activation until interaction window
* 0cd3722 Improve DTF first paint with progressive hero and deferred ambient FX
* 015155c Rename DTF bundles to dash names for static serving
* 8ad7cdc Optimize DTF first-load rendering path and media payload
* 41fb7e5 Tune home dot background feel and response
* c7b4bba Restore side manager FAB and modal
* 37ad67b fix(dtf): align effects, docks, and preflight UX
* 38b0953 DTF: ефекти O2 — Compare parity, Infinite Cards SEO, Multi-step Loader, Vanish Input, Floating Dock, Speed Text, Tooltip/Text-generate/Images-badge
* d355a47 fix: add www.dtf.twocomms.shop to ALLOWED_HOSTS
* c24b907 dtf: defer home background init to idle
* 75039cd dtf: remove status/help from mobile dock
* 22efdfa dtf: move dot effect to home background and optimize render loop
* 0f44c52 dtf: render mcp-style dot distortion on hero canvas
* fe52904 dtf: switch home background to interactive dot distortion
```

## Post-Deploy Notes (2026-02-15)

### Server sync and conflict handling
- Deployment branch `codex/codex-refactor-v1` was behind by 2 commits.
- `git pull` failed due untracked-overwrite conflicts.
- Moved conflicting untracked files to server backup folder:
  - `.untracked_backup_20260215_003548/`
  - moved files count: `91`
- After move, server pull completed to latest branch head.

### Emergency runtime fixes
- `fix: restore clear_cart view export and behavior` (`33abc5b`)
  - Added missing `clear_cart` view in `storefront/views/cart.py`.
- `fix: export missing storefront view handlers for urls` (`44e8fee`)
  - Restored missing exports in `storefront/views/__init__.py` for:
    - `cart_items_api`, `contact_manager`
    - `order_success`, `order_success_preview`, `update_payment_method`, `confirm_payment`
    - `monobank_create_invoice`
    - survey handlers (`survey_*`)
    - `uaprom_products_feed`
- Result: `python manage.py check` on production passes with `0 issues`.

### Production verification
- `python manage.py migrate --noinput`: no pending migrations.
- `python manage.py collectstatic --noinput`: static updated (`25 copied`, `420 unmodified`).
- Cache probe in production shell:
  - `CACHE_BACKEND=django.core.cache.backends.filebased.FileBasedCache`
  - `cache.set/get` now returns expected value (`ok`).

### Current external TTFB snapshot (n=20 per URL)
- `/`: avg `0.428s`, p50 `0.147s`, p95 `1.037s`, slow>=0.5s `7/20`
- `/about/`: avg `0.465s`, p50 `0.142s`, p95 `1.029s`, slow>=0.5s `8/20`
- `/blog/`: avg `0.454s`, p50 `0.209s`, p95 `1.078s`, slow>=0.5s `7/20`
- `/order/`: avg `0.442s`, p50 `0.089s`, p95 `1.229s`, slow>=0.5s `7/20`
- `/gallery/`: avg `0.466s`, p50 `0.190s`, p95 `1.072s`, slow>=0.5s `7/20`

### Interpretation
- Frontend updates are live (`dtf.js?v=20260213h`, lens AVIF source, beams removed).
- Cache backend misbehavior is fixed.
- Main unresolved bottleneck remains intermittent backend latency spikes (~1s bucket), likely outside static/JS path.

## Deep Profiling Pass (2026-02-15)

### Implemented additional fixes
- `perf: reduce request-path and tracking-update overhead` (`31ca17d`)
  - `twocomms/orders/nova_poshta_service.py`:
    - `update_all_tracking_statuses()` now excludes final statuses: `done`, `cancelled`.
  - `twocomms/twocomms/middleware.py`:
    - `SimpleRateLimitMiddleware` skips `GET/HEAD/OPTIONS` for `dtf.*` host.
  - `twocomms/twocomms/production_settings.py`:
    - DB `CONN_MAX_AGE` defaults increased from `60` to `300` (env-overridable).

- `perf: skip final-status orders in tracking update command` (`9eda77e`)
  - `twocomms/orders/management/commands/update_tracking_statuses.py`:
    - command-level queryset now also excludes `done`, `cancelled`.

- `chore: add opt-in dtf request tracing headers` (`7eba32b`)
  - Added `RequestTraceMiddleware` (enabled per request via `X-DTF-Debug: 1`).
  - Returns debug headers for `dtf.*`:
    - `X-App-Pid`
    - `X-App-Django-Ms`
    - `Server-Timing: django;dur=...`

- `perf: defer heavy visual layers until idle on dtf` (`8c7e7b6`)
  - `twocomms/dtf/static/dtf/js/dtf.js`:
    - added deferred `fx-ready` activation (idle or first user intent).
  - `twocomms/dtf/static/dtf/css/dtf.css`:
    - heavy film/noise/aurora layers now disabled until `body.fx-ready`.
  - `twocomms/dtf/templates/dtf/base.html`:
    - asset bumps to `dtf.css?v=20260215a`, `dtf.js?v=20260215a`.

### Server operational changes
- Cron normalization:
  - removed duplicated `update_tracking_statuses` jobs (`* * * * *` and `*/5 * * * *`).
  - left single guarded job:
    - `*/10 * * * * flock ... update_tracking_statuses`
  - added warmup ping:
    - `*/2 * * * * flock ... curl https://dtf.twocomms.shop/about/`
  - crontab backups:
    - `crontab_backup_20260215_013732.txt`
    - `crontab_backup_cleanup_20260215_013752.txt`
    - `crontab_backup_warmup_20260215_014743.txt`

### Key profiling result (root-cause isolation)
- With `X-DTF-Debug: 1`, slow external TTFB bursts (`~0.95–1.10s`) show:
  - `X-App-Django-Ms` around `~6–9 ms` (fast app execution),
  - same behavior across multiple worker PIDs.
- This proves the ~1s spikes are **outside Django app runtime** (hosting/web-server layer queue/throttle under rapid synthetic request bursts).
- Under human-like pacing (1-second interval), measured TTFB becomes stable:
  - sample: avg `~0.077s`, slow>=0.5s `0/12`.

### Deployment/restart caveat
- `touch twocomms/passenger_wsgi.py` is blocked (`Operation not permitted`) on this host.
- Reliable runtime refresh path used in this pass:
  - write `public_html/tmp/restart.txt`
  - if needed, gracefully terminate stale app PIDs observed via debug headers, then re-hit site.

## Hero Scan Smoothing Pass (2026-02-15)

### Implemented
- `dtf/static/dtf/js/dtf.js`
  - `initPrintheadScan()` now defers `scan-animate` start until `body.fx-ready`.
  - Added safe fallback timer (`1600ms`) so scan still starts even if class observer does not fire.

- `dtf/static/dtf/css/dtf.css`
  - For home page before `fx-ready`, disabled heavy hero ambient animations:
    - `hero::before`, `hero-bg`, `scan-hero::after`, `hero-media::after`, `hero-card::after`
  - Kept static visual baseline so Hero remains visible without hard pop-in.

- `dtf/templates/dtf/base.html`
  - cache-bust updates:
    - `dtf.css?v=20260215b`
    - `dtf.js?v=20260215b`

### Goal
- Remove perceived “late rays/scan lag” on first 1–2 seconds.
- Keep same design language while moving expensive hero animation work to idle/intent phase.

## Conditional Bundle Loading Pass (2026-02-15)

### Implemented
- `twocomms/dtf/views.py`
  - Added per-template flags in `_render()`:
    - `dtf_load_effects`
    - `dtf_load_htmx`
  - Introduced template allow-lists:
    - `DTF_EFFECTS_TEMPLATES`
    - `DTF_HTMX_TEMPLATES`

- `twocomms/dtf/templates/dtf/base.html`
  - `effects-bundle.css` now loads only when `dtf_load_effects=True`.
  - `core.js`, `_utils.js`, `motion.js`, `effects-bundle.js` now load only when `dtf_load_effects=True`.
  - `htmx.min.js` now loads only when `dtf_load_htmx=True`.
  - Asset bump:
    - `dtf.css?v=20260215c`
    - `dtf.js?v=20260215c`

### Typography constraint
- Font stack intentionally unchanged:
  - `Space Grotesk`
  - `Manrope`
  - `JetBrains Mono`
- Google Fonts configuration and visual typography are preserved.

## Local Fonts Hosting Pass (2026-02-15)

### Implemented
- Added local static font files under:
  - `twocomms/dtf/static/dtf/fonts/google/`
- Added local font-face bundle:
  - `twocomms/dtf/static/dtf/css/fonts-local.css`
  - generated from the same Google Fonts CSS2 query used before:
    - `Space Grotesk` (400/500/600/700)
    - `Manrope` (400/500/600/700)
    - `JetBrains Mono` (400/500/600)
- Updated base template:
  - removed `fonts.googleapis.com` / `fonts.gstatic.com` links
  - replaced with local preload + noscript stylesheet:
    - `dtf/css/fonts-local.css?v=20260215a`

### Result
- Typography remains visually identical (same families/weights/subsets),
- but font loading is now fully local from DTF static, without external font DNS/TLS requests.

## Nova Poshta / Telegram Reliability Pass (2026-02-15)

### Diagnostics
- `nova_poshta_cron.log` showed repeated API throttling (`Rate limit exceeded`) and long periods with no status updates.
- Current production data snapshot:
  - orders with TTN: `13`
  - active by previous filter (`status not in done/cancelled`): `0`
  - orders with TTN + user `telegram_id`: `0`
- Result: personal Telegram shipment notifications could not be delivered for TTN orders.

### Implemented fixes
- `twocomms/orders/nova_poshta_service.py`
  - Added admin fallback for shipment status notifications when:
    - order has no user,
    - user has no profile,
    - user has no `telegram_id`,
    - personal Telegram send failed/raised exception.
  - Added helper `_send_admin_tracking_fallback(...)`.

- `twocomms/orders/nova_poshta_service.py`
  - Refined TTN update queryset:
    - exclude only `cancelled`,
    - exclude `done` **only** when `shipment_status` already indicates received (`icontains='отримано'`).
  - This allows re-checking `done` orders with non-final/bad shipment statuses (e.g. `Номер не знайдено`).

- `twocomms/orders/management/commands/update_tracking_statuses.py`
  - Aligned queryset logic with service (same refined exclusion rules).
