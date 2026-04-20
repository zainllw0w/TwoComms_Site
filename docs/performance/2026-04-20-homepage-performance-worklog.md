# Homepage Performance Worklog

Дата: `2026-04-20`

## Проверенные факты

- Repo pinned to `Django==5.2.11` in [twocomms/requirements.txt](/Users/zainllw0w/TwoComms/site/twocomms/requirements.txt:2). Упоминание Django 6 в задаче не соответствует текущему коду.
- Production homepage still returns fast HTML; prior audit and current headers indicate client path remains the main bottleneck.
- Production static/font assets currently return `cache-control: public, max-age=604800` (7 days), not the 6-12 month intent described in code/config.
- Production static serving is mixed: `static/CACHE/css/...` and `static/dtf/css/...` already return `max-age=15552000, immutable`, while top-level `static/js/*.js` and `static/fonts/*.woff2` still come back as `max-age=604800` from LiteSpeed.

## Что уже подтверждено как сделанное

- Inter font loading is now fully unified in [base.html](/Users/zainllw0w/TwoComms/site/twocomms/twocomms_django_theme/templates/base.html:246): weights `400/500` reuse `Inter-Regular.woff2`, weights `600/700` reuse `Inter-Bold.woff2`, and the old standalone `fonts.css` layer was removed to stop duplicate font downloads.
- Font Awesome disabled on homepage via [index.html](/Users/zainllw0w/TwoComms/site/twocomms/twocomms_django_theme/templates/pages/index.html:22).
- `data-device-class` detector exists in [base.html](/Users/zainllw0w/TwoComms/site/twocomms/twocomms_django_theme/templates/base.html:121).
- Home-only code split already exists in [main.js](/Users/zainllw0w/TwoComms/site/twocomms/twocomms_django_theme/static/js/main.js:1622).
- Card equalization is already disabled for mobile / low devices in [homepage.js](/Users/zainllw0w/TwoComms/site/twocomms/twocomms_django_theme/static/js/modules/homepage.js:455).
- `effects-lite` is now enabled for `mid` devices in [base.html](/Users/zainllw0w/TwoComms/site/twocomms/twocomms_django_theme/templates/base.html:218), while `perf-lite` remains reserved for `low` devices only.
- DTF mobile dock keeps horizontal centering during entrance animation in [animations.css](/Users/zainllw0w/TwoComms/site/twocomms/dtf/static/dtf/css/components/animations.css:151).
- Homepage no longer starts Microsoft Clarity from the idle path; [analytics-loader.js](/Users/zainllw0w/TwoComms/site/twocomms/twocomms_django_theme/static/js/analytics-loader.js:900) now arms it only after the first real interaction on `/`.
- Homepage no longer starts Ahrefs from a no-interaction timeout on `/`; the script in [base.html](/Users/zainllw0w/TwoComms/site/twocomms/twocomms_django_theme/templates/base.html:100) is now interaction-only for the home route.
- Homepage no longer pulls external `bootstrap.min.css`; [base.html](/Users/zainllw0w/TwoComms/site/twocomms/twocomms_django_theme/templates/base.html:159) now switches `/` to a local [bootstrap-home-subset.css](/Users/zainllw0w/TwoComms/site/twocomms/twocomms_django_theme/static/css/bootstrap-home-subset.css:1) extracted from Bootstrap 5.3.3, so the route keeps the original cascade order without a hand-maintained compatibility block in [home.css](/Users/zainllw0w/TwoComms/site/twocomms/twocomms_django_theme/static/css/home.css:1).
- Mobile bottom-nav no longer uses scroll-adaptive hide/show on phone-sized screens; [main.js](/Users/zainllw0w/TwoComms/site/twocomms/twocomms_django_theme/static/js/main.js:1077) now keeps the dock static for `max-width: 768px`, while [styles.css](/Users/zainllw0w/TwoComms/site/twocomms/twocomms_django_theme/static/css/styles.css:10309) removes the mobile blur / translate-heavy motion that was the strongest jank suspect.
- Runtime heavy-effect relaxation no longer mutates `backdrop-filter` during scroll; [main.js](/Users/zainllw0w/TwoComms/site/twocomms/twocomms_django_theme/static/js/main.js:1285) now limits that path to pausing infinite animations only.
- Guard tests in [test_template_source_guards.py](/Users/zainllw0w/TwoComms/site/tests/test_template_source_guards.py:1) now resolve files from the active checkout instead of a hardcoded absolute repo path, so worktree validation checks the edited tree, not another clone.

## Что остаётся проблемным

- Image fallback to original media still exists if optimized variants are absent in [responsive_images.py](/Users/zainllw0w/TwoComms/site/twocomms/storefront/templatetags/responsive_images.py:243).
- Anonymous page cache was serving a stable `<meta name="csrf-token">` value while production `csrftoken` cookies changed per request. This was confirmed against `https://twocomms.shop/` and had to be fixed before further cache work.
- Homepage still receives global [main.js](/Users/zainllw0w/TwoComms/site/twocomms/twocomms_django_theme/templates/base.html:927), [bootstrap bundle](/Users/zainllw0w/TwoComms/site/twocomms/twocomms_django_theme/templates/base.html:924), and the critical CSS bundle is still significantly larger than the visible-above-the-fold need.
- Production static/media cache TTL on the live host is still 7 days despite code/config intending long-lived immutable caching. That mismatch likely sits in the hosting layer rather than Django code alone.

## Текущий план правок

1. Done: remove premature analytics fallback and defer non-critical analytics more aggressively on homepage.
2. Done: simplify bottom-nav behavior on weaker/mobile devices to reduce scroll jank.
3. Done: replace remaining forced reflow panel-open paths with animation-safe scheduling.
4. Done: remove session-bound CSRF/sync hints from cached anonymous HTML and switch sync hints to client-side persisted flags.
5. Done: defer Ahrefs alongside other non-critical analytics and bump cache-busting versions for changed JS entrypoints/modules.
6. Done: alias Inter `500/600` to already critical `400/700` files and remove the extra `fonts.css` layer so the same font files are not downloaded twice under different URLs.
7. Done: turn on `effects-lite` for mid-tier devices to reduce blur/glow/compositing pressure without dropping into the harsher `perf-lite` mode.
8. Done: fix DTF mobile dock transform so entrance animation preserves `translateX(-50%)` and does not visually jump.
9. Done: keep Clarity off the homepage idle path so bounce visits do not pay that script cost without any user interaction.
10. Done: keep Ahrefs off the homepage timeout path; it now loads on `/` only after real interaction.
11. Done: remove homepage dependency on external `bootstrap.min.css` and replace it with a local route-scoped extracted subset in `css/bootstrap-home-subset.css`.
12. Done: fix source-guard tests so they validate the current checkout/worktree instead of a stale absolute path.
13. Done: make the mobile bottom-nav static on phone-sized screens and remove scroll-time `backdrop-filter` mutations from the runtime optimizer.
14. In progress: continue with next-layer payload reductions and server/runtime hot spots that are still safe without Redis/Celery.

## Верификация после правок

- `DEBUG=1 SECRET_KEY=test python -m unittest tests.test_template_source_guards` — passed after both font-dedupe and mobile-effects changes.
- `DEBUG=1 SECRET_KEY=test python twocomms/manage.py test storefront.tests.test_homepage_pagination_assets tests.test_template_source_guards --verbosity 2` — passed.
- Additional browser verification captured `mid/lower/footer` mobile and `lower` desktop states against the exact homepage bootstrap subset, plus a live-simulation pass with local `main.js` and the new bottom-nav mobile CSS overrides. The lower-page/footer layouts remained aligned with production while the mobile dock stayed visually stable.
- Production curl re-check confirmed the original CSRF mismatch symptom before the fix: cookie changed each request, while cached meta token stayed constant.
- Production after `72e7f848` deploy: homepage switched to `/static/CACHE/css/output.7ad7d9273725.css`, `fonts.css` disappeared from HTML, and the live CSS bundle no longer contains `Inter-Medium.woff2`, `Inter-SemiBold.woff2`, or querystring variants of `Inter-Regular/Bold`.
- Fresh Lighthouse after the font dedupe deploy: `performance 0.80`, `FCP 1.4s`, `LCP 4.6s`, `TBT 110ms`, `CLS 0.002`. Before that pass, the same flow measured roughly `performance 0.67`, `FCP 2.6s`, `LCP 10.1s`.
- Fresh Lighthouse after enabling `effects-lite` for `mid` devices and moving homepage Clarity off the idle path: `performance 0.82`, `FCP 1.4s`, `LCP 4.5s`, `TBT 50ms`, `CLS 0.001`.
