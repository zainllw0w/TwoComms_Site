# Implement2 Emergent Findings Evidence

> Canonical ownership and checkboxes now live in
> `14_IMPLEMENT2.md` / W2.0. This file retains discovery evidence only and must
> not be used as a competing implementation queue.

## W2.1 local baseline evidence (2026-08-13)

The mandatory no-network package is now cwd-independent through
`scripts/run_ig_baseline.py`. The reproducible RED was a manager echo whose
`schedule_analysis` failure was swallowed after takeover state was applied;
the green fix propagates that exception and makes `_handle_echo` transactional,
so HTTP retries receive `503` without a staged message, transition job or
partial takeover. Fresh runs from the repository root, `twocomms/`, and `/tmp`
each passed **207 tests, 0 failures, 0 errors, 0 skipped**. The separate
telephony module passed **62/62**, while the historical full-order/global-state
flake remains open as `F-DEBT-007`. This is SQLite/no-network evidence only;
`T40`, disposable MariaDB parity, and full `IMP-094` release acceptance remain
open.

## W2.2 narrow MariaDB checkout-concurrency boundary (2026-08-14)

The disposable MariaDB runner now reaches the dedicated checkout proposal
lock/race assertion. Exact-SHA CI run `31761170448` at `8f4459f68` passed its
runner/workflow and settings contract steps, lifecycle, and
`checkout-concurrency` on `11.4.12-MariaDB-ubu2404`; generated schemas
`test_twocomms_ig_0d322be43f2f` and `test_twocomms_ig_f6383867aa07` reported
`cleanup=verified`. The initial errno `1644` occurred in Django
`TransactionTestCase` teardown: the append-only event trigger correctly rejects
the default `DELETE` flush. The scoped test uses Django's `TRUNCATE` teardown
path with `reset_sequences=True`, preserving the production trigger.

This is not full T41 parity or production evidence. Each further append-only
test class requires its own root-cause assessment; never disable the trigger
globally. The post-CI branch-only sanitizer hardening was independently
RED/green tested and exact-SHA CI verified: it removes free-form test, subtest,
and `FAILED (...)` details plus dynamic child/cleanup/CLI exception labels from
retained CI failure evidence. It remains branch-only until main and production
proof are recorded.

## W3 pre-deploy delivery findings (2026-08-13)

The independent Wave 3 review found and the scoped slice now covers three
fail-closed boundaries: mid-less ingress without a provider timestamp is
rejected before permission/CRM side effects; opt-out staging uses the same
synthetic key; and a `SENT` receipt must contain unique, nonblank string IDs no
longer than the 255-character database contract. Indexed receipts without an
ID are `UNKNOWN`/review rather than `PARTIAL`. These are release evidence for
`IMP-087.A`, not closure of the remaining full `IMP-087` candidate/payment
work.

The MariaDB disposable run also exposed an existing test-harness limitation:
generic Django `TestCase` flush conflicts with append-only durable commerce
triggers. This is retained as an infrastructure follow-up; the Wave 3 proof
uses a clean native MariaDB schema, direct race/smoke assertions, and explicit
cleanup instead of weakening production triggers.

Post-deploy review found one additional fail-closed gap in the direct durable
delivery API: a transport result claiming `state='sent'` with no receipt list
was classified `PARTIAL`, even though no provider acceptance ID existed. A
focused RED reproduced it. The follow-up classifies zero validated provider
IDs as `UNKNOWN`/review and retains `PARTIAL` only for a genuine multi-part
subset backed by at least one valid receipt ID. This is critical Wave 3
hardening and is deployed before the documentation closeout.

## F-DEPLOY-001 (P1, OPEN): wheelhouse install lock must contain built-wheel hashes

**Discovered:** 2026-08-07 during independent Wave 0 Task 3/Task 4 gate review.

`http-ece==1.2.1` is a required pure-Python transitive of `pywebpush`, but no
published `http-ece` release has a wheel. The dependency compiler therefore
uses one explicit `--no-binary http-ece` exception and records the verified
sdist hash in `requirements.lock`.

Before the fix, that lock could not be used unchanged for the production
wheel-only install. A wheel built from the exact sdist has a different digest,
and a clean `pip install --no-index --only-binary :all: --require-hashes`
rejected it when only the sdist hash was present. This was reproduced with
`http_ece-1.2.1-py2.py3-none-any.whl`:

- sdist SHA256: `8c6ab23116bbf6affda894acfd5f2ca0fb8facbcbb72121c11c75c33e7ce8cff`
- pre-fix locally built wheel SHA256: `8cf3c986fd237fb3bb1a6d48c3e5c6286086f533e7e65b7f88b08f13fafcfdae`
- clean wheel-only install: rejected with a hash mismatch, as required.

The deterministic builder now produces wheel SHA256
`4ee99a46e0ae3f8230632457b935ce953bbf0d8b5a8c3030bbf2b9bbfa6533a8` and the
lock carries both hashes. CI still must prove the immutable manylinux
wheelhouse and target-SHA manifest before this finding is closed.

**Required closure (Task 7 / IMP-094):** in an immutable pinned builder,
rebuild the exact lock-verified sdist as a universal wheel with pinned build
tools and reproducible timestamps; verify wheel metadata/version and source
provenance; add the resulting wheel hash to the install requirements used by
the artifact; generate a sorted target-SHA manifest; and run a clean
`--no-index --find-links --only-binary :all: --require-hashes` install. The
production orchestrator must fail closed if the manifest, target binding, or
any wheel hash is missing or mismatched. Do not source-build during production
maintenance and do not make `pywebpush` optional while Web Push is configured.

**Status:** Task 3 remains code-complete but this finding and the immutable
manylinux evidence keep IMP-094/Wave 0 open until the CI wheelhouse gate is
green.

**Follow-up 2026-08-13:** `c72ecf11` closes the remaining orchestrator
manifest-symlink boundary for this bounded subtask. The finding itself remains
OPEN because the current production SHA has no target-bound wheelhouse and no
complete current release evidence; the production fail-closed probe confirmed
that absence without mutating the live release.

## F-DEPLOY-002 (P1, OPEN): CloudLinux selector diagnostics can expose production secrets

**Discovered:** 2026-08-07 during the read-only Task 4 server inventory.

`cloudlinux-selector get --json --interpreter python` returns the complete
selector environment, including production credentials. It is not a safe
health/evidence command. No returned values are recorded in this repository or
in release evidence.

**Required closure (Task 4 / IMP-094):** the staged orchestrator must use only
fixed selector `start`/`stop` commands and sanitized status fields. It must not
invoke or log selector environment JSON, `env`, `.env` contents, or command
output containing credentials. Any previously captured raw output must be
discarded/redacted and the relevant credentials rotated through the normal
operational procedure outside Git.

## F-DEPLOY-003 (P1, OPEN): maintenance activation can leave an orphaned lease

The production `--maintenance-on` command writes a bounded lease before waiting
for the daemon singleton lock. If that wait times out, the command can fail
without returning the lease identifier while the lease remains active until
expiry. A deploy process that treats the command failure as all-or-nothing can
leave the bot paused and block subsequent `--ensure` runs.

**Required closure (Task 4B):** activation must use an owned lease handshake,
capture the identifier from a sanitized durable status/receipt, and release
only that identifier on every pre-switch failure, timeout and rollback. Tests
must prove no unowned lease is released and no owned lease survives a failed
activation.

## F-DEPLOY-004 (P1, OPEN): legacy operator deploy wrappers bypass release safety

The server inventory found tracked/manual wrappers that reference Python 3.13,
an old host, destructive `git reset --hard`, runtime `makemigrations`, or
in-place overlays. The current crontab does not invoke these wrappers, but an
operator can still run them and bypass the staged release gate.

**Required closure (Task 4C):** after the read-only usage boundary is recorded,
redirect supported entry points to the canonical target-SHA orchestrator or
retire/archive inactive scripts. Contract tests must reject stale interpreters,
old hosts, destructive resets, runtime migration generation, direct SCP overlays
and unbounded restarts.
