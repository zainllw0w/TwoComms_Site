# Management Statistics Flow Map QA

Date: 2026-08-07
Branch: `codex/management-stats-flow-visual`
Local QA URL: `http://127.0.0.1:9876/bot/`

## Scope

The legacy funnel bars were replaced with a two-lane event flow map. The map renders absolute server-provided counts, explicit advanced/drop-off/in-progress facts, proportional rails, and a compact detail surface opened from each stage. It avoids conversion percentages for non-monotonic event signals and hides filled rails for zero values.

## Automated verification

- `management.tests_ig_stats_visuals`: 41 tests, OK.
- `ClientWorkspaceTemplateContractTests` plus inline JavaScript syntax contract: 78 tests, OK.
- `python manage.py check --settings=test_settings`: OK.
- `python manage.py makemigrations --check --dry-run --settings=test_settings`: no changes detected.
- `python -m compileall -q management`: OK.
- `git diff --check`: OK.

The Django test process emits the existing `COMPRESS_OFFLINE` manifest warning and the test-only missing `staticfiles/` warning; neither is a failure and neither is introduced by this change.

## Browser verification

Authenticated QA session: `statsflow`, user `stats-qa`.

| Scenario | Result |
| --- | --- |
| Today / populated | Non-zero nodes and rails rendered; largest explicit drop-off highlighted amber; paid stages green only when non-zero. |
| Custom `2026-08-01` to `2026-08-07` | 10 event nodes, non-zero facts rendered, no horizontal overflow at 390px. |
| Custom `2036-08-05` to `2036-08-05` | No `[data-flow-map]`; compact message `За вибраний період подій ще не зафіксовано.`; card height 236px at 390px. |
| `Увесь час` | Dense layout, `rangeDays=30`, 10 event nodes. |
| Stage interaction | Click opens detail, repeated click closes it, Escape closes and returns focus, outside click closes. |
| Reduced motion | Existing reduced-motion contract disables flow transitions/animations. |
| 1440px | Flow card and advertising flow use full available row width. |
| 768px | Flow map width 642px, minimum node 122px, `body.scrollWidth=768`. |
| 390px | Flow map width 296px, minimum node 144.5px, `body.scrollWidth=390`. |
| 320px | Flow map width 226px, minimum node 110.5px, `body.scrollWidth=320`; navigation scrolls inside its own region. |

## Screenshots

- [Desktop flow map](/Users/zainllw0w/.config/superpowers/worktrees/site/codex-management-stats-flow-visual/output/playwright/stats-flow-final-1440.png)
- [Desktop opened stage](/Users/zainllw0w/.config/superpowers/worktrees/site/codex-management-stats-flow-visual/output/playwright/stats-flow-final-detail-1440.png)
- [Custom populated range](/Users/zainllw0w/.config/superpowers/worktrees/site/codex-management-stats-flow-visual/output/playwright/stats-flow-final-custom-01-07.png)
- [Tablet 768px](/Users/zainllw0w/.config/superpowers/worktrees/site/codex-management-stats-flow-visual/output/playwright/stats-flow-final-768.png)
- [Mobile 390px](/Users/zainllw0w/.config/superpowers/worktrees/site/codex-management-stats-flow-visual/output/playwright/stats-flow-final-390.png)
- [Mobile 320px](/Users/zainllw0w/.config/superpowers/worktrees/site/codex-management-stats-flow-visual/output/playwright/stats-flow-final-320.png)
- [Empty custom range](/Users/zainllw0w/.config/superpowers/worktrees/site/codex-management-stats-flow-visual/output/playwright/stats-flow-final-empty-2036.png)

## Deployment gate

## Production release evidence

- Feature branch pushed: `codex/management-stats-flow-visual` at `54298e8f`.
- `main` integrated and pushed at `3d9976485491fa09b46adf93b91f6d16e81c2e52`.
- Production checkout: branch `main`, SHA `3d9976485491fa09b46adf93b91f6d16e81c2e52`, `HEAD...origin/main=0/0`.
- Passenger restart marker refreshed at `tmp/restart.txt` after the fast-forward pull.
- Server `python manage.py check --deploy`: exit 0 with two pre-existing security warnings (`SECURE_SSL_REDIRECT` and short `SECRET_KEY`); no application errors.
- Public `https://twocomms.shop/healthz/`: HTTP 200, JSON status `ok`.
- `https://management.twocomms.shop/bot/`: HTTP 302 to `/login/?next=/bot/`, confirming the expected staff authentication boundary.
- `https://management.twocomms.shop/healthz/`: HTTP 404 because that subdomain does not publish the public health route; this is expected and not used as the release health check.
