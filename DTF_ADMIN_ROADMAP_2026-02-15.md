# DTF Admin + My Orders Roadmap (2026-02-15)

## Goal
- Build dedicated DTF admin panel on `dtf.twocomms.shop`.
- Build redesigned customer page `Мої замовлення` for film and custom product orders.
- Keep `twocomms.shop` main site untouched.
- Add optional DTF separate DB (`DB_NAME_DTF`) while sharing users from main DB.

## Context Anchors
- Linear epic: `TWO-34`
- Subtasks:
  - `TWO-35` Admin shell and SPA tabs
  - `TWO-36` Blog CMS (CRUD + SEO + slug translit + rich editor)
  - `TWO-37` Customer my orders redesign
  - `TWO-38` Separate DB support for DTF

## Architecture Decisions
1. DTF admin panel is implemented inside `dtf` app under `/admin-panel/` routes.
2. Tab switching is done without page reload via partial endpoints and client-side fetch.
3. Blog CMS is custom (not Django admin-only): inline editor with SEO fields and slug transliteration.
4. User auth remains shared through default DB; optional DTF DB stores `dtf` app entities.
5. `DtfUpload.owner` and `DtfBuilderSession.user` use `db_constraint=False` to avoid hard FK coupling to mirrored auth rows in separate DTF DB.
6. Sidebar behavior was ported from `Effects.MD` concept into local Django static assets (no runtime `npx` dependency in production).

## Delivery Checklist

### Phase A - Data model and backend
- [x] Extend `DtfOrder` for payment status, payment metadata, delivery point details, custom product details.
- [x] Add lifecycle status `received`.
- [x] Add customer-stage mapping helpers for UI.
- [x] Extend `KnowledgePost` with `seo_keywords` and `content_rich_html`.
- [x] Add slug transliteration + unique slug generation helper.
- [x] Add migrations:
  - [x] `0006_dtforder_custom_specs_json_dtforder_delivered_at_and_more.py`
  - [x] `0007_alter_dtfbuildersession_user_alter_dtfupload_owner.py`

### Phase B - DTF admin panel (custom)
- [x] Add routes:
  - [x] `/admin-panel/`
  - [x] `/admin-panel/tab/<tab>/`
  - [x] `/admin-panel/orders/<id>/update/`
  - [x] `/admin-panel/blog/create|update|delete|slug-preview/`
- [x] Add access control for DTF admin (staff/superuser/manager profile).
- [x] Implement tab contexts for:
  - [x] Dashboard (placeholder KPIs)
  - [x] Orders (management + lifecycle/payment updates)
  - [x] Blog (CRUD with SEO)
  - [x] Users (shared user list)
  - [x] Promocodes (placeholder)

### Phase C - Frontend admin shell
- [x] Add template `dtf/admin/panel.html`.
- [x] Add tab partial templates:
  - [x] `dashboard.html`
  - [x] `orders.html`
  - [x] `blog.html`
  - [x] `users.html`
  - [x] `promocodes.html`
- [x] Add JS controller `dtf/static/dtf/js/dtf-admin.js`:
  - [x] SPA tab loading
  - [x] Orders inline update forms (AJAX)
  - [x] Blog form create/update/delete (AJAX)
  - [x] Slug preview endpoint integration
  - [x] Rich text editor loading (Quill via CDN)
- [x] Add admin visual styles in `dtf/static/dtf/css/dtf.css` with responsive sidebar and mobile layout.
- [x] Add mobile sidebar collapse/expand behavior with touch-friendly interaction.

### Phase D - Customer "Мої замовлення" redesign
- [x] Replace `cabinet_orders.html` with card-based adaptive layout.
- [x] Add animated stage timeline with requested statuses.
- [x] Show payment status and amount.
- [x] Show item detail for film/custom-product style orders.
- [x] Show TTN and delivery point info.
- [x] Add action buttons:
  - [x] Contact manager
  - [x] Repeat order
  - [x] Pay button placeholder for unpaid orders

### Phase E - Separate DB support
- [x] Add `twocomms/twocomms/db_routers.py`.
- [x] Add optional `DATABASES['dtf']` wiring in:
  - [x] `twocomms/twocomms/settings.py`
  - [x] `twocomms/twocomms/production_settings.py`
- [x] Add router activation on `DB_NAME_DTF`.

### Phase F - Verification
- [x] `manage.py check` (DEBUG mode) passes.
- [x] `compileall` passes for modified modules.
- [ ] Full `manage.py test dtf` pass (blocked by existing unrelated migration conflict in `storefront` migration chain on local SQLite environment).
- [ ] Browser visual QA screenshots for admin and my-orders desktop/mobile.

## Execution Log
- [x] 2026-02-15: Created Linear epic + subtasks (`TWO-34`..`TWO-38`) and posted implementation progress note in epic.
- [x] 2026-02-15: Implemented custom DTF admin shell with AJAX tab loading and per-tab partial rendering.
- [x] 2026-02-15: Implemented orders management actions in admin panel (lifecycle, payment, TTN, delivery metadata, custom product metadata).
- [x] 2026-02-15: Implemented blog CRUD in admin panel (SEO, transliterated slug, rich editor field, publish control).
- [x] 2026-02-15: Implemented redesigned customer `Мої замовлення` cards with stage progress, payment and delivery statuses, and action buttons.
- [x] 2026-02-15: Added optional separate DB routing for `dtf` app while preserving shared users from main DB.
- [x] 2026-02-15: Added responsive polish for sidebar and stage-progress animation behavior.

## Deployment Notes (server)
1. Pull latest:
```bash
sshpass -p 'trs5m4t1' ssh -o StrictHostKeyChecking=no qlknpodo@195.191.24.169 "bash -lc 'source /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.13/bin/activate && cd /home/qlknpodo/TWC/TwoComms_Site/twocomms && git pull'"
```
2. Ensure env has:
```bash
DB_NAME_DTF=qlknpodo_MySQL_DB_DTF
# optional overrides:
# DB_USER_DTF=
# DB_PASSWORD_DTF=
# DB_HOST_DTF=
# DB_PORT_DTF=
```
3. Run migrations:
```bash
python manage.py migrate
# if using separate DTF alias:
python manage.py migrate --database=dtf
```
4. Collect static:
```bash
python manage.py collectstatic --noinput
```

## Remaining Work (next execution block)
- [x] Connect real promo-code entities in DTF admin tab.
- [x] Add media upload endpoint for blog rich editor images (instead of data URLs).
- [ ] Add dashboard real-time charts and business metrics.
- [ ] Add browser-level QA artifacts (desktop/mobile) and finalize release checklist.
