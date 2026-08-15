# 09_DEPLOYMENT_LOG — production evidence

Production host: `195.191.25.63`, path
`/home/qlknpodo/TWC/TwoComms_Site/twocomms`, branch `main`, database
`qlknpodo_MySQL_DB` (MariaDB/MySQL). Secrets are intentionally omitted.

## Instagram follow intelligence and UGC lifecycle (2026-08-16)

The runtime release was fast-forwarded from `f831519a8` to code SHA
`f476223a25321d21b3af1feeff3c958b9da6722c` (feature implementation
`0eac60f05`). A subsequent documentation-only closeout was pulled separately;
it does not require a runtime restart. The production worktree had no tracked
modifications; pre-existing untracked operational artifacts were preserved.
Authentication used an ephemeral environment value sourced locally from macOS
Keychain; no credential was written to Git, command arguments, or this log.

The approved server sequence completed successfully: `git pull --ff-only`,
`migrate` (applied `management.0166_ig_ugc_reward_lifecycle`), `check`,
`collectstatic --noinput` (1048 post-processed), `compress --force`,
`seed_ig_bot_sales_playbooks` (0 created/updated/preserved), Passenger restart,
`run_instagram_bot --ensure`, bounded payment polling (0 projections/orders),
and `reconcile_ig_follow_intelligence --limit 50 --dry-run` (all selection,
delivery, and failure counters 0). Migration recorder also confirms
`storefront.0095_promocode_guest_ugc`.

Read-only MariaDB proof: all ten new follow/UGC tables are InnoDB. Unique
indexes cover capability singleton, follow/client projections and jobs, CTA
trigger/episode/sent scopes, UGC reward evidence/lifetime/order/promo, UGC
assessment source/provider digest, lifetime identity/client/reward, and
delivery reward. The production dataset currently has 298 Instagram clients but
no follow projections, CTAs, assessments, rewards, lifetime slots, reward
deliveries, lifecycle jobs, or guest-redeemable UGC promos. Duplicate episode
slots, reward/order keys, lifetime client/digests, evidence/provider
fingerprints, and ambiguous reward deliveries are all 0.

Runtime proof: bot settings are enabled with `provider_transport=instagram_login`
and `receive_via_poll=False`; cache heartbeat was present, database heartbeat
age was 0.39 seconds, and one `run_instagram_bot --forever` process was live.
The watchdog, checkout, payment, fulfillment, and Telegram reconciliation
heartbeats were fresh with zero consecutive failures. Public `/` and `/healthz/`
returned 200; management `/login/` returned 200, anonymous `/bot/` returned the
expected 302 to login, and `/bot/health/` returned 200 with no dangerous backlog.
The deployed manager template contains the follow indicator and incremental
polling code. Eighteen historical terminal analysis failures remain visible in
the health payload and were not changed by this release.

No Graph follow contract probe was run because the production database has zero
clients with explicit `opted_in_at`; no valid target exists. No synthetic
customer-message marker or test Meta event was created during deployment or
verification, and no provider send/test-event command was invoked.

## Implement2 W2.1 authoritative order lifecycle and delivery truth (2026-08-14)

The release candidate was published in `main` at exact SHA
`8d8c5d05c647c2cfcc9fb4f70d7ee206f8f0359e`. The prescribed SSH `git pull`
fast-forwarded production from `f81195895e5e7477c893ea87f6dfb277b4c82eeb`;
the targeted command
`python manage.py migrate management 0156 --noinput` then applied
`management.0156_ig_order_event_delivery_receipts` successfully. No restart,
compress, source build, overlay, fixture or provider command was run.

Read-only MariaDB proof after migration: server
`11.4.12-MariaDB-cll-lve`, migration `0156=[X]`,
`management_igordercustomerevent.provider_message_id` is `varchar(255)`,
`delivery_provider_message_ids` is `LONGTEXT` with the exact positive
`JSON_VALID` constraint. `manage.py check` reported zero issues and the
management-only `makemigrations --check --dry-run` returned
`No changes detected`.

Runtime proof: bot `state=running`, `running=True`, `daemon_online=True`,
`provider_transport=instagram_login`, `last_error=''`; dangerous backlog,
inbound/reply/notification/analysis/recovery pending queues and notification
unknown/failed/dead-letter rows are all `0`. `https://twocomms.shop/healthz/`
and `https://management.twocomms.shop/bot/health/` returned HTTP `200`.

No-send reconciliation is unchanged from the pre-pull production baseline:
canonical lifecycle messages, provider send markers and receipts remain `0`,
legacy `IgOrderCustomerEvent` rows remain `5`, and the single historical
delivered funnel fact remains `1`. No customer, Meta, payment, order,
synthetic fixture or provider event was created. The unscoped production
`makemigrations --check --dry-run` still exposes a pre-existing storefront SEO
model drift (`0095` would alter `h2`, `body_html` and `queries_json`); the
management app is clean and no unrelated migration was generated. The existing
stale compression manifest warning and 18 terminal historical analysis
failures remain bounded open evidence under `IMP-094`/`F-DEPLOY-003`.

The documentation-only closeout commit `b96d7874fba36c202ec428bb314fd8d5cfb0d286`
was subsequently fast-forwarded through the same SSH `git pull`; post-pull
`manage.py check`, migration `0156` and both health endpoints remained green.

## Implement2 W2.2 T41 disposable checkout-concurrency gate (2026-08-14)

GitHub Actions run `31761170448` verified test-only commits through
`8f4459f68` against pinned MariaDB `11.4.12-MariaDB-ubu2404`. It passed the
runner/workflow and disposable-settings contract steps, the lifecycle gate, and
the dedicated `checkout-concurrency` gate. The fresh local runner/workflow
packet is `29/29`. Exact sanitized artifact evidence reported lifecycle schema
`test_twocomms_ig_0d322be43f2f` and checkout schema
`test_twocomms_ig_f6383867aa07`, each with `cleanup=verified`. Artifact
`mariadb-gate-evidence` has digest
`sha256:12ce607d8a867317d1f4b502e0a657d465333fffb8108d9ade877129ae0570ce`.
This run includes the follow-up strict allowlist for free-form test results and
dynamic child/cleanup/CLI exception labels. No production database or
customer/provider event was used. This was the branch-stage evidence; the
final-main release proof is recorded below.

The original CI errno `1644` was a teardown-only failure caused by MariaDB
append-only delete triggers and Django's default `DELETE` flush. The test class
now invokes the existing Django flush contract with `reset_sequences=True`,
which selects `TRUNCATE` for cleanup while preserving production triggers.
Full T41 parity and the remaining `IMP-094` release gates stay open.

## Implement2 W2.2 T41 main/prod release proof (2026-08-14)

The complete seven-commit T41 sequence plus its evidence documentation is in
`main` at `9ed640b06c7324f610330d2d9b40fd3cd0e8c2b0`. Manual GitHub Actions run
`31762702125` checked out that exact SHA and passed runner/workflow and
disposable-settings contracts, lifecycle, and checkout-concurrency on pinned
MariaDB `11.4.12-MariaDB-ubu2404`. Artifact `mariadb-gate-evidence`
(`9205282515`, digest
`sha256:2598b0fc7e9acbfcc7a1d641c48a0f16d048cdf546ba151ba7b916cd0c2bab06`)
contains only the two allowlisted success lines; both generated schemas report
`cleanup=verified`.

The required project SSH `git pull` was executed and returned `Already up to
date`. Read-only production verification then showed
`HEAD == origin/main == 9ed640b06c7324f610330d2d9b40fd3cd0e8c2b0`,
`manage.py check` with zero issues, and the Instagram bot running on
`instagram_login` with fresh daemon heartbeat, zero pending/failed/unknown/
dead-letter notification rows, zero analysis backlog, and no recorded error.
The check also emitted the existing fail-safe warning that
`CACHE/manifest.json` is older than static sources; offline compression is
disabled until an approved static refresh. No prohibited restart/compress
command was run, so this remains open deployment evidence under
`F-DEPLOY-003`.

## Implement2 W2.1 T40 production rollback-fixture boundary (2026-08-13)

Production was verified at exact SHA `c09c4ab974d2dc8ff9e969b62cf36d3b117c31ce`,
with MariaDB database `qlknpodo_MySQL_DB`, vendor `mysql`, matching selected
database, and zero visible `test_*` schemas. Under the owned maintenance lease
`t40-w22-20260813`, `verify_ig_production_contract --rollback-fixtures`
returned sent/unknown/dead-letter transitions, `mid_fixture_failure_rollback=proven`,
payment-review `callback_race=proven`, `false_media_review=suppressed`,
`provider_truth=untouched`, and `transport=mocked_no_network`.

The command found no fixture rows and no `AUTO_INCREMENT` change after rollback.
The lease was released by its owner and `run_instagram_bot --ensure` restored the
singleton. No customer, payment, Meta, Telegram or other provider event was sent.
This is GREEN evidence for the T40 fixture boundary only; IMP-094, T41/disposable
MariaDB parity, and immutable current-SHA release provenance F-DEPLOY-001/003
remain open.

## Implement2 W2.1 bounded local reliability release (2026-08-13)

Commit `a8bf03bd99bbc12445dbd64cc49683a5ca5eadbf` was pushed to `main` and
pulled on production with `git pull --ff-only origin main`. The server is at
the exact SHA; tracked status is clean apart from pre-existing untracked
operational files. `migrate --noinput` reported no pending migrations through
`management.0154_synthetic_inbound_event_key`; `manage.py check` and
`makemigrations --check --dry-run` were clean apart from the known MariaDB
conditional-unique/max-length warnings. Static collection and compression
completed, Passenger restart was requested, `run_instagram_bot --ensure`
confirmed the singleton alive, and `run_instagram_bot --once` returned
`ok=True, enqueued=0, skipped=True, handled=0`.

Read-only reconciliation: `/bot/health/` returned HTTP **503** because the
health contract treats the 18 historical terminal `analysis_failed` rows as
degraded, while its JSON state still reports `bot_state=running`,
`dangerous_backlog=0`, `inbound_pending=0`,
`reply_pending=0`, `notification_unresolved=0`, `analysis_pending=0`, and
`analysis_failed=18` historical terminal rows. The host's `/healthz/` path is
not configured (HTTP 404), so no healthz claim is made. The immutable target-
SHA deploy wrapper was not bypassed; current-SHA wheelhouse/release provenance
remains open under `F-DEPLOY-001`/`F-DEPLOY-003`.

## Implement2 Wave 3 bounded `IMP-087.A` release (2026-08-13)

Commit `7ad632dec2808e8fbe036c75da848d68c41987d2` was pushed to `main` and
pulled on production with `git pull --ff-only origin main`. Server `HEAD` and
`origin/main` are exactly this SHA; tracked status is clean apart from
pre-existing untracked operational files. Migration
`management.0154_synthetic_inbound_event_key` is applied. `manage.py check`
reported no issues and `makemigrations --check --dry-run` returned
`No changes detected`.

Read-only production verification returned one live daemon with fresh DB and
daemon heartbeat, `last_error=''`, `pending=0`, `notification_pending=0`,
`analysis_pending=0`, and `analysis_failed=18` historical terminal rows.
`/bot/health/` and `/healthz/` returned HTTP 200. No production customer,
provider, payment or synthetic test event was created. The production
database was used only for migration/runtime/read-only evidence; the race and
receipt smoke ran against disposable native MariaDB 11.4, as recorded in
`14_IMPLEMENT2.md`.

Post-deploy review follow-up `ade00668c41df8a8b8b9d2bd03012a2aba1efcc9`
was pushed after rebasing on the latest `main`, including the independent
storefront migration-sequence repair. It changes only the durable delivery
state reducer and its regression: a provider result claiming `sent` with zero
validated receipt IDs now becomes `UNKNOWN`/review, not `PARTIAL`. Fresh gate:
`143/143`; Django check, migration drift, compileall and diff check are clean.
Production fast-forwarded to exact `ade00668` and then the independent
`0e6555a6`/`ad6fc927` SEO follow-ups; `migrate` had no pending work,
`management.0154` and storefront `0093`/`0094` are applied, static collection
and compression completed, and `run_instagram_bot --ensure` spawned the
singleton. Final read-only status: `running=True`, `alive=True`, fresh 0.8s
heartbeat, `last_error=''`, reply/notification/analysis pending `0/0/0`, both
health endpoints HTTP 200. No synthetic production event was created.

The documentation closeout itself was then fast-forwarded as docs-only commit
`577e711b8f2045ad0c78e944c565f7d96de43468`. The first combined deploy attempt
returned exit 137 during `migrate` under a transient server process/load spike;
no migration was pending and the code/database remained intact. The standard
`run_instagram_bot --ensure` recovery restored the singleton, after which the
exact production SHA, migration state, fresh heartbeat and both health endpoints
were rechecked successfully. This operational nuance remains separate from
the Wave 3 code proof.

## Implement2 W2.0 bounded manifest-provenance slice (2026-08-13)

Commit `c72ecf11` was pushed to `main` and pulled with the required SSH
`git pull --ff-only origin main`. Server SHA is exact
`c72ecf1160e48ba6a4d3c97c802e6f0d3c9d22dd`; tracked status is clean apart from
pre-existing untracked operational files. The focused immutable-release gate
passed `105/105` locally, including the RED/GREEN regression that rejects a
symlinked `manifest.sha256`; compileall and `git diff --check` are clean.

The production command was run only as a fail-closed boundary probe:
`../deploy.sh --target-sha c72ecf11...` exited `1` with
`ReleaseError: immutable wheelhouse target must be a real directory`, before
maintenance or checkout mutation. No source build, pip overlay, or manual
release activation was attempted. Production `manage.py check --deploy`
reported only the existing `security.W008`/`security.W009` warnings,
`makemigrations --check --dry-run` returned `No changes detected`, and
`/bot/health/` returned `200` with bot `running`, fresh heartbeat and zero
dangerous/pending/recovery queues. Current active venv/static paths remain
bound to the older `157e95d4` release; current target wheelhouse and complete
release evidence are still required by `F-DEPLOY-001`/`003`.

## Implement2 W1.7 historical attachment hardening (2026-08-12)

Production runtime verification completed at `ac50e74f93e92229980e7043eeb256ac5ef24913`;
the W1.7 implementation commit `214ae4b9` is reachable through merge
`b9bab236`. Follow-up code adds the historical-provenance guard in
`_resolve_payment_media_candidates` and regressions for stale local media and
live `download_failed` ordering, and explicit `media_capture_eligible` propagation
for raw webhook joins. Fresh focused gate: `162/162` tests passed.

Read-only production MariaDB proof: migration
`management.0153_owned_ig_message_media` is applied; 2,522 Instagram messages
(337 webhook), 29 structured attachment rows, all persisted media
`historical_import`/`metadata_only`, no `live_webhook`/`owned` media, and zero
`media_capture_eligible` rows. Daemon heartbeat is healthy and current schema
queries succeed. No post-migration live analysis job exists, so the telemetry
contract is not claimed from a synthetic production event; `F-AI-018` remains
open under `IMP-044`.

The normal SSH `git pull` path fast-forwarded production through `61486616`
and the subsequent SEO commits `f062a3b1`/`a27bdc2b`/`ce1ca965`/`d8b61973`/
`ac50e74f`; the final docs-only closeout is `35f305bf`.
the W1.7 commit remains
in the deployed ancestry. The immutable release contract was exercised for
the exact latest SHA: wheelhouse manifest validation passed after removing
macOS-only `._*` transfer metadata, and the release switch correctly no-op'd
with `target SHA must differ from the live SHA` because production was already
at `ac50e74f`. The subsequent `35f305bf` commit changes only this deployment
log; no rollback or runtime mutation was needed after that guard.

## Implement2 W1.6 structured control safety (2026-08-10)

`130cd920b8d06ce0edc3b04ed5bf51dc88ed6cd4` was fast-forwarded from
`9141bce1` to production `main`. Migration
`management.0152_harden_ig_stage_prompt` applied successfully; applied history
also confirms `0151_remove_duplicate_ig_payment_protocol=[X]`. Server Django
check returned no issues, migration drift returned `No changes detected`, and
`run_instagram_bot --ensure` spawned the singleton worker on the deployed code.

Fresh local evidence on the rebased main state: 240/240 W1.6 tests, Django
check, migration drift, compileall and diff check. Production read-only prompt
probe found one stored settings row: its historical/custom stored text is not
rewritten by `0152`, while `assemble_system_instruction()` adds the hard-stage
guard and structured `reply_text`/`controls` protocol; no legacy `[PAYLINK:]`,
`[PAYMENT:]`, `[STAGE:]` or `[MANAGER]` protocol remains in runtime.

Production parser probes rejected and removed four whitespace/tab/zero-width/
truncated control forms for both structured and legacy input. Authority probes
recognized `Оплата пройшла`, `Замовлення прийнято`, `Менеджер погодив` and
`Футболка є`; `Оплата ще не підтверджена` remained a safe negative status.
`https://twocomms.shop/healthz/` and
`https://management.twocomms.shop/bot/health/` returned HTTP 200 / `ok`; bot
state is `running`, dangerous backlog and all pending queues are `0`. The 18
analysis failures are the already-recorded terminal historical rows, not a new
pending backlog. No customer, Gemini, Meta, Telegram, payment, order or
synthetic DB event was created by verification.

## Implement2 documentation release (2026-08-07)

`f327ac361dbd28299a29e0618e2cbc9e6614a8a9` fast-forwarded production from
`19f5ef70`. The release is docs-only. `deploy.sh` completed migrate (no pending
migrations), collectstatic, compress and Passenger restart. Its dependency step
again failed to build a `cffi` wheel and continued as non-fatal with the active
venv; this is open `F-TEST-002`/`IMP-094` evidence, not a successful dependency
parity claim.

Post-deploy: exact server SHA `f327ac36`, tracked status clean, Django check
0 issues, `management.0146` applied, daemon `running=True`/`alive=True`, provider
`instagram_login`, heartbeat 0.9 seconds, `last_error=''`, reply/notification/
analysis pending 0/0/0 and terminal analysis failed 18. No customer/Meta/payment
test event was created.

## Runtime/source baseline before Implement2 docs release (2026-08-07)

The synchronized starting SHA for this handoff is
`19f5ef70f20e1b3d5da5975786359fe8c7e06df4` in local `main`, `origin/main` and
production. It contains the deployed code slice `98bb160e` for payment-gated
repeat commercial episodes on top of the earlier `fbe33a68` checkpoint. The
server pull was fast-forward only; `git status --porcelain --untracked-files=no`
is empty. The production Git-root is `/home/qlknpodo/TWC/TwoComms_Site` and the
Django app lives in its `twocomms/` child. `deploy.sh` is present and executable
at that Git-root (Git blob `37c26433...`); do not diagnose it from the app child
as a missing file.

Migrations `management.0143_igfollowuptask_event_continuation`,
`management.0144_ig_inventory_allocation_lifecycle` and
`management.0145_ig_inventory_revision_safety`, plus durable commerce migration
`management.0146`, are applied. The latest recorded full local
`management warehouse` suite passed 2897 tests with 3 skipped and `OK`;
`manage.py check`, migration drift, compileall, diff checks,
static/compression and daemon ensure also passed. The production MySQL test
database gate is still blocked by missing CREATE privilege for
`test_qlknpodo_MySQL_DB`; production DB evidence is therefore read-only or
explicitly rollback-only, not a concurrency test target.
`run_instagram_bot --ensure` and `status_snapshot()` report one daemon,
`enabled=True`, `running=True`, `alive=True`, provider
`instagram_login`, heartbeat age about 0.9 seconds, empty `last_error` and zero
pending reply/notification/analysis/recovery queues.

The read-only MariaDB audit found 18 terminal `IgConversationAnalysisJob` rows.
Seventeen have `trigger=reconcile`, attempts 5 and historical Gemini failures
between 2026-07-30 and 2026-08-03. One fresh row is job `292`, client `310`,
`trigger=manager_message`, attempts 5,
`last_error=stale_lease_retry_exhausted`; it is tracked as open `F-AI-018`.
There are no pending analysis jobs. No historical job was retried and no
customer send was made during verification.

The deployed slices are `IMP-103` (commits `4dfff3a2`, `35d3bd93`), `IMP-104`
(`1f5dcb70`, `7fdbe613`, `1f8cead2`), sender-action observability
(`13bedf8f` plus boundary fix `434428ad`) and `IMP-084` availability foundation
(`17f5b672`), followed by live-visual boundary hardening
(`d3e2c51b`, `0d471ebe`, `c0f9fd1f`) and warehouse reservation lifecycle
(`90fdd0ec`), then bounded commerce-turn parsing and inventory revision safety
(`1849441d`), F-PAY-010 human prepayment authority (`7440bb98`), paid warehouse
commitment protection (`a7857ada`) and resilient reduced-motion gate (`dd93f9f3`),
lease/reclaim invariant (`18ddc636`), late-payment inventory race guard
(`b23dfeed`) and current-episode presentation (`fbe33a68`).

## Current episode, lease and late-payment race deploy (2026-08-05)

`18ddc636`, `b23dfeed` and `fbe33a68` were pushed to `origin/main` and
fast-forwarded on production with no migration. Fresh focused evidence is 18
direct presentation tests, a 159-test buyer/UI gate and 45
lease/inventory/reconciliation/admin tests; Django check
and migration-drift check are clean. Production has one `instagram_login`
daemon with `running=True`, `alive=True`, empty `last_error` and zero pending
reply/notification/analysis queues.

The deployment closes F-CORE-003 and F-STATE-011. It also extends F-CAT-011:
the frozen provider success timestamp is used during payment binding, and an
expired reservation whose stock has been reallocated is review-only and
idempotent. It does not claim the outstanding disposable MariaDB concurrency
gate, readiness/alternatives consumer, durable commerce reducer or manager
review UI as complete.

## F-CAT-011 paid commitment guard deploy (2026-08-05)

`a7857ada` and test-only follow-up `dd93f9f3` were pushed to `origin/main` and
fast-forwarded on production. The slice introduces no migration. `deploy.sh`
completed migrate (no pending migrations), collectstatic, compress and Passenger
restart; its best-effort dependency step reported the existing non-fatal local
`cffi` wheel build failure and continued with the active venv.

Fresh local evidence: focused inventory 92/92, inbox/UI 188/188, repeated full
`management warehouse` 2897 with 3 skipped and `OK`, Django check, migration
drift, compileall and diff check. Production `run_instagram_bot --ensure`
spawned one daemon; `status_snapshot()` returned `running=True`, `alive=True`,
provider `instagram_login`, heartbeat 1.2 seconds, `last_error=''`, reply pending
0 and notification pending/failed/unknown/dead-letter 0/0/0/0.

The deployed invariant is explicit: unexpired `ACTIVE` and all
`PAID_COMMITTED` warehouse reservations protect capacity; a negative adjustment
cannot cross protected quantity; an exact order excludes only its own paid
commitment for fulfillment. No production test data was created. IMP-086 remains
PARTIAL until disposable MariaDB concurrency/constraint proof and manager-review
UI are complete; IMP-094 remains OPEN for its separate MariaDB test gate.

## F-PAY-010 human-authority deploy (2026-08-05)

`7440bb9898340823ce93fb564b693dc19c4427de` was pushed to `origin/main` and
fast-forwarded on production from `1639a485`. The slice introduces no migration.
`deploy.sh` completed migrate (no pending migrations), collectstatic, compress
and Passenger restart; its best-effort `pip install` reported a pre-existing
local `cffi` wheel build failure and continued with the already active venv.
`run_instagram_bot --ensure` spawned one daemon. Final status is
`running=True`, `alive=True`, provider `instagram_login`, fresh heartbeat,
`last_error=''`, reply queue `0` and notification queues `0/0/0/0`.

Fresh local evidence is 41/41 payment/paylink/thermo-price tests, Django check,
py_compile and diff check. A rollback-only production MariaDB fixture proved:
customer-originated amount = `ambiguous`; model offer + customer yes =
`ambiguous`; human offer 350 грн + matching customer confirmation = `accepted`
with exact two message IDs; multi-amount offer = `ambiguous`. The transaction
was rolled back and a post-check found no synthetic clients.

## Parser and inventory revision hardening deploy (2026-08-05)

`1849441da59cb67fd0b07815a67823c76d8681f7` was pushed to `origin/main` and
fast-forwarded on production. Migration
`management.0145_ig_inventory_revision_safety` is applied. The deployed slice
integrates bounded commerce-turn facts before Gemini, pins only trusted
first-party product URLs, preserves exact price/stock reasons through paylink
readiness and manager escalation, orders allocation locks deterministically,
protects reservation revisions and stale write-off callbacks, and routes late
overbooked payment to manager review.

Fresh local evidence is 2877 tests, 3 skipped, `OK`, including stale-instance,
absolute-stock, authoritative variant-price, stock-reason and W7 action-label
regressions. Production `migrate`, `check`, static/compression, restart and daemon
ensure completed; read-only status reported `enabled=True`, provider
`instagram_login`, fresh heartbeat and pending queues `0/0/0/0`. IMP-085 and
IMP-086 remain PARTIAL because durable commerce-session/candidate anchoring,
manager-review UI and disposable MariaDB concurrency/constraint proof are not
yet complete.

## Warehouse reservation lifecycle deploy (2026-08-05)

`90fdd0ec36d585d075fafd1340b2427d456a421c` was fast-forwarded to `origin/main`
and pulled on production. Migration `management.0144_ig_inventory_allocation_lifecycle`
is applied. The deployed path reserves exact warehouse/catalog allocation at
proposal creation, commits warehouse payment without decrementing physical stock,
binds fulfillment/write-off/reversal movements and marks late released payment as
`OVERBOOKED_REVIEW` rather than creating negative stock. The reservation and
warehouse focused gate passed locally before deploy; production `check`, migration
drift, static/compression and daemon ensure passed. One daemon remains
`running=True`, `alive=True`, `instagram_login`, with fresh heartbeat and empty
reply/notification queues.

## IMP-084 exact availability foundation deploy (2026-08-05)

`17f5b672` was pushed to `origin/main` and fast-forwarded on production. The
new service resolves only the configured inventory source (`warehouse`,
`catalog_variant` or `untracked`), returns exact `StockItem`/variant allocation
facts, aggregates repeated basket identities, and returns `UNKNOWN` for missing
or ambiguous mappings instead of guessing. Local verification passed 5/5
availability tests and a 277-test combined availability/checkout/follow-up/
live-visual/restock gate; `manage.py check`, migration drift and daemon ensure
passed on production. This is intentionally a PARTIAL `IMP-084` checkpoint:
proposal/readiness/checkout wiring, reservation/allocation state transitions,
and disposable MariaDB proof remain open under `IMP-086`/`IMP-088`.

## IMP-102 durable follow-up delivery FSM deploy (2026-08-05)

Коммиты `0d4d38c0`, `0e9e9ba5`, `4cb86743` и `414e639e` опубликованы в
`origin/main` и fast-forwarded на production. Применена migration
`management.0141_igfollowuptask_delivery_fsm`. Локально прошли 23/23 focused и
160/160 expanded regression tests, Django check, migration drift, compileall и
`git diff --check`.

Production HEAD:
`414e639eced30a01ff2c5553b08605099465478c`. `status_snapshot()` подтвердил
`is_enabled=True`, `state='running'`, `running=True`, `daemon_online=True`,
`alive=True`, `provider_transport='instagram_login'`, `last_error=''`; daemon
ровно один. Read-only delivery audit: `processing=[]`, `ambiguous=[]`,
`sent_without_message=[]`, `delivery_reviews=[]`.

## F-CAT-007 variant-specific prompt parity deploy (2026-08-05)

`e44d1440` bound catalog sizes to exact `variant + fit`; `0ad694bc` separated an
authoritative empty size contract from absence of a variant-specific source.
Both commits are in `origin/main` and production. Product 110 now enters the
bot prompt as `variant_id=81`, thermo green, exact 1450 грн, oversize sizes
XS/M; the false product-wide `XS/S/M/L/XL/XXL` row is absent.

Verification: 188 focused tests and the full management suite 2675 passed
(3 skipped); Django check, migration drift, compileall and diff check passed.
Final production runtime on `0ad694bc`: one daemon, `running=True`,
`alive=True`, provider `instagram_login`, heartbeat 0.1 s, `last_error=''`,
pending replies/notifications = `0/0`.

## IMP-082/083 typed graph/ranker historical foundation deploy (2026-08-05)

`29684475` was pushed to `main` and fast-forwarded on production. `migrate`
reported no pending migrations; `manage.py check`, migration drift and scoped
compileall passed. `tmp/restart.txt` caused the old daemon to release its lock;
`run_instagram_bot --ensure` spawned one daemon on the deployed code.

Production MariaDB read-only proof built graph digest
`38f2c7df99c9c042c179bc96e0736185b03cfb1f29381722b96c8ce41b7a7b8e`:
product 91 has exact fit prices 800/950 грн; product 110 has only thermo
`variant_id=81` at exact 1450 грн. Hard `color=termo-zelena`, `fit=oversize`,
`size=M` resolves one candidate; `size=L` resolves none. Final runtime:
one daemon, `running=True`, `alive=True`, `instagram_login`, heartbeat 0.5 s,
`last_error=''`, active reply/notification/analysis queues zero. Server tracked
files are clean; unrelated untracked operational files remain untouched.

## F-PAY-015 daemon reconciliation deploy (2026-08-05)

`93ae8684` was pushed to `main` and fast-forwarded on production. `migrate`
reported no pending migrations, `manage.py check` passed, and
`reconcile_ig_commercial_episodes --passes 3` returned
`deals=0, reviews=0, attributions=0`. Static collection, compression, playbook
seed and bounded payment backstop completed; the backstop processed zero
projections/orders. After `tmp/restart.txt`, `run_instagram_bot --ensure`
spawned the new daemon.

Final production evidence: server HEAD `93ae8684`; `running=True`, `alive=True`,
state `running`, provider `instagram_login`, heartbeat age 1.0 second,
`last_error=''`, pending replies/notifications/analysis = `0/0/0`. Client `59`
has separate terminal episodes `2`, `3`, `7`; episodes `2` and `7` are
`lost / superseded_duplicate_payment_review`, episode `3` is fulfilled, and
`current_commercial_episode_id` is null.

## IMP-094 deployment checkpoint (2026-08-04)

`15147ded` was fast-forwarded to `main` and pulled on production. `manage.py
check` and `makemigrations --check --dry-run` passed. Touching
`tmp/restart.txt` stopped the old daemon as designed, but the scheduled
watchdog did not relaunch it promptly; the standard singleton-safe
`run_instagram_bot --ensure` restored the worker. Final `status_snapshot()`:
`is_enabled=True`, `state='running'`, `running=True`, `alive=True`, transport
`instagram_login`, `last_error=''`. No production database was used for tests;
the disposable MariaDB gate in IMP-094 remains open.

## IMP-077 / F-OPS-009 deployment checkpoint (2026-08-04)

`221cf37d` was rebased on the then-current `main`, fast-forwarded to production
with `git pull --ff-only`, and introduced no migrations. Server `manage.py
check` passed; `run_instagram_bot --ensure` reported `daemon alive — ok`.
`status_snapshot()` then confirmed `state='running'`, `running=True`,
`alive=True`, `provider_transport='instagram_login'`, empty `last_error` and
`notification_pending=notification_failed=notification_unknown=notification_dead_letter=0`.
The server contains unrelated untracked operational files; no tracked file was
overwritten outside the fast-forward.

| Date | SHA | Verification | Runtime |
|---|---|---|---|
| 2026-08-03 | `2a89d860` | payment backstop/contract | daemon online |
| 2026-08-03 | `cd070cba` | 9 policies/25 steps, policy tests | `instagram_login` |
| 2026-08-03 | `efc0ee10` / `4ba4212d` | fulfillment + MySQL migration | last_error empty |
| 2026-08-03 | `d0098d0b` | migration 0132, objection tests, InnoDB tables | daemon online |
| 2026-08-03 | `65bbde3e` | IMP-057 docs checkpoint | heartbeat observed |
| 2026-08-03 | `6b86e103` | check, migration drift, compileall, 45 IG tests | `enabled=True`, `transport=instagram_login`, `last_error=''` |
| 2026-08-03 | `afd16725` | audit source reconciliation and canonical docs | docs-only; runtime remains online |
| 2026-08-03 | `59f5a67b` | final validation report included and deployed | docs-only; runtime remains online |
| 2026-08-03 | `c409f7a3` | canonical checkbox plan, registers and source reconciliation; server pull, Django check, migration-drift check and restart | `running`; daemon online; `instagram_login`; no recorded error |
| 2026-08-03 | `92d46c5a` | migration `0133`; check/migration drift/collectstatic/compress; backfill 5; silence scan 96; raw-event reconciliation | `running`; heartbeat fresh; `instagram_login`; `last_error=''` |
| 2026-08-03 | `280c07e8` | migration `0134`; 104 payment/lifecycle tests; superseded invoice polling and check-only proof | `running`; `last_error=''` |
| 2026-08-03 | `6883ac2c` | final IMP-089 code/doc checkpoint; server pull, migrate/check, check-only and runtime verification | `running`; heartbeat 0.6s; `last_error=''` |
| 2026-08-03 | `e04c1c24` | final audit evidence checkpoint; docs-only fast-forward | runtime unchanged; `running`; `last_error=''` |
| 2026-08-04 | `15147ded` | IMP-094 SQLite gate stabilization; production check/migration-drift; daemon recovery | `running`; `alive=True`; `instagram_login`; `last_error=''` |
| 2026-08-04 | `221cf37d` | IMP-077 terminal monitor/key/dedupe completion; focused 75 tests, production check and daemon ensure | `running`; `alive=True`; terminal outbox `0/0` |
| 2026-08-05 | `93ae8684` | F-PAY-015; 134 local tests, MySQL reconcile x3, static/compress, payment backstop, restart | `running`; `alive=True`; `instagram_login`; heartbeat 1.0s; queues `0/0/0` |
| 2026-08-05 | `29684475` | IMP-082/083 partial; 31/230/2672/202 local gates, MySQL graph 91=800/950 and 110=1450, hard incompatible size rejected | one daemon; `running`; `alive=True`; heartbeat 0.5s; queues `0/0/0` |
| 2026-08-05 | `e44d1440` / `0ad694bc` | F-CAT-007 fixed; 188 focused, 2675 full suite, exact variant+fit prompt price/size contract | one daemon; `running`; `alive=True`; heartbeat 0.1s; reply/notification queues `0/0` |
| 2026-08-05 | `0d4d38c0` / `0e9e9ba5` / `4cb86743` / `414e639e` | IMP-102/F-FUP-013; migration `0141`, 23 focused / 160 expanded, check/drift/compileall/diff | one daemon; `running`; `alive=True`; `instagram_login`; delivery queues empty |
| 2026-08-05 | `90fdd0ec` | IMP-086 reservation lifecycle; migration `0144`, exact allocation/paid commit/fulfillment/reversal and overbook review gate | one daemon; `running`; `alive=True`; `instagram_login`; reply/notification queues empty |
| 2026-08-05 | `1849441d` | IMP-085/086 partial; migration `0145`, bounded parser, trusted URL pinning, revision/lock/stale-callback safety; 2877 full tests | one daemon; `enabled=True`; `alive=True`; `instagram_login`; queues `0/0/0/0` |
| 2026-08-05 | `a7857ada` / `dd93f9f3` | F-CAT-011/F-TEST-004; paid commitment capacity guard, 92 inventory, 188 inbox/UI, 2897 full tests, no migration | one daemon; `running=True`; `alive=True`; `instagram_login`; reply/notification queues empty |
| 2026-08-05 | `7440bb98` | F-PAY-010; human-authorized prepayment amount, 41 focused tests, rollback-only MariaDB decision/evidence proof | one daemon; `running=True`; `alive=True`; `instagram_login`; reply/notification queues empty |
| 2026-08-05 | `18ddc636` / `b23dfeed` / `fbe33a68` | F-CORE-003 and F-STATE-011 closed; provider payment-time/reallocation guard extends F-CAT-011; 18 direct presentation + 159 buyer/UI + 45 lease/inventory/reconciliation/admin tests | one daemon; `running=True`; `alive=True`; `instagram_login`; reply/notification/analysis queues empty |

For `6b86e103`, server `git pull --ff-only` completed, `manage.py check` returned
no issues, `makemigrations --check --dry-run` returned `No changes detected`,
and `tmp/restart.txt` was touched. Server HEAD equals the SHA above. The server
worktree has unrelated untracked operational files; no tracked production file
was overwritten outside the requested commit.

For the docs checkpoint `afd16725`, server `git pull --ff-only` completed and
server HEAD was verified as `afd16725f10a07b18406767061c016eb4e0aaefd`. Existing
production DB proof after the pull: `enabled=True`, `transport=instagram_login`,
heartbeat age about 1 second, `last_error=''`. The production user cannot create
the Django test database (`1044 Access denied`), so the focused test command was
not executed on the live DB; the 45/45 result remains the prior isolated gate.

The final validation report commit `59f5a67b` was then pulled with `--ff-only`;
server HEAD was verified as `59f5a67ba7a4e0b89881141aadd966411832c7ca`.

The canonical-plan commit `c409f7a3` was subsequently pushed and pulled with
`git pull --ff-only origin main`; server HEAD was verified as
`c409f7a32d84e02ae9a92d93ba27bb0e176980c4`. `python manage.py check` returned
no issues, `python manage.py makemigrations --check --dry-run` returned `No
changes detected`, and `tmp/restart.txt` was touched to request a Passenger
restart. The runtime evidence was queried through the current
`management.services.instagram_bot.status_snapshot()` API: `is_enabled=True`,
`state='running'`, `alive=True`, `running=True`,
`provider_transport='instagram_login'`, database and daemon heartbeat ages
`0.0` seconds, and `last_error=''`.

For IMP-058, `origin/main` was advanced through `274c2c61`, `79882368` and
`92d46c5a`; the server pulled `92d46c5a` fast-forward and applied
`management.0133_ig_funnel_step_analytics` on MariaDB. Production commands
reported `{'candidates': 5, 'created': 5, 'applied': True}` for canonical
backfill and `{'scanned': 100, 'matched': 96, 'applied': True}` for deterministic
silence facts. The final MySQL/API check reported 197
`IgFunnelStepEvent` rows, 96 `IgFunnelDropOff` rows, 17 event types, and
`status_snapshot()` returned `state='running'`, `daemon_online=True`, a fresh
heartbeat and empty `last_error`.

For IMP-089, `git pull --ff-only` advanced production through `280c07e8` and
applied `management.0134_ig_deal_invoice_lifecycle` on MariaDB. The bounded
check-only command reported `projections=0 provider_invoices=0
superseded_invoices=0 orders=0`; the lifecycle table had zero rows because no
historical superseded invoice IDs exist on this production dataset. The daemon
briefly reported a transient worker error during restart and recovered to
`running=True` with `last_error=''`; no customer messages were sent.

The final consolidation commit `6883ac2c` was then pulled fast-forward. The
server confirmed migration `0134` as applied, `poll_ig_deal_payments
--check-only --limit 50` returned zero candidates, lifecycle rows remained 0,
and `status_snapshot()` reported `is_enabled=True`, `state='running'`,
daemon_online=True`, heartbeat age about 0.6 seconds, transport
`instagram_login`, and empty `last_error`.
