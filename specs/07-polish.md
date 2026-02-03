# 07 — Polish / Perf / Analytics / Deploy (Draft)

## Device Matrix (P0)
- XS/S/M/L/T/D/W/UW breakpoints sanity check
- iOS Safari keyboard behavior on `/order`
- Android Chrome perf + touch targets

## Web Vitals (P0)
- Added lightweight instrumentation hooks (PerformanceObserver) for LCP/INP/CLS in `dtf.js`.
- Ensure Printhead Scan does not block LCP (animation after paint).

## HTMX Re-init (P0)
- Added idempotent init pattern + `htmx.onLoad` re-initialization in `dtf.js`.

## Analytics Events (P1)
- Added events: `used_printhead_scan`, `compare_interaction`, `lens_interaction`, `web_vital`.

## Deploy
- Use production deploy command after push.

## Docs
- Added root `README.md` with assets/deploy guidance (no secrets).
