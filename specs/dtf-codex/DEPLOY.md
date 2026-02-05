# Deploy Notes

## Status
- Production deployment is pending in this session because SSH credentials/host are not available.

## Planned Infra Commands (Template)
```bash
# 1) Backup static files in shared docroot (example paths)
mv /home/USER/public_html/robots.txt /home/USER/public_html/robots.twocomms.shop.bak
mv /home/USER/public_html/sitemap.xml /home/USER/public_html/sitemap.twocomms.shop.bak

# 2) Deploy app changes
cd /home/USER/TWC/TwoComms_Site/twocomms
git pull
source /home/USER/virtualenv/TWC/TwoComms_Site/twocomms/3.13/bin/activate
python manage.py migrate
python manage.py collectstatic --noinput
npm run build:css

# 3) Restart Passenger
touch tmp/restart.txt

# 4) Verify
curl -I https://dtf.twocomms.shop/quality/
curl -I https://dtf.twocomms.shop/price/
curl -I https://dtf.twocomms.shop/prices/
curl -s https://dtf.twocomms.shop/robots.txt
curl -s https://dtf.twocomms.shop/sitemap.xml
```

## Post-deploy Checks
- Verify that other hostnames still serve their own `robots.txt`/`sitemap.xml`.
- Verify `sitemap.xml` host equals `dtf.twocomms.shop`.
- Verify `css/dtf-fixes.css` is served and loaded (network 200 + style overrides visible).
