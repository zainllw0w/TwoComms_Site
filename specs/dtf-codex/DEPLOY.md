# Deploy Runbook — DTF Execution Protocol

## Target
- Host: `dtf.twocomms.shop`
- Branch: `codex/codex-refactor-v1`
- Scope: DTF subdomain only (no main-domain routing/template changes)

## Secret Handling
```bash
export TWC_SSH_PASS='***'
```

## Preconditions
- Local checks are green:
  - `python3 -m compileall -q twocomms/dtf`
  - `python3 twocomms/manage.py test dtf --settings=test_settings`
  - `python3 -m pip_audit -r twocomms/requirements.txt`
- `specs/dtf-codex/CHECKLIST.md` and `specs/dtf-codex/EVIDENCE.md` updated.
- Latest branch pushed to `origin`.

## Canonical SSH Entry
```bash
sshpass -p 'trs5m4t1' ssh -o StrictHostKeyChecking=no qlknpodo@195.191.24.169 "bash -lc '
  source /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.13/bin/activate &&
  cd /home/qlknpodo/TWC/TwoComms_Site/twocomms &&
  git status
'"
```

## Server Deploy Command
```bash
sshpass -p 'trs5m4t1' ssh -o StrictHostKeyChecking=no qlknpodo@195.191.24.169 "bash -lc '
  source /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.13/bin/activate &&
  cd /home/qlknpodo/TWC/TwoComms_Site/twocomms &&
  git fetch --all --prune &&
  git checkout codex/codex-refactor-v1 &&
  git pull --ff-only &&
  python manage.py check &&
  python manage.py migrate --noinput &&
  python manage.py collectstatic --noinput &&
  mkdir -p tmp &&
  touch tmp/restart.txt &&
  git log -1 --oneline
'"
```

## Post-Deploy Validation
```bash
curl -i https://dtf.twocomms.shop/
curl -i https://dtf.twocomms.shop/order/
curl -i https://dtf.twocomms.shop/price/
curl -i https://dtf.twocomms.shop/prices/
curl -i https://dtf.twocomms.shop/quality/
curl -i https://dtf.twocomms.shop/robots.txt
curl -i https://dtf.twocomms.shop/sitemap.xml
curl -i https://twocomms.shop/robots.txt
curl -i https://twocomms.shop/sitemap.xml
```

## Rollback
```bash
sshpass -p 'trs5m4t1' ssh -o StrictHostKeyChecking=no qlknpodo@195.191.24.169 "bash -lc '
  source /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.13/bin/activate &&
  cd /home/qlknpodo/TWC/TwoComms_Site/twocomms &&
  git log --oneline -n 5 &&
  git checkout <last-known-good-commit-or-branch> &&
  python manage.py check &&
  python manage.py collectstatic --noinput &&
  touch tmp/restart.txt
'"
```

## Infra Note
- DTF `robots.txt` and `sitemap.xml` are app-served and host-aware.
- If LiteSpeed/docroot static override exists, verify it does not shadow DTF routes.

## Deploy Log — 2026-02-07
- Branch deployed: `codex/codex-refactor-v1`
- Deployed commit: `8da5b5e`
- Local predeploy gates: passed (compileall/tests/pip-audit)
- Server deploy output:
  - `git checkout codex/codex-refactor-v1` -> OK
  - `git pull --ff-only` -> Already up to date
  - `python manage.py check` -> system check OK
  - `python manage.py migrate --noinput` -> applied `dtf.0003_knowledgepost`
  - `python manage.py collectstatic --noinput` -> 12 copied / 316 unmodified
  - `touch tmp/restart.txt` -> restart trigger updated
- Postdeploy verification commands:
  - `curl -sI https://dtf.twocomms.shop/`
  - `curl -sI https://dtf.twocomms.shop/order/`
  - `curl -sI https://dtf.twocomms.shop/price/`
  - `curl -sI https://dtf.twocomms.shop/quality/`
  - `curl -sI https://dtf.twocomms.shop/gallery/`
  - `curl -sI https://dtf.twocomms.shop/requirements/`
  - `curl -sI https://dtf.twocomms.shop/robots.txt`
  - `curl -sI https://dtf.twocomms.shop/sitemap.xml`
  - `curl -sI https://dtf.twocomms.shop/prices/`
  - `curl -sI https://twocomms.shop/robots.txt`
  - `curl -sI https://twocomms.shop/sitemap.xml`
- Evidence:
  - `specs/dtf-codex/perf/postdeploy-curl-2026-02-07.txt`
  - `specs/dtf-codex/perf/robots-sitemap-2026-02-07.txt`

### Sync deploy (docs update) — 2026-02-07
- Fast-forward to latest commit: `41186a6`
- `python manage.py check` -> OK
- `python manage.py migrate --noinput` -> no migrations to apply
- Server warning observed:
  - `Your models in app(s): 'accounts', 'dtf', 'management' have changes that are not yet reflected in a migration`
- `collectstatic` -> `0 copied, 328 unmodified`
- Restart trigger updated: `touch tmp/restart.txt`
- Action:
  - Added follow-up task `DTF-305` in `MCP_TODO.md` to investigate migration-state drift.
