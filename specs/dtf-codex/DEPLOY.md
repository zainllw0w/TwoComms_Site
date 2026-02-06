# Deploy Notes (DTF Isolation Re-run)

## Target
- DTF-only rollout for `dtf.twocomms.shop` with no behavioral changes to `twocomms.shop`.

## Pre-deploy checks
- `python3 manage.py check --settings=test_settings`
- `python3 manage.py test dtf --settings=test_settings`

## Deployment steps
```bash
sshpass -p '***' ssh -o StrictHostKeyChecking=no qlknpodo@195.191.24.169 "bash -lc '
  source /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.13/bin/activate &&
  cd /home/qlknpodo/TWC/TwoComms_Site/twocomms &&
  git checkout codex/dtf-p0p1-fixes-2026-02 &&
  git pull &&
  python manage.py check &&
  python manage.py migrate --noinput &&
  python manage.py collectstatic --noinput &&
  mkdir -p tmp && touch tmp/restart.txt
'"
```

## Post-deploy smoke
- DTF host:
  - `/`
  - `/quality/`
  - `/price/`
  - `/prices/` (301)
  - `/robots.txt`
  - `/sitemap.xml`
- Main host:
  - `/`
  - `/robots.txt`
  - `/sitemap.xml`

## Status
- Pending commit/push/deploy for current DTF-only re-baseline changes.
