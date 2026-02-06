# Deploy Notes (DTF Isolation Re-run)

## Target
- DTF-only rollout for `dtf.twocomms.shop` without changing `twocomms.shop` behavior.

## Deployed commit
- `0b4843a` on branch `codex/dtf-p0p1-fixes-2026-02`

## Commands executed on server
```bash
source /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.13/bin/activate
cd /home/qlknpodo/TWC/TwoComms_Site/twocomms
git checkout codex/dtf-p0p1-fixes-2026-02
git pull --ff-only
python manage.py check
python manage.py collectstatic --noinput
mkdir -p tmp && touch tmp/restart.txt
```

## Server notes
- `check`: OK
- Warning remains: model changes in `accounts`, `dtf`, `management` are not represented by migrations (pre-existing project state)
- `collectstatic`: completed

## Post-deploy verification
### DTF host
- `/` -> 200
- `/order/` -> 200
- `/quality/` -> 200
- `/price/` -> 200
- `/prices/` -> 301 to `/price/`
- `/robots.txt` -> 200, sitemap points to `https://dtf.twocomms.shop/sitemap.xml`
- `/sitemap.xml` -> 200, DTF-only `<loc>` URLs
- `/order/` includes versioned DTF assets (`dtf.css?v=20260206b`, `dtf.js?v=20260206b`)
- Home/hero and calculator use unified pricing range `350-280` (`base=350`, tiers `10:330,30:310,50:280`)

### Main host
- `/` -> 200
- `/robots.txt` -> 200, sitemap points to `https://twocomms.shop/sitemap.xml`
- `/sitemap.xml` -> 200, main-host `<loc>` URLs
- `/google_merchant_feed.xml` -> 200
- `/prom-feed.xml` -> 200

## Isolation result
- `dtf.twocomms.shop` serves DTF template/assets.
- `twocomms.shop` does not render DTF template/assets.
