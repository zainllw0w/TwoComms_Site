# Implement2 Emergent Findings Evidence

> Canonical ownership and checkboxes now live in
> `14_IMPLEMENT2.md` / W2.0. This file retains discovery evidence only and must
> not be used as a competing implementation queue.

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
