# Homepage Performance Worklog

Дата: `2026-04-20`

## Проверенные факты

- Repo pinned to `Django==5.2.11` in [twocomms/requirements.txt](/Users/zainllw0w/TwoComms/site/twocomms/requirements.txt:2). Упоминание Django 6 в задаче не соответствует текущему коду.
- Production homepage still returns fast HTML; prior audit and current headers indicate client path remains the main bottleneck.
- Production static/font assets currently return `cache-control: public, max-age=604800` (7 days), not the 6-12 month intent described in code/config.

## Что уже подтверждено как сделанное

- Inter `400/700` dedupe implemented between [base.html](/Users/zainllw0w/TwoComms/site/twocomms/twocomms_django_theme/templates/base.html:171) and [fonts.css](/Users/zainllw0w/TwoComms/site/twocomms/twocomms_django_theme/static/css/fonts.css:1).
- Font Awesome disabled on homepage via [index.html](/Users/zainllw0w/TwoComms/site/twocomms/twocomms_django_theme/templates/pages/index.html:22).
- `data-device-class` detector exists in [base.html](/Users/zainllw0w/TwoComms/site/twocomms/twocomms_django_theme/templates/base.html:121).
- Home-only code split already exists in [main.js](/Users/zainllw0w/TwoComms/site/twocomms/twocomms_django_theme/static/js/main.js:1622).
- Card equalization is already disabled for mobile / low devices in [homepage.js](/Users/zainllw0w/TwoComms/site/twocomms/twocomms_django_theme/static/js/modules/homepage.js:455).

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
6. Done: alias Inter `500/600` to already critical `400/700` files to stop loading extra Medium/SemiBold font assets on mobile homepage visits.
7. In progress: continue with next-layer payload reductions and server/runtime hot spots that are still safe without Redis/Celery.

## Верификация после правок

- `DEBUG=1 SECRET_KEY=test python -m unittest tests.test_template_source_guards` — passed.
- `DEBUG=1 SECRET_KEY=test python twocomms/manage.py test storefront.tests.test_homepage_pagination_assets --verbosity 2` — passed.
- Production curl re-check confirmed the original CSRF mismatch symptom before the fix: cookie changed each request, while cached meta token stayed constant.
