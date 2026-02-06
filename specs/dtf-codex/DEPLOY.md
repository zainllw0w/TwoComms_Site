# Deploy Runbook (DTF-only)

## Target
- Host: `dtf.twocomms.shop` (same codebase, isolated via subdomain routing)
- Branch: `codex/dtf-p0p1-fixes-2026-02`

## Secret handling
- Use environment variable for sshpass:
```bash
export TWC_SSH_PASS='***'
```
- Do not store secrets in repo files.

## Remote command pattern
```bash
sshpass -p "$TWC_SSH_PASS" ssh -o StrictHostKeyChecking=no qlknpodo@195.191.24.169 "bash -lc '
  source /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.13/bin/activate &&
  cd /home/qlknpodo/TWC/TwoComms_Site/twocomms &&
  git checkout codex/dtf-p0p1-fixes-2026-02 &&
  git pull --ff-only &&
  python manage.py check &&
  python manage.py migrate --noinput &&
  python manage.py collectstatic --noinput &&
  mkdir -p tmp &&
  touch tmp/restart.txt
'"
```

## Infra note: robots/sitemap override
- This rollout keeps DTF `robots.txt` and `sitemap.xml` app-served.
- If server-level static overrides in shared docroot exist, they must not shadow DTF app routes.
- Verify after deploy:
  - `curl -i https://dtf.twocomms.shop/robots.txt`
  - `curl -i https://dtf.twocomms.shop/sitemap.xml`

## Post-deploy checklist
1. `curl -I https://dtf.twocomms.shop/quality/` is 200
2. `curl -I https://dtf.twocomms.shop/price/` is 200
3. `curl -I https://dtf.twocomms.shop/prices/` is 301 to `/price/`
4. `robots.txt` points to `https://dtf.twocomms.shop/sitemap.xml`
5. `sitemap.xml` is 200 XML and contains only DTF host URLs
6. Mobile menu behavior is correct (open/close/focus/scroll lock)
7. Manager modal is solid and no FAB overlap
8. Before/after slider is draggable and responsive
