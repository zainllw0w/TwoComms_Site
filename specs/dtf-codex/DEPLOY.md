# Deploy Notes

## Status
- Production deployment completed on 2026-02-06 (Europe/Zaporozhye).
- Active production branch: `codex/dtf-p0p1-fixes-2026-02`.
- Latest deployed commit: `941891a`.

## Infra Changes Applied (docroot override fix)
```bash
# static overrides were moved to backup
/home/qlknpodo/public_html/_backup/20260206-012836/robots.twocomms.shop.bak
/home/qlknpodo/public_html/_backup/20260206-012836/sitemap.twocomms.shop.bak

# verified now absent from shared docroot
ls -la /home/qlknpodo/public_html/robots.txt /home/qlknpodo/public_html/sitemap.xml
# -> no docroot robots/sitemap present
```

## Deploy Commands Executed
```bash
cd /home/qlknpodo/TWC/TwoComms_Site/twocomms
git checkout codex/dtf-p0p1-fixes-2026-02
git pull
source /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.13/bin/activate
python manage.py check
mkdir -p tmp && touch tmp/restart.txt
```

## Production Verification (URL Smoke)
```bash
# twocomms.shop
/ -> 200
/catalog/ -> 200
/product/clasic-tshort/ -> 200
/quality/ -> 200
/price/ -> 200
/prices/ -> 301 -> /price/
/checkout/ -> 302 -> /cart/
/cart/ -> 200
/robots.txt -> 200
/sitemap.xml -> 200
/google_merchant_feed.xml -> 200
/prom-feed.xml -> 200

# dtf.twocomms.shop
/ -> 200
/catalog/ -> 200
/product/clasic-tshort/ -> 200
/quality/ -> 200
/price/ -> 200
/prices/ -> 301 -> /price/
/checkout/ -> 302 -> /cart/
/cart/ -> 200
/robots.txt -> 200
/sitemap.xml -> 200
/google_merchant_feed.xml -> 200
/prom-feed.xml -> 200
```

## SEO Host Assertions
- `https://twocomms.shop/robots.txt` includes `Sitemap: https://twocomms.shop/sitemap.xml`.
- `https://dtf.twocomms.shop/robots.txt` includes `Sitemap: https://dtf.twocomms.shop/sitemap.xml`.
- `https://twocomms.shop/sitemap.xml` emits `https://twocomms.shop/...` loc values.
- `https://dtf.twocomms.shop/sitemap.xml` emits `https://dtf.twocomms.shop/...` loc values.
