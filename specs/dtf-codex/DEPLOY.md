# Deploy Runbook — DTF POLISH ONLY

## Target
- Host: `dtf.twocomms.shop`
- Branch: `codex/dtf-p2-polish-only-2026-02`
- Scope: DTF subdomain only (no main-domain routing/template changes)

## Secret Handling
```bash
export TWC_SSH_PASS='***'
```

## Preconditions
- Local checks are green:
  - `DJANGO_SETTINGS_MODULE=test_settings python3 manage.py check`
  - `DJANGO_SETTINGS_MODULE=test_settings python3 manage.py test dtf.tests --keepdb`
- `specs/dtf-codex/CHECKLIST.md` and `specs/dtf-codex/EVIDENCE.md` updated.
- Latest branch pushed to `origin`.

## Server Deploy Command
```bash
sshpass -p "$TWC_SSH_PASS" ssh -o StrictHostKeyChecking=no qlknpodo@195.191.24.169 "bash -lc '
  source /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.13/bin/activate &&
  cd /home/qlknpodo/TWC/TwoComms_Site/twocomms &&
  git fetch --all --prune &&
  git checkout codex/dtf-p2-polish-only-2026-02 &&
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
sshpass -p "$TWC_SSH_PASS" ssh -o StrictHostKeyChecking=no qlknpodo@195.191.24.169 "bash -lc '
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
