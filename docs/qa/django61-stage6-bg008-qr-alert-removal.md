# Django 6.1 Stage 6: QR alert removal

Date: 2026-08-18

Scope: `DJ6-BG-008`

## Decision

The QR thank-you route no longer owns a daemon thread or a Telegram admin
alert. The discarded alert only recounted the same QR page views already
persisted by analytics and had no durable owner, retry, or reconciliation
contract. No task queue, cron job, model, migration, or replacement alert was
added.

The route continues to issue and reuse the QR promo, set the signed
`twc_qr_promo` cookie with its existing salt, return `200` with
`X-Robots-Tag: noindex, nofollow`, and create ordinary `PageView` analytics
records through the existing middleware.

## Focused Regression Evidence

The new `storefront.tests.test_qr_thanks` contract made two real client GET
requests to `/qr/` under the no-network, non-DTF settings profile. It verifies
one `PromoCode`, one `QrDeviceGrant`, signed-cookie reuse, and two non-bot
`PageView` records. It also asserts that no `qr_scan_notified` session key or
`threading.Thread` call remains.

Before the production change, the contract failed at the expected legacy
session marker:

```text
AssertionError: 'qr_scan_notified' unexpectedly found in session
```

After the change:

```bash
TWC_PYTHON="$(cd "$(git rev-parse --git-common-dir)/.." && pwd)/.venv/bin/python"
cd twocomms
"$TWC_PYTHON" manage.py test storefront.tests.test_qr_thanks \
  --settings=test_settings_no_network_non_dtf --noinput -v 1
```

Result: `Ran 1 test ... OK`; Django system check reported no issues.

## Boundaries

This is local source and regression-test evidence only. No historical alert
volume/value measurement, production smoke, deployment, server access, or
database migration was performed. Stage 6 worker, task-backend, and exit-gate
items remain open.
