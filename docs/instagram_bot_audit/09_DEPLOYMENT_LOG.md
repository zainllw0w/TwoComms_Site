# 09_DEPLOYMENT_LOG — production evidence

Production host: `195.191.25.63`, path
`/home/qlknpodo/TWC/TwoComms_Site/twocomms`, branch `main`, database
`qlknpodo_MySQL_DB` (MariaDB/MySQL). Secrets are intentionally omitted.

| Date | SHA | Verification | Runtime |
|---|---|---|---|
| 2026-08-03 | `2a89d860` | payment backstop/contract | daemon online |
| 2026-08-03 | `cd070cba` | 9 policies/25 steps, policy tests | `instagram_login` |
| 2026-08-03 | `efc0ee10` / `4ba4212d` | fulfillment + MySQL migration | last_error empty |
| 2026-08-03 | `d0098d0b` | migration 0132, objection tests, InnoDB tables | daemon online |
| 2026-08-03 | `65bbde3e` | IMP-057 docs checkpoint | heartbeat observed |
| 2026-08-03 | `6b86e103` | check, migration drift, compileall, 45 IG tests | `enabled=True`, `transport=instagram_login`, `last_error=''` |

For `6b86e103`, server `git pull --ff-only` completed, `manage.py check` returned
no issues, `makemigrations --check --dry-run` returned `No changes detected`,
and `tmp/restart.txt` was touched. Server HEAD equals the SHA above. The server
worktree has unrelated untracked operational files; no tracked production file
was overwritten outside the requested commit.

